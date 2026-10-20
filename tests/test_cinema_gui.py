"""Cinema controller regression tests without a Kodi graphics runtime."""
import importlib.util
import sys
import types
from unittest.mock import patch, Mock
from pathlib import Path
import xml.etree.ElementTree as ET
import unittest

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / 'src/plugin.video.flyghtxmz'
sys.path.insert(0, str(ADDON))
import cinema_catalog as catalog


class CinemaTests(unittest.TestCase):
    def module(self, window=object, events=None):
        events = events if events is not None else []
        xbmc = types.ModuleType('xbmc')
        xbmc.LOGINFO, xbmc.LOGERROR = 1, 3
        xbmc.log = lambda *args: None
        gui = types.ModuleType('xbmcgui')
        gui.WindowXMLDialog = window
        gui.INPUT_ALPHANUM = 0
        gui.Dialog = lambda: types.SimpleNamespace(ok=lambda *args: events.append('error'), input=lambda *args, **kw: 'Alien')
        gui.DialogProgress = lambda: types.SimpleNamespace(create=lambda *args: events.append('loading'), close=lambda: events.append('loaded'))
        addon = types.ModuleType('xbmcaddon')
        addon.Addon = lambda: types.SimpleNamespace(getAddonInfo=lambda name: '/fake/addon')
        spec = importlib.util.spec_from_file_location('cinema_under_test', ADDON / 'cinema_gui.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'xbmc': xbmc, 'xbmcgui': gui, 'xbmcaddon': addon}):
            spec.loader.exec_module(module)
        return module

    def test_home_has_platform_shortcuts_and_distinct_media_shelves(self):
        home = catalog.screen()
        self.assertEqual([x['media'] for x in home['shelves']], ['movie', 'series'])
        self.assertEqual([x[0] for x in home['tabs']][:3], ['Netflix', 'Prime Video', 'Apple TV+'])
        platform = catalog.screen('platform', 'atp')
        self.assertTrue(all(x['value'] == 'atp' and x['kind'] == 'platform' for x in platform['shelves']))
        self.assertIn('GB', platform['note'])
        self.assertNotEqual(catalog.screen('movies')['shelves'], catalog.screen('series')['shelves'])
        self.assertTrue(any('genre' in x[2] for x in catalog.screen('movies')['tabs']))

    def test_xml_has_reachable_platform_bar_and_two_bounded_shelves(self):
        root = ET.parse(ADDON / 'resources/skins/Default/1080i/FelipeCinema.xml').getroot()
        self.assertEqual(root.attrib, {'type': 'dialog', 'modality': 'modal'})
        controls = {c.get('id'): c for c in root.findall('./controls/control')}
        for cid in ('100', '200', '400', '410'):
            self.assertEqual(controls[cid].get('type'), 'list')
            for pos, size, maximum in [('left', 'width', 1920), ('top', 'height', 1080)]:
                self.assertLessEqual(int(controls[cid].findtext(pos)) + int(controls[cid].findtext(size)), maximum)
        self.assertEqual(controls['200'].findtext('ondown'), '400')
        self.assertIn('410', [x.text for x in controls['400'].findall('ondown')])
        self.assertEqual(controls['410'].findtext('onup'), '400')
        self.assertEqual(controls['10'].findtext('width'), '1920')

    def test_click_callbacks_only_queue_and_close(self):
        events = []
        class FakeWindow:
            def getControl(self, cid):
                return types.SimpleNamespace(getSelectedPosition=lambda: 0)
            def close(self):
                events.append('closed')
        module = self.module(FakeWindow)
        win = module.CinemaWindow()
        win.model = catalog.screen()
        win.cards = {400: [{'id': 'tt1234567', 'media': 'movie', 'title': 'Movie'}]}
        with patch.object(module, 'load_shelf', side_effect=AssertionError('IO in callback')):
            win.onClick(400)
            self.assertEqual(win.request, ('select', 'tt1234567', 'movie'))
            win.onClick(200)
            self.assertEqual(win.request, ('navigate', 'platform', 'nfx'))
        self.assertEqual(events, ['closed', 'closed'])

    def run_controller(self, requests, on_select=None, fail_page=False):
        events, snapshots = [], []
        requests = iter(requests)
        class FakeWindow:
            def __init__(self, *args):
                events.append('window_created')
            def doModal(self):
                snapshots.append((self.model, self.loaded[:], self.restore_focus))
                self.request = next(requests)
                if self.request[0] == 'select':
                    self.restore_focus = (400, 7)
                events.append('window_closed')
            def __del__(self):
                events.append('window_destroyed')
        module = self.module(FakeWindow, events)
        def load(spec, page):
            self.assertEqual(events.count('window_created'), events.count('window_destroyed'))
            if fail_page and page == 2:
                raise OSError('offline')
            return {'items': [{'id':'tt1234567','media':spec['media'],'title':'Movie','poster':'','plot':''}],
                    'more': True, 'page':page, 'error':''}
        def select(*args):
            self.assertEqual(events[-1], 'window_destroyed')
            events.append('selected')
            return on_select(*args) if on_select else None
        with patch.object(module, 'load_shelf', side_effect=load) as loader:
            result = module.launch(select)
        return result, snapshots, events, loader

    def test_cancelled_detail_restores_page_and_focus_without_reloading(self):
        result, states, events, loader = self.run_controller([
            ('page',0,2), ('select','tt1234567','movie'), ('navigate','exit','')])
        self.assertTrue(result)
        self.assertEqual(loader.call_count, 3)
        self.assertEqual(states[-1][1][0]['page'], 2)
        self.assertEqual(states[-1][2], (400,7))
        self.assertEqual(states[-1][1][1]['page'], 1)

    def test_playback_handoff_does_not_reopen_cinema(self):
        result, states, _, _ = self.run_controller([('select','tt1234567','movie')], on_select=lambda *args: True)
        self.assertTrue(result)
        self.assertEqual(len(states), 1)

    def test_platform_change_and_failed_page_keep_previous_results(self):
        result, states, _, loader = self.run_controller([
            ('navigate','platform','amp'), ('page',0,2), ('navigate','exit','')], fail_page=True)
        self.assertTrue(result)
        self.assertEqual(states[-1][0]['title'], 'Prime Video')
        self.assertEqual(states[-1][1][0]['page'], 1)
        self.assertEqual(loader.call_count, 5)

    def test_back_returns_home_then_exits_and_native_fallback(self):
        result, states, _, _ = self.run_controller([
            ('navigate','movies',''), ('back','',''), ('back','','')])
        self.assertTrue(result)
        self.assertEqual(states[-1][0]['nav'], 'home')
        self.assertFalse(self.run_controller([('navigate','classic','')])[0])

    def test_bad_metadata_is_not_passed_to_kodi(self):
        self.assertEqual(catalog.compact_catalog([{'id':'tmdb:3','type':'movie','title':'bad'}], {}), [])
        rows = catalog.compact_catalog([{'id':'tt1234567','type':'movie','title':34,'plot':{},'poster':[]}], {})
        self.assertEqual(rows[0]['title'], 'Sem título')
        self.assertEqual(rows[0]['poster'], '')

    def test_platform_and_search_pages_call_matching_catalog(self):
        with patch.object(catalog.discovery, 'list_titles', return_value=([],False)) as discover, \
             patch.object(catalog.recent, 'list_titles', return_value=([],False)) as recent, \
             patch('metadata_ptbr._read_cache', return_value={}):
            catalog.load_shelf(catalog.screen('platform','nfx')['shelves'][1], 3)
            discover.assert_called_once_with('series','platform','nfx',3)
            catalog.load_shelf(catalog.screen('search_results','Alien')['shelves'][0], 2)
            recent.assert_called_once_with('search_movie',page=2,search_term='Alien')

if __name__ == '__main__':
    unittest.main()
