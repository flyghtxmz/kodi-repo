"""Testes da integração com catálogo Creative Commons (sem rede)."""
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "src/plugin.video.flyghtxmz/catalog.py"
SPEC = importlib.util.spec_from_file_location("catalog_under_test", FILE)
CAT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAT)


class CatalogTests(unittest.TestCase):
    def test_license_validation(self):
        self.assertTrue(CAT.open_license("https://creativecommons.org/licenses/by/4.0/"))
        self.assertTrue(CAT.open_license("http://creativecommons.org/publicdomain/zero/1.0/"))
        self.assertFalse(CAT.open_license("https://example.org/licenses/by/4.0"))
        self.assertFalse(CAT.open_license("https://creativecommons.org.evil.com/licenses/by/4.0"))
        self.assertFalse(CAT.open_license("http://creativecommons.org/about"))

    def test_query_escapes_user_input(self):
        url = CAT.make_query("busca", 'film ) OR mediatype:software')
        self.assertNotIn(" OR ", url)
        self.assertIn("title:film", url)
        self.assertIn("mediatype:movies", url)

    def test_search_filter_licensed_items(self):
        docs = {"response": {"numFound": 2, "docs": [
            {"identifier": "movie_ok", "title": "Free Film",
             "licenseurl": "https://creativecommons.org/licenses/by/4.0/"},
            {"identifier": "movie_bad", "title": "No license"},
        ]}}
        with patch.object(CAT, "fetch_json", return_value=docs) as call:
            result, more = CAT.search("filmes")
        self.assertEqual([v["identifier"] for v in result], ["movie_ok"])
        self.assertFalse(more)
        arguments = parse_qs(urlsplit(call.call_args.args[0]).query)
        self.assertEqual(arguments["rows"], [str(CAT.PER_PAGE)])
        self.assertIn("licenseurl:", arguments["q"][0])

    def test_search_pagination(self):
        with patch.object(CAT, "fetch_json", return_value={"response": {
            "numFound": 300, "docs": []}}):
            result, more = CAT.search("curtas", page=2)
        self.assertEqual(result, [])
        self.assertTrue(more)

    def test_featured_open_movies_have_auto_resolved_urls(self):
        with patch.object(CAT, "fetch_json", side_effect=AssertionError("Featured must be local")):
            items, next_page = CAT.search("destaques")
            self.assertEqual(len(items), 4)
            self.assertFalse(next_page)
            self.assertEqual(items[0]["title"], "Big Buck Bunny")
            movie = CAT.playback(items[0]["identifier"])
            self.assertTrue(movie["url"].endswith("BigBuckBunny.mp4"))
            self.assertTrue(CAT.open_license(movie["license"]))

    def test_playback_autoselects_compatible_file(self):
        item = {"metadata": {
            "title": "Creative Commons Film",
            "licenseurl": "https://creativecommons.org/licenses/by/4.0/",
        }, "files": [
            {"name": "film_4k.mp4", "size": "900000000"},
            {"name": "film_720p.mp4", "size": "70000000"},
            {"name": "film_thumb.mp4", "size": "100000"},
        ]}
        with patch.object(CAT, "fetch_json", return_value=item):
            result = CAT.playback("movie_ok")
        self.assertTrue(result["url"].endswith("/film_720p.mp4"))
        self.assertEqual(result["title"], "Creative Commons Film")

    def test_playback_requires_license_and_valid_id(self):
        with patch.object(CAT, "fetch_json", return_value={"metadata": {},
                                                           "files": [{"name": "video.mp4"}]}):
            with self.assertRaises(ValueError):
                CAT.playback("movie_no_license")
        with self.assertRaises(ValueError):
            CAT.playback("../../../etc/passwd")

    def test_bad_catalog_category(self):
        with self.assertRaises(ValueError):
            CAT.make_query("unknown")


if __name__ == "__main__":
    unittest.main()
