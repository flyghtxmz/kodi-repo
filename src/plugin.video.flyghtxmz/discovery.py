"""Catálogos por ano e idioma, com país confirmado e identidade IMDb preservada."""
from concurrent.futures import ThreadPoolExecutor
import json
import re
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

import local_cache
from metadata_ptbr import TMDB_STREMIO_BASE
import recent

LANGUAGES = (("Português", "Portuguese"), ("Inglês", "English"), ("Espanhol", "Spanish"),
             ("Francês", "French"), ("Japonês", "Japanese"), ("Coreano", "Korean"),
             ("Italiano", "Italian"), ("Alemão", "German"), ("Hindi", "Hindi"), ("Mandarim", "Mandarin"))
# Este recorte combina país confirmado com seu idioma principal, sem inferir país pelo idioma.
COUNTRIES = (("Brasil — português", "Brazil", "Portuguese"), ("Portugal — português", "Portugal", "Portuguese"),
             ("Estados Unidos — inglês", "United States of America", "English"),
             ("Reino Unido — inglês", "United Kingdom", "English"), ("Japão — japonês", "Japan", "Japanese"),
             ("Coreia do Sul — coreano", "South Korea", "Korean"), ("França — francês", "France", "French"),
             ("Espanha — espanhol", "Spain", "Spanish"), ("Itália — italiano", "Italy", "Italian"),
             ("Alemanha — alemão", "Germany", "German"))


def fetch(url):
    parsed = urlsplit(url)
    tmdb = parsed.hostname == "tmdb.elfhosted.com" and url.startswith(TMDB_STREMIO_BASE + "/")
    cinemeta = parsed.hostname == "v3-cinemeta.strem.io" and bool(re.fullmatch(r"/meta/(movie|series)/tt[0-9]{5,12}\.json", parsed.path))
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443) or not (tmdb or cinemeta):
        raise ValueError("Origem de catálogo inválida.")
    with urlopen(Request(url, headers={"User-Agent": "FelipeVideos/1.5.0 (Kodi)", "Accept": "application/json"}), timeout=3 if cinemeta else 5) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("Catálogo excedeu o limite.")
    return json.loads(raw.decode("utf-8"))


def imdb_for(row):
    identifier = row.get("imdb_id") or row.get("id")
    if isinstance(identifier, str) and recent.IMDB_ID.fullmatch(identifier):
        return identifier
    for link in row.get("links", []) if isinstance(row.get("links"), list) else []:
        if not isinstance(link, dict) or link.get("category") != "imdb":
            continue
        try:
            url = urlsplit(link.get("url") or "")
            match = re.fullmatch(r"/title/(tt[0-9]{5,12})/?", url.path)
            if url.scheme == "https" and url.hostname in ("imdb.com", "www.imdb.com") and not url.username and match:
                return match[1]
        except ValueError:
            pass
    return ""


def _countries(identifier, media):
    key = media + ":" + identifier
    cached = local_cache.get("catalog_countries", key)
    if isinstance(cached, list):
        return cached
    for base in (recent.BASE, TMDB_STREMIO_BASE):
        try:
            meta = fetch(base + "/meta/" + media + "/" + identifier + ".json").get("meta")
            if not isinstance(meta, dict) or imdb_for(meta) != identifier:
                continue
            raw = meta.get("country")
            values = [x.strip().casefold() for x in raw.split(",")] if isinstance(raw, str) else []
            if values:
                local_cache.put("catalog_countries", key, values, ttl=86400, max_entries=512)
                return values
        except (OSError, ValueError, TypeError):
            pass
    return []


def metadata(identifier, media):
    """Fallback de detalhes para títulos TMDb que ainda não constam no Cinemeta."""
    recent.validate_id(identifier)
    if media not in ("movie", "series"):
        raise ValueError("Tipo de catálogo inválido.")
    key = media + ":" + identifier
    cached = local_cache.get("discovery_metadata", key)
    if isinstance(cached, dict) and imdb_for(cached) == identifier:
        return cached
    meta = fetch(TMDB_STREMIO_BASE + "/meta/" + media + "/" + identifier + ".json").get("meta")
    if not isinstance(meta, dict) or imdb_for(meta) != identifier or meta.get("type") not in (None, media):
        raise ValueError("O catálogo retornou outro título.")
    allowed = ("name", "description", "poster", "background", "country", "year", "releaseInfo",
               "genres", "genre", "runtime", "trailers", "trailerStreams")
    result = {name: meta[name] for name in allowed if name in meta}
    result.update(id=identifier, imdb_id=identifier, type=media)
    # A nota IMDb continua reservada ao Cinemeta; não trocar pela nota TMDb.
    if media == "series":
        videos = meta.get("videos")
        result["videos"] = []
        for row in videos[:2500] if isinstance(videos, list) else []:
            if not isinstance(row, dict):
                continue
            season, episode = row.get("season"), row.get("episode")
            if type(season) is int and type(episode) is int and 0 <= season <= 999 and 1 <= episode <= 9999:
                result["videos"].append({"id": "{}:{}:{}".format(identifier, season, episode),
                    "season": season, "episode": episode, "title": row.get("title") or row.get("name"),
                    "released": row.get("released")})
    local_cache.put("discovery_metadata", key, result, ttl=3600, max_entries=32)
    return result


def list_titles(media, kind, value, page=1):
    if media not in ("movie", "series"):
        raise ValueError("Tipo de catálogo inválido.")
    page = max(1, min(int(page), 100))
    skip = (page - 1) * 20
    if kind == "year":
        if not re.fullmatch(r"[12][0-9]{3}", str(value)) or not 1874 <= int(value) <= recent.date.today().year + 1:
            raise ValueError("Ano inválido.")
        data = recent.fetch(recent._url(media, "year", "genre={}&skip={}".format(value, skip)))
    else:
        country = None
        if kind == "country":
            found = next((row for row in COUNTRIES if row[1] == value), None)
            if found is None:
                raise ValueError("País inválido.")
            country, language = found[1], found[2]
        elif kind == "language" and value in {row[1] for row in LANGUAGES}:
            language = value
        elif kind == "anime":
            language = "Japanese"
        else:
            raise ValueError("Filtro inválido.")
        key = "{}:{}:{}:{}".format(media, kind, value, page)
        hit = local_cache.get("discovery_pages", key)
        if isinstance(hit, dict) and isinstance(hit.get("items"), list):
            return hit["items"], bool(hit.get("more"))
        extra = "genre={}&skip={}".format(quote(language, safe=""), skip)
        data = fetch(TMDB_STREMIO_BASE + "/catalog/" + media + "/tmdb.language/" + extra + ".json")
    raw_items = data.get("metas") if isinstance(data, dict) else None
    if not isinstance(raw_items, list):
        raise ValueError("Resposta de catálogo inválida.")
    items, seen = [], set()
    for row in raw_items[:20]:
        if not isinstance(row, dict):
            continue
        if row.get("type") not in (None, media):
            continue
        identifier = imdb_for(row)
        if not identifier or identifier in seen:
            continue
        if kind == "anime":
            genres = row.get("genre") or row.get("genres") or []
            if not isinstance(genres, list) or not any(str(g).casefold() in ("animation", "animação") for g in genres):
                continue
        item = recent.normalize({**row, "imdb_id": identifier}, media)
        if item and kind == "year" and str(item.get("year") or "")[:4] != str(value):
            continue
        if item:
            seen.add(identifier)
            items.append(item)
    if kind == "country":
        aliases = {country.casefold()}
        if country == "United States of America":
            aliases.add("united states")
        with ThreadPoolExecutor(max_workers=8) as pool:
            origin = list(pool.map(lambda item: _countries(item["id"], media), items))
        items = [item for item, countries in zip(items, origin) if aliases.intersection(countries)]
    items.sort(key=lambda row: row["title"].casefold())
    more = len(raw_items) >= 20 and page < 100
    if kind != "year":
        local_cache.put("discovery_pages", key, {"items": items, "more": more}, ttl=3600, max_entries=64)
    return items, more
