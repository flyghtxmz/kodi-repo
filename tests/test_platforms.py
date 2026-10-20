"""Provider catalog identity, pagination, ordering and failure regression tests."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/plugin.video.flyghtxmz"))
import discovery
import recent


def row(identifier="tt1234567", name="Zulu", media="movie"):
    return {"id": "tmdb:123", "name": name, "type": media, "imdbRating": "9.8",
            "links": [{"category": "imdb", "url": "https://imdb.com/title/" + identifier}]}


class PlatformTests(unittest.TestCase):
    def test_identity_order_deduplication_and_next_page(self):
        rows = [row(), row("tt7654321", "Alpha")] + [row()] * 18
        with patch.object(discovery, "fetch", return_value={"metas": rows}) as fetch, \
             patch.object(discovery.local_cache, "get", return_value=None), \
             patch.object(discovery.local_cache, "put"):
            items, more = discovery.list_titles("movie", "platform", "nfx", 2)
        self.assertEqual([x["id"] for x in items], ["tt1234567", "tt7654321"])
        self.assertTrue(more)
        self.assertEqual(items[0]["rating"], "")
        self.assertIn("/movie/tmdb.nfx/skip=20.json", fetch.call_args.args[0])

    def test_bad_filter_never_fetches(self):
        with patch.object(discovery, "fetch") as fetch:
            for media, kind, value in [("invalid", "platform", "nfx"),
                                       ("movie", "platform", "../bad"),
                                       ("series", "trending", "bad")]:
                with self.assertRaises(ValueError):
                    discovery.list_titles(media, kind, value)
            fetch.assert_not_called()

    def test_service_failure_is_not_cached_as_empty_catalog(self):
        payload = {"metas": [{"id": "tmdb:no-content", "name": "Error Loading Content"}]}
        with patch.object(discovery, "fetch", return_value=payload), \
             patch.object(discovery.local_cache, "get", return_value=None), \
             patch.object(discovery.local_cache, "put") as put:
            with self.assertRaises(ValueError):
                discovery.list_titles("series", "platform", "atp")
            put.assert_not_called()

    def test_weekly_trending_and_wrong_media(self):
        with patch.object(discovery, "fetch", return_value={"metas": [row(), row(media="series")]}) as fetch, \
             patch.object(discovery.local_cache, "get", return_value=None), \
             patch.object(discovery.local_cache, "put"):
            items, more = discovery.list_titles("series", "trending", "Week")
        self.assertEqual(len(items), 1)
        self.assertFalse(more)
        self.assertIn("/series/tmdb.trending/genre=Week&skip=0.json", fetch.call_args.args[0])

    def test_wrong_detail_identity_is_rejected(self):
        wrong = {"id": "tt7654321", "type": "movie", "name": "Wrong movie"}
        with patch.object(recent, "fetch", return_value={"meta": wrong}), \
             patch.object(discovery.local_cache, "get", return_value=wrong), \
             patch.object(discovery, "metadata", side_effect=ValueError("unavailable")):
            with self.assertRaises(ValueError):
                recent.detail("tt1234567", "movie")


if __name__ == "__main__":
    unittest.main()
