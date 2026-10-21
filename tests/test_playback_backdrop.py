"""Handoff lifecycle regressions; Kodi rendering requires a real device."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class BackdropTests(unittest.TestCase):
    def setUp(self):
        self.xbmc = types.SimpleNamespace(log=Mock(), LOGWARNING=2, Monitor=Mock(), Player=Mock(),
                                         getCondVisibility=Mock(return_value=False))
        modules = {'xbmc': self.xbmc, 'xbmcgui': types.SimpleNamespace(WindowXML=object),
                   'xbmcaddon': types.SimpleNamespace(Addon=Mock())}
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location('backdrop_test', ROOT / 'src/plugin.video.flyghtxmz/playback_backdrop.py')
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)
        self.window = Mock(dismissed=False)
        self.monitor = Mock()
        self.monitor.abortRequested.return_value = False
        self.monitor.waitForAbort.return_value = False
        self.player = Mock()
        self.player.isPlayingVideo.return_value = False

    def wait(self, ticks):
        self.module.wait_for_handoff(self.window, self.monitor, self.player,
                                     clock=Mock(side_effect=ticks))

    def test_playback_handoff_does_not_touch_player(self):
        self.player.isPlayingVideo.return_value = True
        self.wait([0])
        self.player.stop.assert_not_called()
        self.monitor.waitForAbort.assert_not_called()

    def test_progress_disappearance_ends_wait_after_grace(self):
        self.xbmc.getCondVisibility.side_effect = [True, False, False]
        self.wait([0, 1, 2, 3])
        self.assertEqual(self.monitor.waitForAbort.call_count, 2)

    def test_missing_progress_times_out_without_stopping_player(self):
        self.wait([0, 30])
        self.player.stop.assert_not_called()

    def test_long_buffer_has_visual_timeout(self):
        self.xbmc.getCondVisibility.return_value = True
        self.wait([0, 1200])
        self.monitor.waitForAbort.assert_not_called()

    def test_closed_window_does_not_wait(self):
        self.window.dismissed = True
        self.wait([0])
        self.player.isPlayingVideo.assert_not_called()

    def test_launch_once_when_window_cannot_open(self):
        launch = Mock(return_value=True)
        self.window.show.side_effect = RuntimeError('graphics')
        with patch.object(self.module, 'PlaybackBackdrop', return_value=self.window):
            self.assertTrue(self.module.launch_with_backdrop(launch, 'Filme', 'poster'))
        launch.assert_called_once_with()
        self.window.close.assert_called_once_with()

    def test_wait_failure_does_not_relaunch_or_change_result(self):
        launch = Mock(return_value=True)
        with patch.object(self.module, 'PlaybackBackdrop', return_value=self.window), patch.object(
                self.module, 'wait_for_handoff', side_effect=RuntimeError('graphics')):
            self.assertTrue(self.module.launch_with_backdrop(launch))
        launch.assert_called_once_with()
        self.window.close.assert_called_once_with()

    def test_rejected_request_closes_without_wait(self):
        with patch.object(self.module, 'PlaybackBackdrop', return_value=self.window), patch.object(
                self.module, 'wait_for_handoff') as wait:
            self.assertFalse(self.module.launch_with_backdrop(Mock(return_value=False)))
        wait.assert_not_called()
        self.window.close.assert_called_once_with()

    def test_launch_exception_closes_window(self):
        with patch.object(self.module, 'PlaybackBackdrop', return_value=self.window):
            with self.assertRaises(RuntimeError):
                self.module.launch_with_backdrop(Mock(side_effect=RuntimeError('launch')))
        self.window.close.assert_called_once_with()

    def test_layout_is_not_modal_or_fake_progress(self):
        root = ET.parse(ROOT / 'src/plugin.video.flyghtxmz/resources/skins/Default/1080i/FelipePlayback.xml').getroot()
        self.assertIsNone(root.get('modality'))
        self.assertIsNone(root.get('type'))
        self.assertFalse(root.findall('.//control[@type="progress"]'))
        self.assertFalse(root.findall('.//control[@type="button"]'))


if __name__ == '__main__':
    unittest.main()
