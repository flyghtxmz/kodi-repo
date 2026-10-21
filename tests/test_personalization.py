"""Regressões da biblioteca local e do catálogo brasileiro, sem Kodi real."""
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/plugin.video.flyghtxmz"
sys.path.insert(0, str(SRC))
import user_library


class LocalLibraryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        mock_path = patch.object(user_library, "_path",
                                 side_effect=lambda group: Path(self.directory.name) / ("library_" + group + ".json"))
        mock_path.start()
        self.addCleanup(mock_path.stop)

    def test_favorites_are_persistent_and_removable(self):
        self.assertTrue(user_library.toggle_favorite("tt1234567", "movie", "Meu filme",
            "https://poster.example.org/x.jpg", "2026", ["Action"]))
        self.assertTrue(user_library.is_favorite("tt1234567", "movie"))
        self.assertEqual(user_library.list_items("favorites")[0]["title"], "Meu filme")
        self.assertIn(("movie", "action"), user_library.preferred_genres())
        self.assertFalse(user_library.toggle_favorite("tt1234567", "movie"))
        self.assertEqual(user_library.list_items("favorites"), [])

    def test_continue_is_only_visible_after_playback_and_can_complete(self):
        request = {"id": "tt1234567", "media": "movie", "title": "Filme",
                   "poster": "", "year": "2026"}
        self.assertEqual(user_library.list_items("continue"), [])
        user_library.mark_started(request)
        user_library.update_progress(request, 120, 1200)
        self.assertEqual(user_library.list_items("continue")[0]["position"], 120)
        user_library.update_progress(request, 1150, 1200)
        self.assertEqual(user_library.list_items("continue"), [])
        self.assertEqual(len(user_library.list_items("history")), 1)

    def test_changing_series_episode_clears_prior_position(self):
        one = {"id": "tt1234567", "media": "series", "title": "Série",
               "season": 1, "episode": 1}
        two = dict(one, episode=2)
        user_library.mark_started(one)
        user_library.update_progress(one, 600, 1200)
        user_library.mark_started(two)
        row = user_library.list_items("continue")[0]
        self.assertEqual(row["episode"], 2)
        self.assertEqual(row["position"], 0)

    def test_rejects_invalid_identifier(self):
        with self.assertRaises(ValueError):
            user_library.toggle_favorite("tmdb:22", "movie", "Sem IMDb")


class BrasilCatalogTests(unittest.TestCase):
    def setUp(self):
        addon = types.ModuleType("xbmcaddon")
        addon.Addon = lambda: types.SimpleNamespace(
            getSetting=lambda key: "a" * 32 if key == "tmdb_api_key" else "")
        requests = types.ModuleType("requests")
        requests.get = lambda *args, **kwargs: None
        with patch.dict(sys.modules, {"xbmcaddon": addon, "requests": requests}):
            spec = importlib.util.spec_from_file_location("tmdb_personalization_test",
                SRC / "tmdb_br.py")
            self.tmdb = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.tmdb)

    def test_ptbr_provider_discovery_and_imdb_resolution(self):
        def fetch(path, params=None):
            if path == "/watch/providers/movie":
                return {"results": [{"provider_id": 8, "provider_name": "Netflix"}]}
            if path == "/discover/movie":
                self.assertEqual(params["watch_region"], "BR")
                self.assertEqual(params["with_watch_monetization_types"], "flatrate")
                return {"results": [{"id": 500, "title": "Título brasileiro",
                    "poster_path": "/x.jpg", "overview": "Sinopse", "release_date": "2026-09-10"}],
                    "total_pages": 1}
            if path == "/movie/500/external_ids":
                return {"imdb_id": "tt1234567"}
            raise AssertionError(path)
        with patch.object(self.tmdb, "_request", side_effect=fetch), patch.object(
                self.tmdb.local_cache, "get", return_value=None), patch.object(
                self.tmdb.local_cache, "put"):
            films, more = self.tmdb.platform_titles("movie", "nfx")
            self.assertEqual(films[0]["id"], "tmdb:500")
            self.assertEqual(films[0]["title"], "Título brasileiro")
            self.assertFalse(more)
            self.assertEqual(self.tmdb.resolve_imdb("tmdb:500", "movie"), "tt1234567")


if __name__ == "__main__":
    unittest.main()
