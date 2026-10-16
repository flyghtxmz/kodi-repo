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
    ("movies_popular", "Filmes em alta"),
    ("movies_best_rated", "Mais bem avaliados no IMDb"),
    ("movies_action", "Ação"),
    ("movies_adventure", "Aventura"),
    ("movies_animation", "Animação"),
    ("movies_comedy", "Comédia"),
    ("movies_crime", "Crime"),
    ("movies_documentary", "Documentários"),
    ("movies_drama", "Drama"),
    ("movies_family", "Família"),
    ("movies_fantasy", "Fantasia"),
    ("movies_horror", "Terror"),
    ("movies_mystery", "Mistério"),
    ("movies_romance", "Romance"),
    ("movies_scifi", "Ficção científica"),
    ("movies_thriller", "Suspense"),
    ("series_new", "Séries de {year}"),
    ("series_prev", "Séries de {prev_year}"),
    ("series_popular", "Séries em alta"),
    ("series_best_rated", "Mais bem avaliadas no IMDb"),
    ("series_action", "Ação"),
    ("series_adventure", "Aventura"),
    ("series_animation", "Animação"),
    ("series_comedy", "Comédia"),
    ("series_crime", "Crime"),
    ("series_documentary", "Documentários"),
    ("series_drama", "Drama"),
    ("series_fantasy", "Fantasia"),
    ("series_mystery", "Mistério"),
    ("series_scifi", "Ficção científica"),
    ("series_thriller", "Suspense"),
    ("series_reality", "Reality shows"),
)
CATEGORIES = tuple((category, label) for category, label in ALL_CATEGORIES
                   if category.split("_", 1)[1] in ("new", "prev", "popular", "best_rated"))
GENRE_CATEGORIES = tuple((category, label) for category, label in ALL_CATEGORIES
                         if category.split("_", 1)[1] not in
                         ("new", "prev", "popular", "best_rated"))
GENRE_CODES = {
    "action":"Action", "adventure":"Adventure", "animation":"Animation",
    "comedy":"Comedy", "crime":"Crime", "documentary":"Documentary",
    "drama":"Drama", "family":"Family", "fantasy":"Fantasy",
    "horror":"Horror", "mystery":"Mystery", "romance":"Romance",
    "scifi":"Sci-Fi", "thriller":"Thriller", "reality":"Reality-TV",
}


def fetch(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "v3-cinemeta.strem.io":
        raise ValueError("Origem de catálogo não permitida.")
    req = Request(url, headers={"User-Agent":"KodiFelipeVideos/1.4.0 (metadata)",
                                "Accept":"application/json"})
    with urlopen(req, timeout=12) as response:
        data = response.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        raise ValueError("Resposta do catálogo muito grande.")
    return json.loads(data.decode("utf-8"))


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
    if category not in {name for name, _ in ALL_CATEGORIES}:
        raise ValueError("Categoria desconhecida.")
    media = "movie" if category.startswith("movies_") else "series"
    suffix = category.split("_", 1)[1]
    if suffix == "new":
        return media, "year", "genre={}".format(year)
    if suffix == "prev":
        return media, "year", "genre={}".format(year - 1)
    if suffix == "popular":
        return media, "top", ""
    if suffix == "best_rated":
        return media, "imdbRating", ""
    if suffix in GENRE_CODES:
        return media, "top", "genre=" + quote(GENRE_CODES[suffix], safe="")
    raise ValueError("Categoria desconhecida.")


def normalize(entry, kind=None):
    if not isinstance(entry, dict):
        return None
    imdb = entry.get("imdb_id") or entry.get("id")
    if not isinstance(imdb, str) or not IMDB_ID.fullmatch(imdb):
        return None
    media = entry.get("type") or kind or "movie"
    if media not in ("movie", "series"):
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


def list_titles(category, page=1, search_term="", year=None):
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
        if normalized:
            results.append(normalized)
    def az(movie):
        text = unicodedata.normalize("NFKD", movie["title"].casefold())
        return ("".join(c for c in text if not unicodedata.combining(c)), movie["id"])
    results.sort(key=az)
    return results, len(raw_items) >= PER_PAGE and page < PAGES


def detail(identifier, media="movie"):
    identifier = validate_id(identifier)
    if media not in ("movie", "series"):
        raise ValueError("Tipo de catálogo inválido.")
    payload = fetch(BASE + "/meta/{}/{}.json".format(media, identifier))
    meta = payload.get("meta") or {}
    value = normalize(meta, media)
    if not value:
        raise ValueError("Detalhes indisponíveis.")
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
