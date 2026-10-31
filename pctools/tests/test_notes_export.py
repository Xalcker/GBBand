"""Pruebas de `gbband export-notes`: las notas de una fuente en JSON para arreglarlas en otra consola."""

import json

from gbband_tools import cli, notes_export, songs
from test_vgm import note_every, vgm_bytes


def test_notas_de_un_vgm(tmp_path):
    commands, total = note_every(16, 4)
    path = tmp_path / "prueba.vgm"
    path.write_bytes(vgm_bytes(commands, total))
    data = notes_export.export_notes(path, songs.Options(source=str(path), name="x"))
    assert data["title"] == "Pista" and data["game"] == "Juego" and data["frames"] == 64
    assert [n[0] for n in data["channels"]["Square1"]] == [0, 16, 32, 48]
    assert all(n[3] == 15 for n in data["channels"]["Square1"])  # el volumen de la envolvente ($F0)
    assert data["channels"]["Square2"] == [] and data["drums"] == []


def test_comando(tmp_path, monkeypatch):
    commands, total = note_every(16, 2)
    path = tmp_path / "prueba.vgm"
    path.write_bytes(vgm_bytes(commands, total))
    out = tmp_path / "notas.json"
    monkeypatch.setattr("sys.argv", ["gbband", "export-notes", str(path), "--out", str(out), "--title", "Otra"])
    cli.main()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["title"] == "Otra" and len(data["channels"]["Square1"]) == 2
