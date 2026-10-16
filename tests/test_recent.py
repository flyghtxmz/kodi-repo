"""Testes de metadados públicos de lançamentos (sem consultas reais à rede)."""
import importlib.util
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
        with patch.object(REC, "fetch", return_value=info):
            movie = REC.detail("tt1234567", "movie")
        self.assertEqual(movie["trailer_id"], "ZkN2M4ODdys")

    def test_where_to_watch_is_query_not_illegal_stream(self):
        url = REC.justwatch_search_url("Movie Name (2026)")
        self.assertEqual(urlsplit(url).hostname, "www.justwatch.com")
        self.assertEqual(parse_qs(urlsplit(url).query)["q"], ["Movie Name (2026)"])
        with self.assertRaises(ValueError):
            REC.justwatch_search_url("")


if __name__ == "__main__":
    unittest.main()
