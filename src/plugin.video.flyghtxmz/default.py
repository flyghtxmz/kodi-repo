"""Felipe Vídeos: Kodi 21 Omega (Python 3) com integração opcional Elementum.

O addon não baixa torrents diretamente: entrega magnet/.torrent ao Elementum
instalado no mesmo Kodi. O buffer e o armazenamento pertencem ao Elementum.
"""

import re
import sys
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
    xbmcplugin.addDirectoryItem(
        handle=HANDLE, url=plugin_url(action, **params), listitem=item, isFolder=folder
    )


def finish():
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def show_menu():
    xbmcplugin.setContent(HANDLE, "videos")
    add_item("Filmes", "sections", folder=True, media="movie")
    add_item("Séries", "sections", folder=True, media="series")
    add_item("Buscar filmes e séries", "recent_search")
    add_item("Ferramentas", "tools", folder=True)
    add_item("Sobre o Felipe Vídeos", "about")
    finish()


def show_sections(media):
    from recent import CATEGORIES
    year = date.today().year
    prefix = "series_" if media == "series" else "movies_"
    xbmcplugin.setContent(HANDLE, "videos")
    for category, title in CATEGORIES:
        if category.startswith(prefix):
            add_item(title.format(year=year, prev_year=year-1), "recent",
                     folder=True, category=category)
    add_item("Gêneros", "genres", folder=True, media=media)
    finish()


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
    add_item("Como instalar o Elementum", "elementum_help")
    add_item("Diagnóstico de conexão", "diagnostic")
    add_item("Configurações avançadas", "settings")
    finish()


def show_recent(category, page=1, term=""):
    from recent import list_titles
    xbmcplugin.setContent(HANDLE, "tvshows" if category.startswith("series_") or category == "search_series" else "movies")
    try:
        results, more = list_titles(category, page=page, search_term=term)
        # Mostra nomes e sinopses localizados no painel da capa,
        # preservando o IMDb ID para a busca de torrents.
        from metadata_ptbr import descriptions_for_catalog, FALLBACK_SYNOPSIS
        try:
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
        rendered.sort(key=az)
        for label, plot, movie in rendered:
            info = {"title": label, "plot": plot}
            match = re.match(r"^(\d{4})", movie.get("year") or "")
            if match:
                info["year"] = int(match.group(1))
            art = {"thumb": movie["poster"], "poster": movie["poster"],
                   "icon": movie["poster"]}
            add_item(label, "recent_detail", folder=False, artwork=art,
                     info=info, identifier=movie["id"], media=movie["type"])
        if more:
            add_item("Próxima página >>", "recent", folder=True, category=category,
                     page=page+1, term=term)
        if not results:
            xbmcgui.Dialog().ok("Nenhum título", "Não há títulos nesta seção no momento.")
    except Exception as exc:
        xbmcgui.Dialog().ok("Catálogo de lançamentos", "Erro ao consultar títulos: " + str(exc)[:170])
    finish()


def show_recent_detail(identifier, media):
    """Abre opções do título como popup sem navegar para outro diretório."""
    from recent import detail
    finish()
    try:
        movie = detail(identifier, media=media)
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
        if movie.get("trailer_id"):
            options.append(("Ver trailer", "recent_trailer"))
        options.append(("Onde assistir no Brasil", "recent_where"))
        rating = movie.get("rating") or "Indisponível"
        rating_label = rating + "/10" if rating != "Indisponível" else rating
        heading = "{} ({}) | IMDb: {}".format(
            movie["title"], movie.get("year") or "s/ ano", rating_label)
        if not options:
            xbmcgui.Dialog().ok("Episódios indisponíveis",
                                "Não há temporadas ou episódios cadastrados para esta série.")
            return
        index = xbmcgui.Dialog().select(heading, [label for label, _ in options])
        if index is None or index < 0 or index >= len(options):
            return
        action = options[index][1]
        if isinstance(action, tuple) and action[0] == "season":
            choose_series_episode(movie, action[1])
        elif action == "sources":
            # O ID TMDb não é um identificador IMDb: evite enviá-lo ao Worker.
            choose_cloudflare_source(movie.get("original_title") or movie["title"],
                                     str(movie.get("year") or "")[:4],
                                     movie.get("imdb_id") or (
                                         identifier if re.fullmatch(r"tt[0-9]{5,12}", identifier) else ""))
        else:
            perform_recent_action(action, movie)
    except Exception as exc:
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
    choose_cloudflare_source(
        movie.get("original_title") or series_name,
        str(movie.get("year") or "")[:4],
        imdb, season=season, episode=selected["episode"])


def choose_cloudflare_source(title, year="", imdb="", season=None, episode=None):
    """Exibe popup de fontes e entrega a escolhida ao Elementum."""
    from source_client import list_sources
    try:
        sources = list_sources(title, year=year, imdb=imdb,
                               season=season, episode=episode)
        if not sources:
            xbmcgui.Dialog().ok(
                "Nenhuma fonte disponível",
                "Cloudflare e Torrentio não retornaram fontes compatíveis para este título.")
            return
        labels = []
        for source in sources:
            size_text = "{:.1f} GB".format(source["size"] / 1073741824) if source["size"] else "n/d"
            seed_text = str(source["seeders"]) if source["seeders"] is not None else "n/d"
            language = source["language"] if source["language"] != "unknown" else "n/d"
            labels.append("{} | {} | {} | {} | Seeds: {} | Áudio: {}".format(
                source["title"], source["source"], source["quality"],
                size_text, seed_text, language))
        target = "{} S{:02d}E{:02d}".format(title, season, episode) if season is not None else title
        index = xbmcgui.Dialog().select("Selecionar fonte — {}".format(target), labels)
        if index is None or index < 0 or index >= len(sources):
            return
        start_cloudflare_play(sources[index]["url"], file_index=sources[index].get("file_index"))
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
    if elementum_addon() is None:
        missing_elementum()
        return
    xbmc.executebuiltin("PlayMedia({})".format(build_elementum_url(url, file_index=file_index)))


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


def build_elementum_url(uri, file_index=None):
    """urlencode escapa &, vírgulas e parênteses para não confundir o Kodi."""
    params = {"uri": uri}
    if file_index is not None:
        if type(file_index) is not int or not 0 <= file_index <= 100_000:
            raise ValueError("Índice de arquivo inválido.")
        # Torrentio usa a ordem original do torrent; Elementum chama isso oindex.
        params["oindex"] = file_index
    return "{}?{}".format(ELEMENTUM_PLAY_URL, urlencode(params))


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
    if elementum_addon() is None:
        missing_elementum()
        return
    target = build_elementum_url(uri)
    # O Elementum controla a escolha do arquivo, buffering, playback e seeding.
    # PlayMedia aciona seu plugin de vídeo, sem requerer requisições HTTP locais
    # nem desabilitar proteções de rede da TV Box.
    xbmc.executebuiltin("PlayMedia({})".format(target))


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
        "Felipe Vídeos 1.4.0",
        "Integração opcional com Elementum para reproduzir torrents de origem "
        "autorizada sem aguardar o download completo. Peers podem ver seu IP "
        "e o motor pode compartilhar dados durante a reprodução. "
        "Buffer e limpeza de arquivos são gerenciados pelo Elementum.",
    )


def main():
    params = parse_qs(sys.argv[2].lstrip("?")) if len(sys.argv) > 2 else {}
    action = params.get("action", [""])[0]
    if action == "sections":
        show_sections(params.get("media", ["movie"])[0])
    elif action == "genres":
        show_genres(params.get("media", ["movie"])[0])
    elif action == "tools":
        show_tools()
    elif action == "recent":
        try:
            page = int(params.get("page", ["1"])[0])
        except ValueError:
            page = 1
        show_recent(params.get("category", ["movies_new"])[0],
                    page=page, term=params.get("term", [""])[0])
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
    elif action == "torrent_input":
        open_magnet_dialog()
    elif action == "elementum_settings":
        open_elementum_settings()
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
