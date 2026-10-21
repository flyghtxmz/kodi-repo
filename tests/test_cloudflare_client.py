"""Testes locais do cliente Kodi com provedores independentes."""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "src/plugin.video.flyghtxmz/cloudflare_client.py"


class FakeResponse:
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


class CloudflareClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        addon = types.ModuleType("xbmcaddon")
        addon.Addon = lambda: types.SimpleNamespace(getSetting=lambda key: {
            "cloudflare_endpoint": "https://felipe-example.workers.dev",
        }.get(key, ""))
        requests = types.ModuleType("requests")
        requests.get = lambda *args, **kwargs: FakeResponse({"sources": []})
        with patch.dict(sys.modules, {"xbmcaddon": addon, "requests": requests}):
            spec = importlib.util.spec_from_file_location("cloudflare_client_under_test", PATH)
            cls.client = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.client)
        cls.requests = requests

    def test_worker_requires_https(self):
        self.assertEqual(self.client._worker_url("https://test.workers.dev/"),
                         "https://test.workers.dev")
        for url in ("http://example.org", "https://user:pass@host/",
                    "https://test.workers.dev/foo", "file:///etc/passwd"):
            with self.assertRaises(ValueError):
                self.client._worker_url(url)

    def test_magnet_and_https_torrent_are_valid(self):
        self.assertTrue(self.client.is_supported_source(
            "magnet:?xt=urn:btih:" + "a" * 40))
        self.assertTrue(self.client.is_supported_source(
            "https://media.example.org/film.torrent?download=1"))
        for uri in ("http://media.example.org/film.torrent",
                    "https://archive.org/download/x/x_archive.torrent",
                    "https://127.0.0.1/file.torrent",
                    "https://localhost/file.torrent",
                    "https://example.org/video.mp4",
                    "magnet:?xt=invalid",
                    "javascript:alert(1)"):
            self.assertFalse(self.client.is_supported_source(uri))

    def test_archive_provider_is_removed_even_if_worker_returns_it(self):
        archive = {"title": "Big Buck Bunny", "source": "Internet Archive",
                   "url": "https://archive.org/download/x/x_archive.torrent"}
        valid = {"title": "Vídeo livre", "source": "Provedor autorizado",
                 "url": "https://media.example.org/film.torrent",
                 "quality": "1080p", "language": "pt-br", "seeders": 10}
        with patch.object(self.requests, "get",
                          return_value=FakeResponse({"sources": [archive, valid]})):
            sources = self.client.list_sources("Filme")
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["source"], "Provedor autorizado")

    def test_api_client_requests_without_token(self):
        seen = {}
        def get(url, **kwargs):
            seen.update({"url": url, **kwargs})
            return FakeResponse({"sources": []})
        with patch.object(self.requests, "get", side_effect=get):
            self.assertEqual(self.client.list_sources("Filme", year="2008", imdb="tt1254207"), [])
        self.assertIn("/v1/sources", seen["url"])
        self.assertNotIn("Authorization", seen["headers"])
        self.assertEqual(seen["params"]["imdb"], "tt1254207")

    def test_pt_br_quality_priority(self):
        items = [
            {"title": "Original", "source": "P1", "quality": "4K",
             "language": "en", "url": "magnet:?xt=urn:btih:" + "a"*40},
            {"title": "Dublado", "source": "P2", "quality": "1080p",
             "language": "pt-br", "url": "magnet:?xt=urn:btih:" + "b"*40},
        ]
        with patch.object(self.requests, "get", return_value=FakeResponse({"sources": items})):
            sources = self.client.list_sources("Filme")
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]["title"], "Dublado")

    def test_same_infohash_is_deduped_across_providers(self):
        infohash = "b" * 40
        low = {"title": "Filme 720p", "source": "Comando",
               "url": "magnet:?xt=urn:btih:" + infohash + "&dn=Original",
               "quality": "720p", "seeders": 30, "language": "unknown"}
        high = {"title": "Filme 1080p PT-BR", "source": "Torrentio",
                "url": "magnet:?xt=urn:btih:" + infohash.upper() + "&dn=Dublado",
                "quality": "1080p", "seeders": 8, "language": "pt-br"}
        with patch.object(self.requests, "get",
                          return_value=FakeResponse({"sources": [low, high]})):
            items = self.client.list_sources("Filme")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"], "Torrentio")
        self.assertEqual(items[0]["language"], "pt-br")

    def test_url_torrents_without_hash_remain_separate(self):
        streams = [
            {"title": "A", "source": "P1", "url": "https://a.example.org/x.torrent"},
            {"title": "B", "source": "P2", "url": "https://b.example.org/y.torrent"},
        ]
        with patch.object(self.requests, "get",
                          return_value=FakeResponse({"sources": streams})):
            items = self.client.list_sources("Filme")
        self.assertEqual(len(items), 2)

    def test_distinct_file_indices_for_same_infohash_are_kept(self):
        h = "f" * 40
        rows = [
            {"title": "Episódio 1", "source": "Worker",
             "url": "magnet:?xt=urn:btih:" + h, "fileIdx": 0},
            {"title": "Episódio 2", "source": "Worker",
             "url": "magnet:?xt=urn:btih:" + h, "fileIdx": 1},
        ]
        with patch.object(self.requests, "get",
                          return_value=FakeResponse({"sources": rows})):
            result = self.client.list_sources("Série")
        self.assertEqual(sorted(row["file_index"] for row in result), [0, 1])

    def test_malformed_response_is_rejected(self):
        with patch.object(self.requests, "get",
                          return_value=FakeResponse({"invalid": []})):
            with self.assertRaises(ValueError):
                self.client.list_sources("Filme")


if __name__ == "__main__":
    unittest.main()
