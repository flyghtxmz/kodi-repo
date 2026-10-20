"""Interface Felipe Cinema fullscreen em XML, mantendo a skin global Kodi."""
import xbmc
import xbmcgui
import xbmcaddon

NAVIGATION = [
    ("Início", "movies_popular"),
    ("Filmes", "movies_new"),
    ("Séries", "series_popular"),
    ("Em alta", "movies_popular"),
    ("Buscar", "search"),
    ("Menu clássico", "classic"),
    ("Sair", "exit"),
]
CONTROL_NAV = 100
CONTROL_POSTERS = 400
BACK_ACTIONS = frozenset((9, 10, 92, 2167))


def compact_catalog(movies, localized):
    """Usa os mesmos IMDb IDs e tipos do catálogo já existente."""
    result = []
    for movie in movies[:20]:
        if not isinstance(movie, dict):
            continue
        identifier = movie.get("id")
        media = movie.get("type")
        if not isinstance(identifier, str) or media not in ("movie", "series"):
            continue
        cached = localized.get("{}:{}".format(media, identifier), {})
        if not isinstance(cached, dict):
            cached = {}
        result.append({
            "id": identifier,
            "media": media,
            "title": (cached.get("title") or movie.get("title") or "Sem título")[:150],
            "plot": (cached.get("plot") or "Selecione o título para consultar a sinopse em português.")[:800],
            "poster": movie.get("poster") or "",
        })
    return result


class CinemaWindow(xbmcgui.WindowXMLDialog):
    """Janela modal no lugar do menu de pastas. Controle remoto e voltar suportados."""

    def onInit(self):
        self.movies = []
        self.classic_requested = False
        self.pending_selection = None
        self.getControl(CONTROL_NAV).addItems(
            [xbmcgui.ListItem(label=label) for label, _ in NAVIGATION])
        self._load("movies_popular", "Em destaque")

    def _load(self, category, heading, search_term=""):
        self.setProperty("CinemaSection", heading)
        self.setProperty("CinemaStatus", "Carregando catálogo…")
        try:
            from recent import list_titles
            from metadata_ptbr import _read_cache
            titles, more = list_titles(category, page=1, search_term=search_term)
            raw_cache = _read_cache()
            cached = {}
            for movie in titles[:20]:
                key = "{}:{}".format(movie.get("type"), movie.get("id"))
                entry = raw_cache.get(key)
                if isinstance(entry, dict):
                    cached[key] = {
                        "title": entry.get("localized_title") or "",
                        "plot": entry.get("description") or "",
                    }
            self.movies = compact_catalog(titles, cached)
            cards = []
            for movie in self.movies:
                item = xbmcgui.ListItem(label=movie["title"])
                item.setArt({"poster": movie["poster"], "thumb": movie["poster"]})
                item.setInfo("video", {"title": movie["title"], "plot": movie["plot"]})
                cards.append(item)
            control = self.getControl(CONTROL_POSTERS)
            control.reset()
            if cards:
                control.addItems(cards)
            self.setProperty("CinemaStatus", "{} títulos{}     •     OK para abrir".format(
                len(cards), " — primeira página" if more else ""))
            self.setFocusId(CONTROL_POSTERS if cards else CONTROL_NAV)
        except (OSError, ValueError, TypeError, RuntimeError) as error:
            self.movies = []
            self.getControl(CONTROL_POSTERS).reset()
            self.setProperty("CinemaStatus", "Catálogo temporariamente indisponível. Use outra seção.")
            xbmc.log("Felipe Vídeos Cinema: falha ao carregar ({})".format(
                type(error).__name__), xbmc.LOGERROR)
            self.setFocusId(CONTROL_NAV)

    def _navigate(self, selection):
        if selection < 0 or selection >= len(NAVIGATION):
            return
        heading, category = NAVIGATION[selection]
        if category == "exit":
            self.close()
        elif category == "classic":
            self.classic_requested = True
            self.close()
        elif category == "search":
            text = xbmcgui.Dialog().input("Buscar filmes ou séries", type=xbmcgui.INPUT_ALPHANUM)
            if not text or not text.strip():
                return
            media = xbmcgui.Dialog().select("Tipo de conteúdo", ["Filmes", "Séries"])
            if media in (0, 1):
                self._load("search_movie" if media == 0 else "search_series",
                           "Busca: " + text.strip()[:50], text.strip()[:80])
        else:
            self._load(category, heading)

    def onClick(self, controlId):
        if controlId == CONTROL_NAV:
            self._navigate(self.getControl(CONTROL_NAV).getSelectedPosition())
        elif controlId == CONTROL_POSTERS:
            selected = self.getControl(CONTROL_POSTERS).getSelectedPosition()
            if 0 <= selected < len(self.movies):
                movie = self.movies[selected]
                # Não abra outro diálogo/modal enquanto WindowXMLDialog.onClick
                # está ativo. Algumas builds Kodi Android podem fechar ao
                # sobrepor as janelas ou iniciar Player.Open de dentro daqui.
                self.pending_selection = (movie["id"], movie["media"])
                self.close()

    def onAction(self, action):
        if action.getId() in BACK_ACTIONS:
            self.close()


def launch(on_select):
    """Executa o popup somente depois que a janela cinema foi encerrada.

    True significa janela usada e saída normal; False solicita menu clássico.
    Não chama outros diálogos dentro de onClick/da janela modal.
    """
    addon = xbmcaddon.Addon()
    path = addon.getAddonInfo("path")
    if not path:
        return False
    window = None
    selection = None
    classic = False
    try:
        window = CinemaWindow("FelipeCinema.xml", path, "Default", "1080i")
        window.doModal()
        selection = getattr(window, "pending_selection", None)
        classic = bool(getattr(window, "classic_requested", False))
    except (OSError, RuntimeError, TypeError, ValueError, AttributeError) as error:
        xbmc.log("Felipe Vídeos Cinema: falha ao abrir tela ({})".format(
            type(error).__name__), xbmc.LOGERROR)
        return False
    finally:
        if window is not None:
            # Destruir o objeto modal antes de invocar UI ou reprodução.
            del window
    if classic:
        return False
    if selection:
        try:
            on_select(*selection)
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError) as error:
            xbmc.log("Felipe Vídeos Cinema: falha ao selecionar título ({})".format(
                type(error).__name__), xbmc.LOGERROR)
            xbmcgui.Dialog().ok("Filme indisponível",
                                "Não foi possível abrir as opções do título.")
    return True
