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
        self.last_write = 0
        self.resume_applied = False

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
        self.resume_applied = False
        user_library.mark_started(request)
        _status("video_iniciado")
        self._try_resume()

    def _try_resume(self):
        if not self.current or self.resume_applied:
            return
        try:
            duration = float(self.getTotalTime())
            if duration <= 120:
                return  # Algumas versões só informam a duração após onAVStarted.
            resume = float(self.current.get("resume_seconds") or 0)
            expected = float(self.current.get("resume_duration") or 0)
            self.resume_applied = True
            if (resume > 45 and expected > 120 and resume < duration * .88 and
                    abs(duration - expected) <= max(180, expected * .1)):
                self.seekTime(resume)
                self.last_time, self.last_total = resume, duration
                _status("video_retomado")
        except (OSError, RuntimeError, ValueError, TypeError, AttributeError):
            pass

    def onAVStarted(self):
        self._started()

    def onPlayBackStarted(self):
        self._started()

    def tick(self):
        if not self.current:
            self._started()
        if self.current:
            self._try_resume()
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

    def _stopped(self, ended=False, failed=False):
        if not self.current:
            return
        self.tick()
        user_library.update_progress(self.current, self.last_time, self.last_total,
            completed=bool(ended and self.last_total > 0 and self.last_time / self.last_total > .8))
        _status("falha_player" if failed else "video_finalizado" if ended else "video_interrompido")
        self.current = None
        self.resume_applied = False
        self.last_time = self.last_total = self.last_write = 0

    def onPlayBackStopped(self):
        self._stopped()

    def onPlayBackEnded(self):
        self._stopped(ended=True)

    def onPlayBackError(self):
        if self.current:
            self._stopped(failed=True)
        else:
            _status("falha_player")

if __name__ == "__main__":
    monitor = xbmc.Monitor()
    player = PlaybackTracker()
    while not monitor.waitForAbort(5):
        player.tick()
