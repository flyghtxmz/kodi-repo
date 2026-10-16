"""Testes de metadados públicos de lançamentos (sem consultas reais à rede)."""
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
    def test_year_section_uses_current_year(self):
        self.assertEqual(REC._parts("movies_new", year=2026),
                         ("movie", "year", "genre=2026"))
        self.assertEqual(REC._parts("movies_prev", year=2026),
                         ("movie", "year", "genre=2025"))
        self.assertEqual(REC._parts("series_new", year=2026),
                         ("series", "year", "genre=2026"))
        self.assertEqual(REC._parts("series_prev", year=2026),
                         ("series", "year", "genre=2025"))

    def test_extra_categories_are_supported_by_cinemeta(self):
        self.assertEqual(REC._parts("movies_popular"), ("movie", "top", ""))
        self.assertEqual(REC._parts("movies_best_rated"),
                         ("movie", "imdbRating", ""))
        self.assertEqual(REC._parts("series_best_rated"),
                         ("series", "imdbRating", ""))
        self.assertEqual(REC._parts("movies_action"),
                         ("movie", "top", "genre=Action"))
        self.assertEqual(REC._parts("movies_scifi"),
                         ("movie", "top", "genre=Sci-Fi"))
        self.assertEqual(REC._parts("series_reality"),
                         ("series", "top", "genre=Reality-TV"))
        self.assertIn("genre=Action", REC._url("movie", "top", "genre=Action"))
        self.assertIn("imdbRating", REC._url("series", "imdbRating"))
        with self.assertRaises(ValueError):
            REC._parts("series_unknown")
        self.assertGreaterEqual(len(REC.CATEGORIES), 30)

    def test_validates_imdb_id_and_source(self):
        self.assertEqual(REC.validate_id("tt1234567"), "tt1234567")
        for invalid in ("../tt123456", "xx123456", "tt12", "tt1234567?x=1"):
            with self.assertRaises(ValueError):
                REC.validate_id(invalid)
        with self.assertRaises(ValueError):
            REC.fetch("https://example.net/anything")

    def test_titles_have_poster_year_and_sanitized_metadata(self):
        info = {"metas": [{
            "id": "tt1234567", "type": "movie", "name": "Film Name",
            "year": 2026, "poster": "https://images.metahub.space/poster",
            "description": "A <b>movie</b>", "imdbRating": "7.6",
        }, {"id": "wrong", "name": "Nope"}]}
        with patch.object(REC, "fetch", return_value=info):
            titles, more = REC.list_titles("movies_new", page=1, year=2026)
        self.assertEqual(len(titles), 1)
        self.assertEqual(titles[0]["year"], "2026")
        self.assertEqual(titles[0]["id"], "tt1234567")
        self.assertFalse(more)

    def test_list_titles_sorts_accented_titles_alphabetically(self):
        infos = {"metas": [
            {"id": "tt1234501", "name": "Zorro", "type": "movie"},
            {"id": "tt1234502", "name": "Épico", "type": "movie"},
            {"id": "tt1234503", "name": "Árvore", "type": "movie"},
            {"id": "tt1234504", "name": "brilho", "type": "movie"},
            {"id": "tt1234505", "name": "Amor", "type": "movie"},
        ]}
        with patch.object(REC, "fetch", return_value=infos):
            for category in ("movies_new", "movies_popular", "series_popular", "search_movie"):
                titles, more = REC.list_titles(
                    category, search_term="am" if category == "search_movie" else "")
                self.assertEqual([t["title"] for t in titles],
                                 ["Amor", "Árvore", "brilho", "Épico", "Zorro"])
                self.assertFalse(more)

    def test_alphabetical_sorting_preserves_pagination(self):
        data = {"metas": [
            {"id": "tt1234501", "name": "Zorro"},
            {"id": "tt1234502", "name": "Aventura"},
        ]}
        with patch.object(REC, "fetch", return_value=data) as fetch:
            titles, _ = REC.list_titles("movies_prev", page=2, year=2026)
        self.assertEqual([item["title"] for item in titles],
                         ["Aventura", "Zorro"])
        self.assertIn("skip=20", fetch.call_args.args[0])

    def test_search_query_is_encoded(self):
        with patch.object(REC, "fetch", return_value={"metas": []}) as fetch:
            REC.list_titles("search_movie", search_term="Avatar & Star", year=2026)
        self.assertIn("search=Avatar%20%26%20Star", fetch.call_args.args[0])
        self.assertNotIn(" Star", fetch.call_args.args[0])
        with self.assertRaises(ValueError):
            REC.list_titles("search_series", search_term="")

    def test_details_extract_youtube_id(self):
        info = {"meta": {
            "id": "tt1234567", "type": "movie", "name": "Film Name",
            "year": 2026, "trailerStreams": [{"ytId": "ZkN2M4ODdys"}]}}
        with patch.dict(sys.modules, {"metadata_ptbr": None}):
            with patch.object(REC, "fetch", return_value=info):
                movie = REC.detail("tt1234567", "movie")
        self.assertEqual(movie["trailer_id"], "ZkN2M4ODdys")

    def test_film_and_series_details_show_localized_title_and_imdb_rating(self):
        ptbr = types.ModuleType("metadata_ptbr")
        ptbr.enrich = lambda identifier, media, imdb_rating="": (
            "Enredo em português", "8.7", 100000)
        ptbr.localized_title = lambda identifier, media: "Nome em português"
        for kind in ("movie", "series"):
            incoming = {"meta": {
                "id": "tt1234567", "type": kind,
                "name": "Original English Name",
                "description": "Original English description",
                "imdbRating": "8.6", "year": 2026}}
            with self.subTest(kind=kind):
                with patch.dict(sys.modules, {"metadata_ptbr": ptbr}):
                    with patch.object(REC, "fetch", return_value=incoming) as fetch:
                        result = REC.detail("tt1234567", kind)
                self.assertEqual(result["title"], "Nome em português")
                self.assertEqual(result["plot"], "Enredo em português")
                self.assertEqual(result["rating"], "8.7")
                self.assertEqual(result["rating_checked_at"], 100000)
                self.assertEqual(fetch.call_count, 1)

    def test_tmdb_identifier_is_not_used_as_imdb(self):
        with self.assertRaises(ValueError):
            REC.validate_id("tmdb:969681")

    def test_ptbr_fallback_when_localization_unavailable(self):
        incoming = {"meta": {
            "id": "tt1234567", "type": "movie",
            "name": "Original Name",
            "description": "English description", "year": 2026}}
        with patch.dict(sys.modules, {"metadata_ptbr": None}):
            with patch.object(REC, "fetch", return_value=incoming):
                result = REC.detail("tt1234567", "movie")
        self.assertIn("Sinopse em português", result["plot"])
        self.assertNotIn("English", result["plot"])

    def test_where_to_watch_is_query_not_illegal_stream(self):
        url = REC.justwatch_search_url("Movie Name (2026)")
        self.assertEqual(urlsplit(url).hostname, "www.justwatch.com")
        self.assertEqual(parse_qs(urlsplit(url).query)["q"], ["Movie Name (2026)"])
        with self.assertRaises(ValueError):
            REC.justwatch_search_url("")


if __name__ == "__main__":
    unittest.main()
