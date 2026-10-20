"""Cinema navigation and catalog loading, independent from the modal UI."""
from datetime import date
import discovery
import recent

NAVIGATION = (("Início", "home"), ("Plataformas", "platforms"),
              ("Filmes", "movies"), ("Séries", "series"), ("Em alta", "trending"),
              ("Buscar", "search"), ("Menu nativo", "classic"), ("Sair", "exit"))


def shelf(label, media, kind="trending", value="Week", category=""):
    return {"label": label, "media": media, "kind": kind, "value": value,
            "category": category}


def screen(route="home", value=""):
    """Two independent shelves and visible shortcuts; no network or Kodi calls."""
    platforms = [(name, "platform", code) for name, code, _ in discovery.PLATFORMS]
    tabs = platforms
    note = "Escolha uma plataforma ou explore as fileiras abaixo."
    title = "Seu próximo favorito"
    nav = "home"
    rows = [shelf("Filmes em alta nesta semana", "movie"),
            shelf("Séries em alta nesta semana", "series")]
    if route in ("platform", "platforms"):
        code = value if route == "platform" else discovery.PLATFORMS[0][1]
        found = next((p for p in discovery.PLATFORMS if p[1] == code), None)
        if found is None:
            raise ValueError("Plataforma inválida.")
        title, code, region = found
        nav = "platforms"
        note = "Populares no TMDb • referência: {} • disponibilidade no Brasil pode variar".format(region)
        rows = [shelf("Filmes populares — " + title, "movie", "platform", code),
                shelf("Séries populares — " + title, "series", "platform", code)]
    elif route in ("movies", "series", "category"):
        media = "series" if route == "series" or (route == "category" and value.startswith("series_")) else "movie"
        nav = "series" if media == "series" else "movies"
        prefix = nav + "_"
        title = "Séries para explorar" if media == "series" else "Filmes para explorar"
        note = "Lançamentos, mais avaliados e gêneros • use os atalhos acima das capas"
        year = date.today().year
        tabs = [(name.format(year=year, prev_year=year-1, prev2_year=year-2), "category", key)
                for key, name in recent.CATEGORIES + recent.GENRE_CATEGORIES if key.startswith(prefix)]
        rows = [shelf("Lançamentos de {}".format(year), media, "", category=prefix+"new"),
                shelf("Mais bem avaliados no IMDb", media, "", category=prefix+"best_rated")]
        if route == "category":
            choice = next((x for x in tabs if x[2] == value), None)
            if choice is None:
                raise ValueError("Categoria inválida.")
            title = choice[0]
            rows = [shelf(title, media, "", category=value)]
    elif route in ("trending", "period"):
        period = value if route == "period" else "Day"
        if period not in ("Day", "Week"):
            raise ValueError("Período inválido.")
        nav, title = "trending", "Em alta hoje" if period == "Day" else "Em alta nesta semana"
        tabs = [("Hoje", "period", "Day"), ("Nesta semana", "period", "Week")]
        note = "Tendências TMDb • ordem de popularidade preservada"
        rows = [shelf("Filmes — " + title.lower(), "movie", "trending", period),
                shelf("Séries — " + title.lower(), "series", "trending", period)]
    elif route == "search_results":
        nav, title, tabs = "search", "Busca: " + value[:60], []
        note = "Resultados de filmes e séries • cada fileira tem sua própria paginação"
        rows = [shelf("Filmes encontrados", "movie", "search", value, "search_movie"),
                shelf("Séries encontradas", "series", "search", value, "search_series")]
    elif route != "home":
        raise ValueError("Tela inválida.")
    return {"title": title, "note": note, "nav": nav, "tabs": tabs, "shelves": rows}


def compact_catalog(movies, localized):
    result = []
    for movie in movies[:20]:
        if not isinstance(movie, dict):
            continue
        identifier, media = movie.get("id"), movie.get("type")
        if not isinstance(identifier, str) or not recent.IMDB_ID.fullmatch(identifier) or media not in ("movie", "series"):
            continue
        cached = localized.get("{}:{}".format(media, identifier), {})
        cached = cached if isinstance(cached, dict) else {}
        def text(value, limit):
            return value[:limit] if isinstance(value, str) else ""
        result.append({"id": identifier, "media": media,
            "title": text(cached.get("title") or movie.get("title"), 150) or "Sem título",
            "plot": text(cached.get("plot") or movie.get("plot"), 800) or "Abra a ficha para consultar a sinopse em português.",
            "poster": text(movie.get("poster"), 2000)})
    return result


def load_shelf(spec, page=1):
    page = max(1, min(int(page), 100))
    if spec["kind"] in ("platform", "trending"):
        titles, more = discovery.list_titles(spec["media"], spec["kind"], spec["value"], page)
    else:
        titles, more = recent.list_titles(spec["category"], page=page,
                                         search_term=spec["value"] if spec["kind"] == "search" else "")
    from metadata_ptbr import _read_cache
    raw_cache = _read_cache()
    localized = {}
    for item in titles:
        key = "{}:{}".format(item.get("type"), item.get("id"))
        entry = raw_cache.get(key)
        if isinstance(entry, dict):
            localized[key] = {"title": entry.get("localized_title"), "plot": entry.get("description")}
    return {"items": compact_catalog(titles, localized), "more": bool(more), "page": page, "error": ""}
