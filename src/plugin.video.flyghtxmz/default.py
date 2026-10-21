"""Felipe Vídeos: Kodi 21 Omega (Python 3) com integração opcional Elementum.

O addon não baixa torrents diretamente: entrega magnet/.torrent ao Elementum
instalado no mesmo Kodi. O buffer e o armazenamento pertencem ao Elementum.
"""

import json
import re
import sys
import time
import unicodedata
from datetime import date
from urllib.parse import parse_qs, urlencode, urlsplit

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin


ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
ELEMENTUM_ID = "plugin.video.elementum"
ELEMENTUM_PLAY_URL = "plugin://plugin.video.elementum/play"
ELEMENTUM_HELP = "https://elementumorg.github.io/getting-started/installation/"


def plugin_url(action, **params):
    args = {"action": action}
    args.update({key: value for key, value in params.items() if value is not None})
    return "{}?{}".format(BASE_URL, urlencode(args))


def add_item(label, action, playable=False, folder=False, artwork=None, info=None, **params):
    item = xbmcgui.ListItem(label=label)
    if playable:
        item.setProperty("IsPlayable", "true")
    if artwork:
        item.setArt(artwork)
    if info:
        item.setInfo("video", info)
        # O painel de informações do Kodi Omega usa o VideoInfoTag.
        # Enviar plot e plotoutline evita depender da interpretação do skin.
        try:
            tag = item.getVideoInfoTag()
            plot = info.get("plot") or ""
            if plot:
                tag.setPlot(plot)
                tag.setPlotOutline(info.get("plotoutline") or plot)
            if info.get("title"):
                tag.setTitle(info["title"])
            if info.get("mediatype"):
                tag.setMediaType(info["mediatype"])
            if info.get("year"):
                tag.setYear(int(info["year"]))
            if info.get("imdbnumber"):
                tag.setIMDBNumber(info["imdbnumber"])
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass
    xbmcplugin.addDirectoryItem(
        handle=HANDLE, url=plugin_url(action, **params), listitem=item, isFolder=folder
    )


def finish():
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def checkpoint(stage, identifier="", media=""):
    """Persist last UI stage so a native crash leaves a useful breadcrumb."""
    xbmc.log("Felipe Vídeos: etapa={} id={} tipo={}".format(stage, identifier, media), xbmc.LOGINFO)
    try:
        import local_cache
        local_cache.put("last_navigation", "stage", {
            "stage": stage, "id": identifier, "media": media,
            "at": time.strftime("%Y-%m-%d %H:%M:%S")}, ttl=604800, max_entries=1)
    except (ImportError, AttributeError, OSError, RuntimeError, ValueError, TypeError):
        pass


def show_navigation_diagnostic():
    finish()
    import local_cache
    entry = local_cache.get("last_navigation", "stage") or {}
    xbmcgui.Dialog().textviewer("Última operação do addon", "Etapa: {}\nTítulo IMDb: {}\nTipo: {}\nHorário local: {}\n\n"
        "Este registro mostra até onde o addon chegou; não confirma a causa do fechamento. "
        "Se o Kodi fechou, preserve também kodi.old.log antes de reiniciar novamente."
        .format(entry.get("stage", "Sem registro"), entry.get("id", ""),
                entry.get("media", ""), entry.get("at", "")))


def show_menu(force_cinema=False):
    # Janela fullscreen própria. A skin global permanece intacta; o menu
    # tradicional é usado no caso de falha ou por escolha explícita.
    # Permite desativar a interface cinema sem desinstalar o addon
    # caso a build Kodi/Android tenha incompatibilidade gráfica nativa.
    # Cinema é o padrão; a configuração v3 supera a opção experimental antiga.
    cinema_setting = ADDON.getSetting("cinema_default_v3").strip().lower()
    if (force_cinema or cinema_setting != "false") and getattr(xbmcgui, "WindowXMLDialog", None):
        try:
            from cinema_gui import launch
            if launch(lambda identifier, media: show_recent_detail(
                    identifier, media, finish_directory=False)):
                finish()
                return
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as error:
            xbmc.log("Felipe Vídeos Cinema: fallback para menu clássico ({})".format(
                type(error).__name__), xbmc.LOGERROR)
    show_classic_menu()


def show_classic_menu():
    xbmcplugin.setContent(HANDLE, "videos")
    add_item("Buscar filmes e séries", "recent_search")
    add_item("Em alta hoje e nesta semana", "trending", folder=True)
    add_item("Por plataforma — Netflix, Prime Video, Apple TV+…", "platforms", folder=True)
    add_item("Filmes", "sections", folder=True, media="movie")
    add_item("Séries", "sections", folder=True, media="series")
    add_item("Ferramentas", "tools", folder=True)
    add_item("Sobre o Felipe Vídeos", "about")
    finish()


def show_trending():
    xbmcplugin.setContent(HANDLE, "videos")
    for media, label in (("movie", "Filmes"), ("series", "Séries")):
        for period, suffix in (("Day", "hoje"), ("Week", "nesta semana")):
            add_item(label + " em alta " + suffix, "recent", folder=True,
                     category="series_popular" if media == "series" else "movies_popular",
                     filter_kind="trending", filter_value=period)
    finish()


def show_platforms(media="", provider=""):
    from discovery import PLATFORMS
    xbmcplugin.setContent(HANDLE, "videos")
    if provider:
        platform = next((row for row in PLATFORMS if row[1] == provider), None)
        if platform is None:
            finish()
            return
        for kind, label in (("movie", "Filmes populares"), ("series", "Séries populares")):
            add_item(label + " — " + platform[0], "recent", folder=True,
                     category="series_popular" if kind == "series" else "movies_popular",
                     filter_kind="platform", filter_value=provider,
                     info={"plot": "Popularidade TMDb; referência regional: " + platform[2] +
                           ". Não é o ranking oficial. Consulte Onde assistir no Brasil na ficha."})
    else:
        for label, code, region in PLATFORMS:
            info = {"plot": "Filmes e séries populares. Catálogo de referência: " + region +
                    ". Disponibilidade no Brasil pode variar."}
            if media in ("movie", "series"):
                add_item(label, "recent", folder=True, info=info,
                         category="series_popular" if media == "series" else "movies_popular",
                         filter_kind="platform", filter_value=code)
            else:
                add_item(label, "platforms", folder=True, provider=code, info=info)
    finish()


def show_sections(media):
    from recent import CATEGORIES
    year = date.today().year
    prefix = "series_" if media == "series" else "movies_"
    xbmcplugin.setContent(HANDLE, "videos")
    add_item("Por plataforma", "platforms", folder=True, media=media)
    for category, title in CATEGORIES:
        if category.startswith(prefix):
            add_item(title.format(year=year, prev_year=year-1, prev2_year=year-2), "recent",
                     folder=True, category=category)
    if media == "movie":
        add_item("Clássicos e nostalgia (por década)", "movie_decades", folder=True)
        add_item("Cinema brasileiro", "recent", folder=True,
                 category="movies_popular", filter_kind="country", filter_value="Brazil")
        add_item("Filmes em português", "recent", folder=True,
                 category="movies_popular", filter_kind="language", filter_value="Portuguese")
        add_item("Animes e longas de animação japonesa", "recent", folder=True,
                 category="movies_popular", filter_kind="anime", filter_value="")
    add_item("Gêneros", "genres", folder=True, media=media)
    add_item("Explorar catálogo", "explore", folder=True, media=media)
    finish()


def show_movie_decades():
    """Décadas navegáveis, sem importar listas estáticas de filmes."""
    xbmcplugin.setContent(HANDLE, "videos")
    for decade in range(2010, 1910, -10):
        add_item("Filmes dos anos {}".format(decade),
                 "movie_decade_year", decade=decade)
    finish()


def choose_movie_decade_year(decade):
    """Seleciona ano em popup; abre o catálogo real do Cinemeta."""
    finish()
    if type(decade) is not int or decade < 1920 or decade > 2010 or decade % 10:
        xbmcgui.Dialog().ok("Década inválida", "Selecione uma década do menu de clássicos.")
        return
    years = [year for year in range(decade, min(decade+10, date.today().year+1))]
    if not years:
        return
    selection = xbmcgui.Dialog().select(
        "Filmes dos anos {} — escolha o ano".format(decade),
        [str(year) for year in years])
    if selection is None or selection < 0 or selection >= len(years):
        return
    xbmc.executebuiltin("Container.Update({})".format(plugin_url(
        "recent", category="movies_popular", filter_kind="year",
        filter_value=str(years[selection]), page=1)))


def show_genres(media):
    from recent import GENRE_CATEGORIES
    prefix = "series_" if media == "series" else "movies_"
    xbmcplugin.setContent(HANDLE, "videos")
    for category, label in GENRE_CATEGORIES:
        if category.startswith(prefix):
            add_item(label, "recent", folder=True, category=category)
    finish()


def show_tools():
    xbmcplugin.setContent(HANDLE, "files")
    add_item("Adicionar magnet ou arquivo .torrent", "torrent_input")
    add_item("Configurações do Elementum", "elementum_settings")
    add_item("Testar Elementum (abrir addon)", "elementum_test")
    add_item("Diagnosticar última reprodução", "playback_check")
    add_item("Como instalar o Elementum", "elementum_help")
    add_item("Diagnóstico de conexão", "diagnostic")
    add_item("Diagnosticar fechamento — última operação", "navigation_diagnostic")
    add_item("Legendas PT-BR do título selecionado", "subtitles")
    add_item("Configurações avançadas", "settings")
    add_item("Experimentar interface Cinema", "cinema")
    finish()


def show_recent(category, page=1, term="", filter_kind="", filter_value=""):
    from recent import list_titles
    xbmcplugin.setContent(HANDLE, "tvshows" if category.startswith("series_") or category == "search_series" else "movies")
    try:
        if filter_kind:
            from discovery import list_titles as discover
            media = "series" if category.startswith("series_") else "movie"
            results, more = discover(media, filter_kind, filter_value, page=page)
        else:
            results, more = list_titles(category, page=page, search_term=term)
        # Mostra nomes e sinopses localizados no painel da capa,
        # preservando o IMDb ID para a busca de torrents.
        from metadata_ptbr import descriptions_for_catalog, FALLBACK_SYNOPSIS
        try:
            if filter_kind and filter_kind != "year":
                localized = {"{}:{}".format(item["type"], item["id"]):
                             {"title": item["title"], "plot": item.get("plot") or FALLBACK_SYNOPSIS}
                             for item in results}
            else:
                localized = descriptions_for_catalog(results, include_titles=True)
        except (OSError, ValueError, TypeError):
            localized = {}
        rendered = []
        for movie in results:
            key = "{}:{}".format(movie["type"], movie["id"])
            found = localized.get(key) or {}
            if isinstance(found, str):
                found = {"plot": found}
            label = (found.get("title") or movie["title"]).strip()
            plot = found.get("plot") or FALLBACK_SYNOPSIS
            rendered.append((label, plot, movie))
        def az(row):
            value = unicodedata.normalize("NFKD", row[0].casefold())
            return ("".join(c for c in value if not unicodedata.combining(c)),
                    row[2]["id"])
        if filter_kind not in ("platform", "trending"):
            rendered.sort(key=az)
        for label, plot, movie in rendered:
            info = {"title": label, "plot": plot, "plotoutline": plot,
                    "mediatype": "tvshow" if movie["type"] == "series" else "movie",
                    "imdbnumber": movie["id"]}
            match = re.match(r"^(\d{4})", movie.get("year") or "")
            if match:
                info["year"] = int(match.group(1))
            art = {"thumb": movie["poster"], "poster": movie["poster"],
                   "icon": movie["poster"]}
            add_item(label, "recent_detail", folder=False, artwork=art,
                     info=info, identifier=movie["id"], media=movie["type"])
        if more:
            add_item("Próxima página >>", "recent", folder=True, category=category,
                     page=page+1, term=term, filter_kind=filter_kind, filter_value=filter_value)
        if not results:
            xbmcgui.Dialog().ok("Nenhum título", "Não há títulos nesta seção no momento.")
    except Exception as exc:
        xbmcgui.Dialog().ok("Catálogo de lançamentos", "Erro ao consultar títulos: " + str(exc)[:170])
    finish()


def show_explore(media):
    xbmcplugin.setContent(HANDLE, "videos")
    for label, kind in (("Escolher ano", "year"), ("Idioma original", "language"),
                        ("País e idioma original", "country"), ("Animes", "anime")):
        add_item(label, "choose_filter", media=media, kind=kind)
    if media == "movie":
        add_item("Clássicos por década", "choose_filter", media=media, kind="classic")
    finish()


def choose_filter(media, kind):
    from discovery import LANGUAGES, COUNTRIES
    finish()
    if media not in ("movie", "series"):
        return
    value = ""
    if kind == "year":
        value = xbmcgui.Dialog().input("Ano (ex.: 1999)", type=xbmcgui.INPUT_NUMERIC)
        if not value:
            return
        if not re.fullmatch(r"[12][0-9]{3}", value) or not 1874 <= int(value) <= date.today().year + 1:
            xbmcgui.Dialog().ok("Ano inválido", "Informe um ano entre 1874 e {}.".format(date.today().year + 1))
            return
    elif kind in ("language", "country"):
        choices = LANGUAGES if kind == "language" else COUNTRIES
        index = xbmcgui.Dialog().select("Idioma original" if kind == "language" else "País e idioma original", [row[0] for row in choices])
        if index is None or not 0 <= index < len(choices):
            return
        value = choices[index][1]
    elif kind == "classic":
        decades = list(range(1990, 1880, -10))
        index = xbmcgui.Dialog().select("Década", ["{}–{}".format(n, n+9) for n in decades])
        if index is None or not 0 <= index < len(decades):
            return
        years = list(range(decades[index]+9, decades[index]-1, -1))
        chosen = xbmcgui.Dialog().select("Ano", [str(n) for n in years])
        if chosen is None or not 0 <= chosen < len(years):
            return
        kind, value = "year", str(years[chosen])
    elif kind != "anime":
        return
    xbmc.executebuiltin("Container.Update({})".format(plugin_url(
        "recent", category="series_popular" if media == "series" else "movies_popular",
        filter_kind=kind, filter_value=value, page=1)))


def show_subtitles():
    finish()
    try:
        import local_cache
        import subtitles_client
        player = xbmc.Player()
        if not player.isPlayingVideo():
            xbmcgui.Dialog().ok("Legendas", "Inicie o vídeo e volte a esta opção para escolher a legenda.")
            return
        playing = player.getPlayingFile()
        context = local_cache.get("playback_context", "selected")
        if not isinstance(context, dict):
            xbmcgui.Dialog().ok("Legendas", "Selecione primeiro um título no Felipe Vídeos.")
            return
        entries = subtitles_client.list_subtitles(context)
        if not entries:
            xbmcgui.Dialog().ok("Legendas", "Nenhuma legenda em português encontrada para este título.")
            return
        index = xbmcgui.Dialog().select("Legendas — " + context.get("title", ""), [row["label"] for row in entries])
        if index is None or not 0 <= index < len(entries):
            return
        path = subtitles_client.download(entries[index])
        if player.isPlayingVideo() and player.getPlayingFile() == playing:
            player.setSubtitles(path)
            player.showSubtitles(True)
    except (OSError, ValueError, TypeError, RuntimeError):
        xbmcgui.Dialog().ok("Legendas indisponíveis", "Não foi possível carregar a legenda. Tente novamente mais tarde.")


def show_recent_detail(identifier, media, finish_directory=True):
    """Abre popup sem sair do cinema fullscreen ou criar uma pasta."""
    if isinstance(identifier, str) and identifier.startswith("tmdb:"):
        try:
            from tmdb_br import resolve_imdb
            identifier = resolve_imdb(identifier, media)
        except (ImportError, ValueError, OSError, RuntimeError):
            xbmcgui.Dialog().ok("Ficha indisponível", "Não foi possível identificar este título no IMDb.")
            return False
    from recent import detail
    if finish_directory:
        finish()
    try:
        started = time.monotonic()
        checkpoint("consultando_ficha", identifier, media)
        movie = detail(identifier, media=media)
        xbmc.log("Felipe Vídeos: diagnóstico ficha de título: {:.2f}s".format(
            time.monotonic() - started), xbmc.LOGINFO)
        # Para séries, o primeiro popup lista as temporadas oficiais
        # (sem pasta intermediária). Filmes continuam com Buscar fontes.
        episodes = movie.get("episodes") or {} if media == "series" else {}
        options = []
        if media == "series":
            for season, entries in sorted(episodes.items()):
                title = "Especiais (S00)" if season == 0 else "Temporada {}".format(season)
                options.append(("{} — {} episódio(s)".format(title, len(entries)), ("season", season)))
        else:
            options.append(("Buscar fontes", "sources"))
        import user_library
        saved = user_library.is_favorite(identifier, media)
        options.append(("★ Remover dos favoritos" if saved else "☆ Adicionar aos favoritos", "favorite"))
        if movie.get("trailer_id"):
            options.append(("Ver trailer", "recent_trailer"))
        options.append(("Onde assistir no Brasil", "recent_where"))
        options.append(("Sinopse e detalhes", "recent_info"))
        rating = movie.get("rating") or "Indisponível"
        rating_label = rating + "/10" if rating != "Indisponível" else rating
        heading = "{} ({}) | IMDb: {}".format(
            movie["title"], movie.get("year") or "s/ ano", rating_label)
        if not options:
            xbmcgui.Dialog().ok("Episódios indisponíveis",
                                "Não há temporadas ou episódios cadastrados para esta série.")
            return
        checkpoint("abrindo_opcoes", identifier, media)
        index = xbmcgui.Dialog().select(heading, [label for label, _ in options])
        if index is None or index < 0 or index >= len(options):
            checkpoint("ficha_cancelada", identifier, media)
            return
        action = options[index][1]
        checkpoint("opcao_selecionada", identifier, media)
        if isinstance(action, tuple) and action[0] == "season":
            return choose_series_episode(movie, action[1])
        elif action == "favorite":
            added = user_library.toggle_favorite(identifier, media, movie.get("title", ""),
                movie.get("poster", ""), movie.get("year", ""), movie.get("genres", []))
            xbmcgui.Dialog().notification("Felipe Vídeos",
                "Adicionado à Minha lista" if added else "Removido de Minha lista", time=2500)
            return False
        elif action == "sources":
            # O ID TMDb não é um identificador IMDb: evite enviá-lo ao Worker.
            return choose_cloudflare_source(movie.get("original_title") or movie["title"],
                                     str(movie.get("year") or "")[:4],
                                     movie.get("imdb_id") or (
                                         identifier if re.fullmatch(r"tt[0-9]{5,12}", identifier) else ""),
                                     display_title=movie.get("title"), poster=movie.get("poster"))
        else:
            result = perform_recent_action(action, movie)
            if result:
                return True
        checkpoint("ficha_concluida", identifier, media)
    except Exception as exc:
        checkpoint("erro_python_" + type(exc).__name__, identifier, media)
        xbmc.log("Felipe Vídeos: popup do título falhou ({})".format(
            type(exc).__name__), xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Detalhes indisponíveis", "Não foi possível abrir as opções deste título.")


def choose_series_episode(movie, season):
    """Popup de episódios numerados conforme Cinemeta: S01E01, S01E02, etc."""
    episodes = (movie.get("episodes") or {}).get(season) or []
    if not episodes:
        xbmcgui.Dialog().ok("Episódios indisponíveis",
                            "Não há episódios cadastrados para esta temporada.")
        return
    options = [
        "S{:02d}E{:02d} — {}".format(season, item["episode"], item["title"])
        for item in episodes
    ]
    series_name = movie.get("title") or "Série"
    label = "Especiais" if season == 0 else "Temporada {}".format(season)
    choice = xbmcgui.Dialog().select("{} — {}".format(series_name, label), options)
    if choice is None or choice < 0 or choice >= len(episodes):
        return
    selected = episodes[choice]
    imdb = movie.get("imdb_id") or movie.get("id") or ""
    if not re.fullmatch(r"tt[0-9]{5,12}", imdb):
        xbmcgui.Dialog().ok("Identificador inválido",
                            "IMDb ID da série indisponível para buscar este episódio.")
        return
    return choose_cloudflare_source(
        movie.get("original_title") or series_name,
        str(movie.get("year") or "")[:4],
        imdb, season=season, episode=selected["episode"],
        display_title=series_name, poster=movie.get("poster", ""))


def choose_cloudflare_source(title, year="", imdb="", season=None, episode=None, extended=False,
                            display_title=None, poster="", sources_override=None, filter_mode="all"):
    """Exibe popup de fontes e entrega a escolhida ao Elementum."""
    from source_client import list_sources
    started = time.monotonic()
    try:
        if sources_override is not None:
            all_sources = sources_override
        elif season is not None:
            all_sources = list_sources(title, year=year, imdb=imdb,
                                   season=season, episode=episode, quick=not extended)
        else:
            all_sources = list_sources(title, year=year, imdb=imdb, quick=not extended)
        sources = list(all_sources)
        if filter_mode == "ptbr":
            sources = [s for s in sources if s.get("language") in ("pt-br", "ptbr")]
        elif filter_mode == "1080p":
            sources = [s for s in sources if s.get("quality") == "1080p"]
        elif filter_mode == "4K":
            sources = [s for s in sources if s.get("quality") == "4K"]
        elif filter_mode == "seeders":
            sources = [s for s in sources if (s.get("seeders") or 0) > 0]
        elif filter_mode == "small":
            sources = [s for s in sources if isinstance(s.get("size"), int)
                       and 0 < s["size"] <= 3221225472]
            sources.sort(key=lambda s: s["size"])
        xbmc.log("Felipe Vídeos: diagnóstico busca de fontes: {:.2f}s, {} resultados, modo={}".format(
            time.monotonic() - started, len(sources),
            "completo" if extended else "rápido"), xbmc.LOGINFO)
        if not sources:
            xbmcgui.Dialog().ok(
                "Nenhuma fonte disponível",
                ("Nenhuma fonte encontrada para este episódio." if season is not None else
                 "Nenhuma fonte compatível encontrada para este título."))
            return
        labels = []
        for source in sources:
            size_text = "{:.1f} GB".format(source["size"] / 1073741824) if source["size"] else "n/d"
            seed_text = str(source["seeders"]) if source["seeders"] is not None else "n/d"
            language = source["language"] if source["language"] != "unknown" else "n/d"
            if language in ("pt-br", "ptbr"):
                audio = "🔊 PT-BR indicado"
            elif language == "pt":
                audio = "🇵🇹 Português (região não confirmada)"
            else:
                audio = "❔ Áudio não confirmado"
            labels.append("{} | {} | {} | {} | Seeds: {} | {}".format(
                source["title"], source["source"], source["quality"],
                size_text, seed_text, audio))
        target = "{} S{:02d}E{:02d}".format(title, season, episode) if season is not None else title
        extra_actions = []
        if not extended and imdb:
            extra_actions.append(("🔎 Pesquisar mais fontes de todos os provedores", "extended"))
        extra_actions.append(("🎛 Filtrar fontes (áudio, resolução, seeders, tamanho)", "filters"))
        dubbed = [source for source in sources if str(source.get("language") or "").lower() in ("pt-br", "ptbr")]
        if dubbed:
            extra_actions.append(("🔊 Mostrar somente dublados/PT-BR indicados ({})".format(len(dubbed)), "dubbed"))
        options = labels + [row[0] for row in extra_actions]
        index = xbmcgui.Dialog().select(
            "Selecionar fonte — {} | PT-BR: {} de {}".format(target, len(dubbed), len(sources)), options)
        if index is None or index < 0:
            return
        if index >= len(sources):
            action = extra_actions[index - len(sources)][1]
            if action == "extended":
                return choose_cloudflare_source(
                    title, year=year, imdb=imdb, season=season, episode=episode, extended=True,
                    display_title=display_title, poster=poster)
            if action == "filters":
                names = ["Mostrar todas", "Somente PT-BR indicado", "1080p",
                         "4K", "Com seeders informados", "Até 3 GB"]
                modes = ["all", "ptbr", "1080p", "4K", "seeders", "small"]
                choice = xbmcgui.Dialog().select("Filtrar fontes — " + target, names)
                if choice is None or choice < 0 or choice >= len(modes):
                    return
                return choose_cloudflare_source(title, year=year, imdb=imdb,
                    season=season, episode=episode, extended=extended,
                    display_title=display_title, poster=poster,
                    sources_override=all_sources, filter_mode=modes[choice])
            if action == "dubbed":
                subset = [
                    next(i for i, source in enumerate(sources) if source is candidate)
                    for candidate in dubbed
                ]
                picked = xbmcgui.Dialog().select(
                    "Dublados/PT-BR indicados — {}".format(target),
                    [labels[i] for i in subset])
                if picked is None or picked < 0 or picked >= len(subset):
                    return
                index = subset[picked]
        selected = sources[index]
        # Se o provedor confirma ausência de seeders, oferecer escolha:
        # peers desconhecidos não são necessariamente zero.
        if selected.get("seeders") == 0:
            if not xbmcgui.Dialog().yesno(
                    "Fonte sem seeders",
                    "O provedor informou 0 seeders. A reprodução pode demorar "
                    "ou não iniciar. Deseja tentar mesmo assim?"):
                return
        try:
            from subtitles_client import save_context
            save_context(title, imdb, season=season, episode=episode)
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as error:
            # Legendas são opcionais; falhas de cache não podem impedir o player.
            xbmc.log("Felipe Vídeos: contexto de legendas indisponível ({})".format(
                type(error).__name__), xbmc.LOGWARNING)
        try:
            import local_cache
            local_cache.put("last_playback", "selected", {
                "at": int(time.time()),
                "source": str(selected.get("source") or "Provedor")[:70],
                "language": str(selected.get("language") or "unknown")[:18],
                "seeders": selected.get("seeders"),
                "file_index": selected.get("file_index"),
                "request": "preparando",
            }, ttl=172800, max_entries=1)
        except (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError):
            pass
        try:
            import local_cache
            local_cache.put("playback_request", "current", {
                "at": time.time(), "id": imdb, "media": "series" if season is not None else "movie",
                "title": display_title or title, "poster": poster, "year": year,
                "season": season, "episode": episode
            }, ttl=900, max_entries=1)
        except (ImportError, OSError, ValueError, AttributeError, TypeError):
            pass
        return start_cloudflare_play(selected["url"], file_index=selected.get("file_index"))
    except Exception as error:
        xbmc.log("Felipe Vídeos: consulta de fontes falhou ({})".format(
            type(error).__name__), xbmc.LOGERROR)
        xbmcgui.Dialog().ok(
            "Fontes indisponíveis",
            "Não foi possível consultar as fontes. Verifique a conexão da TV Box.")


def show_cloudflare_sources(title, year="", imdb=""):
    """Compatibilidade: links antigos também abrem o seletor em popup."""
    finish()
    choose_cloudflare_source(title, year=year, imdb=imdb)


def start_cloudflare_play(url, file_index=None):
    """Reproduz somente URI validada pelo cliente no Elementum."""
    from cloudflare_client import is_supported_source
    if not is_supported_source(url):
        xbmcgui.Dialog().ok("Fonte inválida", "O link não é um magnet ou torrent compatível.")
        return
    return launch_elementum(url, file_index=file_index)


def play_cloudflare_source(url):
    """Compatibilidade: links de versões anteriores continuam funcionando."""
    finish()
    start_cloudflare_play(url)


def search_recent():
    result = xbmcgui.Dialog().input("Nome do filme ou série", type=xbmcgui.INPUT_ALPHANUM)
    finish()
    if result and result.strip():
        choice = xbmcgui.Dialog().select("O que deseja pesquisar?", ["Filmes", "Séries"])
        if choice in (0, 1):
            category = "search_movie" if choice == 0 else "search_series"
            xbmc.executebuiltin("Container.Update({})".format(plugin_url(
                "recent", category=category, page=1, term=result.strip()[:80])))


def perform_recent_action(action, movie):
    """Executa ação do popup reutilizando os metadados já consultados."""
    from recent import justwatch_search_url
    if action == "recent_info":
        rating = movie.get("rating") or "Indisponível"
        rating_label = rating + "/10" if rating != "Indisponível" else rating
        desc = "{} ({})\n\nSinopse (PT-BR):\n{}\n\nNota IMDb: {}".format(
            movie["title"], movie["year"],
            movie["plot"] or "Sinopse em português (Brasil) indisponível.",
            rating_label)
        xbmcgui.Dialog().textviewer(movie["title"], desc)
    elif action == "recent_trailer":
        yt_id = movie.get("trailer_id")
        if not yt_id:
            xbmcgui.Dialog().ok("Trailer indisponível", "Não há trailer para este título.")
            return
        try:
            xbmcaddon.Addon(id="plugin.video.youtube")
        except Exception:
            xbmcgui.Dialog().ok("YouTube necessário",
                "Instale o addon YouTube pelo repositório oficial do Kodi.")
            return
        xbmc.executebuiltin("PlayMedia(plugin://plugin.video.youtube/play/?video_id={})".format(yt_id))
        return True
    elif action == "recent_where":
        url = justwatch_search_url(movie["title"])
        if xbmcgui.Dialog().yesno("Onde assistir — Brasil",
                "Abrir pesquisa no navegador Chrome da TV Box?\n\n"
                "Disponibilidade e preços são informados pelo serviço externo."):
            xbmc.executebuiltin(
                "StartAndroidActivity(com.android.chrome,android.intent.action.VIEW,,{})".format(url))


def show_recent_action(action, identifier, media):
    """Compatibilidade com URLs das versões anteriores do addon."""
    from recent import detail
    finish()
    try:
        perform_recent_action(action, detail(identifier, media=media))
    except Exception as exc:
        xbmcgui.Dialog().ok("Não foi possível abrir", str(exc)[:220])


def validate_torrent_uri(raw):
    """Retorna (uri, erro). Não aceita caminhos locais nem esquemas arbitrários."""
    uri = (raw or "").strip()
    if not uri:
        return None, ""
    if len(uri) > 8192 or any(ord(c) < 32 or ord(c) == 127 for c in uri):
        return None, "O link é muito longo ou contém caracteres inválidos."
    try:
        parsed = urlsplit(uri)
    except ValueError:
        return None, "Link malformado."
    if parsed.scheme.lower() == "magnet":
        if parsed.netloc or parsed.path or not parsed.query:
            return None, "Informe um magnet link válido."
        xt_values = parse_qs(parsed.query).get("xt", [])
        supported = any(
            re.fullmatch(r"urn:btih:(?:[a-fA-F0-9]{40}|[a-zA-Z2-7]{32})", xt or "", flags=re.I)
            for xt in xt_values
        )
        if not supported:
            return None, "O magnet precisa conter um infohash BitTorrent válido (xt=urn:btih)."
        return uri, None
    if parsed.scheme.lower() in ("http", "https"):
        if not parsed.netloc or parsed.username or parsed.password:
            return None, "A URL .torrent precisa ter um servidor válido."
        if not parsed.path.lower().endswith(".torrent"):
            return None, "Informe uma URL HTTPS/HTTP terminada em .torrent."
        return uri, None
    return None, "Aceito apenas magnet links ou URLs HTTP(S) de arquivos .torrent."


def _canonical_elementum_magnet(uri):
    """Libtorrent exige xt=urn:btih:HASH com dois-pontos literais.

    Torrentio cria xt=urn%3Abtih%3AHASH (válido em URL genérica, mas o
    Elementum pode rejeitar o infohash). O parâmetro EXTERNO uri continua
    escapado exatamente uma vez por build_elementum_url.
    """
    if not isinstance(uri, str) or not uri.lower().startswith("magnet:?"):
        return uri
    parsed = urlsplit(uri)
    if parsed.scheme.lower() != "magnet" or parsed.netloc or parsed.path:
        raise ValueError("Magnet inválido.")
    # Se já há xt literal válido, não altera magnet introduzido manualmente.
    if re.search(r"(?:^|&)xt=urn:btih:(?:[a-fA-F0-9]{40}|[a-zA-Z2-7]{32})(?:&|$)",
                 parsed.query, re.I):
        return uri
    from urllib.parse import parse_qsl, unquote
    parts = parse_qsl(parsed.query, keep_blank_values=True)
    xt_values = [unquote(value) for name, value in parts if name == "xt"]
    xt = next((value for value in xt_values if re.fullmatch(
        r"urn:btih:(?:[a-fA-F0-9]{40}|[a-zA-Z2-7]{32})", value, re.I)), None)
    if not xt:
        raise ValueError("Magnet sem infohash válido.")
    others = [(key, value) for key, value in parts
              if key in ("dn", "tr", "xl", "ws", "xs", "as")][:32]
    tail = urlencode(others)
    return "magnet:?xt=" + xt + ("&" + tail if tail else "")


def build_elementum_url(uri, file_index=None):
    """urlencode escapa &, vírgulas e parênteses para não confundir o Kodi."""
    params = {"uri": _canonical_elementum_magnet(uri)}
    if file_index is not None:
        if type(file_index) is not int or not 0 <= file_index <= 100_000:
            raise ValueError("Índice de arquivo inválido.")
        # Torrentio usa a ordem original do torrent; Elementum chama isso oindex.
        params["oindex"] = file_index
    return "{}?{}".format(ELEMENTUM_PLAY_URL, urlencode(params))


def launch_elementum(uri, file_index=None):
    """Solicita uma única reprodução e verifica o aceite do Kodi, não o buffer."""
    started = time.monotonic()
    if elementum_addon() is None:
        missing_elementum()
        return False
    try:
        target = build_elementum_url(uri, file_index=file_index)
        details = json.loads(xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "Addons.GetAddonDetails",
            "params": {"addonid": ELEMENTUM_ID, "properties": ["enabled"]}})))
        if isinstance(details, dict):
            result = details.get("result")
            addon = result.get("addon") if isinstance(result, dict) else None
            addon = addon if isinstance(addon, dict) else {}
            if addon.get("enabled") is False:
                xbmcgui.Dialog().ok("Elementum desativado",
                                    "Ative o Elementum em Meus addons → Addons de vídeo e tente novamente.")
                return False
        # Player.Open envia a URL estruturada, sem o parser de texto de PlayMedia,
        # e informa se o Kodi recusou o pedido. O Elementum resolve o torrent.
        response = json.loads(xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0", "id": 2, "method": "Player.Open",
            "params": {"item": {"file": target}}})))
        if not isinstance(response, dict) or response.get("result") != "OK":
            error = response.get("error") if isinstance(response, dict) else None
            code = error.get("code") if isinstance(error, dict) else None
            code = str(code) if type(code) is int else "resposta inválida"
            xbmc.log("Felipe Vídeos: Elementum Player.Open recusado ({})".format(code), xbmc.LOGERROR)
            xbmcgui.Dialog().ok("Falha ao abrir Elementum",
                                "O Kodi não aceitou a reprodução ({}). Abra Ferramentas → Testar Elementum."
                                .format(code))
            return False
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        xbmc.log("Felipe Vídeos: falha na solicitação Player.Open do Elementum", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Falha ao abrir Elementum",
                            "Não foi possível enviar o torrent ao Kodi. Abra Ferramentas → Testar Elementum.")
        return False
    # Aceite da chamada JSON-RPC NÃO confirma nem a execução do plugin nem o
    # início do streaming. Não envie novamente automaticamente.
    elapsed = time.monotonic() - started
    xbmc.log("Felipe Vídeos: Kodi aceitou Player.Open (oindex={}, {:.2f}s); vídeo NÃO verificado".format(
        file_index, elapsed), xbmc.LOGINFO)
    try:
        import local_cache
        event = local_cache.get("last_playback", "selected")
        if not isinstance(event, dict):
            event = {}
        event.update(request="aceito_pelo_kodi", handoff_seconds=round(elapsed, 2))
        local_cache.put("last_playback", "selected", event, ttl=172800, max_entries=1)
    except (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError):
        pass
    try:
        xbmcgui.Dialog().notification(
            "Felipe Vídeos",
            "Pedido recebido pelo Kodi; reprodução não confirmada. "
            "Se não iniciar, abra Ferramentas > Diagnosticar última reprodução.",
            time=5000)
    except (AttributeError, RuntimeError):
        pass
    return True


def elementum_addon():
    try:
        return xbmcaddon.Addon(id=ELEMENTUM_ID)
    except Exception:
        return None


def missing_elementum():
    xbmcgui.Dialog().ok(
        "Elementum necessário",
        "Instale e habilite o Elementum na sua TV Box. "
        "Ele é o motor responsável por receber torrents e preparar o buffer. "
        "Consulte Ferramentas > Como instalar o Elementum.",
    )


def open_magnet_dialog():
    value = xbmcgui.Dialog().input("Cole um magnet ou endereço .torrent", type=xbmcgui.INPUT_ALPHANUM)
    uri, error = validate_torrent_uri(value)
    finish()
    if not uri:
        if error:
            xbmcgui.Dialog().ok("Link inválido", error)
        return
    launch_elementum(uri)


def test_elementum_start():
    """Abre o Elementum para distinguir erro do motor de fonte sem peers."""
    finish()
    installed = elementum_addon()
    if installed is None:
        missing_elementum()
        return
    try:
        version = installed.getAddonInfo("version") or "desconhecida"
    except (AttributeError, RuntimeError, TypeError, ValueError):
        version = "desconhecida"
    xbmcgui.Dialog().ok(
        "Teste de inicialização do Elementum",
        "Elementum instalado (versão {}). O Kodi abrirá o menu do addon. "
        "Se ele não abrir ou travar, o problema é anterior às fontes "
        "do Felipe Vídeos. Caso abra normalmente, teste uma fonte com "
        "seeders positivos e verifique o buffer.".format(version))
    xbmc.executebuiltin(
        "ActivateWindow(Videos,plugin://plugin.video.elementum/,return)")


def check_last_playback():
    """Exibe estado atual e logs, sem consultar torrents ou repetir reprodução."""
    finish()
    try:
        import local_cache
        event = local_cache.get("last_playback", "selected")
        if not isinstance(event, dict):
            event = {}
    except (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError):
        event = {}
    try:
        playing = bool(xbmc.Player().isPlayingVideo())
    except (AttributeError, RuntimeError):
        playing = False
    try:
        from diagnostic import recent_errors
        recent = recent_errors()[-8:]
    except (ImportError, OSError, RuntimeError, TypeError):
        recent = []
    source = str(event.get("source") or "Não registrado")[:70]
    seeders = event.get("seeders")
    seeders = str(seeders) if type(seeders) is int else "Não informados"
    language = str(event.get("language") or "não identificado")
    checked = ("SIM — vídeo ativo" if playing else "NÃO — o Kodi não informa vídeo ativo")
    report = [
        "Reprodução ativa agora: " + checked,
        "Fonte: " + source, "Áudio indicado: " + language,
        "Seeders declarados: " + seeders,
        "Índice do arquivo: " + str(event.get("file_index")),
        "Último envio: " + str(event.get("request") or "não registrado"),
        "Tempo do envio ao Kodi: " + str(event.get("handoff_seconds") or "n/d") + " s",
        "", "Player.Open OK não significa torrent carregado.",
        "Se Elementum também não abre em Ferramentas > Testar Elementum,",
        "investigue a instalação/serviço do Elementum.",
        "Se abre, mas o vídeo não inicia, confira peers, disco e buffer.",
    ]
    if recent:
        report.extend(["", "Últimos registros locais do Kodi (URLs ocultas):"] + recent)
    xbmcgui.Dialog().textviewer("Felipe Vídeos — diagnóstico de reprodução", "\n".join(report))


def open_elementum_settings():
    finish()
    installed = elementum_addon()
    if installed is None:
        missing_elementum()
        return
    installed.openSettings()


def show_help():
    finish()
    xbmcgui.Dialog().ok(
        "Instalar Elementum",
        "No Kodi, instale o Elementum a partir do repositório oficial e "
        "abra o addon ao menos uma vez. Site oficial: " + ELEMENTUM_HELP + "\n\n"
        "Depois, volte a Ferramentas e escolha 'Adicionar magnet'.",
    )


def show_about():
    finish()
    xbmcgui.Dialog().ok(
        "Felipe Vídeos 1.5.7",
        "Integração opcional com Elementum para reproduzir torrents de origem "
        "autorizada sem aguardar o download completo. Peers podem ver seu IP "
        "e o motor pode compartilhar dados durante a reprodução. "
        "Buffer e limpeza de arquivos são gerenciados pelo Elementum.",
    )


def main():
    params = parse_qs(sys.argv[2].lstrip("?")) if len(sys.argv) > 2 else {}
    action = params.get("action", [""])[0]
    if action == "platforms":
        show_platforms(params.get("media", [""])[0], params.get("provider", [""])[0])
    elif action == "trending":
        show_trending()
    elif action == "cinema":
        show_menu(force_cinema=True)
    elif action == "sections":
        show_sections(params.get("media", ["movie"])[0])
    elif action == "movie_decades":
        show_movie_decades()
    elif action == "movie_decade_year":
        try:
            decade = int(params.get("decade", ["0"])[0])
        except ValueError:
            decade = 0
        choose_movie_decade_year(decade)
    elif action == "genres":
        show_genres(params.get("media", ["movie"])[0])
    elif action == "tools":
        show_tools()
    elif action == "explore":
        show_explore(params.get("media", ["movie"])[0])
    elif action == "choose_filter":
        choose_filter(params.get("media", ["movie"])[0], params.get("kind", ["year"])[0])
    elif action == "subtitles":
        show_subtitles()
    elif action == "recent":
        try:
            page = int(params.get("page", ["1"])[0])
        except ValueError:
            page = 1
        show_recent(params.get("category", ["movies_new"])[0],
                    page=page, term=params.get("term", [""])[0],
                    filter_kind=params.get("filter_kind", [""])[0], filter_value=params.get("filter_value", [""])[0])
    elif action == "recent_detail":
        show_recent_detail(params.get("identifier", [""])[0],
                           params.get("media", ["movie"])[0])
    elif action == "cloudflare_sources":
        show_cloudflare_sources(params.get("title", [""])[0],
                                params.get("year", [""])[0],
                                params.get("identifier", [""])[0])
    elif action == "cloudflare_play":
        play_cloudflare_source(params.get("url", [""])[0])
    elif action in ("recent_info", "recent_where", "recent_trailer"):
        show_recent_action(action, params.get("identifier", [""])[0],
                           params.get("media", ["movie"])[0])
    elif action == "recent_search":
        search_recent()
    elif action == "diagnostic":
        finish()
        from diagnostic import run_diagnostic
        xbmcgui.Dialog().textviewer("Diagnóstico Felipe Addons", run_diagnostic())
    elif action == "navigation_diagnostic":
        show_navigation_diagnostic()
    elif action == "torrent_input":
        open_magnet_dialog()
    elif action == "elementum_settings":
        open_elementum_settings()
    elif action == "elementum_test":
        test_elementum_start()
    elif action == "playback_check":
        check_last_playback()
    elif action == "elementum_help":
        show_help()
    elif action == "settings":
        ADDON.openSettings()
        finish()
    elif action == "about":
        show_about()
    else:
        show_menu()


if __name__ == "__main__":
    main()
