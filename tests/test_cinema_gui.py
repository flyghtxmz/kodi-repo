"""Testes estruturais da experiência fullscreen sem motor de UI Kodi."""
import ast
import importlib.util
import sys
import types
from unittest.mock import patch
from pathlib import Path
import xml.etree.ElementTree as ET
import unittest

ROOT=Path(__file__).resolve().parents[1]
ADDON=ROOT/"src/plugin.video.flyghtxmz"
XML=ADDON/"resources/skins/Default/1080i/FelipeCinema.xml"

class CinemaTests(unittest.TestCase):
    def test_dialog_is_fullscreen_modal_with_navigation_and_posters(self):
        root=ET.parse(XML).getroot()
        self.assertEqual(root.tag,"window")
        self.assertEqual(root.get("type"),"dialog")
        self.assertEqual(root.get("modality"),"modal")
        controls=root.findall("./controls/control")
        by_id={c.get("id"):c for c in controls}
        self.assertEqual(by_id["100"].get("type"),"list")
        self.assertEqual(by_id["400"].get("type"),"wraplist")
        self.assertEqual(by_id["10"].findtext("width"),"1920")
        self.assertEqual(by_id["10"].findtext("height"),"1080")
        self.assertEqual(by_id["400"].findtext("orientation"),"horizontal")
        self.assertIn("cinema-bg.png",XML.read_text(encoding="utf-8"))

    def test_movie_popup_runs_only_after_fullscreen_dialog_is_closed(self):
        events = []
        xbmc = types.ModuleType("xbmc")
        xbmc.LOGINFO, xbmc.LOGERROR = 1, 3
        xbmc.log = lambda *args: None
        xbmcgui = types.ModuleType("xbmcgui")
        xbmcaddon = types.ModuleType("xbmcaddon")
        xbmcaddon.Addon = lambda: types.SimpleNamespace(
            getAddonInfo=lambda name: "/fake/addon" if name == "path" else "")
        class FakeWindow:
            def __init__(self, *args):
                self.pending_selection = None
                self.classic_requested = False
            def doModal(self):
                events.append("modal_open")
                self.pending_selection = ("tt1234567", "movie")
                events.append("modal_closed")
        xbmcgui.WindowXMLDialog = FakeWindow
        xbmcgui.Dialog = lambda: types.SimpleNamespace(
            ok=lambda *args: events.append("error"))
        spec = importlib.util.spec_from_file_location(
            "cinema_under_test", ADDON/"cinema_gui.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"xbmc": xbmc, "xbmcgui": xbmcgui, "xbmcaddon": xbmcaddon}):
            spec.loader.exec_module(module)
            output = module.launch(
                lambda identifier, media: events.append(("select", identifier, media)))
        self.assertTrue(output)
        self.assertEqual(events, ["modal_open", "modal_closed",
                                  ("select", "tt1234567", "movie")])

    def test_poster_click_only_schedules_selection_and_closes_window(self):
        actions = []
        xbmc = types.ModuleType("xbmc")
        xbmcgui = types.ModuleType("xbmcgui")
        xbmcaddon = types.ModuleType("xbmcaddon")
        class FakeWindow:
            def getControl(self, control_id):
                return types.SimpleNamespace(getSelectedPosition=lambda: 0)
            def close(self):
                actions.append("closed")
        xbmcgui.WindowXMLDialog = FakeWindow
        spec = importlib.util.spec_from_file_location(
            "cinema_click_test", ADDON/"cinema_gui.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"xbmc": xbmc, "xbmcgui": xbmcgui, "xbmcaddon": xbmcaddon}):
            spec.loader.exec_module(module)
            dialog = module.CinemaWindow()
            dialog.movies = [{"id": "tt1234567", "media": "movie"}]
            dialog.pending_selection = None
            dialog.onClick(module.CONTROL_POSTERS)
        self.assertEqual(dialog.pending_selection, ("tt1234567", "movie"))
        self.assertEqual(actions, ["closed"])

    def test_resources_are_present(self):
        directory=ADDON/"resources/skins/Default/media"
        for resource in ("cinema-bg.png","cinema-white.png"):
            data=(directory/resource).read_bytes()
            self.assertTrue(data.startswith(bytes.fromhex("89504e470d0a1a0a")))

    def test_window_class_and_legacy_fallback_both_exist(self):
        root=ast.parse((ADDON/"cinema_gui.py").read_text(encoding="utf-8"))
        cls=next(node for node in root.body if isinstance(node,ast.ClassDef) and node.name=="CinemaWindow")
        self.assertTrue({"onInit","onClick","onAction","_load"}.issubset({
            node.name for node in cls.body if isinstance(node,ast.FunctionDef)}))
        main=(ADDON/"default.py").read_text(encoding="utf-8")
        self.assertIn('from cinema_gui import launch',main)
        self.assertIn('def show_classic_menu()',main)
        self.assertIn('finish_directory=False',main)
        self.assertIn('def show_recent_detail(identifier, media, finish_directory=True)',main)

if __name__=="__main__":
    unittest.main()
