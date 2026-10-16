"""Consulta o catálogo público Cinemeta para lançamentos e séries atuais.

Metadados NÃO são links de reprodução comercial. Para exibição de obras atuais,
mostra os trailers oficiais (se disponíveis) e o buscador de serviços autorizados.
"""
from datetime import date
import json
import re
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

BASE = "https://v3-cinemeta.strem.io"
IMDB_ID = re.compile(r"^tt[0-9]{5,12}$")
YOUTUBE_ID = re.compile(r"^[a-zA-Z0-9_-]{11}$")
MAX_SIZE = 2_000_000
PAGES = 20
PER_PAGE = 100
CATEGORIES = (
    ("movies_new", "Filmes de {year}"),
    ("movies_prev", "Filmes de {prev_year}"),
    ("movies_popular", "Filmes em alta"),
    ("series_new", "Séries de {year}"),
    ("series_popular", "Séries em alta"),
)


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
    if media not in ("movie", "series") or catalog not in ("top", "year"):
        raise ValueError("Parâmetros de catálogo inválidos.")
    addition = "/" + quote(extra, safe="=&") if extra else ""
    return BASE + "/catalog/{}/{}{}.json".format(media, catalog, addition)


def _parts(category, year=None, query=None):
    year = year or date.today().year
    if category == "movies_new":
        return "movie", "year", "genre={}".format(year)
    if category == "movies_prev":
        return "movie", "year", "genre={}".format(year - 1)
    if category == "movies_popular":
        return "movie", "top", ""
    if category == "series_new":
        return "series", "year", "genre={}".format(year)
    if category == "series_popular":
        return "series", "top", ""
    if category in ("search_movie", "search_series"):
        if not query or not isinstance(query, str) or not query.strip():
            raise ValueError("Digite um título.")
        q = query.strip()[:80]
        return ("movie" if category == "search_movie" else "series"), "top", "search=" + quote(q, safe="")
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
    return value


def justwatch_search_url(title):
    title = safe_title(title, 120)
    if not title:
        raise ValueError("Título ausente.")
    # Navegação externa pelo navegador Android, sem tentar transmitir vídeo protegido.
    return "https://www.justwatch.com/br/busca?" + urlencode({"q": title})
