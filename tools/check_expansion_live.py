"""Verifica metadados reais; --download-subtitle testa um SRT, sem baixar vídeos/torrents."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import sys
import tempfile
import time
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/plugin.video.flyghtxmz"))


def run(download_subtitle=False):
    reports = []
    with tempfile.TemporaryDirectory(prefix="felipe-live-") as directory:
        addon = types.ModuleType("xbmcaddon")
        addon.Addon = lambda: types.SimpleNamespace(
            getAddonInfo=lambda key: directory if key == "profile" else "",
            getSetting=lambda key: "https://felipe-videos-sources.felipemenezes36.workers.dev" if key == "cloudflare_endpoint" else "")
        vfs = types.ModuleType("xbmcvfs")
        vfs.translatePath = lambda path: path
        sys.modules.update(xbmcaddon=addon, xbmcvfs=vfs)
        import torrentio_client
        import mediafusion_client
        import comet_client
        import source_client
        import discovery
        import subtitles_client

        cases = [("Carrie", "2013", "tt1939659", None, None),
                 ("Cidade de Deus", "2002", "tt0317248", None, None),
                 ("Game of Thrones", "2011", "tt0944947", 1, 1)]
        for title, year, imdb, season, episode in cases:
            options = {"year": year, "imdb": imdb}
            if season is not None:
                options.update(season=season, episode=episode)
            started = time.monotonic()
            with ThreadPoolExecutor(max_workers=3) as pool:
                torrent = pool.submit(torrentio_client.list_sources, title, **options)
                fusion = pool.submit(mediafusion_client.list_sources, title, **options)
                comet = pool.submit(comet_client.list_sources, title, **options)
                first, second, third = torrent.result(), fusion.result(), comet.result()
            key = lambda row: (row.get("infoHash"), row.get("file_index"))
            extra = set(map(key, second)) - set(map(key, first))
            comet_extra = set(map(key, third)) - set(map(key, first + second))
            merged = source_client.merge_sources([first, second, third])
            report = {"kind": "sources", "title": title, "season": season, "episode": episode,
                      "torrentio": len(first), "mediafusion": len(second), "new_mediafusion_files": len(extra),
                      "comet": len(third), "new_comet_files": len(comet_extra),
                      "comet_after_merge": sum(row["source"] == "Comet" for row in merged),
                      "combined": len(merged), "mediafusion_after_merge": sum(row["source"] == "MediaFusion" for row in merged),
                      "seconds": round(time.monotonic() - started, 3)}
            print(json.dumps(report), flush=True)
            reports.append(report)
            assert second and third and merged, "A nova origem não retornou fontes utilizáveis"

        for media, kind, value in [("movie", "year", "1999"), ("movie", "language", "Portuguese"),
                                   ("movie", "country", "Brazil"), ("series", "anime", "")]:
            started = time.monotonic()
            items, more = discovery.list_titles(media, kind, value)
            report = {"kind": "catalog", "filter": kind, "value": value, "items": len(items), "more": more,
                      "imdb_valid": all(re.fullmatch(r"tt[0-9]{5,12}", row["id"]) for row in items),
                      "seconds": round(time.monotonic() - started, 3)}
            print(json.dumps(report), flush=True)
            reports.append(report)
            assert items and report["imdb_valid"], "Filtro de catálogo não retornou títulos válidos"

        subtitles = subtitles_client.list_subtitles({"title": "Carrie", "imdb": "tt1939659"})
        report = {"kind": "subtitles", "portuguese": len(subtitles), "pt_br": sum(row["language"] == "PT-BR" for row in subtitles)}
        if download_subtitle and subtitles:
            file = Path(subtitles_client.download(subtitles[0]))
            report["srt_download_valid"] = file.is_file()
            report["srt_bytes"] = file.stat().st_size
        print(json.dumps(report), flush=True)
        reports.append(report)
        assert subtitles and (not download_subtitle or report.get("srt_download_valid")), "Legendas não validadas"

    (ROOT / "expansion-live-verification.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--download-subtitle", action="store_true")
    run(arguments.parse_args().download_subtitle)
