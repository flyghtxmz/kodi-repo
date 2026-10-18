"""Fontes públicas P2P do MediaFusion, consultadas diretamente no Kodi."""
import re

import requests
import local_cache
import torrentio_client

BASE_URL = "https://mediafusionfortheweebs.midnightignite.me"
MAX_BYTES = 500_000


def parse_streams(payload, fallback_title=""):
    if not isinstance(payload, dict) or not isinstance(payload.get("streams"), list):
        raise ValueError("Resposta inesperada do MediaFusion.")
    prepared, metadata = [], {}
    for row in payload["streams"][:100]:
        if not isinstance(row, dict):
            continue
        hints = row.get("behaviorHints")
        hints = hints if isinstance(hints, dict) else {}
        filename = hints.get("filename") or row.get("title") or fallback_title
        description = row.get("description") or ""
        if not isinstance(filename, str) or not isinstance(description, str):
            continue
        converted = dict(row)
        converted["title"] = filename + "\n" + description
        prepared.append(converted)
        infohash = torrentio_client._hash(row.get("infoHash"))
        try:
            index = torrentio_client._file_index(row)
        except ValueError:
            continue
        metadata[(infohash, index)] = (row, hints, description)
    result = torrentio_client.parse_streams({"streams": prepared})
    for source in result:
        row, hints, description = metadata[(source["infoHash"], source.get("file_index"))]
        source["source"] = "MediaFusion"
        size = hints.get("videoSize")
        if type(size) is int and 0 <= size <= 10**15:
            source["size"] = size
        raw_seeds = row.get("seeders")
        source["seeders"] = raw_seeds if type(raw_seeds) is int and raw_seeds >= 0 else None
        # Não interpretar o ícone de reproduções como contagem de seeders.
        if source["language"] == "unknown":
            if re.search(r"Portuguese\s*\(Brazil\)|Brazilian Portuguese", description, re.I):
                source["language"] = "pt-br"
            elif re.search(r"\bPortuguese\b", description, re.I):
                source["language"] = "pt"
            elif re.search(r"\bEnglish\b", description, re.I):
                source["language"] = "en"
    return result


def list_sources(title, year="", imdb="", season=None, episode=None):
    if not imdb:
        return []
    if not isinstance(imdb, str) or not torrentio_client.IMDB_ID.fullmatch(imdb):
        raise ValueError("Identificador IMDb inválido.")
    is_series = season is not None or episode is not None
    if is_series and (type(season) is not int or type(episode) is not int
                      or not 0 <= season <= 999 or not 1 <= episode <= 9999):
        raise ValueError("Temporada ou episódio inválido.")
    identifier = "{}:{}:{}".format(imdb, season, episode) if is_series else imdb
    kind = "series" if is_series else "movie"
    cached = local_cache.get("mediafusion_sources", identifier)
    if isinstance(cached, list):
        return cached
    with requests.get(BASE_URL + "/stream/" + kind + "/" + identifier + ".json",
                      headers={"Accept": "application/json", "User-Agent": "FelipeVideos/1.5.0 (Kodi)"},
                      timeout=(4, 8), stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if getattr(response, "status_code", 200) != 200:
            raise ValueError("Resposta inválida do MediaFusion.")
        parts, length = [], 0
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            length += len(chunk)
            if length > MAX_BYTES:
                raise ValueError("Resposta do MediaFusion excedeu o limite.")
            parts.append(chunk)
        import json
        result = parse_streams(json.loads(b"".join(parts).decode("utf-8")), title)
    local_cache.put("mediafusion_sources", identifier, result, ttl=300 if result else 60)
    return result
