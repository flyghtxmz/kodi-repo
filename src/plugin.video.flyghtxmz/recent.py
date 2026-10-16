"""Consulta o catálogo público Cinemeta para lançamentos e séries atuais.

Metadados NÃO são links de reprodução comercial. Para exibição de obras atuais,
mostra os trailers oficiais (se disponíveis) e o buscador de serviços autorizados.
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
CATEGORIES = (
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
GENRE_CODES = {
    "action":"Action","adventure":"Adventure","animation":"Animation",
    "comedy":"Comedy","crime":"Crime","documentary":"Documentary",
    "drama":"Drama","family":"Family","fantasy":"Fantasy",
    "horror":"Horror","mystery":"Mystery","romance":"Romance",
    "scifi":"Sci-Fi","thriller":"Thriller","reality":"Reality-TV",
}

# Gêneros confirmados pelo manifesto oficial Cinemeta; a URL usa os
# identificadores originais do provedor, mas a interface fica em PT-BR.
GENRES = (
    ("action", "Ação", "Action"),
    ("adventure", "Aventura", "Adventure"),
    ("animation", "Animação", "Animation"),
    ("comedy", "Comédia", "Comedy"),
    ("crime", "Crime", "Crime"),
    ("documentary", "Documentários", "Documentary"),
    ("drama", "Drama", "Drama"),
    ("family", "Família", "Family"),
    ("fantasy", "Fantasia", "Fantasy"),
    ("scifi", "Ficção científica", "Sci-Fi"),
    ("horror", "Terror", "Horror"),
    ("mystery", "Mistério", "Mystery"),
    ("romance", "Romance", "Romance"),
    ("thriller", "Suspense", "Thriller"),
    ("history", "História", "History"),
    ("sport", "Esportes", "Sport"),
    ("war", "Guerra", "War"),
)
GENRE_CATEGORIES = tuple(
    (media + "_genre_" + slug, label)
    for media in ("movies", "series")
    for slug, label, _ in GENRES
) + (
    ("series_genre_reality", "Reality shows"),
    ("series_genre_talk", "Talk shows"),
    ("series_genre_game", "Programas de competição"),
)
GENRE_LOOKUP = {slug: genre for slug, _, genre in GENRES}
GENRE_LOOKUP.update({"reality": "Reality-TV", "talk": "Talk-Show",
                     "game": "Game-Show"})



def fetch(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != "v3-cinemeta.strem.io":
        raise ValueError("Origem de catálogo não permitida.")
    request = Request(url, headers={
        "User-Agent": "KodiFelipeVideos/1.3 (public movie metadata)",
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
    if not isinstance(identifier, str) or not IMDB_ID.fullmatch(identifier):
        raise ValueError("ID de título inválido.")
    return identifier


def _url(media, catalog, extra=""):
    if media not in ("movie", "series") or catalog not in ("top", "year", "imdbRating"):
        raise ValueError("Parâmetros de catálogo inválidos.")
    addition = "/" + quote(extra, safe="=&%") if extra else ""
    return BASE + "/catalog/{}/{}{}.json".format(media, catalog, addition)


def _parts(category, year=None, query=None):
    year = year or date.today().year
    if category in ("search_movie", "search_series"):
        if not query or not isinstance(query, str) or not query.strip():
            raise ValueError("Digite um título.")
        media = "movie" if category == "search_movie" else "series"
        return media, "top", "search=" + quote(query.strip()[:80], safe="")
    if category not in {name for name, _ in CATEGORIES}:
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
    ident = entry.get("imdb_id") or entry.get("id")
    if not isinstance(ident, str) or not IMDB_ID.fullmatch(ident):
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
    rating = safe_title(str(entry.get("imdbRating") or ""), 8)
    return {
        "id": ident, "type": typ, "title": title,
        "year": year, "plot": plot, "poster": poster, "rating": rating,
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
    value["original_title"] = value["title"]
    # Sempre apresenta sinopse PT-BR; em indisponibilidade, texto de fallback
    # em português, não a descrição original em inglês do Cinemeta.
    try:
        from metadata_ptbr import enrich
        synopsis, rating, checked_at = enrich(
            identifier, media, imdb_rating=value.get("rating"))
        value["plot"] = synopsis
        value["rating"] = rating
        value["rating_checked_at"] = checked_at
        from metadata_ptbr import localized_title
        translated = localized_title(identifier, media)
        if translated:
            value["original_title"] = value["title"]
            value["title"] = translated
        try:
            from metadata_ptbr import localized_title
            value["title"] = localized_title(identifier, media) or value["title"]
        except (ImportError, OSError, ValueError, TypeError):
            pass
    except (ImportError, OSError, ValueError, TypeError) as error:
        value["plot"] = "Sinopse em português (Brasil) ainda não disponível."
        value["rating_checked_at"] = None
    return value


def justwatch_search_url(title):
    title = safe_title(title, 120)
    if not title:
        raise ValueError("Título ausente.")
    # Navegação externa pelo navegador Android, sem tentar transmitir vídeo protegido.
    return "https://www.justwatch.com/br/busca?" + urlencode({"q": title})
