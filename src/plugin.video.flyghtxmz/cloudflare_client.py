"""Cliente da API Cloudflare Sources para o Felipe Vídeos.

Somente endpoints HTTPS configurados pelo usuário; o token não vai para URLs
nem para logs. Neste estágio, a API aceita apenas fontes autorizadas do
Internet Archive e não afirma que o áudio de terceiros seja PT-BR.
"""
import re
from urllib.parse import urlsplit

import requests
import xbmcaddon


MAX_RESPONSE_BYTES = 250_000
TIMEOUT = 14
IMDB_ID = re.compile(r"^tt[0-9]{5,12}$")
RANKS = {"SD", "480p", "720p", "1080p", "4K"}


def _worker_url(value):
    if not isinstance(value, str):
        raise ValueError("Configure uma URL HTTPS do Worker.")
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            parsed.path not in ("", "/")):
        raise ValueError("A URL deve ser HTTPS e apontar para a raiz do Worker.")
    return value


def is_supported_source(url):
    if not isinstance(url, str) or len(url) > 4000:
        return False
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https" and parsed.hostname in
            ("archive.org", "www.archive.org") and
            parsed.path.startswith("/download/") and
            parsed.path.lower().endswith("_archive.torrent") and
            not parsed.username and not parsed.password and
            not parsed.query and not parsed.fragment
        )
    except ValueError:
        return False


def _read_json(response):
    parts, total = [], 0
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise ValueError("Resposta do Worker excedeu o limite.")
            parts.append(chunk)
    import json
    return json.loads(b"".join(parts).decode("utf-8"))


def list_sources(title, year="", imdb=""):
    addon = xbmcaddon.Addon()
    endpoint = _worker_url(addon.getSetting("cloudflare_endpoint"))
    token = addon.getSetting("cloudflare_token").strip()
    if not token:
        raise ValueError("Configure o token da API Cloudflare no Kodi.")
    title = " ".join((title or "").split())[:120]
    year = str(year or "")[:4]
    if not title:
        raise ValueError("O título não está disponível.")
    if imdb and not IMDB_ID.fullmatch(imdb):
        raise ValueError("Identificador IMDb incorreto.")

    url = endpoint + "/v1/sources"
    with requests.get(
        url,
        params={"title": title, "year": year, "imdb": imdb},
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
        },
        timeout=TIMEOUT,
        stream=True,
    ) as response:
        response.raise_for_status()
        payload = _read_json(response)
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        raise ValueError("O Worker retornou um formato inesperado.")

    result = []
    for item in payload["sources"][:40]:
        if not isinstance(item, dict) or item.get("verified_license") is not True:
            continue
        uri = item.get("url")
        if not is_supported_source(uri):
            continue
        label = str(item.get("title") or title)[:180]
        q = str(item.get("quality") or "SD")
        if q not in RANKS:
            q = "SD"
        try:
            size = max(0, int(item.get("size") or 0))
        except (ValueError, TypeError):
            size = 0
        try:
            seeds = None if item.get("seeders") is None else max(0, int(item["seeders"]))
        except (ValueError, TypeError):
            seeds = None
        result.append({
            "title": label,
            "source": str(item.get("source") or "Internet Archive")[:80],
            "quality": q,
            "size": size,
            "seeders": seeds,
            "language": str(item.get("language") or "unknown")[:30],
            "url": uri,
        })
    return result
