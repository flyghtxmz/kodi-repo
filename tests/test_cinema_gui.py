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


class FakeControl:
    def __init__(self):
        self.position = 0
        self.items = []
    def reset(self):
        self.items = []
    def addItems(self, items):
        self.items.extend(items)
    def selectItem(self, position):
        self.position = min(position, max(0, len(self.items) - 1))
    def getSelectedPosition(self):
        return self.position


class FakeWindow:
    def __init__(self, *args):
        self.controls = {}
        self.properties = {}
        self.visible = False
    def getControl(self, cid):
        return self.controls.setdefault(cid, FakeControl())
    def setProperty(self, name, value):
        self.properties[name] = value
    def setFocusId(self, cid):
        self.focus = cid
    def show(self):
        self.visible = True
        self.onInit()
    def close(self):
        self.visible = False


class CinemaTests(unittest.TestCase):
    def module(self, window=FakeWindow, events=None):
        events = events if events is not None else []
        xbmc = types.ModuleType('xbmc')
        xbmc.LOGINFO, xbmc.LOGERROR = 1, 3
        xbmc.log = lambda *args: None
        xbmc.Monitor = lambda: types.SimpleNamespace(abortRequested=lambda: False, waitForAbort=lambda seconds: False)
        gui = types.ModuleType('xbmcgui')
        gui.WindowXMLDialog = window
        gui.ListItem = lambda **kwargs: types.SimpleNamespace(setArt=lambda *args: None, setInfo=lambda *args: None, setProperty=lambda *args: None)
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

    def test_callbacks_queue_without_closing_or_fetching_and_ignore_busy_clicks(self):
        module = self.module()
        win = module.CinemaWindow()
        win.prepare(catalog.screen())
        win.show()
        win.cards = {400: [{'id': 'tt1234567', 'media': 'movie', 'title': 'Movie'}]}
        win.set_busy(False)
        with patch.object(module, 'load_shelf', side_effect=AssertionError('IO in callback')):
            win.onClick(400)
            win.onClick(200)  # Duplicate remote inputs must not replace the pending action.
            self.assertEqual(win.requests.get_nowait(), ('select', 'tt1234567', 'movie'))
            self.assertTrue(win.requests.empty())
            self.assertTrue(win.visible)
            win.set_busy(False)
            win.onClick(200)
            self.assertEqual(win.requests.get_nowait(), ('navigate', 'platform', 'nfx'))
            win.set_busy(False)
            win.onAction(types.SimpleNamespace(getId=lambda: 92))
            self.assertEqual(win.requests.get_nowait(), ('back', '', ''))
            self.assertTrue(win.visible)

    def run_controller(self, requests, on_select=None, fail_page=False, fail_initial=False,
                       cancel_search=False, abort=False, init_error=False, error_page=False):
        events, snapshots, windows = [], [], []
        pending = iter(requests)
        class TrackedWindow(FakeWindow):
            def __init__(self, *args):
                super().__init__(*args)
                events.append('window_created')
                windows.append(self)
            def show(self):
                super().show()
                events.append('window_shown')
                if init_error:
                    self.init_error = RuntimeError('missing control')
            def close(self):
                super().close()
                events.append('window_closed')
        module = self.module(TrackedWindow, events)
        def dispatch(seconds):
            if abort:
                return True
            win = windows[0]
            self.assertTrue(win.visible)
            self.assertFalse(win.busy)
            snapshots.append((win.model, win.loaded[:], win.restore_focus))
            request = next(pending)
            if request[0] == 'select':
                win.restore_focus = (400, 7)
            win.set_busy(True)
            win.requests.put_nowait(request)
            return False
        module.xbmc.Monitor = lambda: types.SimpleNamespace(abortRequested=lambda: abort, waitForAbort=dispatch)
        if cancel_search:
            module.xbmcgui.Dialog = lambda: types.SimpleNamespace(input=lambda *args, **kw: '')
        def load(spec, page):
            win = windows[0]
            self.assertTrue(win.visible, 'Native Kodi must never be exposed during catalog IO')
            self.assertTrue(win.busy)
            self.assertEqual(events.count('window_closed'), 0)
            if (fail_page and page == 2) or fail_initial:
                raise OSError('offline')
            return {'items': [{'id':'tt1234567','media':spec['media'],'title':'Movie','poster':'','plot':''} for _ in range(10)],
                    'more': True, 'page':page, 'error':'offline' if error_page and page == 2 else ''}
        def select(*args):
            self.assertTrue(windows[0].visible, 'Cinema must remain underneath child dialogs')
            self.assertTrue(windows[0].busy)
            events.append('selected')
            return on_select(*args) if on_select else None
        with patch.object(module, 'load_shelf', side_effect=load) as loader:
            result = module.launch(select)
        self.assertEqual(events.count('window_created'), 1)
        self.assertEqual(events.count('window_closed'), 1)
        self.assertFalse(windows[0].visible)
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

    def test_next_page_and_previous_page_stay_in_cinema(self):
        result, frames, events, loader = self.run_controller([
            ('page',0,2), ('page',0,3), ('page',0,2), ('navigate','exit','')])
        self.assertTrue(result)
        self.assertEqual([frame[1][0]['page'] for frame in frames], [1,2,3,2])
        self.assertEqual(events.count('window_created'), 1)
        self.assertEqual(events.count('window_closed'), 1)
        self.assertEqual(loader.call_count, 5)

    def test_page_failure_does_not_trigger_native_fallback(self):
        result, frames, _, _ = self.run_controller([
            ('page',0,2), ('navigate','exit','')], fail_page=True)
        self.assertTrue(result)
        self.assertEqual(frames[-1][1][0]['page'], 1)

    def test_cancelled_search_keeps_page_without_reloading(self):
        _, frames, _, loader = self.run_controller([
            ('page',0,2), ('navigate','search',''), ('navigate','exit','')], cancel_search=True)
        self.assertEqual(frames[-1][1][0]['page'], 2)
        self.assertEqual(loader.call_count, 3)

    def test_initial_catalog_failure_stays_in_cinema_with_retry(self):
        result, frames, _, _ = self.run_controller([('navigate','exit','')], fail_initial=True)
        self.assertTrue(result)
        self.assertTrue(frames[0][1][0]['error'])

    def test_error_response_keeps_previous_page(self):
        _, frames, _, _ = self.run_controller([
            ('page',0,2), ('navigate','exit','')], error_page=True)
        self.assertEqual(frames[-1][1][0]['page'], 1)

    def test_abort_and_initialization_failure_close_once_without_loading(self):
        for options in ({'abort': True}, {'init_error': True}):
            with self.subTest(options=options):
                result, _, _, loader = self.run_controller([], **options)
                self.assertTrue(result)
                loader.assert_not_called()

    def test_focus_ribbon_is_visible_in_both_shelves(self):
        root = ET.parse(ADDON / 'resources/skins/Default/1080i/FelipeCinema.xml').getroot()
        for cid in ('400','410'):
            control = root.find("./controls/control[@id='{}']".format(cid))
            labels = [x.text for x in control.findall('./focusedlayout/control/label')]
            self.assertIn('▶ SELECIONADO', labels)

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
