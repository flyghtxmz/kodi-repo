"""Catálogo TMDb localizado para português do Brasil, com nota IMDb Cinemeta.

Os metadados não garantem disponibilidade de fontes/reprodução. A listagem é
localizada; a nota IMDb é obtida separadamente do Cinemeta e cacheada por 24h.
"""
from datetime import date
import json
import re
import unicodedata
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

BASE = ("https://tmdb.elfhosted.com/"
        "N4IgNghgdg5grhGBTEAuEAHALgWgEIBKIAvkA")
IMDB_BASE = "https://v3-cinemeta.strem.io"
TMDB_ID = re.compile(r"^tmdb:[0-9]{1,12}$")
IMDB_ID = re.compile(r"^tt[0-9]{5,12}$")
YOUTUBE_ID = re.compile(r"^[a-zA-Z0-9_-]{11}$")
MAX_SIZE = 2_000_000
PAGES = 100
PER_PAGE = 20
CATEGORIES = (
    ("movies_new", "Filmes de {year}"),
    ("movies_prev", "Filmes de {prev_year}"),
    ("movies_popular", "Filmes populares"),
    ("movies_trending", "Em tendência"),
    ("movies_latest", "Últimos lançamentos"),
    ("series_new", "Séries de {year}"),
    ("series_popular", "Séries populares"),
    ("series_trending", "Em tendência"),
    ("series_latest", "Séries recentes"),
)
GENRE_CATEGORIES = (
    ("movies_genre_action", "Ação"),
    ("movies_genre_adventure", "Aventura"),
    ("movies_genre_comedy", "Comédia"),
    ("movies_genre_crime", "Crime"),
    ("movies_genre_drama", "Drama"),
    ("movies_genre_horror", "Terror"),
    ("movies_genre_thriller", "Suspense"),
    ("movies_genre_scifi", "Ficção científica"),
    ("movies_genre_animation", "Animação"),
    ("movies_genre_romance", "Romance"),
    ("movies_genre_documentary", "Documentários"),
    ("movies_genre_family", "Família"),
    ("movies_genre_fantasy", "Fantasia"),
    ("movies_genre_war", "Guerra"),
    ("movies_genre_history", "História"),
    ("movies_genre_mystery", "Mistério"),
    ("movies_genre_western", "Faroeste"),
    ("series_genre_action", "Ação e aventura"),
    ("series_genre_comedy", "Comédia"),
    ("series_genre_crime", "Crime"),
    ("series_genre_drama", "Drama"),
    ("series_genre_scifi", "Ficção científica e fantasia"),
    ("series_genre_mystery", "Mistério"),
    ("series_genre_documentary", "Documentários"),
    ("series_genre_animation", "Animação"),
    ("series_genre_family", "Família"),
    ("series_genre_reality", "Reality shows"),
    ("series_genre_kids", "Infantis"),
    ("series_genre_politics", "Guerra e política"),
    ("series_genre_soap", "Novelas"),
    ("series_genre_talk", "Talk shows"),
)
MOVIE_GENRES = {
    "action": "Ação", "adventure": "Aventura", "comedy": "Comédia",
    "crime": "Crime", "drama": "Drama", "horror": "Terror",
    "thriller": "Thriller", "scifi": "Ficção científica",
    "animation": "Animação", "romance": "Romance",
    "documentary": "Documentário", "family": "Família",
    "fantasy": "Fantasia", "war": "Guerra",
    "history": "História", "mystery": "Mistério",
    "western": "Faroeste",
}
SERIES_GENRES = {
    "action": "Action & Adventure", "comedy": "Comédia",
    "crime": "Crime", "drama": "Drama", "scifi": "Sci-Fi & Fantasy",
    "mystery": "Mistério", "documentary": "Documentário",
    "animation": "Animação", "family": "Família",
    "reality": "Reality", "kids": "Kids",
    "politics": "War & Politics", "soap": "Soap", "talk": "Talk",
}


def fetch(url):
    parts = urlsplit(url)
    allowed = {"tmdb.elfhosted.com", "v3-cinemeta.strem.io"}
    if parts.scheme != "https" or parts.hostname not in allowed:
        raise ValueError("Origem de catálogo não permitida.")
    request = Request(url, headers={
        "User-Agent": "KodiFelipeVideos/1.4.0 (pt-br-metadata)",
        "Accept": "application/json",
    })
    with urlopen(request, timeout=12) as response:
        content = response.read(MAX_SIZE + 1)
    if len(content) > MAX_SIZE:
        raise ValueError("Resposta do catálogo muito grande.")
    return json.loads(content.decode("utf-8"))


def safe_title(value, limit=150):
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def validate_id(identifier):
    if not isinstance(identifier, str) or not (IMDB_ID.fullmatch(identifier) or TMDB_ID.fullmatch(identifier)):
        raise ValueError("ID de título inválido.")
    return identifier


def _url(media, catalog, extra=""):
    available = ("tmdb.top", "tmdb.year", "tmdb.trending", "tmdb.latest", "tmdb.search")
    if media not in ("movie", "series") or catalog not in available:
        raise ValueError("Parâmetros de catálogo inválidos.")
    addition = "/" + quote(extra, safe="=&%") if extra else ""
    return BASE + "/catalog/{}/{}{}.json".format(media, catalog, addition)


def _parts(category, year=None, query=None):
    year = year or date.today().year
    if category in ("search_movie", "search_series"):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Digite um título.")
        return ("movie" if category == "search_movie" else "series"), "tmdb.search", (
            "search=" + quote(query.strip()[:80], safe=""))
    if category.startswith("movies_genre_"):
        genre = category[len("movies_genre_"):]
        if genre not in MOVIE_GENRES:
            raise ValueError("Gênero desconhecido.")
        return "movie", "tmdb.top", "genre=" + quote(MOVIE_GENRES[genre], safe="")
    if category.startswith("series_genre_"):
        genre = category[len("series_genre_"):]
        if genre not in SERIES_GENRES:
            raise ValueError("Gênero desconhecido.")
        return "series", "tmdb.top", "genre=" + quote(SERIES_GENRES[genre], safe="")
    if category.startswith("movies_"):
        media, action = "movie", category[7:]
    elif category.startswith("series_"):
        media, action = "series", category[7:]
    else:
        raise ValueError("Categoria desconhecida.")
    if action == "new":
        return media, "tmdb.year", "genre={}".format(year)
    if action == "prev" and media == "movie":
        return media, "tmdb.year", "genre={}".format(year - 1)
    if action == "popular":
        return media, "tmdb.top", ""
    if action == "trending":
        return media, "tmdb.trending", "genre=Week"
    if action == "latest":
        return media, "tmdb.latest", ""
    raise ValueError("Categoria desconhecida.")


def normalize(entry, kind=None):
    if not isinstance(entry, dict):
        return None
    ident = entry.get("id") or entry.get("imdb_id")
    if not isinstance(ident, str) or not (IMDB_ID.fullmatch(ident) or TMDB_ID.fullmatch(ident)):
        return None
    typ = entry.get("type") or kind or "movie"
    if typ not in ("movie", "series"):
        return None
    poster = entry.get("poster") or ""
    if not isinstance(poster, str) or not poster.startswith("https://"):
        poster = ""
    title = safe_title(entry.get("name") or entry.get("title"))
    if not title:
        return None
    year = str(entry.get("year") or entry.get("releaseInfo") or "")[:12]
    plot = safe_title(entry.get("description"), 650)
    # Nunca classificar a nota da plataforma TMDb como sendo uma nota IMDb.
    # A nota IMDb é consultada do Cinemeta em detail(), quando disponível.
    imdb_id = entry.get("imdb_id") or ""
    if not isinstance(imdb_id, str) or not IMDB_ID.fullmatch(imdb_id):
        imdb_id = ""
    return {
        "id": ident, "type": typ, "title": title,
        "year": year, "plot": plot, "poster": poster,
        "imdb_id": imdb_id, "rating": "",
    }


def list_titles(category, page=1, search_term="", year=None):
    page = max(1, min(int(page), PAGES))
    media, catalog, extra = _parts(category, year=year, query=search_term)
    if page > 1:
        extra += "&skip={}".format((page - 1) * PER_PAGE) if extra else "skip={}".format((page - 1) * PER_PAGE)
    data = fetch(_url(media, catalog, extra))
    raw_items = data.get("metas") or []
    if not isinstance(raw_items, list):
        raise ValueError("Formato do catálogo alterado.")
    results = []
    for item in raw_items[:PER_PAGE]:
        normalized = normalize(item, media)
        if normalized:
            results.append(normalized)
    # Ordenação A-Z independente de maiúsculas, acentos e idioma da interface.
    # Cinemeta pagina por sua própria ordem: a ordenação vale para os itens carregados.
    def alphabetical_key(item):
        value = unicodedata.normalize("NFKD", item["title"].casefold())
        return ("".join(char for char in value if not unicodedata.combining(char)),
                item["id"])
    results.sort(key=alphabetical_key)
    return results, len(raw_items) >= PER_PAGE and page < PAGES


def detail(identifier, media="movie"):
    identifier = validate_id(identifier)
    if media not in ("movie", "series"):
        raise ValueError("Tipo de catálogo inválido.")
    data = fetch(BASE + "/meta/{}/{}.json".format(media, identifier))
    meta = data.get("meta") or {}
    value = normalize(meta, media)
    if not value:
        raise ValueError("Detalhes indisponíveis.")
    imdb_id = value.get("imdb_id") or (identifier if IMDB_ID.fullmatch(identifier) else "")
    value["imdb_id"] = imdb_id
    sources = meta.get("trailerStreams") or meta.get("trailers") or []
    trailer_id = ""
    for trailer in sources:
        if not isinstance(trailer, dict):
            continue
        candidate = trailer.get("ytId") or trailer.get("source")
        if isinstance(candidate, str) and YOUTUBE_ID.fullmatch(candidate):
            trailer_id = candidate
            break
    value["trailer_id"] = trailer_id
    # A sinopse e o título já chegam traduzidos da API TMDb configurada PT-BR.
    # O campo "imdbRating" do TMDb NÃO substitui a fonte IMDb/Cinemeta.
    if imdb_id:
        try:
            from metadata_ptbr import enrich, cached_rating
            current = cached_rating(imdb_id, media)
            rating = ""
            if not current:
                try:
                    cinemeta = fetch(
                        IMDB_BASE + "/meta/{}/{}.json".format(media, imdb_id))
                    rating = str((cinemeta.get("meta") or {}).get("imdbRating") or "")
                except (OSError, TimeoutError, ValueError, TypeError):
                    pass
            synopsis, rating, checked = enrich(
                imdb_id, media, imdb_rating=rating,
                ptbr_description=value.get("plot") or "")
            value["plot"] = synopsis
            value["rating"] = rating
            value["rating_checked_at"] = checked
        except (ImportError, OSError, ValueError, TypeError):
            value["rating"] = "Indisponível"
            value["rating_checked_at"] = None
    else:
        value["rating"] = "Indisponível"
        value["rating_checked_at"] = None
    if not value.get("plot"):
        value["plot"] = "Sinopse em português (Brasil) ainda não disponível."
    return value


def justwatch_search_url(title):
    title = safe_title(title, 120)
    if not title:
        raise ValueError("Título ausente.")
    # Navegação externa pelo navegador Android, sem tentar transmitir vídeo protegido.
    return "https://www.justwatch.com/br/busca?" + urlencode({"q": title})
