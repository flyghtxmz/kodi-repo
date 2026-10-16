"""Fontes de torrent integradas ao Felipe Vídeos (sem Prowlarr ou Burst).

As consultas são feitas dentro do addon. O Elementum é apenas o motor
de reprodução, recebendo o magnet selecionado.
"""
import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import urlencode, quote
import requests

from catalog import (SEARCH_URL, METADATA_ROOT, DOWNLOAD_ROOT,
                     open_license, sanitize_identifier, make_query)

TIMEOUT = 9
MAX_BYTES = 1_500_000
IMDB_RE = re.compile(r"^tt\d{5,12}$")
HASH_RE = re.compile(r"^[a-fA-F0-9]{40}$")
PT_RE = re.compile(
    r"(?i)(?:\bdublado\b|\bdual[ ._-]*audio\b|\bpt[ ._-]*br\b|"
    r"\bbrazilian\b|\bportugu[eê]s\b|\bnacional\b)"
)
QUALITY_RE = (
    ("4K", re.compile(r"(?i)(?:\b2160p?\b|\b4k\b|\buhd\b)")),
    ("1080p", re.compile(r"(?i)\b1080p?\b")),
    ("720p", re.compile(r"(?i)\b720p?\b")),
    ("480p", re.compile(r"(?i)\b480p?\b")),
)
RANK = {"SD": 0, "480p": 1, "720p": 2, "1080p": 3, "4K": 4}
YTS_URL = "https://yts.mx/api/v2/list_movies.json"
ARCHIVE_URL = "https://archive.org/advancedsearch.php"
HEADERS = {"User-Agent": "FelipeVideosKodi/1.4", "Accept": "application/json"}


def quality(text):
    for name, expression in QUALITY_RE:
        if expression.search(text or ""):
            return name
    return "SD"


def language(text):
    return "PT-BR (não confirmado)" if PT_RE.search(text or "") else "Não informado"


def _normalize(text):
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _similar(a, b):
    one, two = _normalize(a), _normalize(b)
    return bool(one and two) and (one == two or
                                  SequenceMatcher(None, one, two).ratio() >= 0.82)


def _json(url, params=None):
    with requests.get(url, params=params, headers=HEADERS,
                      timeout=TIMEOUT, stream=True) as response:
        response.raise_for_status()
        payload = response.raw.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("Resposta de provedor muito grande")
    import json
    return json.loads(payload.decode("utf-8"))


def _as_int(value):
    try:
        return max(0, int(value or 0))
    except (ValueError, TypeError):
        return 0


def _torrent(title, magnet, seeders, size, source, label=None):
    return {
        "title": str(title or "")[:240],
        "magnet": magnet,
        "seeders": _as_int(seeders),
        "size": _as_int(size),
        "quality": label or quality(str(title or "")),
        "language": language(str(title or "")),
        "source": source,
    }


def yts_movie(imdb_id, title, year):
    """API pública de filmes: o áudio geralmente NÃO é identificado."""
    params = {"query_term": imdb_id if IMDB_RE.fullmatch(imdb_id or "")
              else title[:100], "limit": 15}
    payload = _json(YTS_URL, params=params)
    if payload.get("status") != "ok":
        return []
    result = []
    for movie in (payload.get("data") or {}).get("movies") or []:
        if not isinstance(movie, dict):
            continue
        ident = movie.get("imdb_code") or ""
        name = movie.get("title_english") or movie.get("title") or ""
        if IMDB_RE.fullmatch(imdb_id or ""):
            if ident != imdb_id:
                continue
        elif not _similar(title, name):
            continue
        if year and str(movie.get("year") or "") != str(year)[:4]:
            continue
        for stream in movie.get("torrents") or []:
            if not isinstance(stream, dict):
                continue
            hash_value = str(stream.get("hash") or "").lower()
            if not HASH_RE.fullmatch(hash_value):
                continue
            q = str(stream.get("quality") or "SD")
            if q not in RANK:
                q = quality(q)
            release = "{} ({}) {} {}".format(name, movie.get("year"),
                                              q, stream.get("type") or "").strip()
            magnet = "magnet:?" + urlencode({
                "xt": "urn:btih:" + hash_value,
                "dn": release,
            })
            result.append(_torrent(release, magnet, stream.get("seeds"),
                                   stream.get("size_bytes"), "YTS", q))
    return result


def archive_movie(imdb_id, title, year):
    """Pesquisa uploads com licença declarada e confirma-a no metadata."""
    params = [
        ("q", make_query("busca", title)),
        ("fl[]", "identifier"), ("fl[]", "title"), ("fl[]", "year"),
        ("fl[]", "licenseurl"),
        ("rows", "15"), ("page", "1"), ("output", "json"),
    ]
    records = (_json(ARCHIVE_URL, params=params).get("response") or {}).get("docs") or []
    result = []
    checked = 0
    for item in records:
        if not isinstance(item, dict) or not open_license(item.get("licenseurl")):
            continue
        if not _similar(title, item.get("title") or ""):
            continue
        if year and item.get("year") and str(item["year"])[:4] != str(year)[:4]:
            continue
        try:
            identifier = sanitize_identifier(item.get("identifier"))
        except ValueError:
            continue
        if checked >= 5:
            break
        checked += 1
        meta = _json(METADATA_ROOT + quote(identifier, safe=""))
        if not open_license((meta.get("metadata") or {}).get("licenseurl")):
            continue
        files = meta.get("files") or []
        torrent_file = next((f for f in files
                             if isinstance(f, dict)
                             and isinstance(f.get("name"), str)
                             and f["name"].endswith("_archive.torrent")
                             and f.get("source") == "metadata"
                             and "/" not in f["name"] and ".." not in f["name"]), None)
        if not torrent_file:
            continue
        videos = [f for f in files if isinstance(f, dict)
                  and str(f.get("name") or "").lower().endswith((".mp4", ".mkv", ".webm"))]
        if not videos:
            continue
        label = max((quality(f.get("name") or "") for f in videos),
                    key=lambda q: RANK.get(q, 0))
        if label == "SD":
            # Archive não fornece resolução padronizada em todos os registros.
            label = "SD"
        size = max((_as_int(v.get("size")) for v in videos), default=0)
        url = DOWNLOAD_ROOT + quote(identifier, safe="") + "/" + quote(
            torrent_file["name"], safe="")
        result.append(_torrent("{} ({}) {}".format(title, year or "", label),
                               url, 0, size, "Internet Archive", label))
    return result


PROVIDERS = (("YTS", yts_movie), ("Internet Archive", archive_movie))


def search(title, year="", imdb_id="", minimum_quality="720p"):
    """Agrega fontes embutidas; erros individuais não ocultam outros resultados."""
    import xbmc
    results, errors = [], []
    for name, provider in PROVIDERS:
        try:
            results.extend(provider(imdb_id, title, year))
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            errors.append(name)
            xbmc.log("Felipe Vídeos: provedor {} indisponível ({})".format(
                name, type(exc).__name__), xbmc.LOGERROR)
    rank = RANK.get(minimum_quality, 2)
    filtered, seen = [], set()
    for item in results:
        if RANK.get(item["quality"], 0) < rank:
            continue
        uri = item["magnet"]
        key = uri.split("&", 1)[0] if uri.startswith("magnet:?") else uri
        if key in seen:
            continue
        seen.add(key)
        filtered.append(item)
    filtered.sort(key=lambda item: (
        1 if item["language"].startswith("PT-BR") else 0,
        RANK.get(item["quality"], 0),
        item["seeders"],
    ), reverse=True)
    return filtered[:60], errors
