"""Torrentio consultado pelo próprio Kodi, com cache local e seleção de arquivo."""
import base64
import json
import ipaddress
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlencode, parse_qs, urlsplit

import requests


BASE_URL = "https://torrentio.strem.fun/brazuca"
IMDB_ID = re.compile(r"^tt[0-9]{5,12}$")
STREAM_ID = re.compile(r"^tt[0-9]{5,12}(?::(?:0|[1-9][0-9]{0,2}):[1-9][0-9]{0,3})?$")
MAX_RESPONSE_BYTES = 500_000
MAX_CACHE_BYTES = 1_000_000
CACHE_TTL = 300
TIMEOUT = (4, 8)


def _cache_path():
    try:
        import xbmcaddon
        import xbmcvfs
        profile = xbmcaddon.Addon().getAddonInfo("profile")
        if not profile:
            return None
        directory = Path(xbmcvfs.translatePath(profile))
        directory.mkdir(parents=True, exist_ok=True)
        return directory / "torrentio_sources_cache.json"
    except (ImportError, AttributeError, OSError, ValueError):
        return None


def _read_cache():
    path = _cache_path()
    if path is None:
        return {}
    try:
        if path.stat().st_size > MAX_CACHE_BYTES:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _write_cache(data):
    path = _cache_path()
    if path is None:
        return
    pairs = [(key, value) for key, value in data.items()
             if STREAM_ID.fullmatch(key) and isinstance(value, dict)
             and isinstance(value.get("at"), (int, float))]
    pairs.sort(key=lambda pair: pair[1]["at"], reverse=True)
    pairs = pairs[:32]
    payload = json.dumps(dict(pairs), ensure_ascii=False, separators=(",", ":"))
    while pairs and len(payload.encode("utf-8")) > MAX_CACHE_BYTES:
        pairs.pop()
        payload = json.dumps(dict(pairs), ensure_ascii=False, separators=(",", ":"))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=str(path.parent),
                                         prefix=".torrentio-", suffix=".json", delete=False) as handle:
            temporary = handle.name
            handle.write(payload)
        os.replace(temporary, path)
    except OSError:
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def _hash(value):
    if not isinstance(value, str):
        return None
    if re.fullmatch(r"[0-9a-f]{40}", value, re.I):
        return value.lower()
    if re.fullmatch(r"[a-z2-7]{32}", value, re.I):
        return base64.b32decode(value.upper()).hex()
    return None


def _quality(value):
    if re.search(r"\b(?:2160p?|4k|uhd)\b", value, re.I):
        return "4K"
    for label in ("1080p", "720p", "480p"):
        if re.search(r"\b" + label + r"?\b", value, re.I):
            return label
    return "SD"


def _size(value):
    found = re.search(r"💾\s*(\d+(?:[.,]\d+)?)\s*([KMGT])(?:i)?B", value, re.I)
    if not found:
        return 0
    power = "KMGT".index(found[2].upper()) + 1
    unit = 1024 if re.search(r"iB", found[0], re.I) else 1000
    return round(float(found[1].replace(",", ".")) * unit ** power)


def _language(label):
    """Lê marcas explícitas do arquivo, sem deduzir idioma só pelo indexador.

    Um provedor brasileiro pode publicar áudio original. Isso é um indicativo
    textual, não uma análise real da faixa de áudio do arquivo.
    """
    if not isinstance(label, str):
        return "unknown"
    normalized = label.casefold()
    # "Subs EN/PTBR" e "Legenda PT-BR" indicam LEGENDA, não áudio.
    normalized = re.sub(
        r"(?i)\b(?:subs?|subtitles?|legendas?|legendado|legendada)"
        r"[\s._:-]*(?:(?:en(?:glish)?|pt[ ._-]?br|pt|por|portugu[eê]s)"
        r"(?:\s*/\s*(?:en(?:glish)?|pt[ ._-]?br|pt|por|portugu[eê]s))*)",
        " ", normalized)
    explicit_br = (
        "🇧🇷" in label or
        re.search(r"(?<![a-z0-9])(?:pt[. _-]?br|br[. _-]?pt|ptbr|brazilian"
                  r"|portugu[eê]s(?:[ ._-]+do)?[ ._-]+brasil(?:eiro)?"
                  r"|brasil(?:eiro)?[ ._-]+portugu[eê]s"
                  r"|audio[ ._-]+br|áudio[ ._-]+br"
                  r"|dublad[oa]s?|dub[ ._-]?pt[ ._-]?br)(?![a-z0-9])",
                  normalized, re.I)
    )
    if explicit_br:
        return "pt-br"
    if ("🇵🇹" in label or
            re.search(r"(?<![a-z0-9])(?:portugu[eê]s|portuguese|pt[. _-]?pt)(?![a-z0-9])",
                      normalized, re.I)):
        return "pt"
    if "🇬🇧" in label or re.search(r"(?<![a-z0-9])english(?![a-z0-9])", normalized):
        return "en"
    return "unknown"


def _file_index(row):
    value = row.get("fileIdx")
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= 100_000:
        raise ValueError("Índice de arquivo inválido.")
    return value



def _is_public_tracker(raw):
    """Não repassa endpoints locais, credentials ou protocolos desconhecidos."""
    if not isinstance(raw, str) or not 7 <= len(raw) <= 220:
        return False
    try:
        parsed = urlsplit(raw)
        if (parsed.scheme not in ("udp", "http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.fragment
                or parsed.port == 0):
            return False
        host = parsed.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith((".local", ".lan", ".internal")):
            return False
        try:
            if not ipaddress.ip_address(host).is_global:
                return False
        except ValueError:
            pass
        return True
    except ValueError:
        return False


def _trackers(row):
    """Recupera trackers explicitamente fornecidos pelo Torrentio (sem inventar)."""
    candidate = []
    sources = row.get("sources")
    if isinstance(sources, list):
        candidate.extend(item[8:] for item in sources
                         if isinstance(item, str) and item.startswith("tracker:"))
    listed = row.get("trackers")
    if isinstance(listed, list):
        candidate.extend(item for item in listed if isinstance(item, str))
    magnet = row.get("magnet")
    if isinstance(magnet, str) and len(magnet) <= 3000:
        parsed = urlsplit(magnet)
        if parsed.scheme == "magnet":
            candidate.extend(parse_qs(parsed.query).get("tr", []))
    trackers = []
    for item in candidate:
        if _is_public_tracker(item) and item not in trackers:
            trackers.append(item)
        if len(trackers) == 8:
            break
    return trackers


def parse_streams(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("streams"), list):
        raise ValueError("Resposta inesperada do Torrentio.")
    result = {}
    for row in payload["streams"][:100]:
        if not isinstance(row, dict):
            continue
        infohash = _hash(row.get("infoHash"))
        label = row.get("title")
        if not infohash or not isinstance(label, str) or not label.strip():
            continue
        try:
            file_index = _file_index(row)
        except ValueError:
            continue
        # Sem índice não é possível escolher com segurança um filme de um pacote.
        if file_index is None and re.search(r"\b(?:trilogia|trilogy|collection|coleção|pack|todos os filmes)\b", label, re.I):
            continue
        title = re.sub(r"[\x00-\x1f\x7f]", " ", label.splitlines()[0]).strip()[:180]
        # A língua pode estar na descrição, no nome Stremio, no filename ou
        # no campo explícito languages. Nunca inferir só do nome do provedor.
        hints = row.get("behaviorHints") if isinstance(row.get("behaviorHints"), dict) else {}
        languages = row.get("languages")
        language_data = " ".join(str(v) for v in languages[:8]) if isinstance(languages, list) else ""
        language_text = " ".join((label, str(row.get("description") or ""),
                                  str(hints.get("filename") or ""), language_data))
        detected_language = _language(language_text)
        if detected_language == "unknown" and isinstance(row.get("name"), str):
            # "name" costuma ser "Torrentio\n1080p" e pode indicar idioma.
            # Ignorar identificadores de provedores para não criar falsos PT-BR.
            name_text = row["name"]
            for provider_name in ("MicoLeaoDublado", "Comando", "BluDV"):
                name_text = name_text.replace(provider_name, "")
            detected_language = _language(name_text)
        origin = re.search(r"⚙\ufe0f?\s*([^\r\n]+)", label)
        provider = "Torrentio" + (" / " + origin[1].strip()[:60] if origin else "")
        seed_count = re.search(r"👤\s*(\d+)", label)
        source = {
            "title": title, "source": provider,
            "quality": _quality(str(row.get("name") or "") + " " + title),
            "size": _size(label), "seeders": int(seed_count[1]) if seed_count else None,
            "language": detected_language, "infoHash": infohash,
            # Inclui os trackers devolvidos pelo indexador. Magnet só com
            # infohash pode depender exclusivamente de DHT e atrasar metadata.
            # libtorrent/Elementum exige xt com separadores ':' literais.
            # Somente dn/tr recebem urlencode aqui; uri externo é escapado
            # UMA vez pelo plugin Kodi ao montar /play?uri=...
            "url": "magnet:?xt=urn:btih:" + infohash + "&" + urlencode(
                [("dn", title)] + [("tr", tracker) for tracker in _trackers(row)]),
        }
        if file_index is not None:
            source["file_index"] = file_index
        key = (infohash, file_index)
        previous = result.get(key)
        if previous is None or (source["seeders"] or 0) > (previous["seeders"] or 0):
            result[key] = source
    return list(result.values())


def list_sources(title, year="", imdb="", season=None, episode=None):
    if not imdb:
        return []
    if not isinstance(imdb, str) or not IMDB_ID.fullmatch(imdb):
        raise ValueError("Identificador IMDb incorreto.")
    is_series = season is not None or episode is not None
    if is_series and (type(season) is not int or type(episode) is not int
                      or not 0 <= season <= 999 or not 1 <= episode <= 9999):
        raise ValueError("Temporada ou episódio inválido.")
    stream_id = "{}:{}:{}".format(imdb, season, episode) if is_series else imdb
    stream_type = "series" if is_series else "movie"
    cache = _read_cache()
    entry = cache.get(stream_id)
    if (isinstance(entry, dict) and isinstance(entry.get("at"), (int, float))
            and 0 <= time.time() - entry["at"] < CACHE_TTL and isinstance(entry.get("sources"), list)):
        return entry["sources"]
    with requests.get(BASE_URL + "/stream/" + stream_type + "/" + stream_id + ".json",
                      headers={"Accept": "application/json", "User-Agent": "FelipeVideos/1.4.1 (Kodi)"},
                      timeout=TIMEOUT, stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if getattr(response, "status_code", 200) != 200:
            raise ValueError("O Torrentio não retornou uma resposta de busca.")
        parts, total = [], 0
        for chunk in response.iter_content(chunk_size=8192):
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise ValueError("Resposta do Torrentio excedeu o limite.")
            parts.append(chunk)
        sources = parse_streams(json.loads(b"".join(parts).decode("utf-8")))
    cache[stream_id] = {"at": time.time(), "sources": sources}
    _write_cache(cache)
    return sources
