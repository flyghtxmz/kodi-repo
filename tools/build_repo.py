#!/usr/bin/env python3
"""Empacota addons e regenera o índice compatível com repositórios Kodi."""

import hashlib
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
REPOSITORY_ID = "repository.flyghtxmz"

def addon_sources():
    addons = sorted(SRC.glob("*/addon.xml"))
    if not addons:
        raise RuntimeError("Nenhum addon.xml encontrado em src/")
    return addons

def bundle(directory, version):
    addon_id = directory.name
    output_dir = ROOT / addon_id
    output_dir.mkdir(exist_ok=True)
    destination = output_dir / f"{addon_id}-{version}.zip"
    with ZipFile(destination, mode="w", compression=ZIP_DEFLATED) as archive:
        for file in sorted(directory.rglob("*")):
            if not file.is_file() or any(part in {"__pycache__", ".DS_Store"} for part in file.parts) or file.suffix in {".pyc", ".pyo"}:
                continue
            relative = file.relative_to(SRC).as_posix()
            entry = ZipInfo(relative, date_time=(2024, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, file.read_bytes())
    return destination

def build():
    index = ET.Element("addons")
    repo_zip = None
    for xml_path in addon_sources():
        addon = ET.parse(xml_path).getroot()
        addon_id = addon.attrib.get("id")
        version = addon.attrib.get("version")
        if addon_id != xml_path.parent.name or not version:
            raise ValueError(f"Manifest inválido: {xml_path}")
        index.append(addon)
        zip_path = bundle(xml_path.parent, version)
        if addon_id == REPOSITORY_ID:
            repo_zip = zip_path
    if not repo_zip:
        raise ValueError(f"Manifest {REPOSITORY_ID} não encontrado")
    ET.indent(index, space="  ")
    xml_data = ET.tostring(index, encoding="utf-8", xml_declaration=True)
    (ROOT / "addons.xml").write_bytes(xml_data)
    (ROOT / "addons.xml.md5").write_text(hashlib.md5(xml_data).hexdigest(), encoding="ascii")
    destination = ROOT / repo_zip.name
    shutil.copy2(repo_zip, destination)
    index_page = (
        '<!DOCTYPE html>\n<html><head><meta charset="utf-8">'
        '<title>Felipe Addons Kodi</title></head><body>\n'
        f'<a href="{destination.name}">{destination.name}</a>\n'
        '<p>Instalador do repositório Kodi. Abra este endereço no File Manager do Kodi.</p>\n'
        f'<a href="plugin.video.flyghtxmz/plugin.video.flyghtxmz-{ET.parse(SRC / "plugin.video.flyghtxmz" / "addon.xml").getroot().attrib["version"]}.zip">Felipe Vídeos - instalador direto e diagnóstico</a>\n'
        '</body></html>\n'
    )
    (ROOT / "index.html").write_text(index_page, encoding="utf-8")
    (ROOT / ".nojekyll").touch()
    print(f"OK: gerado {destination.name}, addons.xml e ZIPs de {len(index)} addons")

if __name__ == "__main__":
    build()
