"""Diagnóstico local do repositório Felipe Addons em Kodi Android.

Executa solicitações de leitura dos três arquivos públicos. Não lê dados do usuário,
não testa torrents, não envia relatórios, nem altera configurações do aparelho.
"""
import hashlib
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

import xbmcvfs
import xbmcaddon

ROOT = "https://raw.githubusercontent.com/flyghtxmz/kodi-repo/main/"
TARGETS = ("addons.xml.md5", "addons.xml", "repository.flyghtxmz-1.0.3.zip")


def _data(value):
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    return value.encode("utf-8") if isinstance(value, str) else bytes(value)


def kodi_read(url):
    file = xbmcvfs.File(url, "r")
    try:
        return _data(file.readBytes(1048576))
    finally:
        file.close()


def python_read(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Kodi-Felipe-Diagnostic/1.0"})
    with urllib.request.urlopen(req, timeout=7) as response:
        return response.read(1048576)


def _error(exc):
    # A URL do próprio repositório não contém token/senha, mas não exibimos URLs extras.
    msg = str(exc).replace(ROOT, "<repo>")
    return "{}: {}".format(type(exc).__name__, msg[:180])


def recent_errors(logname="kodi.log"):
    """Filtra erros e o envio ao player no log local, sem expor URLs ou credenciais."""
    try:
        if logname not in ("kodi.log", "kodi.old.log"):
            return []
        path = xbmcvfs.translatePath("special://logpath/" + logname)
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            handle.seek(0, os.SEEK_END)
            length = handle.tell()
            handle.seek(max(0, length - 180000))
            lines = handle.read().splitlines()
        results = []
        for line in lines:
            lowered = line.lower()
            if not any(term in lowered for term in ("flyghtxmz", "felipe vídeos:", "felipe vídeos cinema:", "elementum", "crepository:")):
                continue
            if re.search(r"authorization|password|senha|token|setting auth|login", lowered):
                continue
            scrubbed = re.sub(r"(?:https?://|plugin://|magnet:\?)\S+", "<url>", line, flags=re.I)
            results.append(scrubbed[-260:])
        return results[-12:]
    except Exception:
        return []


def run_diagnostic():
    version = xbmcaddon.Addon().getAddonInfo("version")
    results = ["Felipe Vídeos " + version, "Teste de conectividade e reprodução local", ""]
    kodi_results = {}
    python_results = {}
    for target in TARGETS:
        url = ROOT + target
        try:
            kodi_results[target] = kodi_read(url)
            results.append("Kodi VFS {}: OK ({} bytes)".format(target, len(kodi_results[target])))
        except Exception as e:
            results.append("Kodi VFS {}: ERRO {}".format(target, _error(e)))
        try:
            python_results[target] = python_read(url)
            results.append("Python HTTPS {}: OK ({} bytes)".format(target, len(python_results[target])))
        except Exception as e:
            results.append("Python HTTPS {}: ERRO {}".format(target, _error(e)))
    results.append("")
    for origin, data in (("Kodi VFS", kodi_results), ("Python HTTPS", python_results)):
        try:
            actual = hashlib.md5(data["addons.xml"]).hexdigest()
            expected = data["addons.xml.md5"].decode("ascii").strip()
            addons = ET.fromstring(data["addons.xml"])
            ids = [node.get("id") for node in addons.findall("addon")]
            valid = actual == expected and "plugin.video.flyghtxmz" in ids
            results.append("{} catálogo/checksum: {}".format(origin, "OK" if valid else "DIVERGENTE"))
        except (KeyError, ValueError, ET.ParseError, UnicodeError) as e:
            results.append("{} catálogo/checksum: INDISPONÍVEL ({})".format(origin, _error(e)))
    recent = recent_errors()
    if recent:
        results.extend(["", "Log atual — reprodução/repositório (URLs ocultas):"] + recent)
    previous = recent_errors("kodi.old.log")
    if previous:
        results.extend(["", "Log da sessão anterior (útil após o Kodi fechar):"] + previous)
    results.extend(["", "Se o Kodi VFS falha e o Python funciona: possível problema no curl/TLS do Kodi.", "Se ambos funcionam: conferir log de CRepository e limpar estado antigo via reinstalação e atualizar addons.", "Envie uma foto desta tela para análise."])
    return "\n".join(results)
