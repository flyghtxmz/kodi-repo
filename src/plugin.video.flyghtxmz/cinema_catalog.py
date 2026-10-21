"""Cinema navigation and catalog loading, independent from the modal UI."""
from datetime import date
import json
import discovery
import recent

NAVIGATION = (("Início", "home"), ("Minha lista", "favorites"),
              ("Continuar", "continue"), ("Para você", "recommendations"),
              ("Plataformas", "platforms"), ("Filmes", "movies"),
              ("Séries", "series"), ("Em alta", "trending"),
              ("Buscar", "search"), ("Menu nativo", "classic"), ("Sair", "exit"))


def shelf(label, media, kind="trending", value="Week", category="", year=""):
    return {"label": label, "media": media, "kind": kind, "value": value,
            "category": category, "year": year}


def screen(route="home", value=""):
    """Two independent shelves and visible shortcuts; no network or Kodi calls."""
    platforms = [(name, "platform", code) for name, code, _ in discovery.PLATFORMS]
    tabs = platforms
    note = "Escolha uma plataforma ou explore as fileiras abaixo."
    title = "Seu próximo favorito"
    nav = "home"
    rows = [shelf("Filmes em alta nesta semana", "movie"),
            shelf("Séries em alta nesta semana", "series")]
    if route == "home":
        try:
            from user_library import list_items
            extras = []
            if list_items("continue"):
                extras.append(shelf("▶ Continuar assistindo", "mixed", "library", "continue"))
            if list_items("favorites"):
                extras.append(shelf("★ Minha lista", "mixed", "library", "favorites"))
            rows = extras + rows + [shelf("Lançamentos do ano", "movie", "category",
                                              category="movies_new")]
        except (ImportError, OSError, ValueError, RuntimeError):
            pass
        note = "Use ↓ na última fileira para ver mais • OK para abrir • Minha lista para favoritos"
    elif route in ("favorites", "continue"):
        nav = route
        title = "Minha lista" if route == "favorites" else "Continuar assistindo"
        note = "Salvo somente neste dispositivo • sem conta externa"
        tabs = []
        rows = [shelf(title, "mixed", "library", route)]
    elif route == "recommendations":
        nav, title = "recommendations", "Para você"
        note = "Sugestões baseadas nos gêneros de seus favoritos; sem enviar histórico"
        tabs = []
        chosen = []
        try:
            from user_library import preferred_genres
            selected = preferred_genres()
            for media, genre in selected:
                candidates = [(key, name) for key, name in recent.GENRE_CATEGORIES
                              if key.startswith("movies_" if media == "movie" else "series_")
                              and recent.GENRE_CODES.get(key.split("genre_", 1)[-1], "").casefold() == genre]
                if candidates:
                    key, name = candidates[0]
                    chosen.append(shelf("Você gosta de " + name, media, "category", category=key))
                if len(chosen) >= 3:
                    break
        except (ImportError, OSError, ValueError):
            pass
        rows = chosen or [shelf("Filmes bem avaliados", "movie", "category", category="movies_best_rated"),
                          shelf("Séries bem avaliadas", "series", "category", category="series_best_rated")]
    elif route in ("platform", "platforms"):
        code = value if route == "platform" else discovery.PLATFORMS[0][1]
        found = next((p for p in discovery.PLATFORMS if p[1] == code), None)
        if found is None:
            raise ValueError("Plataforma inválida.")
        title, code, region = found
        nav = "platforms"
        try:
            from tmdb_br import has_key
            brazil = has_key()
        except (ImportError, OSError, RuntimeError, AttributeError):
            brazil = False
        note = ("TMDb Brasil • streaming por assinatura • disponibilidade pode mudar"
                if brazil else "Referência: {} • configure chave TMDb para filtrar disponibilidade no Brasil".format(region))
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
        try:
            query = json.loads(value) if value.startswith("{") else {"q": value}
            if not isinstance(query, dict):
                raise ValueError("Busca inválida")
        except (ValueError, TypeError):
            query = {"q": value}
        term = str(query.get("q") or "")[:80]
        media_filter = query.get("media") or "all"
        year = str(query.get("year") or "")
        nav, title, tabs = "search", "Busca: " + term[:60], []
        note = "Busca avançada • filtro: {} • ano: {}".format(
            {"movie":"filmes", "series":"séries"}.get(media_filter, "todos"),
            year or "todos")
        rows = []
        if media_filter in ("all", "movie"):
            rows.append(shelf("Filmes encontrados", "movie", "search", term, "search_movie", year))
        if media_filter in ("all", "series"):
            rows.append(shelf("Séries encontradas", "series", "search", term, "search_series", year))
    elif route != "home":
        raise ValueError("Tela inválida.")
    return {"title": title, "note": note, "nav": nav, "tabs": tabs, "shelves": rows}


def compact_catalog(movies, localized):
    result = []
    for movie in movies[:20]:
        if not isinstance(movie, dict):
            continue
        identifier, media = movie.get("id"), movie.get("type")
        if not isinstance(identifier, str) or not (
                recent.IMDB_ID.fullmatch(identifier) or
                (movie.get("trusted_tmdb") and identifier.startswith("tmdb:") and identifier[5:].isdigit())
                ) or media not in ("movie", "series"):
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
    if spec["kind"] == "library":
        from user_library import list_items
        items = list_items(spec["value"])
        result = []
        for row in items[(page-1)*20:page*20]:
            percent = round(100 * (row.get("position") or 0) / (row.get("duration") or 1)) if row.get("duration") else 0
            episode = (" • T{:02d}E{:02d}".format(row["season"], row["episode"])
                       if type(row.get("season")) is int and type(row.get("episode")) is int else "")
            result.append({"id": row["id"], "media": row["media"],
                "title": row.get("title") or "Sem título", "poster": row.get("poster") or "",
                "plot": ("Assistido: {}%".format(percent) + episode if spec["value"] == "continue"
                         else "Na sua lista • abra para ver as opções")})
        return {"items": result, "more": page * 20 < len(items), "page": page, "error": ""}
    if spec["kind"] == "platform":
        try:
            from tmdb_br import has_key, platform_titles
            use_br = has_key()
        except (ImportError, OSError, RuntimeError, AttributeError):
            use_br = False
        if use_br:
            titles, more = platform_titles(spec["media"], spec["value"], page)
            for item in titles:
                item["trusted_tmdb"] = True
            return {"items": compact_catalog(titles, {}), "more": bool(more),
                    "page": page, "error": ""}
    if spec["kind"] in ("platform", "trending"):
        titles, more = discovery.list_titles(spec["media"], spec["kind"], spec["value"], page)
    else:
        titles, more = recent.list_titles(spec["category"], page=page,
                                         search_term=spec["value"] if spec["kind"] == "search" else "")
    if spec.get("year"):
        titles = [item for item in titles if str(item.get("year") or "").startswith(spec["year"])]
    from metadata_ptbr import _read_cache, descriptions_for_catalog
    raw_cache = _read_cache()
    localized = {}
    try:
        localized = descriptions_for_catalog(titles, include_titles=True)
    except (OSError, ValueError, RuntimeError, TypeError):
        pass
    for item in titles:
        key = "{}:{}".format(item.get("type"), item.get("id"))
        entry = raw_cache.get(key)
        if isinstance(entry, dict) and key not in localized:
            localized[key] = {"title": entry.get("localized_title"), "plot": entry.get("description")}
    return {"items": compact_catalog(titles, localized), "more": bool(more), "page": page, "error": ""}
