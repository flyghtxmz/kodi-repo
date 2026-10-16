"""Seleciona mídia em português e resolve a fonte com serviços configurados."""
import json
import re
from pathlib import Path

import xbmc
import xbmcaddon

from .debrid import resolve_magnet
from .torrent_search import search_torrents, _infer_quality

ADDON = xbmcaddon.Addon()
PT_TERMS = (
    "dublado", "dual", "pt-br", "portugues", "português",
    "nacional", "brazilian", "br-",
)
RANK = {"SD": 0, "480p": 1, "720p": 2, "1080p": 3, "4K": 4}
MAPPING = Path(__file__).resolve().parents[1] / "data" / "mapping.json"


def _log(message):
    xbmc.log("Felipe Vídeos / fontes: " + message, xbmc.LOGERROR)


def _pt_audio(title):
    """Marcadores de release são uma preferência, não prova do áudio contido."""
    name = title.casefold() if isinstance(title, str) else ""
    return any(term in name for term in PT_TERMS)


def _read_mapping(imdb_id):
    """Fallback opcional; não interpreta JSON como código."""
    if not isinstance(imdb_id, str) or not re.fullmatch(r"tt\d{5,12}", imdb_id):
        return []
    if not MAPPING.is_file() or MAPPING.stat().st_size > 500_000:
        return []
    with MAPPING.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    item = payload.get(imdb_id) or {}
    return item.get("sources") or [] if isinstance(item, dict) else []


def get_playable_url(imdb_id, title, year):
    """Tenta até 5 fontes que atendem aos limites configurados."""
    try:
        quality = ADDON.getSetting("min_quality").strip() or "1080p"
        rank = RANK.get(quality, 3)
        min_seeders = max(0, int(ADDON.getSetting("min_seeders") or "3"))
        prowlarr_url = ADDON.getSetting("prowlarr_url").strip()
        tag = ADDON.getSetting("prowlarr_language_tag").strip()
        if prowlarr_url:
            candidates = search_torrents(imdb_id, title, year, language_tag=tag)
        else:
            candidates = _read_mapping(imdb_id)
        matches = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            release = str(item.get("title") or "")
            if not _pt_audio(release):
                continue
            try:
                seeds = int(item.get("seeders") or 0)
            except (ValueError, TypeError):
                seeds = 0
            quality_label = item.get("quality") or _infer_quality(release)
            if seeds < min_seeders or RANK.get(quality_label, 0) < rank:
                continue
            if not isinstance(item.get("magnet"), str):
                continue
            if not item["magnet"].startswith("magnet:?"):
                continue
            matches.append((RANK[quality_label], seeds, item))
        matches.sort(key=lambda row: (row[0], row[1]), reverse=True)
        for _, _, source in matches[:5]:
            playable_url = resolve_magnet(source["magnet"])
            if playable_url:
                public_info = {k: source.get(k) for k in
                               ("title", "quality", "seeders", "size", "source")}
                return playable_url, public_info
    except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as error:
        _log("Falha nas preferências/fontes (%s)" % type(error).__name__)
    return None, None
