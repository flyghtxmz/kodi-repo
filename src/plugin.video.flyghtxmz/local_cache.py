"""Bounded, atomic per-key cache; no credentials or arbitrary file paths."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time


def directory():
    try:
        import xbmcaddon
        import xbmcvfs
        profile = xbmcaddon.Addon().getAddonInfo('profile')
        if not profile:
            return None
        path = Path(xbmcvfs.translatePath(profile)) / 'http_cache'
        path.mkdir(parents=True, exist_ok=True)
        return path
    except (ImportError, AttributeError, OSError):
        return None


def get(key, ttl):
    root = directory()
    if root is None:
        return None
    path = root / (hashlib.sha256(key.encode()).hexdigest() + '.json')
    try:
        if path.stat().st_size > 2_100_000:
            return None
        value = json.loads(path.read_text(encoding='utf-8'))
        if 0 <= time.time() - float(value['at']) < ttl:
            return value['data']
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return None


def put(key, data):
    root = directory()
    if root is None:
        return
    temporary = None
    try:
        payload = json.dumps({'at': time.time(), 'data': data}, ensure_ascii=False)
        if len(payload.encode()) > 2_100_000:
            return
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=root, delete=False) as handle:
            temporary = handle.name
            handle.write(payload)
        os.replace(temporary, root / (hashlib.sha256(key.encode()).hexdigest() + '.json'))
        files = sorted(root.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        total = 0
        for index, path in enumerate(files):
            total += path.stat().st_size
            if index >= 100 or total > 12_000_000:
                path.unlink(missing_ok=True)
    except (OSError, ValueError, TypeError):
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def clear():
    root = directory()
    if root:
        for path in root.glob('*.json'):
            path.unlink(missing_ok=True)
        for name in ('metadata_ptbr_cache.json', 'torrentio_sources_cache.json', 'torrentio_sources_v2_cache.json'):
            (root.parent / name).unlink(missing_ok=True)
