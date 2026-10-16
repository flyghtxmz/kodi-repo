"""Combina fontes do Worker e do Torrentio direto, sem depender de uma só origem."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

import cloudflare_client
import torrentio_client


def _priority(item):
    language = str(item.get("language") or "unknown").casefold().replace("_", "-")
    language_rank = 3 if language in ("pt-br", "ptbr", "brazilian", "portugues", "português") else 2 if language == "pt" else 1 if language == "en" else 0
    quality_rank = {"4K": 4, "1080p": 3, "720p": 2, "480p": 1, "SD": 0}
    return (language_rank, quality_rank.get(item.get("quality"), 0), item.get("seeders") or 0)


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


def list_sources(title, year="", imdb=""):
    if not isinstance(title, str) or not title.strip():
        raise ValueError("O título não está disponível.")
    if imdb and (not isinstance(imdb, str) or not cloudflare_client.IMDB_ID.fullmatch(imdb)):
        raise ValueError("Identificador IMDb incorreto.")
    groups, failures = [], []
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {pool.submit(client.list_sources, title, year=year, imdb=imdb): name
                for name, client in (("Cloudflare", cloudflare_client), ("Torrentio", torrentio_client))
                if imdb or name == "Cloudflare"}
        for job in as_completed(jobs):
            try:
                groups.append(job.result())
            except Exception as error:
                failures.append(jobs[job])
                logging.getLogger(__name__).warning("Fonte %s indisponível (%s)", jobs[job], type(error).__name__)
    result = merge_sources(groups)
    if not result and len(failures) == len(jobs):
        raise ValueError("Não foi possível consultar Cloudflare/Torrentio.")
    return result
