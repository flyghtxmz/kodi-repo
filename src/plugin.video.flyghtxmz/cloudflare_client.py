"""Cliente da API Cloudflare Sources para o Felipe Vídeos.

Aceita provedores definidos na API do usuário, sem exigir token local.
Bloqueia o provedor removido, além de links malformados e endereços locais.
"""
import re
import ipaddress
from urllib.parse import parse_qs, urlsplit
import json

import requests
import xbmcaddon


DISCOVERY_URL = ("https://raw.githubusercontent.com/flyghtxmz/kodi-repo/"
                 "main/cloudflare/kodi-sources/endpoint.json")
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


def configured_endpoint():
    """Obtém endpoint de arquivo público sem gravar segredo no addon."""
    addon = xbmcaddon.Addon()
    manual = addon.getSetting("cloudflare_endpoint").strip()
    if manual:
        return _worker_url(manual)
    with requests.get(DISCOVERY_URL, timeout=8, stream=True) as response:
        response.raise_for_status()
        payload = _read_json(response)
    if not isinstance(payload, dict) or not payload.get("endpoint"):
        raise ValueError("O endereço do Worker ainda não foi publicado no projeto.")
    return _worker_url(payload["endpoint"])


def _is_removed_provider(item):
    name = str(item.get("source") or item.get("provider") or "").strip().lower()
    return name in ("internet archive", "internetarchive", "archive.org", "archive")


def is_supported_source(url):
    """Aceita magnet válido ou HTTPS .torrent; bloqueia fontes removidas e hosts locais."""
    if not isinstance(url, str) or len(url) > 8192 or any(ord(c) < 32 or ord(c) == 127 for c in url):
        return False
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() == "magnet":
            if parsed.netloc or parsed.path or not parsed.query:
                return False
            xts = parse_qs(parsed.query).get("xt", [])
            return any(re.fullmatch(
                r"urn:btih:(?:[a-fA-F0-9]{40}|[a-zA-Z2-7]{32})", xt or "", re.I
            ) for xt in xts)
        if (parsed.scheme != "https" or not parsed.hostname or
                parsed.username or parsed.password or parsed.port not in (None, 443) or
                not parsed.path.lower().endswith(".torrent")):
            return False
        host = parsed.hostname.lower().rstrip(".")
        if (host in ("archive.org", "www.archive.org", "localhost") or
                host.endswith((".local", ".localhost", ".internal", ".lan"))):
            return False
        try:
            if not ipaddress.ip_address(host).is_global:
                return False
        except ValueError:
            pass
        return True
    except (ValueError, TypeError):
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
    endpoint = configured_endpoint()
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
    seen = set()
    for item in payload["sources"][:80]:
        if not isinstance(item, dict) or _is_removed_provider(item):
            continue
        uri = item.get("url") or item.get("magnet") or item.get("torrent")
        if not is_supported_source(uri) or uri in seen:
            continue
        seen.add(uri)
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
            "source": str(item.get("source") or item.get("provider") or "Fonte externa")[:80],
            "quality": q,
            "size": size,
            "seeders": seeds,
            "language": str(item.get("language") or "unknown")[:30],
            "url": uri,
        })
    def order(item):
        language = item["language"].casefold().replace("_", "-")
        ptbr = language in ("pt-br", "ptbr", "portugues", "português", "brazilian")
        ranks = {"4K": 4, "1080p": 3, "720p": 2, "480p": 1, "SD": 0}
        return (ptbr, ranks.get(item["quality"], 0), item["seeders"] or 0)
    result.sort(key=order, reverse=True)
    return result
