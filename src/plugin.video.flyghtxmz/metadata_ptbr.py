"""Sinopses PT-BR do TMDb + cache local de 24h para nota IMDb do Cinemeta.

Sem chave no Kodi e sem alterar o Worker Cloudflare. A fonte TMDb serve
somente para tradução da descrição: a nota IMDb continua vindo do Cinemeta.
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
import tempfile
import time
from urllib.request import Request, urlopen

TMDB_STREMIO_BASE = (
    "https://tmdb.elfhosted.com/"
    "N4IgNghgdg5grhGBTEAuEAHALgWgEIBKIAvkA"
)
IMDB_ID = re.compile(r"^tt\d{5,12}$")
RATING = re.compile(r"^(?:10(?:\.0)?|[0-9](?:\.[0-9])?)$")
RATING_TTL = 24 * 60 * 60
DESCRIPTION_TTL = 7 * 24 * 60 * 60
RETRY_TTL = 24 * 60 * 60
MAX_RESPONSE_BYTES = 250_000
MAX_CACHE_BYTES = 2_000_000
MAX_ENTRIES = 600
FALLBACK_SYNOPSIS = "Sinopse em português (Brasil) ainda não disponível."


def _profile_path():
    try:
        import xbmcaddon
        import xbmcvfs
        profile = xbmcaddon.Addon().getAddonInfo("profile")
        if not profile:
            return None
        directory = Path(xbmcvfs.translatePath(profile))
        directory.mkdir(parents=True, exist_ok=True)
        return directory / "metadata_ptbr_cache.json"
    except (ImportError, AttributeError, OSError, ValueError):
        return None


def _read_cache():
    path = _profile_path()
    if path is None:
        return {}
    try:
        if not path.is_file() or path.stat().st_size > MAX_CACHE_BYTES:
            return {}
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _write_cache(data):
    path = _profile_path()
    if path is None:
        return
    # Evita crescimento sem limites, mantendo os acessos mais recentes.
    items = sorted(data.items(), key=lambda pair: max(
        float(pair[1].get("rating_checked_at") or 0),
        float(pair[1].get("description_attempt_at") or 0)
    ) if isinstance(pair[1], dict) else 0, reverse=True)[:MAX_ENTRIES]
    compact = {key: value for key, value in items}
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(path.parent),
            prefix=".metadata_ptbr-", suffix=".json", delete=False
        ) as handle:
            temp_path = handle.name
            json.dump(compact, handle, ensure_ascii=False, separators=(",", ":"))
        os.replace(temp_path, path)
    except (OSError, ValueError, TypeError):
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def _valid_rating(value):
    if value is None:
        return ""
    value = str(value).strip().replace(",", ".")
    return value if RATING.fullmatch(value) else ""


def _read_ptbr_description(identifier, media, timeout=9):
    if not IMDB_ID.fullmatch(identifier) or media not in ("movie", "series"):
        raise ValueError("Parâmetros de metadados inválidos.")
    address = "{}/meta/{}/{}.json".format(TMDB_STREMIO_BASE, media, identifier)
    request = Request(address, headers={
        "User-Agent": "FelipeVideosKodi/1.3.8 (metadata)",
        "Accept": "application/json",
    })
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("Resposta não autorizada para sinopse.")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Metadados ultrapassaram o limite.")
    payload = json.loads(raw.decode("utf-8"))
    meta = payload.get("meta") if isinstance(payload, dict) else None
    if not isinstance(meta, dict):
        raise ValueError("Metadados inválidos.")
    source_id = meta.get("imdb_id") or meta.get("id")
    if source_id != identifier:
        raise ValueError("Metadados retornaram outro título.")
    overview = meta.get("description")
    return " ".join(overview.split())[:1600] if isinstance(overview, str) else ""


def enrich(identifier, media, imdb_rating="", now=None):
    """Retorna (sinopse_ptbr, nota_imdb, verificado_em).

    Quando nota ainda não tem 24h, mantém o valor em cache. Após expiração,
    aceita nota fornecida pela nova leitura Cinemeta (nunca nota TMDb).
    Falha no PT-BR mantém a última sinopse conhecida ou mensagem em português.
    """
    if not IMDB_ID.fullmatch(identifier or "") or media not in ("movie", "series"):
        raise ValueError("Identificador inválido.")
    current = float(time.time() if now is None else now)
    cache = _read_cache()
    key = "{}:{}".format(media, identifier)
    entry = cache.get(key)
    if not isinstance(entry, dict):
        entry = {}
    changed = False

    last_rating = float(entry.get("rating_checked_at") or 0)
    rating = _valid_rating(entry.get("rating"))
    if last_rating <= 0 or current - last_rating >= RATING_TTL or last_rating > current:
        updated = _valid_rating(imdb_rating)
        if updated:
            rating = updated
        entry["rating"] = rating
        entry["rating_checked_at"] = current
        changed = True

    description = entry.get("description") or ""
    last_synopsis = float(entry.get("description_checked_at") or 0)
    last_attempt = float(entry.get("description_attempt_at") or 0)
    if (not description or current - last_synopsis >= DESCRIPTION_TTL) and (
            last_attempt <= 0 or current - last_attempt >= RETRY_TTL or last_attempt > current):
        entry["description_attempt_at"] = current
        changed = True
        try:
            translated = _read_ptbr_description(identifier, media)
            if translated:
                description = translated
                entry["description"] = translated
                entry["description_checked_at"] = current
        except (OSError, TimeoutError, ValueError, TypeError, UnicodeError, json.JSONDecodeError):
            pass

    if changed:
        cache[key] = entry
        _write_cache(cache)
    return (description or FALLBACK_SYNOPSIS,
            rating or "Indisponível",
            entry.get("rating_checked_at"))



def descriptions_for_catalog(items, now=None):
    """Preenche a sinopse no painel do Kodi ao listar filmes e séries.

    Usa cache de sete dias; somente descrições ausentes/vencidas são
    requisitadas, com concorrência limitada. Erros são isolados por título.
    Nunca apresenta sinopses em inglês do catálogo Cinemeta como substitutas.
    """
    current = float(time.time() if now is None else now)
    cache = _read_cache()
    plots = {}
    pending = []
    for movie in items[:20]:
        identifier = movie.get("id") if isinstance(movie, dict) else None
        media = movie.get("type") if isinstance(movie, dict) else None
        if not isinstance(identifier, str) or not IMDB_ID.fullmatch(identifier):
            continue
        if media not in ("movie", "series"):
            continue
        key = "{}:{}".format(media, identifier)
        entry = cache.get(key, {})
        if not isinstance(entry, dict):
            entry = {}
        description = entry.get("description")
        description = description if isinstance(description, str) else ""
        plots[key] = description or FALLBACK_SYNOPSIS
        checked = float(entry.get("description_checked_at") or 0)
        attempt = float(entry.get("description_attempt_at") or 0)
        stale = not description or checked <= 0 or current - checked >= DESCRIPTION_TTL or checked > current
        may_retry = attempt <= 0 or current - attempt >= RETRY_TTL or attempt > current
        if stale and may_retry:
            pending.append((key, identifier, media))

    if not pending:
        return plots

    def fetch_one(identifier, media):
        # Timeout curto para que uma fonte lenta não bloqueie o catálogo.
        try:
            return _read_ptbr_description(identifier, media, timeout=3)
        except (OSError, TimeoutError, ValueError, TypeError, UnicodeError):
            return ""

    with ThreadPoolExecutor(max_workers=min(8, len(pending))) as executor:
        jobs = {executor.submit(fetch_one, identifier, media): key
                for key, identifier, media in pending}
        for job in as_completed(jobs):
            key = jobs[job]
            entry = cache.get(key)
            if not isinstance(entry, dict):
                entry = {}
            entry["description_attempt_at"] = current
            try:
                description = job.result()
            except Exception:
                description = ""
            if description:
                entry["description"] = description
                entry["description_checked_at"] = current
                plots[key] = description
            cache[key] = entry
    _write_cache(cache)
    return plots


def cached_rating(identifier, media):
    """Usado nas listas para mostrar uma nota já verificada, sem requisições extras."""
    entry = _read_cache().get("{}:{}".format(media, identifier), {})
    if not isinstance(entry, dict):
        return ""
    checked = float(entry.get("rating_checked_at") or 0)
    now = time.time()
    if checked > 0 and 0 <= now - checked < RATING_TTL:
        return _valid_rating(entry.get("rating"))
    return ""
