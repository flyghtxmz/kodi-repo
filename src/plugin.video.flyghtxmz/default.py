"""Felipe Vídeos: Kodi 21 Omega (Python 3) com integração opcional Elementum.

O addon não baixa torrents diretamente: entrega magnet/.torrent ao Elementum
instalado no mesmo Kodi. O buffer e o armazenamento pertencem ao Elementum.
"""

import re
import sys
from urllib.parse import parse_qs, urlencode, urlsplit

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin


ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
DEMO_URL = "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"
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
    from catalog import CATEGORIES
    xbmcplugin.setContent(HANDLE, "videos")
    for category, title in CATEGORIES:
        add_item(title, "catalog", folder=True, category=category)
    add_item("Pesquisar filmes e vídeos", "search")
    add_item("Diagnosticar repositório (erro de conexão)", "diagnostic")
    add_item("Adicionar magnet ou URL .torrent", "torrent_input")
    add_item("Configurar Elementum (buffer / armazenamento)", "elementum_settings")
    add_item("Como instalar o Elementum", "elementum_help")
    add_item("Flores (vídeo de demonstração)", "demo", playable=True)
    if ADDON.getSetting("custom_url").strip():
        add_item("Reproduzir meu vídeo", "custom", playable=True)
    add_item("Configurar URL do meu vídeo", "settings")
    add_item("Sobre o addon", "about")
    finish()


def show_catalog(category, page=1, term=""):
    from catalog import search
    xbmcplugin.setContent(HANDLE, "movies")
    try:
        results, has_next = search(category=category, page=page, search_term=term)
    except Exception as exc:
        xbmcgui.Dialog().ok("Catálogo indisponível", "Não foi possível consultar o catálogo agora. " + str(exc)[:150])
        finish()
        return
    for entry in results:
        info = {"title": entry["title"], "plot": entry.get("plot") or "Licença Creative Commons ou domínio público."}
        try:
            year = int(entry.get("year") or 0)
            if 1870 <= year <= 2100:
                info["year"] = year
        except (ValueError, TypeError):
            pass
        art = {"thumb": entry["thumb"], "poster": entry["thumb"], "icon": entry["thumb"]}
        add_item(entry["title"], "catalog_play", playable=True, artwork=art, info=info,
                 identifier=entry["identifier"])
    if has_next:
        add_item("Próxima página >>", "catalog", folder=True, category=category,
                 page=page + 1, term=term)
    if not results:
        xbmcgui.Dialog().ok("Nenhum resultado", "Tente outra categoria ou termo de busca.")
    finish()


def search_catalog():
    term = xbmcgui.Dialog().input("Pesquisar vídeos de licença aberta", type=xbmcgui.INPUT_ALPHANUM)
    finish()
    if term and term.strip():
        xbmc.executebuiltin("Container.Update({})".format(plugin_url("catalog", category="busca",
                                                                       page=1, term=term.strip()[:80])))


def play_catalog(identifier):
    from catalog import playback
    try:
        data = playback(identifier)
        video = xbmcgui.ListItem(label=data["title"], path=data["url"])
        video.setProperty("IsPlayable", "true")
        video.setArt({"thumb": data["thumb"], "icon": data["thumb"]})
        video.setInfo("video", {"title": data["title"], "plot": data.get("plot") or ""})
        xbmcplugin.setResolvedUrl(HANDLE, True, video)
    except Exception as exc:
        xbmcgui.Dialog().ok("Não foi possível reproduzir", str(exc)[:220])
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())


def play_http(url, label):
    if not url or not url.lower().startswith(("https://", "http://")):
        xbmcgui.Dialog().ok("Felipe Vídeos", "Configure uma URL HTTP ou HTTPS válida.")
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    item = xbmcgui.ListItem(label=label, path=url)
    item.setProperty("IsPlayable", "true")
    xbmcplugin.setResolvedUrl(HANDLE, True, item)


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


def build_elementum_url(uri):
    """urlencode escapa &, vírgulas e parênteses para não confundir o Kodi."""
    return "{}?{}".format(ELEMENTUM_PLAY_URL, urlencode({"uri": uri}))


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
        "Consulte a opção 'Como instalar o Elementum' neste addon.",
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
        "Depois, volte ao Felipe Vídeos e escolha 'Adicionar magnet'.",
    )


def show_about():
    finish()
    xbmcgui.Dialog().ok(
        "Felipe Vídeos 1.2.0",
        "Integração opcional com Elementum para reproduzir torrents de origem "
        "autorizada sem aguardar o download completo. Peers podem ver seu IP "
        "e o motor pode compartilhar dados durante a reprodução. "
        "Buffer e limpeza de arquivos são gerenciados pelo Elementum.",
    )


def main():
    params = parse_qs(sys.argv[2].lstrip("?")) if len(sys.argv) > 2 else {}
    action = params.get("action", [""])[0]

    if action == "catalog":
        try:
            page = int(params.get("page", ["1"])[0])
        except ValueError:
            page = 1
        show_catalog(params.get("category", ["destaques"])[0],
                     page=page, term=params.get("term", [""])[0])
    elif action == "catalog_play":
        play_catalog(params.get("identifier", [""])[0])
    elif action == "search":
        search_catalog()
    elif action == "demo":
        play_http(DEMO_URL, "Flores - MDN")
    elif action == "custom":
        play_http(ADDON.getSetting("custom_url").strip(), "Meu vídeo")
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
