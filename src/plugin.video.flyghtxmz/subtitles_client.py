"""Busca de legendas PT-BR/PT por título, aplicada somente por escolha do usuário."""
import hashlib
import json
import re
from urllib.parse import urlsplit

import requests
import local_cache
import torrentio_client

BASE_URL = "https://opensubtitles-v3.strem.io"


def valid_url(value):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 for c in value):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and bool(re.fullmatch(r"subs[0-9]*\.strem\.io", url.hostname or ""))
                and not url.username and not url.password and url.port in (None, 443) and not url.fragment)
    except ValueError:
        return False


def save_context(title, imdb, season=None, episode=None):
    if not isinstance(imdb, str) or not torrentio_client.IMDB_ID.fullmatch(imdb):
        return
    if season is not None or episode is not None:
        if type(season) is not int or type(episode) is not int or not 0 <= season <= 999 or not 1 <= episode <= 9999:
            return
    local_cache.put("playback_context", "selected", {"title": str(title)[:180], "imdb": imdb,
                    "season": season, "episode": episode}, ttl=21600, max_entries=1)


def list_subtitles(context):
    imdb = context.get("imdb")
    if not isinstance(imdb, str) or not torrentio_client.IMDB_ID.fullmatch(imdb):
        raise ValueError("Selecione um título no Felipe Vídeos.")
    season, episode = context.get("season"), context.get("episode")
    kind, identifier = "movie", imdb
    if season is not None or episode is not None:
        if type(season) is not int or type(episode) is not int or not 0 <= season <= 999 or not 1 <= episode <= 9999:
            raise ValueError("Episódio inválido.")
        kind, identifier = "series", "{}:{}:{}".format(imdb, season, episode)
    hit = local_cache.get("subtitle_lists", identifier)
    if isinstance(hit, list):
        return hit
    with requests.get(BASE_URL + "/subtitles/" + kind + "/" + identifier + ".json",
                      headers={"User-Agent": "FelipeVideos/1.5.0 (Kodi)", "Accept": "application/json"},
                      timeout=(4, 8), stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if getattr(response, "status_code", 200) != 200:
            raise ValueError("Resposta de legendas inválida.")
        raw = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            raw.extend(chunk)
            if len(raw) > 500_000:
                raise ValueError("Resposta de legendas excedeu o limite.")
    body = json.loads(raw.decode("utf-8"))
    if not isinstance(body, dict) or not isinstance(body.get("subtitles"), list):
        raise ValueError("Resposta de legendas inválida.")
    result, seen = [], set()
    for row in body["subtitles"][:500]:
        if not isinstance(row, dict) or row.get("lang") not in ("pob", "por", "pt", "pt-BR") or not valid_url(row.get("url")):
            continue
        url = row["url"]
        if url in seen:
            continue
        seen.add(url)
        name = str(row.get("movieReleaseName") or row.get("subtitleFileName") or "Legenda em português")[:160]
        language = "PT-BR" if row["lang"] in ("pob", "pt-BR") else "PT"
        result.append({"url": url, "label": language + " | " + name, "language": language})
    result.sort(key=lambda row: row["language"] != "PT-BR")
    local_cache.put("subtitle_lists", identifier, result, ttl=3600 if result else 60)
    return result


def download(row):
    url = row.get("url")
    if not valid_url(url):
        raise ValueError("Origem da legenda inválida.")
    path = local_cache.path_for("subtitle_download")
    if path is None:
        raise ValueError("Não foi possível acessar o armazenamento do addon.")
    raw = bytearray()
    with requests.get(url, headers={"User-Agent": "FelipeVideos/1.5.0 (Kodi)"},
                      timeout=(4, 8), stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if getattr(response, "status_code", 200) != 200:
            raise ValueError("O download da legenda não respondeu corretamente.")
        for chunk in response.iter_content(chunk_size=8192):
            raw.extend(chunk)
            if len(raw) > 2_000_000:
                raise ValueError("Legenda excedeu o limite.")
    text = bytes(raw).decode("utf-8-sig")
    if not re.search(r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->", text):
        raise ValueError("O serviço não retornou uma legenda SRT válida.")
    destination = path.parent / ("felipe_subtitle_" + hashlib.sha256(url.encode()).hexdigest()[:16] + ".srt")
    destination.write_text(text, encoding="utf-8")
    files = sorted(path.parent.glob("felipe_subtitle_*.srt"), key=lambda item: item.stat().st_mtime, reverse=True)
    for old in files[5:]:
        if re.fullmatch(r"felipe_subtitle_[a-f0-9]{16}\.srt", old.name):
            try:
                old.unlink()
            except OSError:
                pass
    return str(destination)
