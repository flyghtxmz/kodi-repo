"""Testes sem rede do cliente Kodi da API de fontes Cloudflare."""
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
        self.status_code = 200

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
            "cloudflare_token": "test-token",
        }.get(key, ""))
        requests = types.ModuleType("requests")
        requests.get = lambda *args, **kwargs: FakeResponse({"sources": []})
        with patch.dict(sys.modules, {"xbmcaddon": addon, "requests": requests}):
            spec = importlib.util.spec_from_file_location("cloudflare_client_under_test", PATH)
            cls.client = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.client)
        cls.requests = requests

    def test_only_https_root_worker_is_allowed(self):
        self.assertEqual(self.client._worker_url("https://test.workers.dev/"),
                         "https://test.workers.dev")
        for url in ("http://example.org", "https://user:pass@host/",
                    "https://test.workers.dev/foo", "file:///etc/passwd"):
            with self.assertRaises(ValueError):
                self.client._worker_url(url)

    def test_only_known_archive_torrents_are_playable(self):
        self.assertTrue(self.client.is_supported_source(
            "https://archive.org/download/Bunny/Bunny_archive.torrent"))
        for url in ("https://evil.example/file_archive.torrent",
                    "http://archive.org/download/Bunny/Bunny_archive.torrent",
                    "https://archive.org/download/x/movie.mp4",
                    "https://archive.org.evil.example/download/x/x_archive.torrent"):
            self.assertFalse(self.client.is_supported_source(url))

    def test_bearer_token_sent_as_header_not_url(self):
        example = {
            "verified_license": True, "source": "Internet Archive",
            "title": "Big Buck Bunny", "quality": "1080p",
            "size": 70000000, "seeders": None, "language": "unknown",
            "url": "https://archive.org/download/Bunny/Bunny_archive.torrent",
        }
        seen = {}

        def get(url, **kwargs):
            seen.update({"url": url, **kwargs})
            return FakeResponse({"sources": [example]})

        with patch.object(self.requests, "get", side_effect=get):
            result = self.client.list_sources("Big Buck Bunny", year="2008",
                                              imdb="tt1254207")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["seeders"], None)
        self.assertIn("/v1/sources", seen["url"])
        self.assertEqual(seen["headers"]["Authorization"], "Bearer test-token")
        self.assertNotIn("test-token", str(seen["params"]))
        self.assertNotIn("test-token", seen["url"])

    def test_unverified_and_untrusted_sources_removed(self):
        bad = {
            "verified_license": True, "quality": "1080p",
            "url": "https://untrusted.example/movie_archive.torrent",
        }
        unverified = {
            "verified_license": False, "quality": "1080p",
            "url": "https://archive.org/download/x/x_archive.torrent",
        }
        with patch.object(self.requests, "get",
                          return_value=FakeResponse({"sources": [bad, unverified]})):
            self.assertEqual(self.client.list_sources("Some movie", "2010"), [])

    def test_malformed_response_is_rejected(self):
        with patch.object(self.requests, "get",
                          return_value=FakeResponse({"not_sources": []})):
            with self.assertRaises(ValueError):
                self.client.list_sources("Some movie")


if __name__ == "__main__":
    unittest.main()
