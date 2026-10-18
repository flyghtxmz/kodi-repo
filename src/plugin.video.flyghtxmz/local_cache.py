"""Cache limitado ao perfil local do addon; não usa armazenamento remoto."""
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time

MAX_BYTES = 2_000_000
_lock = threading.RLock()


def path_for(name):
    if not re.fullmatch(r"[a-z_]+", name):
        raise ValueError("Nome de cache inválido.")
    try:
        import xbmcaddon
        import xbmcvfs
        profile = xbmcaddon.Addon().getAddonInfo("profile")
        if not profile:
            return None
        directory = Path(xbmcvfs.translatePath(profile))
        directory.mkdir(parents=True, exist_ok=True)
        return directory / (name + ".json")
    except (ImportError, AttributeError, OSError, ValueError):
        return None


def _read(path):
    try:
        if path is None or path.stat().st_size > MAX_BYTES:
            return {}
        result = json.loads(path.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def get(name, key):
    with _lock:
        entry = _read(path_for(name)).get(key)
    if not isinstance(entry, dict):
        return None
    started, ttl = entry.get("at"), entry.get("ttl")
    if not isinstance(started, (int, float)) or not isinstance(ttl, (int, float)):
        return None
    if not 0 <= time.time() - started < ttl:
        return None
    return entry.get("data")


def put(name, key, data, ttl=300, max_entries=64):
    path = path_for(name)
    if path is None:
        return
    temporary = None
    with _lock:
        cache = _read(path)
        cache[key] = {"at": time.time(), "ttl": ttl, "data": data}
        pairs = [(k, v) for k, v in cache.items() if isinstance(v, dict)
                 and isinstance(v.get("at"), (int, float))]
        pairs.sort(key=lambda pair: pair[1]["at"], reverse=True)
        pairs = pairs[:max_entries]
        payload = json.dumps(dict(pairs), ensure_ascii=False, separators=(",", ":"))
        while pairs and len(payload.encode("utf-8")) > MAX_BYTES:
            pairs.pop()
            payload = json.dumps(dict(pairs), ensure_ascii=False, separators=(",", ":"))
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=str(path.parent),
                                             prefix=".felipe-", suffix=".json", delete=False) as handle:
                temporary = handle.name
                handle.write(payload)
            os.replace(temporary, path)
        except OSError:
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
