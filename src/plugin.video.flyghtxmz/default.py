"""Felipe Vídeos: plugin de vídeo mínimo compatível com Kodi 19+ (Python 3)."""

import sys
from urllib.parse import parse_qs, urlencode

import xbmcaddon
import xbmcgui
import xbmcplugin


ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
DEMO_URL = "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"


def plugin_url(action):
    return "{}?{}".format(BASE_URL, urlencode({"action": action}))


def add_item(label, action, playable=False):
    item = xbmcgui.ListItem(label=label)
    if playable:
        item.setProperty("IsPlayable", "true")
    xbmcplugin.addDirectoryItem(
        handle=HANDLE, url=plugin_url(action), listitem=item, isFolder=False
    )


def show_menu():
    xbmcplugin.setContent(HANDLE, "videos")
    add_item("Flores (vídeo de demonstração)", "demo", playable=True)
    custom_url = ADDON.getSetting("custom_url").strip()
    if custom_url:
        add_item("Reproduzir meu vídeo", "custom", playable=True)
    add_item("Configurar URL do meu vídeo", "settings")
    add_item("Sobre o addon", "about")
    xbmcplugin.endOfDirectory(HANDLE)


def play(url, label):
    if not url or not url.lower().startswith(("https://", "http://")):
        xbmcgui.Dialog().ok("Felipe Vídeos", "Configure uma URL HTTP ou HTTPS válida.")
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    item = xbmcgui.ListItem(label=label, path=url)
    item.setProperty("IsPlayable", "true")
    xbmcplugin.setResolvedUrl(HANDLE, True, item)


def main():
    params = parse_qs(sys.argv[2].lstrip("?")) if len(sys.argv) > 2 else {}
    action = params.get("action", [""])[0]

    if action == "demo":
        play(DEMO_URL, "Flores - MDN")
    elif action == "custom":
        play(ADDON.getSetting("custom_url").strip(), "Meu vídeo")
    elif action == "settings":
        ADDON.openSettings()
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
    elif action == "about":
        xbmcgui.Dialog().ok(
            "Felipe Vídeos",
            "Addon inicial do seu repositório Kodi. "
            "O vídeo de teste é um clipe CC0 disponibilizado pela MDN. "
            "Nas configurações, você pode inserir a URL de um vídeo autorizado.",
        )
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
    else:
        show_menu()


if __name__ == "__main__":
    main()
