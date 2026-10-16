"""Testes executáveis sem instalar o Kodi."""

import hashlib
import runpy
import sys
import types
import unittest
from urllib.parse import urlencode
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://flyghtxmz.github.io/kodi-repo/"
BASE_REPO_URL = "https://raw.githubusercontent.com/flyghtxmz/kodi-repo/main/"

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
        self.assertEqual(directory.findtext("info"), BASE_REPO_URL + "addons.xml")
        self.assertEqual(directory.findtext("checksum"), BASE_REPO_URL + "addons.xml.md5")
        self.assertEqual(directory.findtext("datadir"), BASE_REPO_URL)
        self.assertEqual(directory.find("datadir").attrib["zip"], "true")
        version = manifest.getroot().attrib["version"]
        filename = f"repository.flyghtxmz-{version}.zip"
        self.assertTrue((ROOT / filename).exists())
        self.assertIn(f'href="{filename}"', (ROOT / "index.html").read_text())
        self.assertEqual(directory.findtext("hashes"), "false")
        self.assertEqual(manifest.find("./requires/import[@addon='xbmc.addon']").attrib["version"], "12.0.0")
        self.assertIsNotNone(manifest.find("./extension[@point='xbmc.addon.metadata']/summary[@lang='en_GB']"))

    def test_python_syntax(self):
        for file in (ROOT / "src").rglob("*.py"):
            compile(file.read_text(encoding="utf-8"), str(file), "exec")

class PluginTests(unittest.TestCase):
    def run_addon(self, action="", custom_url="", magnet_input="", elementum_installed=True, query=None, catalog_data=None):
        calls = {"items": [], "resolved": [], "ends": [], "settings": 0, "commands": [], "dialogs": []}
        xbmc = types.ModuleType("xbmc")
        xbmcaddon = types.ModuleType("xbmcaddon")
        xbmcgui = types.ModuleType("xbmcgui")
        xbmcplugin = types.ModuleType("xbmcplugin")

        class Addon:
            def __init__(self, id=None):
                if id == "plugin.video.elementum" and not elementum_installed:
                    raise RuntimeError("Elementum ausente")

            def getSetting(self, key):
                return custom_url if key == "custom_url" else ""

            def openSettings(self):
                calls["settings"] += 1

        class ListItem:
            def __init__(self, label="", path=""):
                self.label, self.path = label, path
                self.properties = {}
                self.art = {}
                self.info = {}

            def setProperty(self, key, val):
                self.properties[key] = val

            def setArt(self, artwork):
                self.art.update(artwork)

            def setInfo(self, media_type, data):
                self.info.update(data)

        class Dialog:
            def ok(self, title, message):
                calls["dialogs"].append((title, message))

            def input(self, *args, **kwargs):
                return magnet_input

            def select(self, title, options):
                return 0

            def yesno(self, title, message):
                return True

            def textviewer(self, title, content):
                calls["dialogs"].append((title, content))

        catalog_stub = types.ModuleType("catalog")
        catalog_stub.CATEGORIES = (
            ("destaques", "Mais populares"), ("filmes", "Filmes"),
            ("series", "Séries e programas"), ("documentarios", "Documentários"),
            ("animacoes", "Animações"), ("curtas", "Curtas-metragens"),
        )
        catalog_stub.search = lambda **kwargs: (catalog_data if catalog_data is not None else [], False)
        catalog_stub.playback = lambda identifier: {
            "title": "Vídeo licenciado", "url": "https://archive.org/download/demo/clip.mp4",
            "plot": "Teste", "thumb": "https://archive.org/services/img/demo",
        }
        recent_stub = types.ModuleType("recent")
        recent_stub.CATEGORIES = (
            ("movies_new", "Filmes de {year}"),
            ("movies_prev", "Filmes de {prev_year}"),
            ("movies_popular", "Filmes em alta"),
            ("series_new", "Séries de {year}"),
            ("series_popular", "Séries em alta"),
        )
        recent_stub.list_titles = lambda category, **kwargs: ([{
            "id":"tt1234567", "type":"movie", "title":"Movie Recent",
            "year":"2026", "plot":"Sinopse", "poster":"https://example.org/poster.jpg",
        }], False)
        recent_stub.detail = lambda ident, media="movie": {
            "id": ident, "type": media, "title": "Movie Recent",
            "year": "2026", "plot": "Sinopse", "rating": "7.5",
            "poster": "https://example.org/poster.jpg", "trailer_id": "ZkN2M4ODdys",
        }
        recent_stub.justwatch_search_url = lambda title: "https://www.justwatch.com/br/busca?q=Movie+Recent"
        xbmcaddon.Addon = Addon
        xbmc.executebuiltin = calls["commands"].append
        xbmcgui.INPUT_ALPHANUM = 0
        xbmcgui.ListItem = ListItem
        xbmcgui.Dialog = Dialog
        xbmcplugin.addDirectoryItem = lambda **kwargs: calls["items"].append(kwargs)
        xbmcplugin.setContent = lambda *args: None
        xbmcplugin.endOfDirectory = lambda *args, **kwargs: calls["ends"].append(True)
        xbmcplugin.setResolvedUrl = lambda *args: calls["resolved"].append(args)
        arguments = {"action": action} if action else {}
        arguments.update(query or {})
        argv = ["plugin://plugin.video.flyghtxmz/", "15", "?" + urlencode(arguments) if arguments else ""]
        with patch.dict(sys.modules, {"xbmc": xbmc, "xbmcaddon": xbmcaddon, "xbmcgui": xbmcgui,
                                      "xbmcplugin": xbmcplugin, "catalog": catalog_stub,
                                      "recent": recent_stub}):
            with patch.object(sys, "argv", argv):
                runpy.run_path(str(ROOT / "src/plugin.video.flyghtxmz/default.py"), run_name="__main__")
        return calls

    def test_menu_without_custom_video(self):
        result = self.run_addon()
        self.assertEqual(len(result["items"]), 21)
        self.assertEqual(len(result["ends"]), 1)
        self.assertTrue(result["items"][18]["listitem"].properties.get("IsPlayable"))

    def test_menu_with_custom_video(self):
        result = self.run_addon(custom_url="https://example.com/test.mp4")
        self.assertEqual(len(result["items"]), 22)

    def test_catalog_shows_directories_and_search(self):
        result = self.run_addon()
        self.assertTrue(all(result["items"][index]["isFolder"] for index in range(5)))
        self.assertTrue(all(result["items"][index]["isFolder"] for index in range(7, 13)))
        self.assertIn("action=search", result["items"][13]["url"])

    def test_catalog_lists_playable_items_with_cover(self):
        entry = {"identifier": "demo_id", "title": "Vídeo licenciado", "plot": "Sinopse",
                 "thumb": "https://archive.org/services/img/demo_id", "year": "2008"}
        result = self.run_addon("catalog", query={"category": "destaques"},
                                catalog_data=[entry])
        self.assertEqual(len(result["items"]), 1)
        video = result["items"][0]["listitem"]
        self.assertEqual(video.info["title"], "Vídeo licenciado")
        self.assertTrue(video.properties.get("IsPlayable"))
        self.assertEqual(video.art["thumb"], entry["thumb"])

    def test_catalog_plays_resolved_video_without_user_url(self):
        result = self.run_addon("catalog_play", query={"identifier": "demo"})
        self.assertEqual(result["resolved"][0][1], True)
        self.assertIn("archive.org/download", result["resolved"][0][2].path)

    def test_search_opens_catalog_using_user_title(self):
        result = self.run_addon("search", magnet_input="Open Film")
        self.assertEqual(len(result["commands"]), 1)
        self.assertIn("category=busca", result["commands"][0])
        self.assertIn("Open+Film", result["commands"][0])

    def test_recent_menu_uses_dynamic_sections(self):
        result = self.run_addon()
        self.assertIn("Filmes de", result["items"][0]["listitem"].label)
        self.assertIn("action=recent", result["items"][0]["url"])
        self.assertIn("action=recent_search", result["items"][5]["url"])

    def test_recent_list_has_poster_and_details(self):
        result = self.run_addon("recent", query={"category": "movies_new"})
        self.assertEqual(len(result["items"]), 1, result["dialogs"])
        self.assertTrue(result["items"][0]["isFolder"])
        self.assertIn("tt1234567", result["items"][0]["url"])
        self.assertEqual(result["items"][0]["listitem"].info["year"], 2026)

    def test_recent_details_offer_trailer_and_watch_options(self):
        result = self.run_addon("recent_detail", query={"identifier": "tt1234567", "media": "movie"})
        self.assertEqual(len(result["items"]), 4)
        self.assertIn("recent_elementum", result["items"][0]["url"])
        self.assertIn("recent_trailer", result["items"][1]["url"])
        self.assertIn("recent_where", result["items"][2]["url"])
        self.assertIn("recent_info", result["items"][3]["url"])

    def test_elementum_film_search_without_prowlarr(self):
        result = self.run_addon("recent_elementum", query={"identifier": "tt1234567"})
        self.assertEqual(len(result["commands"]), 1)
        self.assertIn("plugin.video.elementum/search?q=Movie+Recent+2026",
                      result["commands"][0])

    def test_elementum_film_search_without_elementum_installed(self):
        result = self.run_addon("recent_elementum",
                                query={"identifier": "tt1234567"},
                                elementum_installed=False)
        self.assertFalse(result["commands"])
        self.assertEqual(result["dialogs"][0][0], "Elementum necessário")

    def test_recent_where_opens_provider_search(self):
        result = self.run_addon("recent_where", query={"identifier": "tt1234567", "media": "movie"})
        self.assertEqual(len(result["commands"]), 1)
        self.assertIn("StartAndroidActivity(com.android.chrome", result["commands"][0])

    def test_recent_search_uses_keyboard(self):
        result = self.run_addon("recent_search", magnet_input="Avatar")
        self.assertEqual(len(result["commands"]), 1)
        self.assertIn("search_movie", result["commands"][0])
        self.assertIn("Avatar", result["commands"][0])

    def test_demo_playback(self):
        result = self.run_addon("demo")
        handle, okay, video = result["resolved"][0]
        self.assertTrue(okay)
        self.assertEqual(handle, 15)
        self.assertTrue(video.path.startswith("https://"))

    def test_custom_playback_rejects_untrusted_scheme(self):
        result = self.run_addon("custom", custom_url="file:///test.mp4")
        self.assertFalse(result["resolved"][0][1])


    def test_magnet_input_calls_elementum_with_encoded_uri(self):
        from urllib.parse import parse_qs, urlsplit
        magnet = "magnet:?xt=urn:btih:" + "a" * 40 + "&dn=Public Domain, A (Demo)"
        result = self.run_addon("torrent_input", magnet_input=magnet)
        self.assertEqual(len(result["ends"]), 1)
        self.assertEqual(len(result["commands"]), 1)
        command = result["commands"][0]
        self.assertTrue(command.startswith("PlayMedia(plugin://plugin.video.elementum/play?"))
        self.assertTrue(command.endswith(")"))
        url = command[len("PlayMedia("):-1]
        self.assertEqual(parse_qs(urlsplit(url).query)["uri"], [magnet])
        self.assertNotIn("Public Domain, A", command)

    def test_missing_elementum_uses_instruction_dialog(self):
        magnet = "magnet:?xt=urn:btih:" + "0" * 40
        result = self.run_addon("torrent_input", magnet_input=magnet, elementum_installed=False)
        self.assertFalse(result["commands"])
        self.assertEqual(result["dialogs"][0][0], "Elementum necessário")

    def test_invalid_hash_and_scheme_do_not_play(self):
        for invalid in ("magnet:?xt=urn:btih:oops", "javascript:alert(1)",
                        "file:///storage/movie.torrent", "https://x.invalid/file.mp4",
                        "magnet:?dn=sem-hash", "https://[broken/"):
            with self.subTest(invalid=invalid):
                result = self.run_addon("torrent_input", magnet_input=invalid)
                self.assertFalse(result["commands"])
                self.assertEqual(result["dialogs"][0][0], "Link inválido")

    def test_cancel_is_silent(self):
        result = self.run_addon("torrent_input", magnet_input="")
        self.assertEqual(result["dialogs"], [])
        self.assertFalse(result["commands"])

    def test_torrent_http_url_handoff(self):
        from urllib.parse import parse_qs, urlsplit
        uri = "https://example.com/free-film.torrent?key=foo&lang=pt"
        result = self.run_addon("torrent_input", magnet_input=uri)
        command = result["commands"][0]
        self.assertEqual(parse_qs(urlsplit(command[len("PlayMedia("):-1]).query)["uri"], [uri])

    def test_elementum_settings_and_missing_dependency(self):
        self.assertEqual(self.run_addon("elementum_settings")["settings"], 1)
        self.assertEqual(self.run_addon("elementum_settings", elementum_installed=False)["dialogs"][0][0], "Elementum necessário")

    def test_magnet_accepts_base32(self):
        magnet = "magnet:?xt=urn:btih:" + "A" * 32
        self.assertEqual(len(self.run_addon("torrent_input", magnet_input=magnet)["commands"]), 1)

    def test_settings_action(self):
        result = self.run_addon("settings")
        self.assertEqual(result["settings"], 1)

if __name__ == "__main__":
    unittest.main()
