import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ADDON = Path(__file__).resolve().parents[1] / 'src/plugin.video.flyghtxmz'
sys.path.insert(0, str(ADDON))
import local_cache
import user_state


class CacheTests(unittest.TestCase):
    def test_fresh_expired_and_corrupt_cache(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(local_cache, 'directory', return_value=Path(tmp)):
            with patch.object(local_cache.time, 'time', return_value=100):
                local_cache.put('catalog', {'metas': []})
                self.assertEqual(local_cache.get('catalog', 30), {'metas': []})
            with patch.object(local_cache.time, 'time', return_value=200):
                self.assertIsNone(local_cache.get('catalog', 30))
                self.assertIsNotNone(local_cache.get('catalog', 300))
            next(Path(tmp).glob('*.json')).write_text('{broken')
            self.assertIsNone(local_cache.get('catalog', 300))

    def test_favorites_history_survive_cache_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'http_cache'
            root.mkdir()
            with patch.object(local_cache, 'directory', return_value=root), patch.object(user_state, 'directory', return_value=root):
                film = {'id': 'tt1234567', 'type': 'movie', 'title': 'Film'}
                self.assertTrue(user_state.toggle_favorite(film))
                user_state.remember_search('Film', 'movie')
                user_state.remember_search('Film', 'movie')
                local_cache.put('catalog', {})
                local_cache.clear()
                self.assertEqual(len(user_state.read()['favorites']), 1)
                self.assertEqual(len(user_state.read()['searches']), 1)
                self.assertFalse(user_state.toggle_favorite(film))
                self.assertEqual(user_state.read()['favorites'], [])
