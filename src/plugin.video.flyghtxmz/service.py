"""Service de baixo consumo para confirmar vídeo iniciado e guardar progresso."""
import time
import xbmc
import local_cache
import user_library

def _recent_request():
    request = local_cache.get("playback_request", "current")
    if (not isinstance(request, dict) or
            time.time() - float(request.get("at", 0)) > 600):
        return None
    return request

def _status(value):
    previous = local_cache.get("last_playback", "selected") or {}
    if isinstance(previous, dict):
        previous["request"] = value
        previous["verified_at"] = int(time.time())
        local_cache.put("last_playback", "selected", previous, ttl=172800, max_entries=1)

class PlaybackTracker(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.current = None
        self.last_time = 0.
        self.last_total = 0.
        self.last_write = 0.

    def _started(self):
        if self.current:
            return
        request = _recent_request()
        if not request:
            return
        try:
            if not self.isPlayingVideo():
                return
        except (RuntimeError, OSError):
            return
        self.current = request
        user_library.mark_started(request)
        _status("video_iniciado")

    def onAVStarted(self):
        self._started()

    def onPlayBackStarted(self):
        self._started()

    def tick(self):
        if not self.current:
            self._started()
        if not self.current or time.monotonic() - self.last_write < 15:
            return
        try:
            if not self.isPlayingVideo():
                return
            seconds, duration = self.getTime(), self.getTotalTime()
            self.last_time, self.last_total = seconds, duration
            user_library.update_progress(self.current, seconds, duration)
            self.last_write = time.monotonic()
        except (OSError, RuntimeError, ValueError, TypeError):
            pass

    def _stopped(self, ended=False):
        if not self.current:
            return
        self.tick()
        user_library.update_progress(self.current, self.last_time, self.last_total,
            completed=bool(ended and self.last_total > 0 and self.last_time / self.last_total > .8))
        _status("video_finalizado" if ended else "video_interrompido")
        self.current = None
        self.last_time = self.last_total = self.last_write = 0

    def onPlayBackStopped(self):
        self._stopped()

    def onPlayBackEnded(self):
        self._stopped(ended=True)

    def onPlayBackError(self):
        _status("falha_player")
        self._stopped()

if __name__ == "__main__":
    monitor = xbmc.Monitor()
    player = PlaybackTracker()
    while not monitor.waitForAbort(5):
        player.tick()
