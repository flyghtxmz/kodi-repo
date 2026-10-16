"""Testes executáveis sem instalar o Kodi."""

import hashlib
import runpy
import sys
import types
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://flyghtxmz.github.io/kodi-repo/"

class RepositoryTests(unittest.TestCase):
    def test_addons_index_is_well_formed_and_matches_zips(self):
        index = ET.fromstring((ROOT / "addons.xml").read_bytes())
        expected = {"plugin.video.flyghtxmz", "repository.flyghtxmz"}
        self.assertEqual({a.get("id") for a in index.findall("addon")}, expected)
        for addon in index.findall("addon"):
            addon_id, version = addon.get("id"), addon.get("version")
            package = ROOT / addon_id / f"{addon_id}-{version}.zip"
            self.assertTrue(package.is_file(), str(package))
            with ZipFile(package) as archive:
                manifest = ET.fromstring(archive.read(f"{addon_id}/addon.xml"))
                self.assertEqual(manifest.get("id"), addon_id)
                self.assertEqual(manifest.get("version"), version)
                self.assertTrue(all(path.startswith(addon_id + "/") for path in archive.namelist()))

    def test_md5_matches_index(self):
        xml = (ROOT / "addons.xml").read_bytes()
        actual = (ROOT / "addons.xml.md5").read_text()
        self.assertEqual(hashlib.md5(xml).hexdigest(), actual)

    def test_repo_urls_and_install_source(self):
        manifest = ET.parse(ROOT / "src/repository.flyghtxmz/addon.xml")
        directory = manifest.find("./extension[@point='xbmc.addon.repository']/dir")
        self.assertEqual(directory.findtext("info"), BASE_URL + "addons.xml")
        self.assertEqual(directory.findtext("checksum"), BASE_URL + "addons.xml.md5")
        self.assertEqual(directory.findtext("datadir"), BASE_URL)
        self.assertEqual(directory.find("datadir").attrib["zip"], "true")
        self.assertTrue((ROOT / "repository.flyghtxmz-1.0.0.zip").exists())
        self.assertIn('href="repository.flyghtxmz-1.0.0.zip"', (ROOT / "index.html").read_text())

    def test_python_syntax(self):
        for file in (ROOT / "src").rglob("*.py"):
            compile(file.read_text(encoding="utf-8"), str(file), "exec")

class PluginTests(unittest.TestCase):
    def run_addon(self, action="", custom_url=""):
        calls = {"items": [], "resolved": [], "ends": [], "settings": 0}
        xbmcaddon = types.ModuleType("xbmcaddon")
        xbmcgui = types.ModuleType("xbmcgui")
        xbmcplugin = types.ModuleType("xbmcplugin")

        class Addon:
            def getSetting(self, key):
                return custom_url if key == "custom_url" else ""

            def openSettings(self):
                calls["settings"] += 1

        class ListItem:
            def __init__(self, label="", path=""):
                self.label, self.path = label, path
                self.properties = {}

            def setProperty(self, key, val):
                self.properties[key] = val

        class Dialog:
            def ok(self, title, message):
                calls["dialog"] = title + message

        xbmcaddon.Addon = Addon
        xbmcgui.ListItem = ListItem
        xbmcgui.Dialog = Dialog
        xbmcplugin.addDirectoryItem = lambda **kwargs: calls["items"].append(kwargs)
        xbmcplugin.setContent = lambda *args: None
        xbmcplugin.endOfDirectory = lambda *args, **kwargs: calls["ends"].append(True)
        xbmcplugin.setResolvedUrl = lambda *args: calls["resolved"].append(args)
        argv = ["plugin://plugin.video.flyghtxmz/", "15", ("?action=" + action) if action else ""]
        with patch.dict(sys.modules, {"xbmcaddon": xbmcaddon, "xbmcgui": xbmcgui, "xbmcplugin": xbmcplugin}):
            with patch.object(sys, "argv", argv):
                runpy.run_path(str(ROOT / "src/plugin.video.flyghtxmz/default.py"), run_name="__main__")
        return calls

    def test_menu_without_custom_video(self):
        result = self.run_addon()
        self.assertEqual(len(result["items"]), 3)
        self.assertEqual(len(result["ends"]), 1)
        self.assertTrue(result["items"][0]["listitem"].properties.get("IsPlayable"))

    def test_menu_with_custom_video(self):
        result = self.run_addon(custom_url="https://example.com/test.mp4")
        self.assertEqual(len(result["items"]), 4)

    def test_demo_playback(self):
        result = self.run_addon("demo")
        handle, okay, video = result["resolved"][0]
        self.assertTrue(okay)
        self.assertEqual(handle, 15)
        self.assertTrue(video.path.startswith("https://"))

    def test_custom_playback_rejects_untrusted_scheme(self):
        result = self.run_addon("custom", custom_url="file:///test.mp4")
        self.assertFalse(result["resolved"][0][1])

    def test_settings_action(self):
        result = self.run_addon("settings")
        self.assertEqual(result["settings"], 1)

if __name__ == "__main__":
    unittest.main()
