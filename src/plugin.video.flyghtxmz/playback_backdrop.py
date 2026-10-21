"""Non-modal artwork behind Elementum's real progress/cancel dialog."""
import time
import xbmc
import xbmcgui
import xbmcaddon


class PlaybackBackdrop(xbmcgui.WindowXML):
    def prepare(self, title, poster):
        self.title = str(title or "Preparando vídeo")[:180]
        self.poster = str(poster or "")
        self.dismissed = False

    def onInit(self):
        self.setProperty("PlaybackTitle", self.title)
        self.setProperty("PlaybackPoster", self.poster)

    def onAction(self, action):
        if action.getId() in (9, 10, 92, 2167):
            self.dismissed = True
            self.close()


def wait_for_handoff(window, monitor, player, clock=time.monotonic):
    """Only dismiss our artwork; never manipulate playback or native dialogs."""
    started = clock()
    last_progress = None
    while not window.dismissed and not monitor.abortRequested():
        if player.isPlayingVideo():
            return
        now = clock()
        if xbmc.getCondVisibility("Window.IsVisible(10101)"):
            last_progress = now
        elif last_progress is not None and now - last_progress >= 2:
            return  # Buffer finished, cancelled, or failed; allow the player handoff.
        if (last_progress is None and now - started >= 30) or now - started >= 1200:
            return  # Visual timeout only: the Elementum request is left untouched.
        if monitor.waitForAbort(0.1):
            return


def launch_with_backdrop(launch, title="", poster=""):
    window = None
    try:
        window = PlaybackBackdrop("FelipePlayback.xml", xbmcaddon.Addon().getAddonInfo("path"),
                                  "Default", "1080i")
        window.prepare(title, poster)
        window.show()
    except Exception:
        # A skin/graphics problem must not prevent or duplicate Player.Open.
        if window is not None:
            try:
                window.close()
            except Exception:
                pass
        window = None
    try:
        accepted = launch()
        if accepted and window is not None:
            try:
                wait_for_handoff(window, xbmc.Monitor(), xbmc.Player())
            except Exception:
                xbmc.log("Felipe Vídeos: fundo de carregamento indisponível", xbmc.LOGWARNING)
        return accepted
    finally:
        if window is not None:
            try:
                window.close()
            except Exception:
                pass
