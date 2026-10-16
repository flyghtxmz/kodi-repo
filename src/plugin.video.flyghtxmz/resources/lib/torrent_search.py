"""Pesquisa genérica em um Prowlarr configurado localmente.

A fonte e as credenciais são do usuário; não existem indexadores embutidos.
"""
import re

import requests
import xbmc
import xbmcaddon

ADDON = xbmcaddon.Addon()
TIMEOUT = 20
QUALITY_PATTERNS = (
    ("4K", r"(?i)(?:\b2160p?\b|\b4k\b|\buhd\b)"),
    ("1080p", r"(?i)\b1080p?\b"),
    ("720p", r"(?i)\b720p?\b"),
    ("480p", r"(?i)\b480p?\b"),
)
IMDB_RE = re.compile(r"^tt[0-9]{5,12}$")


def _log(message):
    xbmc.log("Felipe Vídeos: " + message, xbmc.LOGERROR)


def _infer_quality(title):
    if not isinstance(title, str):
        return "SD"
    for quality, pattern in QUALITY_PATTERNS:
        if re.search(pattern, title):
            return quality
    return "SD"


def _request_json(base_url, path, api_key, params=None):
    response = requests.get(
        base_url.rstrip("/") + path,
        params=params,
        headers={"X-Api-Key": api_key, "Accept": "application/json"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _indexer_ids(base_url, key, language_tag):
    if not language_tag:
        return None
    tags = _request_json(base_url, "/api/v1/tag", key)
    if not isinstance(tags, list):
        raise ValueError("Resposta de tags inválida")
    wanted = {
        int(tag["id"]) for tag in tags
        if isinstance(tag, dict) and
        str(tag.get("label") or "").casefold() == language_tag.casefold()
        and isinstance(tag.get("id"), int)
    }
    if not wanted:
        return []
    indexers = _request_json(base_url, "/api/v1/indexer", key)
    if not isinstance(indexers, list):
        raise ValueError("Resposta de indexadores inválida")
    return [
        int(indexer["id"]) for indexer in indexers
        if isinstance(indexer, dict)
        and isinstance(indexer.get("id"), int)
        and wanted.intersection(indexer.get("tags") or [])
        and indexer.get("enable", True)
    ]


def search_torrents(imdb_id, title, year, language_tag="portugues"):
    """Retorna resultados genéricos das fontes configuradas no Prowlarr.

    O nome da tag é convertido em IDs de indexadores; não é enviado como
    parâmetro `tags` à busca, pois essa API espera `indexerIds`.
    """
    base = ADDON.getSetting("prowlarr_url").strip()
    key = ADDON.getSetting("prowlarr_api_key").strip()
    if not base or not key:
        return []
    if not base.startswith(("http://", "https://")):
        _log("Endereço do Prowlarr inválido")
        return []
    try:
        ids = _indexer_ids(base, key, language_tag)
        if ids == []:
            return []
        search_term = " ".join(str(p).strip() for p in (title, year) if p)
        params = [("type", "movie"), ("limit", "100")]
        if isinstance(imdb_id, str) and IMDB_RE.fullmatch(imdb_id):
            params.append(("imdbId", imdb_id[2:]))
        else:
            params.append(("query", search_term[:200]))
        if ids is not None:
            params.extend(("indexerIds", item) for item in ids)
        data = _request_json(base, "/api/v1/search", key, params=params)
        if isinstance(data, dict):
            data = data.get("releases") or data.get("results") or []
        if not isinstance(data, list):
            return []
        items = []
        for row in data:
            if not isinstance(row, dict):
                continue
            name = str(row.get("title") or "")
            uri = row.get("magnetUrl") or row.get("magnet") or ""
            if not isinstance(uri, str) or not uri.startswith("magnet:?"):
                continue
            items.append({
                "title": name[:300],
                "magnet": uri,
                "seeders": max(0, int(row.get("seeders") or 0)),
                "size": max(0, int(row.get("size") or 0)),
                "quality": _infer_quality(name),
                "source": str(row.get("indexer") or "")[:100],
            })
        return sorted(items, key=lambda item: item["seeders"], reverse=True)
    except (requests.RequestException, ValueError, TypeError, KeyError) as error:
        _log("Prowlarr: falha na consulta (%s)" % type(error).__name__)
        return []
