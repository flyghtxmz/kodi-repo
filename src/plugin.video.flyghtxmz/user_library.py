"""Coleção privada e histórico de reprodução do Felipe Vídeos (sem conta externa)."""
import json
import os
import re
import tempfile
import threading
import time
from pathlib import Path

_LOCK = threading.RLock()
_IMDB = re.compile(r"^tt[0-9]{5,12}$")
_MAX_FAVORITES = 250
_MAX_HISTORY = 120

def _path():
    import xbmcaddon
    import xbmcvfs
    root = Path(xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("profile")))
    root.mkdir(parents=True, exist_ok=True)
    return root / "felipe_library.json"

def _read():
    try:
        path = _path()
        if not path.exists() or path.stat().st_size > 350000:
            return {"favorites": {}, "history": {}}
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            return {"favorites": {}, "history": {}}
        return {k: obj.get(k) if isinstance(obj.get(k), dict) else {}
                for k in ("favorites", "history")}
    except (OSError, ValueError, TypeError, ImportError, AttributeError):
        return {"favorites": {}, "history": {}}

def _write(data):
    temp = None
    try:
        path = _path()
        for group, limit in (("favorites", _MAX_FAVORITES), ("history", _MAX_HISTORY)):
            items = data.get(group, {})
            data[group] = dict(sorted(items.items(),
                key=lambda row: float(row[1].get("updated", 0)) if isinstance(row[1], dict) else 0,
                reverse=True)[:limit])
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                prefix=".felipe-library-", dir=str(path.parent), delete=False) as f:
            temp = f.name
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(temp, path)
    except (OSError, ValueError, TypeError, ImportError, AttributeError):
        if temp:
            try:
                os.unlink(temp)
            except OSError:
                pass

def _key(identifier, media):
    if media not in ("movie", "series") or not isinstance(identifier, str) or not _IMDB.fullmatch(identifier):
        raise ValueError("Título inválido")
    return media + ":" + identifier

def _title(data):
    return {"id": data["id"], "media": data["media"],
            "title": str(data.get("title") or "Sem título")[:160],
            "poster": str(data.get("poster") or "")[:2000] if str(data.get("poster") or "").startswith("https://") else "",
            "year": str(data.get("year") or "")[:12],
            "genres": [str(g)[:50] for g in (data.get("genres") or [])[:6] if isinstance(g, str)]}

def toggle_favorite(identifier, media, title="", poster="", year="", genres=None):
    key = _key(identifier, media)
    with _LOCK:
        data = _read()
        if key in data["favorites"]:
            data["favorites"].pop(key)
            selected = False
        else:
            row = _title({"id": identifier, "media": media, "title": title,
                "poster": poster, "year": year, "genres": genres or []})
            row["updated"] = time.time()
            data["favorites"][key] = row
            selected = True
        _write(data)
        return selected

def is_favorite(identifier, media):
    try:
        key = _key(identifier, media)
    except ValueError:
        return False
    with _LOCK:
        return key in _read()["favorites"]

def list_items(section):
    if section not in ("favorites", "continue", "history"):
        return []
    with _LOCK:
        data = _read()
    if section == "favorites":
        rows = list(data["favorites"].values())
    else:
        rows = list(data["history"].values())
        if section == "continue":
            rows = [r for r in rows if r.get("started") and not r.get("completed")]
    rows = [r for r in rows if isinstance(r, dict) and
            r.get("media") in ("movie", "series") and isinstance(r.get("id"), str) and _IMDB.fullmatch(r["id"])]
    rows.sort(key=lambda item: float(item.get("updated", 0)), reverse=True)
    return rows[:60]

def mark_started(request):
    try:
        key = _key(request["id"], request["media"])
    except (KeyError, ValueError, TypeError):
        return
    with _LOCK:
        data = _read()
        prior = data["history"].get(key, {})
        row = _title(request)
        row["started"] = True
        row["updated"] = time.time()
        row["position"] = float(prior.get("position", 0)) if isinstance(prior, dict) else 0
        row["duration"] = float(prior.get("duration", 0)) if isinstance(prior, dict) else 0
        row["completed"] = False
        if request.get("media") == "series":
            row["season"] = request.get("season")
            row["episode"] = request.get("episode")
        data["history"][key] = row
        _write(data)

def update_progress(request, seconds, duration, completed=False):
    try:
        key = _key(request["id"], request["media"])
        seconds = max(0, float(seconds))
        duration = max(0, float(duration))
    except (KeyError, ValueError, TypeError, OverflowError):
        return
    with _LOCK:
        data = _read()
        row = data["history"].get(key)
        if not isinstance(row, dict):
            return
        # Mark complete only after meaningful playback or the Kodi ended event.
        ratio = seconds / duration if duration > 0 else 0
        row.update(position=round(seconds, 1), duration=round(duration, 1),
            completed=bool(completed or (duration > 120 and ratio >= .92)),
            updated=time.time())
        data["history"][key] = row
        _write(data)

def preferred_genres():
    from collections import Counter
    favorites = list_items("favorites")
    counts = Counter((f.get("media"), str(genre).casefold()) for f in favorites for genre in f.get("genres", []))
    return [pair for pair, _ in counts.most_common(8)]
