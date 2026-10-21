"""Persistent Cinema shell; catalog IO and popups stay outside GUI callbacks."""
from queue import Queue, Empty, Full
import json
from datetime import date
from threading import Event
from time import monotonic
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
    """Callbacks enqueue actions without closing the shell or doing network IO."""

    def prepare(self, model):
        self.model = model
        self.loaded = [None] * len(model["shelves"])
        self.shelf_offset = 0
        self.restore_focus = (CONTROL_TABS, 0)
        self.requests = Queue(maxsize=1)
        self.ready = Event()
        self.init_error = None
        self.busy = True

    def onInit(self):
        try:
            self.render()
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError) as error:
            self.init_error = error
        finally:
            self.ready.set()

    def render(self):
        self.cards = {}
        self.getControl(CONTROL_NAV).reset()
        self.getControl(CONTROL_NAV).addItems([xbmcgui.ListItem(label=name) for name, _ in NAVIGATION])
        nav_index = next((i for i, (_, key) in enumerate(NAVIGATION) if key == self.model["nav"]), 0)
        self.getControl(CONTROL_NAV).selectItem(nav_index)
        self.setProperty("CinemaSection", self.model["title"])
        self.setProperty("CinemaNote", self.model["note"])
        self.setProperty("CinemaHasTabs", "true" if self.model["tabs"] else "")
        self.setProperty("CinemaHasRow2", "")
        self.setProperty("CinemaHasRow1", "")
        below = self.shelf_offset + len(SHELF_CONTROLS) < len(self.model["shelves"])
        self.setProperty("CinemaShelfHint", "↓ Mais fileiras" if below else "")
        self.setProperty("CinemaHeroImage", "")
        tabs = self.getControl(CONTROL_TABS)
        tabs.reset()
        tabs.addItems([xbmcgui.ListItem(label=label) for label, _, _ in self.model["tabs"]])
        for visible_index, control in enumerate(SHELF_CONTROLS):
            index = self.shelf_offset + visible_index
            if index >= len(self.model["shelves"]):
                continue
            spec, data = self.model["shelves"][index], self.loaded[index]
            if data is None:
                data = {"items": [{"title": "Carregando títulos…", "action": "empty"}],
                        "page": 1, "more": False, "error": ""}
            self._load(control, spec, data)
            if visible_index == 0 and data.get("items"):
                self.setProperty("CinemaHeroImage", data["items"][0].get("poster") or "")
        focus, index = self.restore_focus
        available = (CONTROL_NAV, CONTROL_TABS) + SHELF_CONTROLS[:min(len(SHELF_CONTROLS), len(self.loaded) - self.shelf_offset)]
        if focus not in available or (focus == CONTROL_TABS and not self.model["tabs"]):
            focus, index = CONTROL_NAV, nav_index
        self.setFocusId(focus)
        self.getControl(focus).selectItem(max(0, index))
        self.set_busy(self.busy)

    def set_busy(self, busy, message="Carregando…"):
        self.busy = busy
        self.setProperty("CinemaStatus", message if busy else
                         "Cinema 1.7.1 • BORDA DOURADA: foco • OK: abrir • ←→: navegar • ↑↓: fileiras")

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
        if self.busy:
            return
        self.restore_focus = (control, self.getControl(control).getSelectedPosition())
        self.set_busy(True)
        try:
            self.requests.put_nowait(request)
        except Full:
            pass

    def onClick(self, controlId):
        if self.busy or controlId not in (CONTROL_NAV, CONTROL_TABS) + SHELF_CONTROLS:
            return
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
                self._queue(("page", self.shelf_offset + SHELF_CONTROLS.index(controlId), movie["page"]), controlId)
            elif not movie.get("action"):
                self._queue(("select", movie["id"], movie["media"]), controlId)

    def onAction(self, action):
        key = action.getId()
        if key in BACK_ACTIONS:
            self._queue(("back", "", ""), CONTROL_NAV)
            return
        focus_reader = getattr(self, "getFocusId", None)
        focused = focus_reader() if callable(focus_reader) else self.restore_focus[0]
        if self.busy:
            return
        # XML up/down routes stay on the same list. Handle exactly one hop
        # here, using the source focus, so entering row 2 cannot also scroll it.
        if key == 4:
            if focused == CONTROL_TABS:
                self.setFocusId(CONTROL_POSTERS)
            elif focused == SHELF_CONTROLS[0] and self.shelf_offset + 1 < len(self.loaded):
                self.setFocusId(SHELF_CONTROLS[1])
            elif focused == SHELF_CONTROLS[1] and self.shelf_offset + 2 < len(self.loaded):
                self._queue(("scroll", 1, ""), focused)
        elif key == 3:
            if focused == SHELF_CONTROLS[1]:
                self.setFocusId(SHELF_CONTROLS[0])
            elif focused == SHELF_CONTROLS[0]:
                if self.shelf_offset > 0:
                    self._queue(("scroll", -1, ""), focused)
                else:
                    self.setFocusId(CONTROL_TABS if self.model["tabs"] else CONTROL_NAV)
            elif focused == CONTROL_TABS:
                self.setFocusId(CONTROL_NAV)



def launch(on_select):
    """Keep one shell visible during IO, paging and child dialogs.

    show() returns to this controller rather than blocking like doModal(). Kodi
    callbacks only enqueue requests; the plugin thread handles IO and dialogs.
    Title dialogs close and release Cinema first; cancel restores its plain data.
    Catalog navigation and pagination keep the same shell visible.
    """
    path = xbmcaddon.Addon().getAddonInfo("path")
    if not path:
        return False
    window = None
    try:
        monitor = xbmc.Monitor()
        window = CinemaWindow("FelipeCinema.xml", path, "Default", "1080i")
        window.prepare(screen("home", ""))
        window.show()
        deadline = monotonic() + 15
        while not window.ready.is_set():
            if monitor.waitForAbort(0.05):
                return True
            if monotonic() >= deadline:
                raise RuntimeError("Cinema initialization timed out")
        if window.init_error is not None:
            raise window.init_error
        route = "home"
        while not monitor.abortRequested():
            # The shell is already visible, including on the first catalog load.
            for index in range(window.shelf_offset, min(len(window.model["shelves"]),
                                                         window.shelf_offset + len(SHELF_CONTROLS))):
                spec = window.model["shelves"][index]
                if window.loaded[index] is not None:
                    continue
                if monitor.abortRequested():
                    return True
                window.set_busy(True, "Carregando " + spec["label"] + "…")
                try:
                    window.loaded[index] = load_shelf(spec, 1)
                except (OSError, ValueError, TypeError, RuntimeError) as error:
                    xbmc.log("Felipe Cinema: catálogo indisponível ({})".format(type(error).__name__), xbmc.LOGERROR)
                    window.loaded[index] = {"items": [], "page": 1, "more": False,
                        "error": "Catálogo indisponível. Tente novamente ou escolha outra seção."}
                window.render()
            window.set_busy(False)
            while not monitor.abortRequested():
                try:
                    request = window.requests.get_nowait()
                    break
                except Empty:
                    if monitor.waitForAbort(0.05):
                        return True
            else:
                return True
            action, target, extra = request
            if action == "scroll":
                window.shelf_offset = max(0, min(window.shelf_offset + target,
                    max(0, len(window.loaded) - len(SHELF_CONTROLS))))
                window.restore_focus = (SHELF_CONTROLS[-1] if target > 0 else SHELF_CONTROLS[0], 0)
                window.render()
                continue
            if action == "select":
                # Keep only plain catalog data. Destroy the modal Cinema before
                # native title/source dialogs or asynchronous Player.Open.
                saved = (window.model, window.loaded, window.shelf_offset, window.restore_focus)
                window.close()
                # Evita libertar o objeto C++ enquanto os callbacks da janela
                # ainda estão no ciclo de eventos do Android/Kodi.
                native_sleep = getattr(xbmc, "sleep", None)
                if callable(native_sleep):
                    native_sleep(350)
                window = None
                xbmc.log("Felipe Cinema: janela encerrada antes da ficha " + target, xbmc.LOGINFO)
                try:
                    if on_select(target, extra):
                        return True
                except (OSError, RuntimeError, TypeError, ValueError, AttributeError) as error:
                    xbmc.log("Felipe Cinema: falha na ficha ({})".format(type(error).__name__), xbmc.LOGERROR)
                    xbmcgui.Dialog().ok("Título indisponível", "Não foi possível abrir a ficha. Escolha outro título.")
                if monitor.abortRequested():
                    return True
                window = CinemaWindow("FelipeCinema.xml", path, "Default", "1080i")
                window.prepare(saved[0])
                window.loaded, window.shelf_offset, window.restore_focus = saved[1:]
                window.show()
                deadline = monotonic() + 15
                while not window.ready.is_set():
                    if monitor.waitForAbort(0.05):
                        return True
                    if monotonic() >= deadline:
                        raise RuntimeError("Cinema restoration timed out")
                if window.init_error is not None:
                    raise window.init_error
                continue
            if action == "page":
                index, page = target, extra
                previous_focus = window.restore_focus
                window.set_busy(True, "Carregando página {}…".format(page))
                try:
                    new_page = load_shelf(window.model["shelves"][index], page)
                    if new_page.get("error") and window.loaded[index].get("items"):
                        xbmcgui.Dialog().ok("Página indisponível", "A página anterior foi mantida.")
                    else:
                        window.loaded[index] = new_page
                        window.restore_focus = (SHELF_CONTROLS[index - window.shelf_offset], 0)
                except (OSError, ValueError, TypeError, RuntimeError):
                    window.restore_focus = previous_focus
                    xbmcgui.Dialog().ok("Página indisponível", "Tente novamente em instantes.")
                window.render()
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
                kind = xbmcgui.Dialog().select("Tipo de conteúdo", ["Filmes e séries", "Só filmes", "Só séries"])
                if kind is None or kind < 0:
                    continue
                year = xbmcgui.Dialog().input("Ano (opcional; deixar vazio = todos)",
                                               type=xbmcgui.INPUT_NUMERIC)
                year = str(year or "").strip()
                if year and (not year.isdigit() or not 1880 <= int(year) <= date.today().year + 2):
                    xbmcgui.Dialog().ok("Ano inválido", "Digite um ano válido ou deixe em branco.")
                    continue
                target, extra = "search_results", json.dumps(
                    {"q": term.strip()[:80], "media": ("all", "movie", "series")[kind],
                     "year": year})
            route = target
            window.model = screen(route, extra)
            window.loaded = [None] * len(window.model["shelves"])
            window.shelf_offset = 0
            window.restore_focus = (CONTROL_POSTERS, 0)
            window.render()
        return True
    except (OSError, RuntimeError, TypeError, ValueError, AttributeError) as error:
        xbmc.log("Felipe Cinema: falha de interface ({})".format(type(error).__name__), xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Felipe Cinema indisponível",
            "A janela Cinema não pôde ser mantida. Reabra o addon para tentar novamente. "
            "Se necessário, desative Cinema em Configurar → Interface.")
        return True
    finally:
        if window is not None:
            window.close()
