"""PT-BR synopsis and 24-hour IMDb rating cache without network/Kodi."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src/plugin.video.flyghtxmz/metadata_ptbr.py"
SPEC = importlib.util.spec_from_file_location("metadata_ptbr_for_test", MODULE_PATH)
META = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(META)


class MetadataPtbrTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        cache_path = Path(self.temp.name) / "cache.json"
        patcher = patch.object(META, "_profile_path", return_value=cache_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_rating_checked_daily_not_overwritten_before_ttl(self):
        with patch.object(META, "_read_ptbr_description", return_value="Sinopse brasileira.") as call:
            desc, rate, stamp = META.enrich("tt0111161", "movie", "9.3", now=100000)
            self.assertEqual((desc, rate, stamp), ("Sinopse brasileira.", "9.3", 100000))
            second = META.enrich("tt0111161", "movie", "9.4", now=100000 + 300)
            self.assertEqual(second[1], "9.3")
            self.assertEqual(second[2], 100000)
            updated = META.enrich("tt0111161", "movie", "9.4", now=100000 + META.RATING_TTL)
            self.assertEqual(updated[1], "9.4")
            self.assertEqual(updated[2], 100000 + META.RATING_TTL)
            self.assertEqual(call.call_count, 1)

    def test_ptbr_description_fallback_does_not_show_english(self):
        with patch.object(META, "_read_ptbr_description", side_effect=TimeoutError("offline")) as call:
            desc, rating, checked = META.enrich("tt0111161", "movie", "9.3", now=100000)
            self.assertIn("Sinopse em português", desc)
            self.assertEqual(rating, "9.3")
            META.enrich("tt0111161", "movie", "9.3", now=100100)
            self.assertEqual(call.call_count, 1)

    def test_description_ttl_is_seven_days_and_cached_through_rating_refresh(self):
        with patch.object(META, "_read_ptbr_description", side_effect=["Primeiro texto", "Texto atualizado"]) as call:
            first = META.enrich("tt0111161", "movie", "9.3", now=100000)
            next_day = META.enrich("tt0111161", "movie", "9.4", now=100000 + META.RATING_TTL)
            next_week = META.enrich("tt0111161", "movie", "9.4", now=100000 + META.DESCRIPTION_TTL)
            self.assertEqual(first[0], "Primeiro texto")
            self.assertEqual(next_day[0], "Primeiro texto")
            self.assertEqual(next_week[0], "Texto atualizado")
            self.assertEqual(call.call_count, 2)

    def test_cached_rating_only_returns_fresh_value(self):
        with patch.object(META, "_read_ptbr_description", return_value="Enredo PT-BR"):
            META.enrich("tt0111161", "movie", "8.9", now=100000)
        with patch.object(META.time, "time", return_value=100100):
            self.assertEqual(META.cached_rating("tt0111161", "movie"), "8.9")
        with patch.object(META.time, "time", return_value=100000+META.RATING_TTL):
            self.assertEqual(META.cached_rating("tt0111161", "movie"), "")

    def test_rating_falls_back_to_last_known_value_if_upstream_omits_it(self):
        with patch.object(META, "_read_ptbr_description", return_value="Enredo"):
            META.enrich("tt0111161", "movie", "8.6", now=100000)
            old= META.enrich("tt0111161", "movie", "", now=100000 + META.RATING_TTL)
        self.assertEqual(old[1], "8.6")

    def test_catalog_prefetch_renders_ptbr_descriptions_and_caches_them(self):
        titles = [
            {"id": "tt0111161", "type": "movie"},
            {"id": "tt0944947", "type": "series"},
        ]
        def translated(identifier, media, timeout=9):
            return "Sinopse em português: " + identifier
        with patch.object(META, "_read_ptbr_description", side_effect=translated) as get:
            first = META.descriptions_for_catalog(titles, now=100000)
            second = META.descriptions_for_catalog(titles, now=100500)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(first, second)
        self.assertIn("Sinopse em português", first["movie:tt0111161"])
        self.assertIn("Sinopse em português", first["series:tt0944947"])

    def test_catalog_prefetch_handles_timeout_and_throttles_retry(self):
        movies = [{"id": "tt0111161", "type": "movie"}]
        with patch.object(META, "_read_ptbr_description", side_effect=TimeoutError()) as get:
            first = META.descriptions_for_catalog(movies, now=100000)
            again = META.descriptions_for_catalog(movies, now=100100)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(first, again)
        self.assertEqual(first["movie:tt0111161"], META.FALLBACK_SYNOPSIS)

    def test_catalog_prefetch_respects_twenty_item_page_limit(self):
        movies = [{"id": "tt%07d" % (1000000 + i), "type": "movie"}
                  for i in range(23)]
        with patch.object(META, "_read_ptbr_description", return_value="Tradução") as get:
            results = META.descriptions_for_catalog(movies, now=100000)
        self.assertEqual(len(results), 20)
        self.assertEqual(get.call_count, 20)

    def test_source_url_is_ptbr_configured_and_id_checked(self):
        self.assertEqual(
            META.TMDB_STREMIO_BASE,
            "https://tmdb.elfhosted.com/N4IgNghgdg5grhGBTEAuEAHALgWgEIBKIAvkA")
        class FakeResponse:
            status=200
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self, size):
                return json.dumps({"meta":{
                    "imdb_id":"tt0111161",
                    "description":"Em 1946, Andy Dufresne é condenado."}
                }).encode()
        with patch.object(META, "urlopen", return_value=FakeResponse()) as called:
            self.assertIn("Em 1946", META._read_ptbr_description("tt0111161", "movie"))
            self.assertIn("/meta/movie/tt0111161.json", called.call_args.args[0].full_url)
        with patch.object(META, "urlopen", return_value=FakeResponse()):
            with self.assertRaises(ValueError):
                META._read_ptbr_description("tt0944947", "series")


if __name__ == "__main__":
    unittest.main()
