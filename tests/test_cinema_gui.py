"""Testes estruturais da experiência fullscreen sem motor de UI Kodi."""
import ast
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
