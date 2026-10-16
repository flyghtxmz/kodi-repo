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
                         ("movie", "tmdb.year", "genre=2026"))
        self.assertEqual(REC._parts("movies_prev", year=2026),
                         ("movie", "tmdb.year", "genre=2025"))
        self.assertEqual(REC._parts("series_new", year=2026),
                         ("series", "tmdb.year", "genre=2026"))

    def test_portuguese_categories_use_tmdb_catalog_ids(self):
        self.assertEqual(REC._parts("movies_popular"),
                         ("movie", "tmdb.top", ""))
        self.assertEqual(REC._parts("movies_trending"),
                         ("movie", "tmdb.trending", "genre=Week"))
        self.assertEqual(REC._parts("movies_latest"),
                         ("movie", "tmdb.latest", ""))
        self.assertEqual(REC._parts("movies_action"),
                         ("movie", "tmdb.top", "genre=A%C3%A7%C3%A3o"))
        self.assertEqual(REC._parts("series_crime"),
                         ("series", "tmdb.top", "genre=Crime"))
        self.assertEqual(REC._parts("series_scifi"),
                         ("series", "tmdb.top", "genre=Sci-Fi%20%26%20Fantasy"))
        self.assertIn("tmdb.top", REC._url("movie", "tmdb.top"))
        with self.assertRaises(ValueError):
            REC._parts("series_unknown")
        self.assertGreaterEqual(len(REC.CATEGORIES), 25)

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
        with patch.object(REC, "fetch", return_value=info):
            movie = REC.detail("tt1234567", "movie")
        self.assertEqual(movie["trailer_id"], "ZkN2M4ODdys")

    def test_film_and_series_details_use_ptbr_tmdb_and_daily_imdb_rating(self):
        ptbr = types.ModuleType("metadata_ptbr")
        ptbr.cached_rating = lambda identifier, media: ""
        ptbr.enrich = lambda identifier, media, imdb_rating="", ptbr_description="": (
            ptbr_description, "8.7", 100000)
        for kind in ("movie", "series"):
            with self.subTest(kind=kind):
                localized = {"meta": {
                    "id": "tt1234567", "type": kind,
                    "name": "Nome em português", "description": "Enredo em português",
                    "year": 2026, "imdb_id": "tt1234567"}}
                cinemeta = {"meta": {"imdbRating": "8.6"}}
                with patch.dict(sys.modules, {"metadata_ptbr": ptbr}):
                    with patch.object(REC, "fetch", side_effect=[localized, cinemeta]) as fetch:
                        result = REC.detail("tt1234567", kind)
                self.assertEqual(result["title"], "Nome em português")
                self.assertEqual(result["plot"], "Enredo em português")
                self.assertEqual(result["rating"], "8.7")
                self.assertEqual(result["rating_checked_at"], 100000)
                self.assertEqual(result["imdb_id"], "tt1234567")
                self.assertEqual(fetch.call_count, 2)

    def test_tmdb_id_without_imdb_mapping_keeps_ptbr_but_no_imdb_rating(self):
        incoming = {"meta": {
            "id": "tmdb:969681", "type": "movie",
            "name": "Homem-Aranha: Um Novo Dia",
            "description": "É um novo dia para Peter Parker.",
            "year": 2026}}
        with patch.object(REC, "fetch", return_value=incoming) as fetch:
            result = REC.detail("tmdb:969681", "movie")
        self.assertEqual(result["title"], "Homem-Aranha: Um Novo Dia")
        self.assertIn("Peter Parker", result["plot"])
        self.assertEqual(result["rating"], "Indisponível")
        self.assertEqual(result["imdb_id"], "")
        self.assertEqual(fetch.call_count, 1)

    def test_empty_tmdb_description_uses_ptbr_fallback(self):
        incoming = {"meta": {
            "id": "tmdb:969681", "type": "movie",
            "name": "Nome local", "description": "", "year": 2026}}
        with patch.object(REC, "fetch", return_value=incoming):
            result = REC.detail("tmdb:969681", "movie")
        self.assertIn("Sinopse em português", result["plot"])

    def test_where_to_watch_is_query_not_illegal_stream(self):
        url = REC.justwatch_search_url("Movie Name (2026)")
        self.assertEqual(urlsplit(url).hostname, "www.justwatch.com")
        self.assertEqual(parse_qs(urlsplit(url).query)["q"], ["Movie Name (2026)"])
        with self.assertRaises(ValueError):
            REC.justwatch_search_url("")


if __name__ == "__main__":
    unittest.main()
