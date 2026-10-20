"""Cinema fullscreen: preloaded shelves, deferred actions, bounded pagination."""
import xbmc
import xbmcgui
import xbmcaddon
from cinema_catalog import NAVIGATION, compact_catalog, screen, load_shelf

CONTROL_NAV = 100
CONTROL_TABS = 200
CONTROL_POSTERS = 400
SHELF_CONTROLS = (400, 410)
BACK_ACTIONS = frozenset((9, 10, 92, 2167))


class CinemaWindow(xbmcgui.WindowXMLDialog):
    """Callbacks only operate controls or close the window; never fetch or open dialogs."""

    def onInit(self):
        self.request = None
        self.cards = {}
        self.getControl(CONTROL_NAV).reset()
        self.getControl(CONTROL_NAV).addItems([xbmcgui.ListItem(label=name) for name, _ in NAVIGATION])
        nav_index = next((i for i, (_, key) in enumerate(NAVIGATION) if key == self.model["nav"]), 0)
        self.getControl(CONTROL_NAV).selectItem(nav_index)
        self.setProperty("CinemaSection", self.model["title"])
        self.setProperty("CinemaNote", self.model["note"])
        self.setProperty("CinemaHasTabs", "true" if self.model["tabs"] else "")
        self.setProperty("CinemaHasRow2", "")
        tabs = self.getControl(CONTROL_TABS)
        tabs.reset()
        tabs.addItems([xbmcgui.ListItem(label=label) for label, _, _ in self.model["tabs"]])
        for control, spec, data in zip(SHELF_CONTROLS, self.model["shelves"], self.loaded):
            self._load(control, spec, data)
        focus, index = self.restore_focus
        available = (CONTROL_NAV, CONTROL_TABS) + SHELF_CONTROLS[:len(self.loaded)]
        if focus not in available or (focus == CONTROL_TABS and not self.model["tabs"]):
            focus, index = CONTROL_NAV, nav_index
        self.setFocusId(focus)
        self.getControl(focus).selectItem(max(0, index))
        self.setProperty("CinemaStatus", "Cinema 1.6.2 • BORDA VERMELHA: seleção • OK: abrir • ←→: navegar • ↑↓: fileiras")

    def _load(self, control, spec, data):
        row = SHELF_CONTROLS.index(control) + 1
        heading = "{}  ·  página {}".format(spec["label"], data["page"])
        self.setProperty("CinemaRow{}".format(row), heading)
        entries = []
        if data["page"] > 1:
            entries.append({"title": "← Página anterior", "action": "page", "page": data["page"]-1})
        entries.extend(data["items"])
        if data["more"]:
            entries.append({"title": "Próxima página →", "action": "page", "page": data["page"]+1})
        if data["error"]:
            entries.append({"title": "Tentar novamente", "action": "page", "page": data["page"], "plot": data["error"]})
        elif not data["items"]:
            entries.append({"title": "Nenhum título nesta página", "action": "empty", "plot": "Escolha outra plataforma, categoria ou página."})
        self.cards[control] = entries
        items = []
        for movie in entries:
            item = xbmcgui.ListItem(label=movie["title"])
            poster = movie.get("poster") or ""
            item.setArt({"poster": poster, "thumb": poster})
            item.setInfo("video", {"title": movie["title"], "plot": movie.get("plot") or ""})
            item.setProperty("CinemaAction", "true" if movie.get("action") else "")
            item.setProperty("CinemaNavigation", "página" if movie.get("action") == "page" else "")
            items.append(item)
        self.getControl(control).reset()
        self.getControl(control).addItems(items)
        self.setProperty("CinemaHasRow{}".format(row), "true")

    def _queue(self, request, control):
        self.restore_focus = (control, self.getControl(control).getSelectedPosition())
        self.request = request
        self.close()

    def onClick(self, controlId):
        selected = self.getControl(controlId).getSelectedPosition()
        if controlId == CONTROL_NAV and 0 <= selected < len(NAVIGATION):
            self._queue(("navigate", NAVIGATION[selected][1], ""), controlId)
        elif controlId == CONTROL_TABS and 0 <= selected < len(self.model["tabs"]):
            _, route, value = self.model["tabs"][selected]
            self._queue(("navigate", route, value), controlId)
        elif controlId in SHELF_CONTROLS:
            entries = self.cards.get(controlId, [])
            if not 0 <= selected < len(entries):
                return
            movie = entries[selected]
            if movie.get("action") == "page":
                self._queue(("page", SHELF_CONTROLS.index(controlId), movie["page"]), controlId)
            elif not movie.get("action"):
                self._queue(("select", movie["id"], movie["media"]), controlId)

    def onAction(self, action):
        if action.getId() in BACK_ACTIONS:
            self.request = ("back", "", "")
            self.close()


def launch(on_select):
    """All IO/popups happen between modal lifetimes, never in UI callbacks.

    on_select returns True only when playback was handed off, so cancelling a
    title returns to the same shelf/page without racing the asynchronous player.
    """
    path = xbmcaddon.Addon().getAddonInfo("path")
    if not path:
        return False
    route, value = "home", ""
    model = screen(route, value)
    loaded = [None] * len(model["shelves"])
    focus = (CONTROL_TABS, 0)
    while True:
        for index, spec in enumerate(model["shelves"]):
            if loaded[index] is not None:
                continue
            # No modal cinema window exists while a catalog is loading.
            progress = xbmcgui.DialogProgress()
            try:
                progress.create("Felipe Cinema", "Carregando " + spec["label"] + "…")
                loaded[index] = load_shelf(spec, 1)
            except (OSError, ValueError, TypeError, RuntimeError) as error:
                xbmc.log("Felipe Cinema: catálogo indisponível ({})".format(type(error).__name__), xbmc.LOGERROR)
                loaded[index] = {"items": [], "page": 1, "more": False,
                                 "error": "Catálogo indisponível. Tente novamente ou escolha outra seção."}
            finally:
                progress.close()
        window = None
        try:
            window = CinemaWindow("FelipeCinema.xml", path, "Default", "1080i")
            window.model, window.loaded, window.restore_focus = model, loaded, focus
            window.doModal()
            request = window.request
            focus = window.restore_focus
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError) as error:
            xbmc.log("Felipe Cinema: falha de interface ({})".format(type(error).__name__), xbmc.LOGERROR)
            xbmcgui.Dialog().ok("Felipe Cinema indisponível",
                "A janela Cinema não pôde ser mantida. Reabra o addon para tentar novamente. "
                "Se necessário, desative Cinema em Configurar → Interface.")
            return True
        finally:
            if window is not None:
                del window
        if not request:
            return True
        action, target, extra = request
        if action == "select":
            try:
                if on_select(target, extra):
                    return True
            except (OSError, RuntimeError, TypeError, ValueError, AttributeError) as error:
                xbmc.log("Felipe Cinema: falha na ficha ({})".format(type(error).__name__), xbmc.LOGERROR)
                xbmcgui.Dialog().ok("Título indisponível", "Não foi possível abrir a ficha. Escolha outro título.")
            continue
        if action == "page":
            index, page = target, extra
            progress = xbmcgui.DialogProgress()
            try:
                progress.create("Felipe Cinema", "Carregando página {}…".format(page))
                new_page = load_shelf(model["shelves"][index], page)
                if new_page.get("error") and loaded[index].get("items"):
                    xbmcgui.Dialog().ok("Página indisponível", "A página anterior foi mantida.")
                else:
                    loaded[index] = new_page
            except (OSError, ValueError, TypeError, RuntimeError):
                # Keep the previous page; a temporary outage must not erase it.
                xbmcgui.Dialog().ok("Página indisponível", "Tente novamente em instantes.")
            finally:
                progress.close()
            focus = (SHELF_CONTROLS[index], 0)
            continue
        if action == "back":
            if route == "home":
                return True
            target, extra = "home", ""
        if target == "exit":
            return True
        if target == "classic":
            return False
        if target == "search":
            term = xbmcgui.Dialog().input("Buscar filmes e séries", type=xbmcgui.INPUT_ALPHANUM)
            if not term or not term.strip():
                continue
            target, extra = "search_results", term.strip()[:80]
        route, value = target, extra
        model = screen(route, value)
        loaded = [None] * len(model["shelves"])
        focus = (CONTROL_POSTERS, 0)
