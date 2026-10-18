"""Fontes públicas do Comet, pela conexão do Kodi e com cache local."""
import json

import requests
import local_cache
import mediafusion_client
import torrentio_client

BASE_URL = "https://comet.feels.legal"
MAX_BYTES = 2_000_000


def parse_streams(payload, fallback_title=""):
    if not isinstance(payload, dict) or not isinstance(payload.get("streams"), list):
        raise ValueError("Resposta inesperada do Comet.")
    rows = payload["streams"][:2000]
    result = []
    # A ordenação remota por resolução pode deixar PT-BR após o item 100.
    # Leia a resposta limitada antes de escolher as melhores alternativas.
    for offset in range(0, len(rows), 100):
        result.extend(mediafusion_client.parse_streams({"streams": rows[offset:offset + 100]}, fallback_title))
    for source in result:
        source["source"] = "Comet"
    language = {"pt-br": 3, "pt": 2, "en": 1}
    quality = {"4K": 4, "1080p": 3, "720p": 2, "480p": 1}
    result.sort(key=lambda row: (language.get(row["language"], 0), row.get("seeders") or 0,
                                 quality.get(row["quality"], 0)), reverse=True)
    unique = {}
    for source in result:
        unique.setdefault((source["infoHash"], source.get("file_index")), source)
    return list(unique.values())[:100]


def list_sources(title, year="", imdb="", season=None, episode=None):
    if not imdb:
        return []
    if not isinstance(imdb, str) or not torrentio_client.IMDB_ID.fullmatch(imdb):
        raise ValueError("Identificador IMDb inválido.")
    series = season is not None or episode is not None
    if series and (type(season) is not int or type(episode) is not int
                   or not 0 <= season <= 999 or not 1 <= episode <= 9999):
        raise ValueError("Temporada ou episódio inválido.")
    identifier = "{}:{}:{}".format(imdb, season, episode) if series else imdb
    cached = local_cache.get("comet_sources", identifier)
    if isinstance(cached, list):
        return cached
    kind = "series" if series else "movie"
    with requests.get(BASE_URL + "/stream/" + kind + "/" + identifier + ".json",
                      headers={"Accept": "application/json", "User-Agent": "FelipeVideos/1.5.0 (Kodi)"},
                      timeout=(4, 8), stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if getattr(response, "status_code", 200) != 200:
            raise ValueError("Resposta inválida do Comet.")
        chunks, length = [], 0
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            length += len(chunk)
            if length > MAX_BYTES:
                raise ValueError("Resposta do Comet excedeu o limite.")
            chunks.append(chunk)
        result = parse_streams(json.loads(b"".join(chunks).decode("utf-8")), title)
    local_cache.put("comet_sources", identifier, result, ttl=300 if result else 60)
    return result
