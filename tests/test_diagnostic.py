"""Diagnóstico exibe o envio ao Elementum sem expor URLs ou credenciais."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class DiagnosticTests(unittest.TestCase):
    def load(self, logfile=""):
        vfs = types.ModuleType("xbmcvfs")
        vfs.translatePath = lambda value: logfile
        addon = types.ModuleType("xbmcaddon")
        addon.Addon = lambda: types.SimpleNamespace(getAddonInfo=lambda key: "1.5.1")
        spec = importlib.util.spec_from_file_location("diagnostic", ROOT / "src/plugin.video.flyghtxmz/diagnostic.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"xbmcvfs": vfs, "xbmcaddon": addon}):
            spec.loader.exec_module(module)
        return module

    def test_elementum_and_launch_log_are_included_with_secrets_hidden(self):
        with tempfile.TemporaryDirectory() as directory:
            logfile = Path(directory) / "kodi.log"
            logfile.write_text("\n".join([
                "INFO unrelated component",
                "INFO Felipe Vídeos: Elementum Player.Open aceito pelo Kodi (oindex=0)",
                "ERROR Elementum loading magnet:?xt=urn:btih:abc&key=private",
                "ERROR Elementum plugin://plugin.video.elementum/play?uri=private",
                "ERROR Elementum https://remote.example/torrent?key=private",
                "DEBUG Elementum Setting auth to user:privatepass",
                "DEBUG Elementum password=privatepass",
            ]), encoding="utf-8")
            module = self.load(str(logfile))
            lines = "\n".join(module.recent_errors())
            self.assertIn("Player.Open aceito", lines)
            self.assertEqual(lines.count("<url>"), 3)
            self.assertNotIn("private", lines)
            self.assertNotIn("unrelated", lines)

    def test_crash_report_reads_previous_session_without_leaking_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "kodi.log").write_text(
                "INFO unrelated service\\n", encoding="utf-8")
            (Path(directory) / "kodi.old.log").write_text(
                "ERROR Felipe Vídeos Cinema: erro ao selecionar título\\n"
                "ERROR elementum magnet:?xt=urn:btih:secret&token=private\\n",
                encoding="utf-8")
            module = self.load(str(Path(directory) / "kodi.log"))
            module.xbmcvfs.translatePath = lambda target: str(
                Path(directory) / target.split("/")[-1])
            with patch.object(module, "kodi_read", side_effect=OSError("offline")), \
                    patch.object(module, "python_read", side_effect=OSError("offline")):
                report = module.run_diagnostic()
            self.assertIn("Log da sessão anterior", report)
            self.assertIn("erro ao selecionar", report)
            self.assertNotIn("token=private", report)
            self.assertIn("<url>", report)

    def test_diagnostic_header_uses_installed_addon_version(self):
        module = self.load()
        def unavailable(*args):
            raise OSError("unavailable")
        with patch.object(module, "kodi_read", side_effect=unavailable), \
                patch.object(module, "python_read", side_effect=unavailable):
            report = module.run_diagnostic()
        self.assertTrue(report.startswith("Felipe Vídeos 1.5.1\n"))
        self.assertNotIn("1.1.2", report)


if __name__ == "__main__":
    unittest.main()
