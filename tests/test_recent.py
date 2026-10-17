"""Testes de catálogo Cinemeta com IDs IMDb e localização PT-BR sem rede."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "src/plugin.video.flyghtxmz/recent.py"
SPEC = importlib.util.spec_from_file_location("recent_under_test", FILE)
REC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REC)


class RecentCatalogTests(unittest.TestCase):
    def test_year_sections_follow_current_year(self):
        self.assertEqual(REC._parts("movies_new", year=2026),
                         ("movie", "year", "genre=2026"))
        self.assertEqual(REC._parts("movies_prev", year=2026),
                         ("movie", "year", "genre=2025"))
        self.assertEqual(REC._parts("series_new", year=2026),
                         ("series", "year", "genre=2026"))

    def test_additional_years_and_genres(self):
        self.assertEqual(REC._parts("movies_prev2", year=2026),
                         ("movie", "year", "genre=2024"))
        self.assertEqual(REC._parts("series_prev", year=2026),
                         ("series", "year", "genre=2025"))
        self.assertEqual(REC._parts("series_prev2", year=2026),
                         ("series", "year", "genre=2024"))
        self.assertEqual(REC._parts("movies_genre_western"),
                         ("movie", "top", "genre=Western"))
        self.assertEqual(REC._parts("series_genre_history"),
                         ("series", "top", "genre=History"))

    def test_genres_and_ratings_use_supported_cinemeta_catalogs(self):
        self.assertEqual(REC._parts("movies_best_rated"),
                         ("movie", "imdbRating", ""))
        self.assertEqual(REC._parts("series_best_rated"),
                         ("series", "imdbRating", ""))
        self.assertEqual(REC._parts("movies_genre_action"),
                         ("movie", "top", "genre=Action"))
        self.assertEqual(REC._parts("movies_genre_scifi"),
                         ("movie", "top", "genre=Sci-Fi"))
        self.assertEqual(REC._parts("series_genre_reality"),
                         ("series", "top", "genre=Reality-TV"))
        self.assertEqual(REC._parts("series_genre_documentary"),
                         ("series", "top", "genre=Documentary"))
        self.assertIn("imdbRating", REC._url("series", "imdbRating"))
        self.assertIn("genre=Action", REC._url("movie", "top", "genre=Action"))
        self.assertGreaterEqual(len(REC.GENRE_CATEGORIES), 25)
        self.assertIn(("movies_genre_horror", "Terror"), REC.GENRE_CATEGORIES)
        with self.assertRaises(ValueError):
            REC._parts("movies_genre_reality")
        with self.assertRaises(ValueError):
            REC._parts("series_genre_nonexistent")

    def test_validates_imdb_identity_and_cinemeta_origin(self):
        self.assertEqual(REC.validate_id("tt1234567"), "tt1234567")
        for invalid in ("../tt123456", "xx123456", "tt12",
                        "tmdb:969681", "tt1234567?x=1"):
            with self.assertRaises(ValueError):
                REC.validate_id(invalid)
        with self.assertRaises(ValueError):
            REC.fetch("https://example.net/anything")

    def test_normalized_metadata_is_bound_to_imdb_id(self):
        movie = REC.normalize({
            "id": "tt1234567", "type": "movie", "name": "Film Name",
            "poster": "https://example.org/poster", "year": 2026,
            "description": "English overview", "imdbRating": "7.4"})
        self.assertEqual(movie["id"], "tt1234567")
        self.assertEqual(movie["rating"], "7.4")
        self.assertEqual(movie["year"], "2026")
        self.assertIsNone(REC.normalize({"id": "tmdb:1234", "name": "Movie"}))

    def test_search_is_encoded_and_pagination_kept(self):
        with patch.object(REC, "fetch", return_value={"metas": []}) as fetch:
            REC.list_titles("search_movie", search_term="Avatar & Star", year=2026)
            self.assertIn("search=Avatar%20%26%20Star", fetch.call_args.args[0])
            REC.list_titles("movies_prev", page=2, year=2026)
            self.assertIn("skip=20", fetch.call_args.args[0])
        with self.assertRaises(ValueError):
            REC.list_titles("search_series", search_term="")

    def test_alphabetical_listing_ignores_accents_and_case(self):
        payload = {"metas": [
            {"id":"tt1234501", "name":"Zorro"},
            {"id":"tt1234502", "name":"Épico"},
            {"id":"tt1234503", "name":"Árvore"},
            {"id":"tt1234504", "name":"brilho"},
            {"id":"tt1234505", "name":"Amor"},
        ]}
        with patch.object(REC, "fetch", return_value=payload):
            for category in ("movies_new", "movies_genre_drama", "search_movie"):
                found, more = REC.list_titles(category,
                    search_term="am" if category=="search_movie" else "")
                self.assertEqual([m["title"] for m in found],
                                 ["Amor", "Árvore", "brilho", "Épico", "Zorro"])
                self.assertFalse(more)

    def test_detail_preserves_original_title_for_worker_but_displays_ptbr(self):
        meta = {"meta":{
            "id":"tt1234567", "name":"The Film", "type":"movie",
            "description":"English summary", "year":2026, "imdbRating":"8.6",
            "trailerStreams":[{"ytId":"ZkN2M4ODdys"}],
        }}
        localized = types.ModuleType("metadata_ptbr")
        localized.enrich = lambda *args, **kwargs: (
            "Descrição brasileira.", "8.7", 10000)
        localized.localized_title = lambda ident,media: "O Filme"
        with patch.dict(sys.modules, {"metadata_ptbr":localized}):
            with patch.object(REC, "fetch", return_value=meta):
                movie = REC.detail("tt1234567")
        self.assertEqual(movie["title"], "O Filme")
        self.assertEqual(movie["original_title"], "The Film")
        self.assertEqual(movie["plot"], "Descrição brasileira.")
        self.assertEqual(movie["rating"], "8.7")
        self.assertEqual(movie["trailer_id"], "ZkN2M4ODdys")

    def test_localization_failure_never_displays_original_english_synopsis(self):
        incoming = {"meta":{
            "id":"tt1234567", "name":"The Film", "type":"series",
            "description":"English summary to avoid", "year":2026}}
        local = types.ModuleType("metadata_ptbr")
        local.enrich = lambda *args,**kwargs: (_ for _ in ()).throw(ValueError("offline"))
        local.localized_title = lambda *args:""
        with patch.dict(sys.modules, {"metadata_ptbr":local}):
            with patch.object(REC, "fetch", return_value=incoming):
                movie = REC.detail("tt1234567", "series")
        self.assertIn("Sinopse em português", movie["plot"])
        self.assertNotIn("English", movie["plot"])

    def test_real_season_episode_numbers_and_specials_are_preserved(self):
        identity = "tt0944947"
        rows = [
            {"id": identity + ":2:8", "season": 2, "episode": 8, "title": "Eight"},
            {"id": identity + ":1:3", "season": 1, "episode": 3, "title": "Third"},
            {"id": identity + ":0:1", "season": 0, "episode": 1, "title": "Special"},
            {"id": identity + ":1:1", "season": 1, "episode": 1, "title": "Pilot"},
            {"id": identity + ":1:3", "season": 1, "episode": 3, "title": "Third duplicate"},
            {"id": identity + ":1:8", "season": 1, "episode": 9, "title": "Bad ID"},
            {"id": "tt1234567:1:2", "season": 1, "episode": 2},
            {"id": identity + ":3:1", "season": 3, "episode": 0},
            {"id": identity + ":2:5", "season": True, "episode": 5},
            {"season": 4, "episode": 2},
        ]
        groups = REC.episodes_for_series({"videos": rows}, identity)
        self.assertEqual(list(groups), [0, 1, 2, 4])
        self.assertEqual([x["episode"] for x in groups[1]], [1, 3])
        self.assertEqual([x["episode"] for x in groups[2]], [8])
        self.assertEqual(groups[0][0]["id"], identity + ":0:1")
        self.assertEqual(groups[4][0]["id"], identity + ":4:2")
        self.assertNotIn(3, groups)

    def test_detail_adds_series_episodes_without_renumbering(self):
        identity = "tt0944947"
        data = {"meta": {
            "id": identity, "type": "series", "name": "Game of Thrones",
            "year": 2011, "videos": [
                {"id": identity + ":3:7", "season": 3, "episode": 7, "title": "The Bear"},
                {"id": identity + ":3:5", "season": 3, "episode": 5, "title": "Kissed"},
            ]}}
        localized = types.ModuleType("metadata_ptbr")
        localized.enrich = lambda *args, **kwargs: ("Sinopse PT-BR", "9.2", 1000)
        localized.localized_title = lambda *args: "A Guerra dos Tronos"
        with patch.dict(sys.modules, {"metadata_ptbr": localized}):
            with patch.object(REC, "fetch", return_value=data):
                result = REC.detail(identity, "series")
        self.assertEqual([item["episode"] for item in result["episodes"][3]], [5, 7])
        self.assertEqual(result["episodes"][3][1]["id"], identity + ":3:7")

    def test_rejects_wrong_detail_identity_and_media(self):
        for meta in ({'id': 'tt1234568', 'type': 'movie', 'name': 'Wrong'},
                     {'id': 'tt1234567', 'type': 'series', 'name': 'Wrong'}):
            with patch.object(REC, 'fetch', return_value={'meta': meta}):
                with self.assertRaises(ValueError):
                    REC.detail('tt1234567', 'movie')

    def test_segmentation_rejects_mixed_types_and_wrong_year(self):
        rows = [
            {'id': 'tt1234501', 'type': 'movie', 'name': 'Correct', 'year': 2020},
            {'id': 'tt1234502', 'type': 'series', 'name': 'Series', 'year': 2020},
            {'id': 'tt1234503', 'type': 'movie', 'name': 'Wrong year', 'year': 2019},
        ]
        with patch.object(REC, 'fetch', return_value={'metas': rows + rows}):
            found, more = REC.list_titles('movies_year_2020')
        self.assertEqual([x['id'] for x in found], ['tt1234501'])
        with self.assertRaises(ValueError):
            REC._parts('movies_year_3000')

    def test_justwatch_search_uses_title(self):
        url = REC.justwatch_search_url("Um Sonho de Liberdade")
        self.assertEqual(urlsplit(url).hostname, "www.justwatch.com")
        self.assertEqual(parse_qs(urlsplit(url).query)["q"], ["Um Sonho de Liberdade"])


if __name__ == "__main__":
    unittest.main()
