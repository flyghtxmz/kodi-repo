"""Novas fontes, filtros com IMDb confirmado, cache e legendas escolhidas pelo usuário."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "src/plugin.video.flyghtxmz"
HASH = "a" * 40


class Response:
    status_code = 200

    def __init__(self, body=None, raw=None):
        self.raw = json.dumps(body).encode() if raw is None else raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=8192):
        yield self.raw


def load(name):
    spec = importlib.util.spec_from_file_location(name, ADDON / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def meta(identifier="tt0317248", name="Cidade de Deus", **other):
    return {"id": "tmdb:598", "name": name, "type": "movie", "releaseInfo": "2002",
            "links": [{"category": "imdb", "url": "https://imdb.com/title/" + identifier}], **other}


class ExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        request = types.ModuleType("requests")
        request.get = lambda *args, **kwargs: Response({"streams": []})
        addon = types.ModuleType("xbmcaddon")
        addon.Addon = lambda: types.SimpleNamespace(getSetting=lambda key: "https://example.workers.dev")
        cls.modules = {"requests": request, "xbmcaddon": addon}
        with patch.dict(sys.modules, cls.modules):
            for name in ["local_cache", "torrentio_client", "cloudflare_client", "metadata_ptbr", "recent",
                         "mediafusion_client", "comet_client", "discovery", "subtitles_client", "source_client"]:
                module = load(name)
                cls.modules[name] = module
                sys.modules[name] = module
                setattr(cls, name, module)
        cls.request = request

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        patched = patch.object(self.local_cache, "path_for", side_effect=lambda name: Path(self.directory.name) / (name + ".json"))
        patched.start()
        self.addCleanup(patched.stop)

    def test_mediafusion_preserves_index_trackers_and_does_not_invent_seeders(self):
        body = {"streams": [{"infoHash": HASH, "fileIdx": 9, "name": "MediaFusion 2160p",
            "description": "🌐 English + Portuguese\n▶️ 311", "behaviorHints": {"filename": "Show.S01E01.mkv", "videoSize": 1000000000},
            "sources": ["tracker:udp://tracker.example.org:80/announce"]}]}
        row = self.mediafusion_client.parse_streams(body)[0]
        self.assertEqual(row["file_index"], 9)
        self.assertEqual(row["source"], "MediaFusion")
        self.assertEqual(row["language"], "pt")
        self.assertIsNone(row["seeders"])
        self.assertIn("tr=", row["url"])
        self.assertEqual(row["size"], 1000000000)

    def test_mediafusion_episode_request_and_cache_are_independent(self):
        body = {"streams": [{"infoHash": HASH, "fileIdx": 0, "title": "Episode"}]}
        with patch.object(self.request, "get", return_value=Response(body)) as get:
            for episode in (1, 1, 2):
                self.mediafusion_client.list_sources("Show", imdb="tt0944947", season=1, episode=episode)
        self.assertEqual(get.call_count, 2)
        self.assertIn("/stream/series/tt0944947:1:2.json", get.call_args.args[0])
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_second_series_provider_survives_torrentio_failure(self):
        sample = self.mediafusion_client.parse_streams({"streams": [{"infoHash": HASH, "fileIdx": 4, "title": "Episode"}]})
        with patch.object(self.torrentio_client, "list_sources", side_effect=OSError("offline")), \
                patch.object(self.mediafusion_client, "list_sources", return_value=sample), \
                patch.object(self.comet_client, "list_sources", return_value=[]), \
                patch.object(self.cloudflare_client, "list_sources") as worker:
            found = self.source_client.list_sources("Show", imdb="tt0944947", season=1, episode=1)
        self.assertEqual(found, sample)
        worker.assert_not_called()

    def test_comet_keeps_portuguese_after_first_100_and_exact_file_index(self):
        rows = [{"infoHash": format(index, "040x"), "fileIdx": 0, "name": "Comet 2160p",
                 "description": "English", "behaviorHints": {"filename": "Movie.mkv"}}
                for index in range(101)]
        rows.append({"infoHash": HASH, "fileIdx": 7, "name": "Comet 1080p",
                     "description": "🇧🇷", "behaviorHints": {"filename": "Movie.S01E02.mkv"}})
        parsed = self.comet_client.parse_streams({"streams": rows})
        self.assertEqual(len(parsed), 100)
        self.assertEqual(parsed[0]["language"], "pt-br")
        self.assertEqual(parsed[0]["file_index"], 7)
        self.assertEqual(parsed[0]["source"], "Comet")

    def test_comet_cache_and_response_size_limit(self):
        with patch.object(self.request, "get", return_value=Response({"streams": []})) as get:
            self.comet_client.list_sources("Movie", imdb="tt1939659")
            self.comet_client.list_sources("Movie", imdb="tt1939659")
        self.assertEqual(get.call_count, 1)
        with patch.object(self.request, "get", return_value=Response(raw=b"x" * (self.comet_client.MAX_BYTES + 1))):
            with self.assertRaises(ValueError):
                self.comet_client.list_sources("Show", imdb="tt0944947", season=1, episode=1)

    def test_worker_retries_localized_title_only_for_empty_search(self):
        localized = types.ModuleType("metadata_ptbr")
        localized.localized_title = lambda *args: "Cidade de Deus"
        with patch.dict(sys.modules, {"metadata_ptbr": localized}), \
                patch.object(self.cloudflare_client, "list_sources", side_effect=[[], [{"source": "found"}]]) as query:
            result = self.source_client._worker_sources("City of God", year="2002", imdb="tt0317248")
        self.assertTrue(result)
        self.assertEqual([call.args[0] for call in query.call_args_list], ["City of God", "Cidade de Deus"])
        self.assertEqual(query.call_args.kwargs["imdb"], "tt0317248")
        with patch.object(self.cloudflare_client, "list_sources", return_value=[{"source": "already found"}]) as query:
            self.source_client._worker_sources("City of God", year="2002", imdb="tt0317248")
        self.assertEqual(query.call_count, 1)

    def test_tmdb_catalog_id_is_resolved_only_through_valid_imdb_identity(self):
        self.assertEqual(self.discovery.imdb_for(meta()), "tt0317248")
        self.assertEqual(self.discovery.imdb_for({"id": "tmdb:598"}), "")
        evil = meta(links=[{"category": "imdb", "url": "https://imdb.com.attacker.org/title/tt0317248"}])
        self.assertEqual(self.discovery.imdb_for(evil), "")

    def test_country_requires_confirmation_and_reuses_page_cache(self):
        def fetch(url):
            if "/catalog/" in url:
                return {"metas": [meta(), meta("tt9999999", "Filme de Portugal")]}
            identifier = url.rsplit("/", 1)[1].split(".")[0]
            return {"meta": {"imdb_id": identifier, "country": "Brazil, France" if identifier == "tt0317248" else "Portugal"}}
        with patch.object(self.discovery, "fetch", side_effect=fetch) as fetcher:
            items, more = self.discovery.list_titles("movie", "country", "Brazil")
            again, _ = self.discovery.list_titles("movie", "country", "Brazil")
        self.assertEqual([row["id"] for row in items], ["tt0317248"])
        self.assertEqual(items, again)
        self.assertFalse(more)
        self.assertEqual(fetcher.call_count, 3)

    def test_anime_filter_excludes_live_action_and_keeps_imdb(self):
        with patch.object(self.discovery, "fetch", return_value={"metas": [meta(type="series", genre=["Animação"]), meta("tt9999999", type="series", genre=["Drama"])]}) as get:
            found, _ = self.discovery.list_titles("series", "anime", "")
        self.assertEqual(len(found), 1)
        self.assertIn("genre=Japanese", get.call_args.args[0])

    def test_invalid_catalog_parameters_never_reach_network(self):
        with patch.object(self.discovery, "fetch") as fetch, patch.object(self.recent, "fetch") as recent:
            for media, kind, value in [("tv", "year", "2002"), ("movie", "year", "../../"),
                                        ("movie", "country", "invented"), ("movie", "language", "../")]:
                with self.assertRaises(ValueError):
                    self.discovery.list_titles(media, kind, value)
            fetch.assert_not_called()
            recent.assert_not_called()

    def test_year_filter_uses_actual_year_and_pagination(self):
        with patch.object(self.recent, "fetch", return_value={"metas": [meta(imdb_id="tt0317248", releaseInfo="1999")]}) as get:
            found, _ = self.discovery.list_titles("movie", "year", "1999", page=3)
        self.assertIn("genre=1999&skip=40", get.call_args.args[0])
        self.assertEqual(found[0]["id"], "tt0317248")

    def test_subtitle_list_filters_language_origin_and_duplicates(self):
        url = "https://subs5.strem.io/en/download/subencoding-stremio-utf8/file/1"
        rows = [{"lang": "por", "url": url, "movieReleaseName": "Português"},
                {"lang": "pob", "url": url+"2", "movieReleaseName": "Brasil"},
                {"lang": "eng", "url": url+"3"}, {"lang": "pob", "url": "https://localhost/private"},
                {"lang": "pob", "url": url+"2"}]
        with patch.object(self.request, "get", return_value=Response({"subtitles": rows})) as get:
            found = self.subtitles_client.list_subtitles({"imdb": "tt0944947", "season": 1, "episode": 1})
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0]["language"], "PT-BR")
        self.assertIn("/subtitles/series/tt0944947:1:1.json", get.call_args.args[0])

    def test_subtitle_download_rejects_html_and_saves_only_srt(self):
        row = {"url": "https://subs5.strem.io/en/download/file/1"}
        with patch.object(self.request, "get", return_value=Response(raw=b"<html>Error</html>")):
            with self.assertRaises(ValueError):
                self.subtitles_client.download(row)
        data = b"1\n00:00:01,000 --> 00:00:02,000\nTexto de teste\n"
        with patch.object(self.request, "get", return_value=Response(raw=data)):
            filename = self.subtitles_client.download(row)
        self.assertTrue(Path(filename).is_file())
        self.assertTrue(filename.endswith(".srt"))

    def test_context_is_local_and_expires(self):
        self.subtitles_client.save_context("Episode", "tt0944947", season=2, episode=3)
        item = self.local_cache.get("playback_context", "selected")
        self.assertEqual(item["episode"], 3)
        with patch.object(self.local_cache.time, "time", return_value=10**15):
            self.assertIsNone(self.local_cache.get("playback_context", "selected"))

    def test_metadata_fallback_preserves_episode_identity_and_does_not_replace_imdb_rating(self):
        value = {"imdb_id": "tt0944947", "type": "series", "name": "Série", "imdbRating": "9.9",
                 "videos": [{"id": "tmdb:1399:2:8", "season": 2, "episode": 8, "title": "Episódio oito"}]}
        with patch.object(self.discovery, "fetch", return_value={"meta": value}):
            found = self.discovery.metadata("tt0944947", "series")
        self.assertNotIn("imdbRating", found)
        self.assertEqual(found["id"], "tt0944947")
        self.assertEqual(found["videos"][0]["id"], "tt0944947:2:8")
        with patch.object(self.discovery, "fetch", return_value={"meta": {**value, "imdb_id": "tt9999999"}}):
            with self.assertRaises(ValueError):
                self.discovery.metadata("tt0944948", "series")

    def test_recent_detail_uses_verified_fallback_when_cinemeta_is_missing(self):
        fallback = {"id": "tt0317248", "imdb_id": "tt0317248", "type": "movie", "name": "Cidade de Deus"}
        metadata = types.ModuleType("metadata_ptbr")
        metadata.enrich = lambda *args, **kwargs: ("Sinopse", "", 0)
        metadata.localized_title = lambda *args: "Cidade de Deus"
        with patch.dict(sys.modules, {"discovery": self.discovery, "metadata_ptbr": metadata}), \
                patch.object(self.recent, "fetch", return_value={"meta": None}), \
                patch.object(self.discovery, "metadata", return_value=fallback) as query:
            found = self.recent.detail("tt0317248", media="movie")
        query.assert_called_once_with("tt0317248", "movie")
        self.assertEqual(found["id"], "tt0317248")


if __name__ == "__main__":
    unittest.main()
