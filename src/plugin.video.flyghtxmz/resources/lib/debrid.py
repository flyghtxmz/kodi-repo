"""Resolve um magnet em URL HTTPS via serviço debrid configurado no Kodi."""
import time
from urllib.parse import urlsplit

import requests
import xbmc
import xbmcaddon

ADDON = xbmcaddon.Addon()
TIMEOUT = 20
RETRIES = 30
BASE_RD = "https://api.real-debrid.com/rest/1.0"
BASE_TB = "https://api.torbox.app/v1/api"
VIDEO_EXTENSIONS = (".mkv", ".mp4", ".m4v", ".avi", ".mov", ".webm", ".ts")


def _log(message):
    xbmc.log("Felipe Vídeos / debrid: " + message, xbmc.LOGERROR)


def _request(method, url, token, **kwargs):
    response = requests.request(
        method,
        url,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        timeout=TIMEOUT,
        **kwargs
    )
    response.raise_for_status()
    if response.status_code == 204 or not response.content:
        return {}
    return response.json()


def _safe_video(items):
    """Seleciona o maior vídeo que não pareça preview ou sample."""
    videos = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        filename = str(item.get("path") or item.get("name") or item.get("short_name") or "")
        low = filename.casefold()
        if not low.endswith(VIDEO_EXTENSIONS):
            continue
        if any(part in low for part in ("sample", "preview", "trailer", "extras")):
            continue
        try:
            size = int(item.get("bytes") or item.get("size") or 0)
        except (ValueError, TypeError):
            size = 0
        videos.append((size, item))
    return max(videos, key=lambda pair: pair[0])[1] if videos else None


def _verified_url(value):
    if not isinstance(value, str):
        return None
    u = urlsplit(value)
    return value if u.scheme == "https" and u.netloc else None


def _realdebrid(magnet, token):
    base = BASE_RD + "/torrents"
    torrent = _request("POST", base + "/addMagnet", token, data={"magnet": magnet})
    ident = torrent.get("id")
    if not ident:
        return None
    _request("POST", base + "/selectFiles/" + str(ident), token, data={"files": "all"})
    for attempt in range(RETRIES):
        info = _request("GET", base + "/info/" + str(ident), token)
        status = info.get("status") or ""
        if status in ("magnet_error", "error", "virus", "dead"):
            return None
        if status == "downloaded":
            selected = [f for f in info.get("files") or [] if f.get("selected")]
            chosen = _safe_video(selected)
            if not chosen:
                return None
            # links seguem a ordem dos arquivos selecionados no retorno da API.
            try:
                index = next(i for i, row in enumerate(selected)
                             if row.get("id") == chosen.get("id"))
                selected_link = (info.get("links") or [])[index]
            except (IndexError, StopIteration):
                return None
            result = _request("POST", BASE_RD + "/unrestrict/link",
                              token, data={"link": selected_link})
            return _verified_url(result.get("download"))
        if attempt < RETRIES - 1:
            time.sleep(2)
    return None


def _torbox(magnet, token):
    base = BASE_TB + "/torrents"
    result = _request("POST", base + "/createtorrent", token,
                      data={"magnet": magnet})
    data = result.get("data") or {}
    ident = data.get("torrent_id") or data.get("id") if isinstance(data, dict) else None
    if not ident:
        return None
    for attempt in range(RETRIES):
        payload = _request("GET", base + "/mylist", token, params={"id": str(ident)})
        record = payload.get("data") or {}
        if isinstance(record, list):
            record = next((r for r in record if str(r.get("id")) == str(ident)), {})
        if not isinstance(record, dict):
            record = {}
        status = str(record.get("download_state") or record.get("status") or "").casefold()
        if status in ("error", "failed", "dead", "cancelled"):
            return None
        if record.get("download_finished") or status in ("completed", "ready", "cached"):
            selected = _safe_video(record.get("files") or [])
            if not selected:
                return None
            file_id = selected.get("id") or selected.get("file_id")
            if file_id is None:
                return None
            direct = _request("GET", base + "/requestdl", token,
                              params={"torrent_id": str(ident), "file_id": file_id})
            data = direct.get("data")
            return _verified_url(data if isinstance(data, str) else
                                 (data or {}).get("url"))
        if attempt < RETRIES - 1:
            time.sleep(2)
    return None


def resolve_magnet(magnet):
    """Resolve o link configurado sem gravar tokens em código ou logs."""
    token = ADDON.getSetting("debrid_token").strip()
    provider = ADDON.getSetting("debrid_provider").strip() or "realdebrid"
    if not token or not isinstance(magnet, str) or not magnet.startswith("magnet:?"):
        return None
    try:
        if provider == "torbox":
            return _torbox(magnet, token)
        if provider == "realdebrid":
            return _realdebrid(magnet, token)
    except (requests.RequestException, ValueError, TypeError, KeyError, IndexError) as exc:
        _log("Falha ao resolver (%s)" % type(exc).__name__)
    return None
