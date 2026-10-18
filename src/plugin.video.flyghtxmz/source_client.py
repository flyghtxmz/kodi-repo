"""Combina o Worker e fontes Stremio diretas, isolando falhas de cada origem."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import unicodedata

import cloudflare_client
import torrentio_client
import mediafusion_client
import comet_client


def _priority(item):
    language = str(item.get("language") or "unknown").casefold().replace("_", "-")
    language_rank = 3 if language in ("pt-br", "ptbr", "brazilian", "portugues", "português") else 2 if language == "pt" else 1 if language == "en" else 0
    quality_rank = {"4K": 4, "1080p": 3, "720p": 2, "480p": 1, "SD": 0}
    # Dentro da preferência de idioma, privilegiar peers realmente informados
    # antes de resolução: 1080p com seeders tende a iniciar antes de 4K vazio.
    raw_seeds = item.get("seeders")
    try:
        seeds = max(0, int(raw_seeds)) if raw_seeds is not None else 0
    except (TypeError, ValueError):
        seeds = 0
    return (language_rank, 1 if seeds > 0 else 0, seeds,
            quality_rank.get(item.get("quality"), 0))


def merge_sources(groups):
    unique = {}
    for group in groups:
        for item in group[:100]:
            if not isinstance(item, dict) or not cloudflare_client.is_supported_source(item.get("url")):
                continue
            if cloudflare_client._is_removed_provider(item):
                continue
            index = item.get("file_index")
            if index is not None and (type(index) is not int or not 0 <= index <= 100_000):
                continue
            infohash = cloudflare_client._torrent_hash(item, item["url"])
            key = (infohash or item["url"], index)
            previous = unique.get(key)
            if previous is None or _priority(item) > _priority(previous):
                unique[key] = dict(item)
    # Havendo seleção explícita, descarte a opção genérica do mesmo pacote.
    indexed = {key[0] for key in unique if key[1] is not None}
    result = [value for key, value in unique.items() if key[1] is not None or key[0] not in indexed]
    result.sort(key=_priority, reverse=True)
    return result[:100]


def _worker_sources(title, year="", imdb=""):
    result = cloudflare_client.list_sources(title, year=year, imdb=imdb)
    if result or not imdb:
        return result
    try:
        from metadata_ptbr import localized_title
        translated = localized_title(imdb, "movie")
    except (ImportError, AttributeError, OSError, TypeError, ValueError):
        translated = ""
    def normalized(value):
        return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if c.isalnum())
    if isinstance(translated, str) and translated.strip() and normalized(translated) != normalized(title):
        return cloudflare_client.list_sources(translated[:120], year=year, imdb=imdb)
    return result


def list_sources(title, year="", imdb="", season=None, episode=None):
    if not isinstance(title, str) or not title.strip():
        raise ValueError("O título não está disponível.")
    if imdb and (not isinstance(imdb, str) or not cloudflare_client.IMDB_ID.fullmatch(imdb)):
        raise ValueError("Identificador IMDb incorreto.")
    # Séries são pesquisadas por episódio individual. Não enviamos a
    # pesquisa ao Worker legado (que aceita só título de filme): ele
    # poderia responder com uma fonte da série inteira/episódio errado.
    if season is not None or episode is not None:
        if (type(season) is not int or type(episode) is not int or
                not 0 <= season <= 999 or not 1 <= episode <= 9999 or not imdb):
            raise ValueError("Temporada ou episódio inválido.")
        selected = (("Torrentio", torrentio_client.list_sources), ("MediaFusion", mediafusion_client.list_sources),
                    ("Comet", comet_client.list_sources))
    else:
        selected = (("Cloudflare", _worker_sources), ("Torrentio", torrentio_client.list_sources),
                    ("MediaFusion", mediafusion_client.list_sources), ("Comet", comet_client.list_sources))
    groups, failures = [], []
    options = {"year": year, "imdb": imdb}
    if season is not None:
        options.update(season=season, episode=episode)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(search, title, **options): name
                for name, search in selected
                if imdb or name == "Cloudflare"}
        for job in as_completed(jobs):
            try:
                groups.append(job.result())
            except Exception as error:
                failures.append(jobs[job])
                logging.getLogger(__name__).warning("Fonte %s indisponível (%s)", jobs[job], type(error).__name__)
    result = merge_sources(groups)
    if not result and len(failures) == len(jobs):
        raise ValueError("Não foi possível consultar as fontes disponíveis.")
    return result
