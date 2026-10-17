"""Catálogos Cinemeta por IMDb ID; títulos e sinopses localizados em PT-BR.

Mantém IDs IMDb para o Torrentio/Worker mesmo quando o título mostrado é traduzido.
"""
from datetime import date
import json
import re
import unicodedata
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

BASE = "https://v3-cinemeta.strem.io"
IMDB_ID = re.compile(r"^tt[0-9]{5,12}$")
YOUTUBE_ID = re.compile(r"^[a-zA-Z0-9_-]{11}$")
MAX_SIZE = 2_000_000
PAGES = 100
PER_PAGE = 20
ALL_CATEGORIES = (
    ("movies_new", "Lançamentos de {year}"),
    ("movies_prev", "Filmes de {prev_year}"),
    ("movies_prev2", "Filmes de {prev2_year}"),
    ("movies_popular", "Filmes em alta"),
    ("movies_best_rated", "Mais bem avaliados no IMDb"),
    ("series_new", "Séries de {year}"),
    ("series_prev", "Séries de {prev_year}"),
    ("series_prev2", "Séries de {prev2_year}"),
    ("series_popular", "Séries em alta"),
    ("series_best_rated", "Mais bem avaliadas no IMDb"),
)
CATEGORIES = ALL_CATEGORIES

GENRE_CATEGORIES = (
    ("movies_genre_action", "Ação"),
    ("movies_genre_adventure", "Aventura"),
    ("movies_genre_animation", "Animação"),
    ("movies_genre_comedy", "Comédia"),
    ("movies_genre_crime", "Crime"),
    ("movies_genre_documentary", "Documentários"),
    ("movies_genre_drama", "Drama"),
    ("movies_genre_family", "Família"),
    ("movies_genre_fantasy", "Fantasia"),
    ("movies_genre_horror", "Terror"),
    ("movies_genre_mystery", "Mistério"),
    ("movies_genre_romance", "Romance"),
    ("movies_genre_scifi", "Ficção científica"),
    ("movies_genre_thriller", "Suspense"),
    ("movies_genre_history", "História"),
    ("movies_genre_war", "Guerra"),
    ("movies_genre_western", "Faroeste"),
    ("movies_genre_music", "Música"),
    ("series_genre_action", "Ação"),
    ("series_genre_adventure", "Aventura"),
    ("series_genre_animation", "Animação"),
    ("series_genre_comedy", "Comédia"),
    ("series_genre_crime", "Crime"),
    ("series_genre_documentary", "Documentários"),
    ("series_genre_drama", "Drama"),
    ("series_genre_fantasy", "Fantasia"),
    ("series_genre_mystery", "Mistério"),
    ("series_genre_scifi", "Ficção científica"),
    ("series_genre_thriller", "Suspense"),
    ("series_genre_history", "História"),
    ("series_genre_war", "Guerra"),
    ("series_genre_western", "Faroeste"),
    ("series_genre_reality", "Reality shows"),
)
GENRE_CODES = {
    "action":"Action", "adventure":"Adventure", "animation":"Animation",
    "comedy":"Comedy", "crime":"Crime", "documentary":"Documentary",
    "drama":"Drama", "family":"Family", "fantasy":"Fantasy",
    "horror":"Horror", "mystery":"Mystery", "romance":"Romance",
    "history":"History", "war":"War", "western":"Western", "music":"Music",
    "scifi":"Sci-Fi", "thriller":"Thriller", "reality":"Reality-TV",
}


def fetch(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "v3-cinemeta.strem.io":
        raise ValueError("Origem de catálogo não permitida.")
    from local_cache import get, put
    ttl = 86400 if '/meta/' in parsed.path else 1800
    cached = get(url, ttl)
    if isinstance(cached, dict):
        return cached
    req = Request(url, headers={"User-Agent":"KodiFelipeVideos/1.4.0 (metadata)",
                                "Accept":"application/json"})
    try:
        with urlopen(req, timeout=8) as response:
            data = response.read(MAX_SIZE + 1)
        if len(data) > MAX_SIZE:
            raise ValueError("Resposta do catálogo muito grande.")
        payload = json.loads(data.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Formato de catálogo inválido.")
        put(url, payload)
        return payload
    except (OSError, ValueError):
        stale = get(url, 7 * 86400)
        if isinstance(stale, dict):
            return stale
        raise


def safe_title(value, limit=150):
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def validate_id(identifier):
    if not isinstance(identifier, str) or not IMDB_ID.fullmatch(identifier):
        raise ValueError("ID IMDb inválido.")
    return identifier


def _url(media, catalog, extra=""):
    if media not in ("movie", "series") or catalog not in ("top", "year", "imdbRating"):
        raise ValueError("Parâmetros de catálogo inválidos.")
    addition = "/" + quote(extra, safe="=&%") if extra else ""
    return BASE + "/catalog/{}/{}{}.json".format(media, catalog, addition)


def _parts(category, year=None, query=None):
    year = year or date.today().year
    if category in ("search_movie", "search_series"):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Digite um título.")
        media = "movie" if category == "search_movie" else "series"
        return media, "top", "search=" + quote(query.strip()[:80], safe="")
    match = re.fullmatch(r"(movies|series)_year_(\d{4})", category)
    if match and 1900 <= int(match[2]) <= year:
        return ('movie' if match[1] == 'movies' else 'series'), 'year', 'genre=' + match[2]
    allowed = {name for name, _ in CATEGORIES + GENRE_CATEGORIES}
    if category not in allowed:
        raise ValueError("Categoria desconhecida.")
    media = "movie" if category.startswith("movies_") else "series"
    suffix = category.split("_", 1)[1]
    if suffix == "new":
        return media, "year", "genre={}".format(year)
    if suffix == "prev":
        return media, "year", "genre={}".format(year - 1)
    if suffix == "prev2":
        return media, "year", "genre={}".format(year - 2)
    if suffix == "popular":
        return media, "top", ""
    if suffix == "best_rated":
        return media, "imdbRating", ""
    if suffix.startswith("genre_"):
        genre = suffix[6:]
        if genre in GENRE_CODES:
            return media, "top", "genre=" + quote(GENRE_CODES[genre], safe="")
    raise ValueError("Categoria desconhecida.")


def normalize(entry, kind=None):
    if not isinstance(entry, dict):
        return None
    imdb = entry.get("imdb_id") or entry.get("id")
    if not isinstance(imdb, str) or not IMDB_ID.fullmatch(imdb):
        return None
    media = entry.get("type") or kind or "movie"
    if media not in ("movie", "series") or (kind and media != kind):
        return None
    poster = entry.get("poster") or ""
    if not isinstance(poster, str) or not poster.startswith("https://"):
        poster = ""
    name = safe_title(entry.get("name") or entry.get("title"))
    if not name:
        return None
    return {
        "id": imdb, "type": media, "title": name,
        "year": str(entry.get("year") or entry.get("releaseInfo") or "")[:12],
        "plot": safe_title(entry.get("description"), 650),
        "poster": poster,
        "rating": safe_title(str(entry.get("imdbRating") or ""), 8),
    }


def list_titles(category, page=1, search_term="", year=None, sort="name"):
    page = max(1, min(int(page), PAGES))
    media, catalog, extra = _parts(category, year=year, query=search_term)
    if page > 1:
        extra += ("&" if extra else "") + "skip={}".format((page - 1) * PER_PAGE)
    data = fetch(_url(media, catalog, extra))
    raw_items = data.get("metas") or []
    if not isinstance(raw_items, list):
        raise ValueError("Formato do catálogo alterado.")
    results = []
    for item in raw_items[:PER_PAGE]:
        normalized = normalize(item, media)
        if normalized and normalized['id'] not in {row['id'] for row in results}:
            requested_year = re.search(r'genre=(\d{4})(?:&|$)', extra)
            if requested_year and normalized['year'] and normalized['year'][:4] != requested_year[1]:
                continue
            results.append(normalized)
    def az(movie):
        text = unicodedata.normalize("NFKD", movie["title"].casefold())
        return ("".join(c for c in text if not unicodedata.combining(c)), movie["id"])
    if sort == "name":
        results.sort(key=az)
    return results, len(raw_items) >= PER_PAGE and page < PAGES


def episodes_for_series(meta, identifier):
    """Extrai temporadas e episódios respeitando IDs e números oficiais."""
    validate_id(identifier)
    videos = meta.get("videos") if isinstance(meta, dict) else None
    if not isinstance(videos, list):
        return {}
    groups = {}
    for row in videos[:2500]:
        if not isinstance(row, dict):
            continue
        season, episode = row.get("season"), row.get("episode")
        if (type(season) is not int or type(episode) is not int or
                not 0 <= season <= 999 or not 1 <= episode <= 9999):
            continue
        canonical = "{}:{}:{}".format(identifier, season, episode)
        if row.get("id") and row["id"] != canonical:
            continue
        title = safe_title(row.get("title") or row.get("name"), 140)
        item = {"season": season, "episode": episode,
                "id": canonical, "title": title or "Episódio {}".format(episode),
                "released": str(row.get("released") or "")[:32]}
        group = groups.setdefault(season, {})
        prior = group.get(episode)
        if prior is None or (prior["title"].startswith("Episódio ") and title):
            group[episode] = item
    return {season: [group[num] for num in sorted(group)]
            for season, group in sorted(groups.items())}


def detail(identifier, media="movie"):
    identifier = validate_id(identifier)
    if media not in ("movie", "series"):
        raise ValueError("Tipo de catálogo inválido.")
    payload = fetch(BASE + "/meta/{}/{}.json".format(media, identifier))
    meta = payload.get("meta") or {}
    value = normalize(meta, media)
    if not value or value["id"] != identifier:
        raise ValueError("Detalhes não correspondem ao título solicitado.")
    trailers = meta.get("trailerStreams") or meta.get("trailers") or []
    trailer_id = ""
    for trailer in trailers:
        if not isinstance(trailer, dict):
            continue
        candidate = trailer.get("ytId") or trailer.get("source")
        if isinstance(candidate, str) and YOUTUBE_ID.fullmatch(candidate):
            trailer_id = candidate
            break
    value["trailer_id"] = trailer_id
    value["original_title"] = value["title"]
    if media == "series":
        value["episodes"] = episodes_for_series(meta, identifier)
    try:
        from metadata_ptbr import enrich
        synopsis, rating, checked_at = enrich(
            identifier, media, imdb_rating=value.get("rating"))
        value["plot"] = synopsis
        value["rating"] = rating
        value["rating_checked_at"] = checked_at
    except (ImportError, OSError, ValueError, TypeError):
        value["plot"] = "Sinopse em português (Brasil) ainda não disponível."
        value["rating_checked_at"] = None
    try:
        from metadata_ptbr import localized_title
        value["title"] = localized_title(identifier, media) or value["title"]
    except (ImportError, OSError, ValueError, TypeError):
        pass
    return value


def justwatch_search_url(title):
    title = safe_title(title, 120)
    if not title:
        raise ValueError("Título ausente.")
    return "https://www.justwatch.com/br/busca?" + urlencode({"q": title})
