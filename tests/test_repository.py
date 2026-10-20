"""Testes executáveis sem instalar o Kodi."""

import hashlib
import json
import runpy
import sys
import types
import unittest
from urllib.parse import urlencode, urlsplit, parse_qs
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
    def run_addon(self, action="", custom_url="", magnet_input="", elementum_installed=True, query=None, cloudflare_endpoint="", popup_choices=None, source_items=None, allow_zero_seed=True, player_active=False, subtitle_items=None, subtitle_error=None, elementum_enabled=True, player_open_response=None):
        calls = {"items": [], "resolved": [], "ends": [], "settings": 0, "commands": [], "dialogs": [], "popups": [], "lookups": [], "rpc": [], "play_requests": [], "notifications": [], "logs": []}
        choices = list(popup_choices) if popup_choices is not None else [0]
        xbmc = types.ModuleType("xbmc")
        xbmcaddon = types.ModuleType("xbmcaddon")
        xbmcgui = types.ModuleType("xbmcgui")
        xbmcplugin = types.ModuleType("xbmcplugin")

        class Addon:
            def __init__(self, id=None):
                if id == "plugin.video.elementum" and not elementum_installed:
                    raise RuntimeError("Elementum ausente")

            def getAddonInfo(self, key):
                return "0.1.114" if key == "version" else ""

            def getSetting(self, key):
                return custom_url if key == "custom_url" else (cloudflare_endpoint if key == "cloudflare_endpoint" else "")

            def openSettings(self):
                calls["settings"] += 1

        class FakeVideoInfoTag:
            def __init__(self):
                self.data = {}
            def setPlot(self, value):
                self.data["plot"] = value
            def setPlotOutline(self, value):
                self.data["plotoutline"] = value
            def setTitle(self, value):
                self.data["title"] = value
            def setMediaType(self, value):
                self.data["mediatype"] = value
            def setYear(self, value):
                self.data["year"] = value
            def setIMDBNumber(self, value):
                self.data["imdbnumber"] = value

        class ListItem:
            def __init__(self, label="", path=""):
                self.label, self.path = label, path
                self.properties = {}
                self.art = {}
                self.info = {}
                self.video_tag = FakeVideoInfoTag()

            def getVideoInfoTag(self):
                return self.video_tag

            def setProperty(self, key, val):
                self.properties[key] = val

            def setArt(self, artwork):
                self.art.update(artwork)

            def setInfo(self, media_type, data):
                self.info.update(data)

        class Dialog:
            def notification(self, title, message, **kwargs):
                calls["notifications"].append((title, message))

            def ok(self, title, message):
                calls["dialogs"].append((title, message))

            def input(self, *args, **kwargs):
                return magnet_input

            def select(self, title, options):
                calls["popups"].append((title, options))
                return choices.pop(0) if choices else -1

            def yesno(self, title, message):
                calls["dialogs"].append((title, message))
                return allow_zero_seed

            def textviewer(self, title, content):
                calls["dialogs"].append((title, content))

        metadata_stub = types.ModuleType("metadata_ptbr")
        metadata_stub.FALLBACK_SYNOPSIS = "Sinopse em português (Brasil) ainda não disponível."
        metadata_stub.descriptions_for_catalog = lambda movies, include_titles=False: {
            "{}:{}".format(movie["type"], movie["id"]): {
                "title": "Filme recente",
                "plot": "Uma história envolvente apresentada em português do Brasil."
            } for movie in movies
        }
        cloudflare_stub = types.ModuleType("cloudflare_client")
        def fake_sources(title, year="", imdb="", season=None, episode=None, quick=False):
            calls["lookups"].append((title, imdb, season, episode))
            return source_items if source_items is not None else [{
                "title": "Vídeo autorizado", "quality": "1080p", "size": 1024,
                "source": "Provedor de teste", "seeders": 8,
                "language": "pt-br", "url": "https://media.example.org/video.torrent",
            }]
        cloudflare_stub.list_sources = fake_sources
        cloudflare_stub.is_supported_source = lambda url: (
            url == "https://media.example.org/video.torrent" or
            (isinstance(url, str) and url.startswith("magnet:?xt=urn")))
        recent_stub = types.ModuleType("recent")
        recent_stub.CATEGORIES = (
            ("movies_new", "Filmes de {year}"),
            ("movies_prev", "Filmes de {prev_year}"),
            ("movies_prev2", "Filmes de {prev2_year}"),
            ("movies_popular", "Filmes em alta"),
            ("movies_rating", "Mais bem avaliados (IMDb)"),
            ("series_new", "Séries de {year}"),
            ("series_prev", "Séries de {prev_year}"),
            ("series_prev2", "Séries de {prev2_year}"),
            ("series_popular", "Séries em alta"),
            ("series_rating", "Mais bem avaliadas (IMDb)"),
        )
        recent_stub.GENRE_CATEGORIES = (
            ("movies_genre_action", "Ação"),
            ("movies_genre_horror", "Terror"),
            ("series_genre_drama", "Drama"),
            ("series_genre_reality", "Reality shows"),
        )
        recent_stub.list_titles = lambda category, **kwargs: ([{
            "id":"tt1234567", "type":"movie", "title":"Movie Recent",
            "year":"2026", "plot":"Sinopse", "poster":"https://example.org/poster.jpg",
        }], False)
        recent_stub.detail = lambda ident, media="movie": {
            "id": ident, "type": media, "title": "Movie Recent",
            "year": "2026", "plot": "Sinopse", "rating": "7.5",
            "poster": "https://example.org/poster.jpg", "trailer_id": "ZkN2M4ODdys",
            "original_title": "Test Series" if media == "series" else "Movie Recent",
            "episodes": ({
                0: [{"season": 0, "episode": 1, "title": "Especial", "id": ident + ":0:1"}],
                1: [
                    {"season": 1, "episode": 1, "title": "Piloto", "id": ident + ":1:1"},
                    {"season": 1, "episode": 3, "title": "Terceiro", "id": ident + ":1:3"},
                ],
                2: [{"season": 2, "episode": 8, "title": "Final", "id": ident + ":2:8"}],
            } if media == "series" else {}),
        }
        recent_stub.justwatch_search_url = lambda title: "https://www.justwatch.com/br/busca?q=Movie+Recent"
        xbmcaddon.Addon = Addon
        xbmc.executebuiltin = calls["commands"].append
        def execute_rpc(raw):
            request = json.loads(raw)
            calls["rpc"].append(request)
            if request["method"] == "Addons.GetAddonDetails":
                return json.dumps({"jsonrpc": "2.0", "id": request["id"],
                                   "result": {"addon": {"enabled": elementum_enabled}}})
            if request["method"] == "Player.Open":
                calls["play_requests"].append(request["params"]["item"]["file"])
                return player_open_response if player_open_response is not None else json.dumps({"result": "OK"})
            raise AssertionError("Método inesperado: " + request["method"])
        xbmc.executeJSONRPC = execute_rpc
        xbmc.LOGINFO, xbmc.LOGWARNING, xbmc.LOGERROR = 1, 2, 3
        xbmc.log = lambda message, level: calls["logs"].append((message, level))
        calls["subtitle_paths"] = []
        calls["subtitle_visibility"] = []
        xbmc.Player = lambda: types.SimpleNamespace(isPlayingVideo=lambda: player_active,
            getPlayingFile=lambda: "http://elementum.local/video.mkv",
            setSubtitles=calls["subtitle_paths"].append, showSubtitles=calls["subtitle_visibility"].append)
        subtitles_stub = types.ModuleType("subtitles_client")
        def save_context(*args, **kwargs):
            if subtitle_error:
                raise subtitle_error
        subtitles_stub.save_context = save_context
        subtitles_stub.list_subtitles = lambda context: subtitle_items or []
        subtitles_stub.download = lambda row: "/addon/profile/test.srt"
        cache_stub = types.ModuleType("local_cache")
        cache_stub.get = lambda *args: {"imdb": "tt1234567", "title": "Filme recente"}
        discovery_stub = types.ModuleType("discovery")
        discovery_stub.LANGUAGES = (("Português", "Portuguese"), ("Inglês", "English"))
        discovery_stub.COUNTRIES = (("Brasil — português", "Brazil", "Portuguese"),)
        discovery_stub.list_titles = lambda media, kind, value, page=1: ([{
            "id": "tt1234567", "type": media, "title": "Título localizado", "year": "2002",
            "plot": "Sinopse em português", "poster": "https://example.org/poster.jpg"}], True)
        xbmcgui.INPUT_ALPHANUM = 0
        xbmcgui.INPUT_NUMERIC = 1
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
                                      "xbmcplugin": xbmcplugin,
                                      "recent": recent_stub, "cloudflare_client": cloudflare_stub,
                                      "source_client": cloudflare_stub,
                                      "metadata_ptbr": metadata_stub, "subtitles_client": subtitles_stub,
                                      "local_cache": cache_stub, "discovery": discovery_stub}):
            with patch.object(sys, "argv", argv):
                runpy.run_path(str(ROOT / "src/plugin.video.flyghtxmz/default.py"), run_name="__main__")
        return calls

    def test_main_menu_is_short_and_categorized(self):
        result = self.run_addon()
        self.assertEqual(len(result["items"]), 5)
        labels = [i["listitem"].label for i in result["items"]]
        self.assertEqual(labels, ["Filmes", "Séries", "Buscar filmes e séries",
                                  "Ferramentas", "Sobre o Felipe Vídeos"])
        self.assertEqual(len(result["ends"]), 1)
        self.assertNotIn("Archive", " ".join(labels))
        self.assertNotIn("demo", " ".join(i["url"] for i in result["items"]))

    def test_explore_menu_and_filter_preserves_pagination(self):
        result = self.run_addon("explore", query={"media": "movie"})
        self.assertEqual([x["listitem"].label for x in result["items"]],
                         ["Escolher ano", "Idioma original", "País e idioma original", "Animes", "Clássicos por década"])
        page = self.run_addon("recent", query={"category": "movies_popular", "filter_kind": "language", "filter_value": "Portuguese"})
        self.assertEqual(page["items"][0]["listitem"].label, "Título localizado")
        self.assertIn("filter_kind=language", page["items"][-1]["url"])
        self.assertIn("filter_value=Portuguese", page["items"][-1]["url"])

    def test_movie_decades_have_direct_year_picker_popup(self):
        decades = self.run_addon("movie_decades")
        labels = [x["listitem"].label for x in decades["items"]]
        self.assertEqual(len(labels), 10)
        self.assertEqual(labels[0], "Filmes dos anos 2010")
        self.assertEqual(labels[-1], "Filmes dos anos 1920")
        self.assertTrue(all(not x["isFolder"] for x in decades["items"]))
        self.assertIn("decade=1980", decades["items"][3]["url"])

        year = self.run_addon("movie_decade_year", query={"decade": "1980"},
                              popup_choices=[5])
        self.assertEqual(len(year["popups"]), 1)
        self.assertEqual(year["popups"][0][1], [str(x) for x in range(1980, 1990)])
        self.assertIn("filter_kind=year", year["commands"][0])
        self.assertIn("filter_value=1985", year["commands"][0])
        self.assertIn("page=1", year["commands"][0])

    def test_invalid_or_cancelled_classic_selection_does_not_navigate(self):
        for decade, choices in (("1880", [0]), ("bogus", [0]), ("1990", [-1])):
            with self.subTest(decade=decade):
                result = self.run_addon("movie_decade_year",
                                        query={"decade": decade}, popup_choices=choices)
                self.assertEqual(result["commands"], [])
        movies = self.run_addon("recent", query={"category": "movies_popular",
            "filter_kind": "year", "filter_value": "1985"})
        self.assertTrue(movies["items"])
        self.assertFalse(movies["items"][0]["isFolder"])

    def test_year_picker_validates_and_opens_the_selected_year(self):
        result = self.run_addon("choose_filter", query={"media": "movie", "kind": "year"}, magnet_input="1999")
        self.assertIn("filter_value=1999", result["commands"][0])
        invalid = self.run_addon("choose_filter", query={"media": "movie", "kind": "year"}, magnet_input="../../")
        self.assertEqual(invalid["commands"], [])
        self.assertEqual(invalid["dialogs"][0][0], "Ano inválido")

    def test_subtitle_selection_requires_playback_and_applies_user_choice(self):
        stopped = self.run_addon("subtitles")
        self.assertEqual(stopped["subtitle_paths"], [])
        self.assertIn("Inicie o vídeo", stopped["dialogs"][0][1])
        played = self.run_addon("subtitles", player_active=True, popup_choices=[0],
                               subtitle_items=[{"label": "PT-BR | release de teste", "url": "https://subs5.strem.io/file/1"}])
        self.assertEqual(played["subtitle_paths"], ["/addon/profile/test.srt"])
        self.assertEqual(played["subtitle_visibility"], [True])

    def test_cancel_subtitles_leaves_playback_unchanged(self):
        result = self.run_addon("subtitles", player_active=True, popup_choices=[-1],
                                subtitle_items=[{"label": "PT-BR", "url": "https://subs5.strem.io/file/1"}])
        self.assertEqual(result["subtitle_paths"], [])

    def test_sections_and_tools(self):
        movies = self.run_addon("sections", query={"media": "movie"})
        series = self.run_addon("sections", query={"media": "series"})
        tools = self.run_addon("tools")
        self.assertEqual(len(movies["items"]), 11)
        self.assertEqual(len(series["items"]), 7)
        self.assertEqual([i["listitem"].label for i in movies["items"][5:9]], [
            "Clássicos e nostalgia (por década)", "Cinema brasileiro",
            "Filmes em português", "Animes e longas de animação japonesa"])
        self.assertIn("movie_decades", movies["items"][5]["url"])
        self.assertIn("filter_kind=country", movies["items"][6]["url"])
        self.assertIn("filter_value=Brazil", movies["items"][6]["url"])
        self.assertIn("filter_kind=language", movies["items"][7]["url"])
        self.assertIn("filter_kind=anime", movies["items"][8]["url"])
        self.assertEqual(len(tools["items"]), 8)
        self.assertEqual(movies["items"][-1]["listitem"].label, "Explorar catálogo")
        self.assertEqual(series["items"][-1]["listitem"].label, "Explorar catálogo")
        film_genres = self.run_addon("genres", query={"media": "movie"})
        show_genres = self.run_addon("genres", query={"media": "series"})
        self.assertEqual([x["listitem"].label for x in film_genres["items"]], ["Ação", "Terror"])
        self.assertEqual([x["listitem"].label for x in show_genres["items"]], ["Drama", "Reality shows"])
        self.assertTrue(all(x["isFolder"] for x in movies["items"]))
        self.assertIn("torrent_input", tools["items"][0]["url"])
        self.assertIn("elementum_settings", tools["items"][1]["url"])
        self.assertIn("elementum_test", tools["items"][2]["url"])

    def test_recent_list_has_poster_and_details(self):
        result = self.run_addon("recent", query={"category": "movies_new"})
        self.assertEqual(len(result["items"]), 1, result["dialogs"])
        self.assertFalse(result["items"][0]["isFolder"])
        self.assertIn("tt1234567", result["items"][0]["url"])
        self.assertEqual(result["items"][0]["listitem"].info["year"], 2026)
        self.assertEqual(result["items"][0]["listitem"].label, "Filme recente")
        self.assertEqual(result["items"][0]["listitem"].info["title"], "Filme recente")
        self.assertEqual(result["items"][0]["listitem"].info["plot"],
                         "Uma história envolvente apresentada em português do Brasil.")
        self.assertEqual(result["items"][0]["listitem"].info["plotoutline"],
                         "Uma história envolvente apresentada em português do Brasil.")
        self.assertEqual(result["items"][0]["listitem"].video_tag.data["plot"],
                         "Uma história envolvente apresentada em português do Brasil.")
        self.assertEqual(result["items"][0]["listitem"].video_tag.data["plotoutline"],
                         "Uma história envolvente apresentada em português do Brasil.")
        self.assertEqual(result["items"][0]["listitem"].video_tag.data["mediatype"], "movie")
        self.assertEqual(result["items"][0]["listitem"].video_tag.data["imdbnumber"], "tt1234567")
        self.assertNotIn("Abra o título", result["items"][0]["listitem"].info["plot"])

    def test_popup_title_choices_without_new_folder(self):
        result = self.run_addon("recent_detail",
            query={"identifier": "tt1234567", "media": "movie"},
            popup_choices=[-1])
        self.assertEqual(result["items"], [])
        self.assertEqual(len(result["popups"]), 1)
        self.assertEqual(result["popups"][0][1],
            ["Buscar fontes", "Ver trailer", "Onde assistir no Brasil"])
        self.assertEqual(result["commands"], [])

    def test_popup_source_selection_starts_elementum(self):
        result = self.run_addon("recent_detail",
            query={"identifier": "tt1234567", "media": "movie"},
            popup_choices=[0, 0])
        self.assertEqual(result["items"], [])
        self.assertEqual(len(result["popups"]), 2)
        self.assertIn("Provedor de teste", result["popups"][1][1][0])
        self.assertEqual(result["commands"], [])
        self.assertEqual(len(result["play_requests"]), 1)
        self.assertIn("plugin.video.elementum/play?uri=", result["play_requests"][0])
        self.assertEqual(len(result["notifications"]), 1)

    def test_quick_lookup_shows_more_sources_entry(self):
        result = self.run_addon("recent_detail",
            query={"identifier": "tt1234567", "media": "movie"},
            popup_choices=[0, -1])
        labels = result["popups"][1][1]
        self.assertTrue(any("Pesquisar mais fontes" in value for value in labels))
        self.assertTrue(any("Mostrar somente dublados/PT-BR" in value for value in labels))
        self.assertEqual(len(result["lookups"]), 1)
        self.assertEqual(result["play_requests"], [])
        self.assertTrue(any("diagnóstico busca de fontes" in row[0] for row in result["logs"]))

    def test_search_more_sources_reopens_popup_without_new_folder(self):
        result = self.run_addon("recent_detail",
            query={"identifier": "tt1234567", "media": "movie"},
            popup_choices=[0, 1, 0])
        self.assertEqual(len(result["popups"]), 3)
        self.assertEqual(len(result["lookups"]), 2)
        self.assertFalse(any("Pesquisar mais fontes" in value for value in result["popups"][2][1]))
        self.assertEqual(len(result["play_requests"]), 1)
        self.assertEqual(result["items"], [])

    def test_ptbr_only_option_filters_audio_selection(self):
        rows = [{
            "title": "Dublado", "source": "P1", "quality": "1080p",
            "size": 100, "seeders": 10, "language": "pt-br",
            "url": "https://media.example.org/video.torrent"
        },{
            "title": "Original", "source": "P2", "quality": "4K",
            "size": 100, "seeders": 30, "language": "en",
            "url": "https://media.example.org/video.torrent"
        }]
        result = self.run_addon("recent_detail", query={"identifier": "tt1234567"},
                                source_items=rows, popup_choices=[0, 3, 0])
        self.assertEqual(len(result["popups"]), 3)
        self.assertIn("Dublados/PT-BR", result["popups"][2][0])
        self.assertEqual(len(result["popups"][2][1]), 1)
        self.assertIn("Dublado", result["popups"][2][1][0])
        self.assertEqual(len(result["play_requests"]), 1)

    def test_playback_check_shows_no_confirmed_video(self):
        result = self.run_addon("playback_check")
        self.assertEqual(len(result["play_requests"]), 0)
        self.assertEqual(result["dialogs"][0][0],
                         "Felipe Vídeos — diagnóstico de reprodução")
        self.assertIn("não informa vídeo ativo", result["dialogs"][0][1])

    def test_zero_seed_source_warns_before_playback(self):
        empty = [{
            "title": "Filme sem peers", "source": "Torrentio", "quality": "1080p",
            "size": 2000, "seeders": 0, "language": "pt-br",
            "url": "https://media.example.org/video.torrent",
        }]
        cancelled = self.run_addon("recent_detail",
            query={"identifier": "tt1234567"},
            popup_choices=[0, 0], source_items=empty, allow_zero_seed=False)
        self.assertEqual(cancelled["commands"], [])
        self.assertEqual(cancelled["play_requests"], [])
        self.assertEqual(cancelled["dialogs"][0][0], "Fonte sem seeders")
        agreed = self.run_addon("recent_detail",
            query={"identifier": "tt1234567"},
            popup_choices=[0, 0], source_items=empty)
        self.assertEqual(len(agreed["play_requests"]), 1)

    def test_unknown_seeders_do_not_trigger_zero_seed_warning(self):
        source = [{
            "title": "Filme", "source": "Torrentio", "quality": "1080p",
            "size": 2000, "seeders": None, "language": "pt-br",
            "url": "https://media.example.org/video.torrent",
        }]
        result = self.run_addon("recent_detail",
            query={"identifier": "tt1234567"},
            popup_choices=[0, 0], source_items=source, allow_zero_seed=False)
        self.assertEqual(len(result["play_requests"]), 1)
        self.assertEqual(result["dialogs"], [])

    def test_old_cloudflare_action_opens_popup(self):
        result = self.run_addon("cloudflare_sources",
            query={"title": "Vídeo autorizado", "year": "2008", "identifier": "tt1234567"},
            popup_choices=[0])
        self.assertEqual(result["items"], [])
        self.assertEqual(len(result["popups"]), 1)
        self.assertEqual(len(result["play_requests"]), 1)

    def test_cancel_popup_does_not_start_playback(self):
        for picks in ([-1], [0, -1]):
            with self.subTest(picks=picks):
                result = self.run_addon("recent_detail",
                    query={"identifier": "tt1234567"}, popup_choices=picks)
                self.assertEqual(result["commands"], [])
                self.assertEqual(result["play_requests"], [])
                self.assertEqual(result["dialogs"], [])

    def test_logged_failure_case_magnet_hash_survives_outer_kodi_encoding(self):
        # Regression: screenshot 2026-10-18 showed missing info-hash from URI
        # for a Torrentio magnet with percent-encoded urn separators.
        hash_value = "a" * 40
        upstream = ("magnet:?xt=urn%3Abtih%3A" + hash_value +
                    "&dn=Film.Subs.EN%2FPTBR")
        response = self.run_addon("recent_detail",
            query={"identifier": "tt1234567"}, popup_choices=[0, 0],
            source_items=[{
                "title": "Film Subs EN/PTBR", "quality": "1080p",
                "seeders": 1, "size": 1200, "source": "Torrentio",
                "language": "unknown", "url": upstream, "file_index": 0
            }])
        self.assertEqual(len(response["play_requests"]), 1)
        handoff = response["play_requests"][0]
        self.assertNotIn("urn%253Abtih%253A", handoff)
        magnet = parse_qs(urlsplit(handoff).query)["uri"][0]
        self.assertEqual(parse_qs(urlsplit(magnet).query)["xt"],
                         ["urn:btih:" + hash_value])
        self.assertIn("magnet:?xt=urn:btih:", magnet)
        self.assertIn("oindex=0", handoff)

    def test_original_literal_magnet_unchanged_for_manual_input(self):
        original = "magnet:?xt=urn:btih:" + "a"*40 + "&dn=Public Domain, A (Demo)"
        result = self.run_addon("torrent_input", magnet_input=original)
        target = result["play_requests"][0]
        self.assertEqual(parse_qs(urlsplit(target).query)["uri"], [original])

    def test_source_file_index_is_sent_as_elementum_original_index(self):
        for file_index in (0, 3):
            result = self.run_addon("recent_detail", query={"identifier": "tt1234567"},
                popup_choices=[0, 0], source_items=[{
                    "title": "Arquivo do pacote", "source": "Torrentio", "quality": "1080p",
                    "language": "pt-br", "seeders": 8, "size": 1024,
                    "url": "https://media.example.org/video.torrent", "file_index": file_index,
                }])
            self.assertEqual(len(result["play_requests"]), 1)
            self.assertIn("&oindex={}".format(file_index), result["play_requests"][0])
            self.assertNotIn("&index=", result["play_requests"][0])

    def test_empty_sources_shows_message(self):
        result = self.run_addon("recent_detail",
            query={"identifier": "tt1234567"}, popup_choices=[0],
            source_items=[])
        self.assertEqual(len(result["popups"]), 1)
        self.assertEqual(result["dialogs"][0][0], "Nenhuma fonte disponível")

    def test_series_popup_shows_actual_seasons_not_folders(self):
        result = self.run_addon(
            "recent_detail", query={"identifier": "tt1234567", "media": "series"},
            popup_choices=[-1])
        self.assertEqual(result["items"], [])
        seasons = result["popups"][0][1]
        self.assertIn("Especiais (S00) — 1 episódio(s)", seasons)
        self.assertIn("Temporada 1 — 2 episódio(s)", seasons)
        self.assertIn("Temporada 2 — 1 episódio(s)", seasons)
        self.assertNotIn("Buscar fontes", seasons)

    def test_series_popup_uses_correct_season_episode_not_list_index(self):
        result = self.run_addon(
            "recent_detail", query={"identifier": "tt1234567", "media": "series"},
            popup_choices=[1, 1, 0])
        self.assertEqual(len(result["popups"]), 3)
        self.assertEqual(
            result["popups"][1][1],
            ["S01E01 — Piloto", "S01E03 — Terceiro"])
        self.assertIn("S01E03", result["popups"][2][0])
        self.assertEqual(result["lookups"], [("Test Series", "tt1234567", 1, 3)])
        self.assertEqual(len(result["play_requests"]), 1)

    def test_series_specials_and_episode_cancel(self):
        special = self.run_addon(
            "recent_detail", query={"identifier": "tt1234567", "media": "series"},
            popup_choices=[0, 0, 0])
        self.assertEqual(special["lookups"][0][2:], (0, 1))
        cancelled = self.run_addon(
            "recent_detail", query={"identifier": "tt1234567", "media": "series"},
            popup_choices=[2, -1])
        self.assertEqual(len(cancelled["popups"]), 2)
        self.assertEqual(cancelled["lookups"], [])
        self.assertEqual(cancelled["commands"], [])
        self.assertEqual(cancelled["play_requests"], [])

    def test_series_second_season_episode_eight(self):
        result = self.run_addon(
            "recent_detail", query={"identifier": "tt1234567", "media": "series"},
            popup_choices=[2, 0, 0])
        self.assertIn("S02E08", result["popups"][2][0])
        self.assertEqual(result["lookups"][0][2:], (2, 8))

    def test_cloudflare_rejects_untrusted_playback_links(self):
        result = self.run_addon("cloudflare_play", query={
            "url": "file:///tmp/malicious.torrent"})
        self.assertEqual(result["commands"], [])
        self.assertEqual(result["play_requests"], [])

    def test_recent_where_opens_provider_search(self):
        result = self.run_addon("recent_where", query={"identifier": "tt1234567", "media": "movie"})
        self.assertEqual(len(result["commands"]), 1)
        self.assertIn("StartAndroidActivity(com.android.chrome", result["commands"][0])

    def test_recent_search_uses_keyboard(self):
        result = self.run_addon("recent_search", magnet_input="Avatar")
        self.assertEqual(len(result["commands"]), 1)
        self.assertIn("search_movie", result["commands"][0])
        self.assertIn("Avatar", result["commands"][0])

    def test_magnet_input_calls_elementum_with_encoded_uri(self):
        from urllib.parse import parse_qs, urlsplit
        magnet = "magnet:?xt=urn:btih:" + "a" * 40 + "&dn=Public Domain, A (Demo)"
        result = self.run_addon("torrent_input", magnet_input=magnet)
        self.assertEqual(len(result["ends"]), 1)
        self.assertEqual(result["commands"], [])
        self.assertEqual(len(result["play_requests"]), 1)
        url = result["play_requests"][0]
        self.assertTrue(url.startswith("plugin://plugin.video.elementum/play?"))
        self.assertEqual(parse_qs(urlsplit(url).query)["uri"], [magnet])
        self.assertNotIn("Public Domain, A", url)

    def test_missing_elementum_uses_instruction_dialog(self):
        magnet = "magnet:?xt=urn:btih:" + "0" * 40
        result = self.run_addon("torrent_input", magnet_input=magnet, elementum_installed=False)
        self.assertFalse(result["commands"])
        self.assertFalse(result["play_requests"])
        self.assertEqual(result["dialogs"][0][0], "Elementum necessário")

    def test_invalid_hash_and_scheme_do_not_play(self):
        for invalid in ("magnet:?xt=urn:btih:oops", "javascript:alert(1)",
                        "file:///storage/movie.torrent", "https://x.invalid/file.mp4",
                        "magnet:?dn=sem-hash", "https://[broken/"):
            with self.subTest(invalid=invalid):
                result = self.run_addon("torrent_input", magnet_input=invalid)
                self.assertFalse(result["commands"])
                self.assertFalse(result["play_requests"])
                self.assertEqual(result["dialogs"][0][0], "Link inválido")

    def test_cancel_is_silent(self):
        result = self.run_addon("torrent_input", magnet_input="")
        self.assertEqual(result["dialogs"], [])
        self.assertFalse(result["commands"])
        self.assertFalse(result["play_requests"])

    def test_torrent_http_url_handoff(self):
        from urllib.parse import parse_qs, urlsplit
        uri = "https://example.com/free-film.torrent?key=foo&lang=pt"
        result = self.run_addon("torrent_input", magnet_input=uri)
        url = result["play_requests"][0]
        self.assertEqual(parse_qs(urlsplit(url).query)["uri"], [uri])

    def test_elementum_settings_and_missing_dependency(self):
        self.assertEqual(self.run_addon("elementum_settings")["settings"], 1)
        self.assertEqual(self.run_addon("elementum_settings", elementum_installed=False)["dialogs"][0][0], "Elementum necessário")

    def test_elementum_diagnostic_opens_the_addon_not_an_unverified_torrent(self):
        result = self.run_addon("elementum_test")
        self.assertEqual(len(result["ends"]), 1)
        self.assertEqual(len(result["commands"]), 1)
        self.assertEqual(
            result["commands"][0],
            "ActivateWindow(Videos,plugin://plugin.video.elementum/,return)")
        self.assertIn("0.1.114", result["dialogs"][0][1])

    def test_elementum_diagnostic_warns_if_addon_not_installed(self):
        result = self.run_addon("elementum_test", elementum_installed=False)
        self.assertEqual(result["commands"], [])
        self.assertEqual(result["dialogs"][0][0], "Elementum necessário")

    def test_magnet_accepts_base32(self):
        magnet = "magnet:?xt=urn:btih:" + "A" * 32
        self.assertEqual(len(self.run_addon("torrent_input", magnet_input=magnet)["play_requests"]), 1)

    def test_subtitle_cache_failure_does_not_block_selected_torrent(self):
        for error in (OSError("profile unavailable"), ValueError("corrupt cache"), RuntimeError("Kodi profile")):
            result = self.run_addon("recent_detail", query={"identifier": "tt1234567"},
                                    popup_choices=[0, 0], subtitle_error=error)
            self.assertEqual(len(result["play_requests"]), 1)
            self.assertEqual(result["dialogs"], [])
            self.assertTrue(any("contexto de legendas" in line for line, level in result["logs"]))

    def test_disabled_elementum_is_reported_without_starting_playback(self):
        result = self.run_addon("recent_detail", query={"identifier": "tt1234567"},
                                popup_choices=[0, 0], elementum_enabled=False)
        self.assertEqual(result["play_requests"], [])
        self.assertEqual(result["dialogs"][0][0], "Elementum desativado")
        self.assertEqual(result["notifications"], [])

    def test_kodi_rejection_is_visible_and_does_not_repeat_torrent(self):
        result = self.run_addon("recent_detail", query={"identifier": "tt1234567"},
                                popup_choices=[0, 0], player_open_response=json.dumps({
                                    "error": {"code": -32602, "message": "Invalid params"}}))
        self.assertEqual(len(result["play_requests"]), 1)
        self.assertEqual(result["commands"], [])
        self.assertEqual(result["dialogs"][0][0], "Falha ao abrir Elementum")
        self.assertIn("-32602", result["dialogs"][0][1])
        self.assertEqual(result["notifications"], [])

    def test_invalid_player_response_is_visible_without_second_playback(self):
        for payload in ("not JSON", "null", "{}"):
            result = self.run_addon("recent_detail", query={"identifier": "tt1234567"},
                                    popup_choices=[0, 0], player_open_response=payload)
            self.assertEqual(len(result["play_requests"]), 1)
            self.assertEqual(result["dialogs"][0][0], "Falha ao abrir Elementum")
            self.assertEqual(result["notifications"], [])

    def test_settings_action(self):
        result = self.run_addon("settings")
        self.assertEqual(result["settings"], 1)

if __name__ == "__main__":
    unittest.main()
