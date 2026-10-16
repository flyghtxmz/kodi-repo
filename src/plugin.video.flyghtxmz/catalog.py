"""Catálogo de vídeos de licença aberta: busca/metadata oficiais do Internet Archive.

O índice é consultado sob demanda, sem URLs digitadas pelo usuário.
A licença é checada no resultado e novamente no item antes de iniciar a reprodução.
Não usa scraper, torrent indexers ou listas de conteúdo não autorizado.
"""
import html
import json
import re
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_ROOT = "https://archive.org/metadata/"
DOWNLOAD_ROOT = "https://archive.org/download/"
IMAGE_ROOT = "https://archive.org/services/img/"
PER_PAGE = 24
MAX_PAGE = 40
MAX_TERM = 80
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
TAGS_RE = re.compile(r"<[^>]*>")
BASE_QUERY = "mediatype:movies AND licenseurl:http*creativecommons.org*"
CATEGORIES = (
    ("destaques", "Mais populares"),
    ("filmes", "Filmes"),
    ("series", "Séries e programas"),
    ("documentarios", "Documentários"),
    ("animacoes", "Animações"),
    ("curtas", "Curtas-metragens"),
)
FILTERS = {
    "destaques": "",
    "filmes": "(subject:film OR subject:movie OR subject:feature)",
    "series": "(subject:series OR subject:television OR subject:episode)",
    "documentarios": "(subject:documentary OR subject:documentario)",
    "animacoes": "(subject:animation OR subject:cartoon)",
    "curtas": "(subject:short OR subject:shortfilm)",
    "busca": "",
}


def _string(value):
    if isinstance(value, list):
        return _string(value[0]) if value else ""
    return value.strip() if isinstance(value, str) else ""


def open_license(value):
    """Aceita apenas URL reconhecida de licença CC ou domínio público."""
    value = _string(value)
    try:
        url = urlsplit(value)
        if url.scheme not in ("http", "https") or url.hostname not in (
            "creativecommons.org", "www.creativecommons.org"
        ):
            return False
        path = url.path.rstrip("/") + "/"
        return bool(
            re.match(r"^/licenses/(?:by|by-sa|by-nd|by-nc|by-nc-sa|by-nc-nd)/\d", path)
            or re.match(r"^/publicdomain/(?:zero|mark)/\d", path)
        )
    except ValueError:
        return False


def sanitize_identifier(value):
    if isinstance(value, str) and IDENTIFIER_RE.fullmatch(value):
        return value
    raise ValueError("Identificador inválido no catálogo.")


def clean_text(value, length=450):
    if isinstance(value, list):
        value = " ".join(_string(v) for v in value[:3])
    value = html.unescape(TAGS_RE.sub(" ", _string(value)))
    value = re.sub(r"\s+", " ", value).strip()
    return value[:length]


def fetch_json(url):
    request = Request(url, headers={
        "User-Agent": "FelipeVideosKodi/1.2 (Kodi catalog)",
        "Accept": "application/json",
    })
    with urlopen(request, timeout=11) as response:
        if not (200 <= response.status < 300):
            raise RuntimeError("Servidor de catálogo indisponível.")
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("Catálogo excedeu o tamanho máximo.")
    return json.loads(raw.decode("utf-8"))


def make_query(category, search_term=""):
    if category not in FILTERS:
        raise ValueError("Categoria desconhecida.")
    terms = [BASE_QUERY]
    if FILTERS[category]:
        terms.append(FILTERS[category])
    if category == "busca":
        words = re.findall(r"[\wÀ-ÿ]+", _string(search_term)[:MAX_TERM], re.UNICODE)
        words = words[:8]
        if not words:
            raise ValueError("Digite um título para pesquisar.")
        terms += ["title:" + word for word in words]
    return " AND ".join(terms)


def search(category="destaques", page=1, search_term=""):
    page = max(1, min(int(page), MAX_PAGE))
    params = [
        ("q", make_query(category, search_term)),
        ("fl[]", "identifier"), ("fl[]", "title"), ("fl[]", "description"),
        ("fl[]", "year"), ("fl[]", "creator"), ("fl[]", "licenseurl"),
        ("sort[]", "downloads desc"),
        ("rows", str(PER_PAGE)), ("page", str(page)), ("output", "json"),
    ]
    data = fetch_json(SEARCH_URL + "?" + urlencode(params))
    response = data.get("response") or {}
    docs = response.get("docs") or []
    results = []
    for doc in docs:
        if not isinstance(doc, dict) or not open_license(doc.get("licenseurl")):
            continue
        try:
            ident = sanitize_identifier(doc.get("identifier"))
        except ValueError:
            continue
        results.append({
            "identifier": ident,
            "title": clean_text(doc.get("title"), 130) or ident,
            "plot": clean_text(doc.get("description")),
            "year": doc.get("year"),
            "creator": clean_text(doc.get("creator"), 100),
            "license": _string(doc.get("licenseurl")),
            "thumb": IMAGE_ROOT + quote(ident, safe=""),
        })
    count = int(response.get("numFound") or 0)
    return results, (page * PER_PAGE < count and page < MAX_PAGE)


def playback(identifier):
    ident = sanitize_identifier(identifier)
    data = fetch_json(METADATA_ROOT + quote(ident, safe=""))
    info = data.get("metadata") or {}
    if not isinstance(info, dict) or not open_license(info.get("licenseurl")):
        raise ValueError("O item não possui licença aberta verificável.")
    files = data.get("files") or []
    choices = []
    extensions = {".mp4": 0, ".m4v": 1, ".mov": 2, ".webm": 3, ".ogv": 4}
    for file in files:
        if not isinstance(file, dict):
            continue
        name = file.get("name")
        if not isinstance(name, str) or len(name) > 240:
            continue
        if not name or name.startswith("/") or ".." in name.split("/") or "\\" in name:
            continue
        ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in extensions:
            continue
        lowered = name.lower()
        if any(part in lowered for part in ("_thumb", "thumbnail", "trailer", "sample", "preview")):
            continue
        try:
            size = int(file.get("size") or 0)
        except (ValueError, TypeError):
            size = 0
        if size > 3_000_000_000:
            continue
        # Prefer MP4 H264 at TV-box-friendly resolution; avoid huge 4K originals.
        video_priority = 0 if any(x in lowered for x in ("720p", "720.", "1280x720")) else (
            1 if any(x in lowered for x in ("480p", "480.", "512kb")) else (
                3 if any(x in lowered for x in ("2160", "4k", "1080p")) else 2))
        choices.append(((extensions[ext], video_priority, size or 999_999_999), name))
    if not choices:
        raise ValueError("Este título não possui vídeo compatível para reprodução.")
    filename = min(choices)[1]
    return {
        "url": DOWNLOAD_ROOT + quote(ident, safe="") + "/" + quote(filename, safe="/"),
        "title": clean_text(info.get("title"), 130) or ident,
        "plot": clean_text(info.get("description")),
        "license": _string(info.get("licenseurl")),
        "creator": clean_text(info.get("creator"), 100),
        "thumb": IMAGE_ROOT + quote(ident, safe=""),
    }
