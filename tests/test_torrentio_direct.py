"""Consulta direta, cache, combinação de origens e índices originais do torrent."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "src/plugin.video.flyghtxmz"
HASH = "a" * 40


class Response:
    status_code = 200

    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=8192):
        yield self.payload


def load(name):
    spec = importlib.util.spec_from_file_location(name, ADDON / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stream(**changes):
    row = {"infoHash": HASH, "name": "Torrentio\n1080p", "fileIdx": 0,
           "title": "Filme Dublado\n👤 12 💾 1.5 GB ⚙️ Comando\n🇵🇹"}
    row.update(changes)
    return row


class TorrentioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        requests = types.ModuleType("requests")
        requests.get = lambda *args, **kwargs: Response({"streams": []})
        addon = types.ModuleType("xbmcaddon")
        addon.Addon = lambda: types.SimpleNamespace(getSetting=lambda key: "https://example.workers.dev")
        with patch.dict(sys.modules, {"requests": requests, "xbmcaddon": addon}):
            cls.torrentio = load("torrentio_client")
            cls.cloudflare = load("cloudflare_client")
        cls.mediafusion = types.ModuleType("mediafusion_client")
        cls.mediafusion.list_sources = lambda *args, **kwargs: []
        cls.comet = types.ModuleType("comet_client")
        cls.comet.list_sources = lambda *args, **kwargs: []
        with patch.dict(sys.modules, {"torrentio_client": cls.torrentio, "cloudflare_client": cls.cloudflare,
                                     "mediafusion_client": cls.mediafusion, "comet_client": cls.comet}):
            cls.sources = load("source_client")
        cls.requests = requests

    def setUp(self):
        self.cache_patch = patch.object(self.torrentio, "_cache_path", return_value=None)
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)

    def test_parser_preserves_zero_and_original_index_and_language(self):
        rows = [stream(), stream(infoHash="b"*40, fileIdx=3),
                stream(infoHash="c"*40, fileIdx=None, title="Filme MULTI\n🇵🇹")]
        parsed = self.torrentio.parse_streams({"streams": rows})
        self.assertEqual([item.get("file_index") for item in parsed], [0, 3, None])
        self.assertEqual(parsed[0]["language"], "pt-br")
        self.assertEqual(parsed[2]["language"], "pt")
        self.assertEqual(parsed[0]["quality"], "1080p")
        self.assertEqual(parsed[0]["size"], 1_500_000_000)
        self.assertEqual(parsed[0]["seeders"], 12)
        self.assertEqual(parsed[0]["source"], "Torrentio / Comando")
        self.assertTrue(self.cloudflare.is_supported_source(parsed[0]["url"]))

    def test_parser_rejects_bad_hashes_indices_and_ambiguous_packs(self):
        rows = [stream(infoHash="invalid"), stream(fileIdx=-1), stream(fileIdx=True),
                stream(fileIdx="3"), stream(fileIdx=100_001),
                stream(fileIdx=None, title="Trilogia Dublado"),
                stream(infoHash="A"*32, fileIdx=2)]
        parsed = self.torrentio.parse_streams({"streams": rows})
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["infoHash"], "0"*40)
        self.assertEqual(parsed[0]["file_index"], 2)

    def test_magnet_includes_original_public_trackers(self):
        from urllib.parse import parse_qs, urlsplit
        result = self.torrentio.parse_streams({"streams": [stream(sources=[
            "dht:" + HASH,
            "tracker:udp://tracker.example.org:6969/announce",
            "tracker:https://tracker2.example.org/announce",
            "tracker:udp://tracker.example.org:6969/announce",
            "tracker:http://127.0.0.1:9090/announce",
            "tracker:ftp://invalid.example/announce",
        ])]})
        self.assertEqual(len(result), 1)
        magnet = result[0]["url"]
        params = parse_qs(urlsplit(magnet).query)
        self.assertEqual(params["tr"], [
            "udp://tracker.example.org:6969/announce",
            "https://tracker2.example.org/announce",
        ])
        self.assertEqual(params["xt"], ["urn:btih:" + HASH])
        self.assertEqual(result[0]["file_index"], 0)

    def test_no_invented_trackers_when_provider_omits_them(self):
        from urllib.parse import parse_qs, urlsplit
        uri = self.torrentio.parse_streams({"streams": [stream()]})[0]["url"]
        self.assertNotIn("tr", parse_qs(urlsplit(uri).query))

    def test_seeded_ptbr_1080p_outranks_unseeded_ptbr_4k(self):
        rows = self.torrentio.parse_streams({"streams": [
            stream(infoHash="b"*40, title="Filme Dublado\n👤 0 💾 12.5 GB", name="Torrentio 4K"),
            stream(infoHash="c"*40, title="Filme Dublado\n👤 24 💾 1.9 GB", name="Torrentio 1080p"),
        ]})
        ranked = self.sources.merge_sources([rows])
        self.assertEqual(ranked[0]["seeders"], 24)
        self.assertEqual(ranked[0]["quality"], "1080p")
        self.assertEqual(ranked[1]["seeders"], 0)

    def test_direct_request_uses_imdb_without_worker_or_token(self):
        with patch.object(self.requests, "get", return_value=Response({"streams": [stream()]})) as get:
            result = self.torrentio.list_sources("Filme", year="2008", imdb="tt1254207")
        self.assertEqual(len(result), 1)
        self.assertEqual(get.call_args.args[0], "https://torrentio.strem.fun/brazuca/stream/movie/tt1254207.json")
        self.assertNotIn("Authorization", get.call_args.kwargs["headers"])
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        self.assertEqual(get.call_args.kwargs["timeout"], (4, 8))

    def test_series_request_uses_exact_episode_identifier(self):
        with patch.object(self.requests, "get",
                          return_value=Response({"streams": [stream()]})) as get:
            results = self.torrentio.list_sources(
                "Game of Thrones", imdb="tt0944947", season=2, episode=8)
        self.assertEqual(len(results), 1)
        self.assertEqual(get.call_args.args[0],
            "https://torrentio.strem.fun/brazuca/stream/series/tt0944947:2:8.json")

    def test_series_requests_cache_each_episode_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            with patch.object(self.torrentio, "_cache_path", return_value=path), \
                    patch.object(self.requests, "get",
                                 return_value=Response({"streams": [stream()]})) as get:
                for season, episode in ((1, 1), (1, 3), (1, 1), (2, 8)):
                    self.torrentio.list_sources(
                        "Game of Thrones", imdb="tt0944947",
                        season=season, episode=episode)
                self.assertEqual(get.call_count, 3)
                stored = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(sorted(stored), [
                    "tt0944947:1:1", "tt0944947:1:3", "tt0944947:2:8"])

    def test_episode_lookup_skips_movie_worker(self):
        with patch.object(self.cloudflare, "list_sources") as worker, \
                patch.object(self.torrentio, "list_sources",
                             return_value=[self.torrentio.parse_streams(
                                 {"streams": [stream()]})[0]]) as torrent:
            result = self.sources.list_sources(
                "Game of Thrones", imdb="tt0944947", season=2, episode=8)
        worker.assert_not_called()
        self.assertEqual(torrent.call_args.kwargs["season"], 2)
        self.assertEqual(torrent.call_args.kwargs["episode"], 8)
        self.assertEqual(len(result), 1)

    def test_episode_numbers_must_be_valid(self):
        for season, episode in ((None, 1), (1, None), (-1, 1),
                                (1, 0), (True, 2), (2, True), (1000, 1)):
            with self.subTest(season=season, episode=episode):
                with self.assertRaises(ValueError):
                    self.sources.list_sources(
                        "Game of Thrones", imdb="tt0944947",
                        season=season, episode=episode)

    def test_invalid_imdb_never_causes_a_request(self):
        with patch.object(self.requests, "get") as get:
            self.assertEqual(self.torrentio.list_sources("Filme"), [])
            for imdb in ("../secret", "https://localhost", "tt123/../../", "bad"):
                with self.assertRaises(ValueError):
                    self.torrentio.list_sources("Filme", imdb=imdb)
            get.assert_not_called()

    def test_local_cache_is_reused_and_expired_entries_are_refreshed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            with patch.object(self.torrentio, "_cache_path", return_value=path), \
                    patch.object(self.requests, "get", return_value=Response({"streams": [stream()]})) as get:
                first = self.torrentio.list_sources("Filme", imdb="tt1254207")
                self.assertEqual(first, self.torrentio.list_sources("Filme", imdb="tt1254207"))
                self.assertEqual(get.call_count, 1)
                data = json.loads(path.read_text(encoding="utf-8"))
                data["tt1254207"]["at"] = 0
                path.write_text(json.dumps(data), encoding="utf-8")
                self.torrentio.list_sources("Filme", imdb="tt1254207")
                self.assertEqual(get.call_count, 2)

    def test_oversized_or_invalid_responses_fail_without_saving_cache(self):
        for response in (Response({"invalid": []}), Response({"streams": [], "large": "x"*500_000})):
            with patch.object(self.requests, "get", return_value=response), \
                    patch.object(self.torrentio, "_write_cache") as write:
                with self.assertRaises(ValueError):
                    self.torrentio.list_sources("Filme", imdb="tt1254207")
                write.assert_not_called()

    def test_quick_mode_returns_torrentio_without_querying_all_providers(self):
        item = self.torrentio.parse_streams({"streams": [stream()]})[0]
        with patch.object(self.torrentio, "list_sources", return_value=[item]) as primary, \
                patch.object(self.cloudflare, "list_sources") as worker, \
                patch.object(self.mediafusion, "list_sources") as media, \
                patch.object(self.comet, "list_sources") as comet:
            result = self.sources.list_sources("Filme", imdb="tt1254207", quick=True)
        self.assertEqual(result, [item])
        primary.assert_called_once()
        worker.assert_not_called()
        media.assert_not_called()
        comet.assert_not_called()

    def test_quick_mode_falls_back_to_other_providers_on_empty_or_error(self):
        item = self.torrentio.parse_streams({"streams": [stream()]})[0]
        for primary_answer in ([], OSError("Torrentio indisponível")):
            with self.subTest(primary_answer=str(primary_answer)):
                kwargs = ({"side_effect": primary_answer}
                          if isinstance(primary_answer, Exception)
                          else {"return_value": primary_answer})
                with patch.object(self.torrentio, "list_sources", **kwargs) as primary, \
                        patch.object(self.cloudflare, "list_sources", return_value=[item]) as worker, \
                        patch.object(self.mediafusion, "list_sources", return_value=[]), \
                        patch.object(self.comet, "list_sources", return_value=[]):
                    result = self.sources.list_sources("Filme", imdb="tt1254207", quick=True)
                self.assertEqual(result, [item])
                primary.assert_called_once()
                worker.assert_called_once()

    def test_dubbed_audio_marked_from_description_filename_and_language_fields(self):
        rows = [
            stream(infoHash="f" * 40, title="Título original", name="Torrentio",
                   description="Português Brasileiro Dublado"),
            stream(infoHash="e" * 40, title="Título original", name="Torrentio",
                   behaviorHints={"filename": "Nome.2026.PT.BR.1080p.mkv"}),
            stream(infoHash="d" * 40, title="Título original", name="Torrentio",
                   languages=["Brazilian Portuguese"]),
            stream(infoHash="c" * 40, title="Título original", name="Torrentio",
                   description="English", sources=["MicoLeaoDublado"]),
        ]
        found = self.torrentio.parse_streams({"streams": rows})
        self.assertEqual([source["language"] for source in found],
                         ["pt-br", "pt-br", "pt-br", "en"])

    def test_quick_lookup_without_ptbr_queries_other_providers(self):
        item_unknown = self.torrentio.parse_streams({
            "streams": [stream(infoHash="a"*40, title="Filme 1080p sem legenda", name="Torrentio")]})[0]
        item_brazil = self.torrentio.parse_streams({
            "streams": [stream(infoHash="b"*40, title="Filme Dublado", name="Torrentio")]})[0]
        with patch.object(self.torrentio, "list_sources", return_value=[item_unknown]) as primary, \
                patch.object(self.cloudflare, "list_sources", return_value=[item_brazil]) as worker, \
                patch.object(self.mediafusion, "list_sources", return_value=[]), \
                patch.object(self.comet, "list_sources", return_value=[]):
            found = self.sources.list_sources("Filme", imdb="tt1254207", quick=True)
        self.assertEqual(found[0]["language"], "pt-br")
        self.assertEqual(len(found), 2)
        primary.assert_called_once()
        worker.assert_called_once()

    def test_sources_are_fetched_in_parallel(self):
        barrier = threading.Barrier(2)
        item = self.torrentio.parse_streams({"streams": [stream()]})[0]
        def provider(*args, **kwargs):
            barrier.wait(timeout=3)
            return [item]
        with patch.object(self.cloudflare, "list_sources", side_effect=provider), \
                patch.object(self.torrentio, "list_sources", side_effect=provider):
            self.assertEqual(len(self.sources.list_sources("Filme", imdb="tt1254207")), 1)

    def test_one_provider_failure_does_not_hide_the_other(self):
        item = self.torrentio.parse_streams({"streams": [stream()]})[0]
        for first, second in ((self.cloudflare, self.torrentio), (self.torrentio, self.cloudflare)):
            with patch.object(first, "list_sources", side_effect=OSError("offline")), \
                    patch.object(second, "list_sources", return_value=[item]):
                self.assertEqual(self.sources.list_sources("Filme", imdb="tt1254207"), [item])
        with patch.object(self.cloudflare, "list_sources", side_effect=OSError("offline")), \
                patch.object(self.torrentio, "list_sources", side_effect=OSError("offline")), \
                patch.object(self.mediafusion, "list_sources", side_effect=OSError("offline")), \
                patch.object(self.comet, "list_sources", side_effect=OSError("offline")):
            with self.assertRaises(ValueError):
                self.sources.list_sources("Filme", imdb="tt1254207")

    def test_deduplication_keeps_distinct_files_and_prefers_explicit_selection(self):
        indexed = self.torrentio.parse_streams({"streams": [stream(), stream(fileIdx=3)]})
        unindexed = {**indexed[0], "source": "Worker", "file_index": None}
        result = self.sources.merge_sources([[unindexed], indexed, indexed])
        self.assertEqual(len(result), 2)
        self.assertEqual({item["file_index"] for item in result}, {0, 3})

    def test_generic_portuguese_does_not_outrank_explicit_pt_br(self):
        rows = self.torrentio.parse_streams({"streams": [
            stream(infoHash="b"*40, fileIdx=None, name="Torrentio 4K", title="Filme\n🇵🇹"),
            stream(fileIdx=None, name="Torrentio 720p"),
        ]})
        ordered = self.sources.merge_sources([rows])
        self.assertEqual(ordered[0]["language"], "pt-br")


if __name__ == "__main__":
    unittest.main()
