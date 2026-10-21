"""Catálogos por disponibilidade de assinatura no Brasil via TMDb oficial.

Requer chave TMDb opcional do próprio usuário. Sem chave, o catálogo legado
continua funcionando, mas não afirma disponibilidade no Brasil.
"""
import json
import re
import unicodedata
import requests
import xbmcaddon
import local_cache

API = "https://api.themoviedb.org/3"
POSTER = "https://image.tmdb.org/t/p/w342"
MATCHES = {
    "nfx": ("Netflix",),
    "amp": ("Amazon Prime Video", "Prime Video"),
    "atp": ("Apple TV Plus", "Apple TV+"),
    "dnp": ("Disney Plus", "Disney+"),
    "hbm": ("Max", "HBO Max"),
    "pmp": ("Paramount Plus", "Paramount+"),
    "gop": ("Globoplay",),
    "cru": ("Crunchyroll",),
}

def has_key():
    try:
        return bool(xbmcaddon.Addon().getSetting("tmdb_api_key").strip())
    except (OSError, AttributeError, RuntimeError):
        return False

def _request(path, params=None):
    key = xbmcaddon.Addon().getSetting("tmdb_api_key").strip()
    if not key or not re.fullmatch(r"[a-zA-Z0-9]{20,100}", key):
        raise ValueError("Configure sua chave TMDb em Configurações → Catálogos Brasil.")
    params = dict(params or {})
    params["api_key"] = key
    with requests.get(API + path, params=params, timeout=(4, 9), stream=True,
                      allow_redirects=False, headers={"Accept": "application/json"}) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("TMDb indisponível")
        size = 0
        raw = []
        for chunk in response.iter_content(8192):
            size += len(chunk)
            if size > 650000:
                raise ValueError("Catálogo muito grande")
            raw.append(chunk)
        data = json.loads(b"".join(raw).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Resposta inválida do TMDb")
    return data

def _simple(name):
    text = unicodedata.normalize("NFKD", name.casefold())
    return "".join(c for c in text if c.isalnum())

def provider_id(code, media):
    if code not in MATCHES or media not in ("movie", "series"):
        raise ValueError("Plataforma inválida")
    cache_key = media + ":" + code
    cached = local_cache.get("tmdb_br_providers", cache_key)
    if type(cached) is int:
        return cached
    kind = "movie" if media == "movie" else "tv"
    data = _request("/watch/providers/" + kind, {"watch_region": "BR", "language": "pt-BR"})
    providers = data.get("results", [])
    aliases = [_simple(a) for a in MATCHES[code]]
    for alias in aliases:
        for provider in providers:
            if (isinstance(provider, dict) and _simple(str(provider.get("provider_name") or "")) == alias
                    and type(provider.get("provider_id")) is int):
                local_cache.put("tmdb_br_providers", cache_key, provider["provider_id"],
                                ttl=86400, max_entries=32)
                return provider["provider_id"]
    raise ValueError("Plataforma não encontrada no catálogo brasileiro")

def _list(results, media):
    items = []
    for row in results[:20]:
        if not isinstance(row, dict) or type(row.get("id")) is not int:
            continue
        original = row.get("title") if media == "movie" else row.get("name")
        year = row.get("release_date") if media == "movie" else row.get("first_air_date")
        poster = row.get("poster_path")
        items.append({
            "id": "tmdb:" + str(row["id"]), "type": media,
            "title": str(original or "Sem título")[:160],
            "plot": str(row.get("overview") or "")[:800],
            "year": str(year or "")[:4],
            "poster": POSTER + poster if isinstance(poster, str) and poster.startswith("/") else "",
            "rating": "",
        })
    return items

def platform_titles(media, code, page=1):
    if media not in ("movie", "series") or code not in MATCHES or not 1 <= page <= 100:
        raise ValueError("Catálogo inválido")
    cache_key = "{}:{}:{}".format(media, code, page)
    cached = local_cache.get("tmdb_br_pages", cache_key)
    if isinstance(cached, dict):
        return cached.get("items", []), bool(cached.get("more"))
    provider = provider_id(code, media)
    kind = "movie" if media == "movie" else "tv"
    payload = _request("/discover/" + kind, {
        "language": "pt-BR", "page": page, "include_adult": "false",
        "sort_by": "popularity.desc", "watch_region": "BR",
        "with_watch_providers": str(provider),
        "with_watch_monetization_types": "flatrate",
    })
    items = _list(payload.get("results", []), media)
    more = page < min(int(payload.get("total_pages") or 1), 100)
    local_cache.put("tmdb_br_pages", cache_key, {"items": items, "more": more},
                    ttl=3600, max_entries=64)
    return items, more

def resolve_imdb(identifier, media):
    if not isinstance(identifier, str) or not re.fullmatch(r"tmdb:[0-9]{1,10}", identifier):
        raise ValueError("ID TMDb inválido")
    if media not in ("movie", "series"):
        raise ValueError("Tipo inválido")
    cache_key = media + ":" + identifier
    cached = local_cache.get("tmdb_br_imdb", cache_key)
    if isinstance(cached, str) and re.fullmatch(r"tt[0-9]{5,12}", cached):
        return cached
    kind = "movie" if media == "movie" else "tv"
    found = _request("/{}/{}/external_ids".format(kind, identifier[5:]))
    imdb = found.get("imdb_id")
    if not isinstance(imdb, str) or not re.fullmatch(r"tt[0-9]{5,12}", imdb):
        raise ValueError("Título sem identificador IMDb compatível")
    local_cache.put("tmdb_br_imdb", cache_key, imdb, ttl=2592000, max_entries=400)
    return imdb
