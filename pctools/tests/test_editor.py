"""Pruebas del servidor del editor de charts (sin navegador): páginas, stream de "Escuchar" y validación."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from gbband_tools import audio_gb as gb
from gbband_tools import editor


@pytest.fixture(scope="module")
def server():
    app = editor.App(editor.load_song_source("luna"))
    httpd = editor.make_server(app, 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", app
    httpd.shutdown()
    httpd.server_close()


def get(url: str):
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8"), response.headers.get_content_type()


def post(url: str, body: dict, headers: dict | None = None):
    request = urllib.request.Request(url, json.dumps(body).encode("utf-8"), {"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def page_data(page: str) -> dict:
    return json.loads(page.split("const DATA = ")[1].split(";\n")[0])


def test_pagina_con_la_cancion_y_el_apu(server):
    url, _ = server
    page, kind = get(url + "/")
    assert kind == "text/html" and "GBBand - editor de charts" in page
    assert "const GbPlayer" in page and "NesPlayer" not in page and "__GBPLAYER__" not in page and "__DATA__" not in page
    data = page_data(page)
    assert data["title"] == "LUZ DE LUNA" and data["editable"] and data["audioFrames"] > 1000
    assert {"guitarra", "teclado", "bajo", "bateria"} == {i["name"] for i in data["instruments"]}


def test_stream_de_escuchar_es_el_de_la_rom(server):
    url, app = server
    payload = json.loads(get(url + "/api/player")[0])
    stream = (app.src.song_dir / "stream_b.bin").read_bytes() + (app.src.song_dir / "stream_c.bin").read_bytes()
    decoded = gb.decode_stream(stream)
    by_frame = {f: (wave, regs) for f, wave, regs in payload["frames"]}
    for index, fw in enumerate(decoded):
        written = {(gb.CHANNEL_BASE[ch] + r - 0xFF00, v) for ch, items in fw.channels.items() for r, v in items.items()}
        if not written and fw.wave is None:
            assert index not in by_frame
            continue
        wave, regs = by_frame[index]
        assert {tuple(x) for x in regs} == written
        assert (bytes(wave) if wave else None) == fw.wave


def test_validar_un_chart(server):
    url, _ = server
    note = lambda frame, mask: {"frame": frame, "mask": mask, "end": None, "star": False}
    status, body = post(url + "/api/validate", {"song": "luna", "key": "guitarra/experto", "chart": [note(300, 0b101)]})
    assert status == 200 and any(p["kind"] == "error" for p in body["problems"])  # verde + amarillo a la vez
    status, body = post(url + "/api/validate", {"song": "luna", "key": "guitarra/experto", "chart": [note(300, 0b1)]})
    assert status == 200 and not [p for p in body["problems"] if p["kind"] == "error"]


def test_guardar_sin_cambios_no_escribe_ediciones(server):
    url, app = server
    charts = page_data(get(url + "/")[0])["charts"]
    edits_file = app.src.song_dir / "edits.json"
    existed = edits_file.exists()
    status, body = post(url + "/api/save", {"song": "luna", "charts": charts})
    assert status == 200 and "(0 ediciones)" in body["message"]
    assert edits_file.exists() == existed


def test_otra_cancion_o_otro_origen_se_rechazan(server):
    url, _ = server
    status, body = post(url + "/api/save", {"song": "otra", "charts": {}})
    assert status == 400 and "ya no es la abierta" in body["error"]
    status, body = post(url + "/api/save", {"song": "luna", "charts": {}}, {"Origin": "http://malo.example"})
    assert status == 403


def test_menu_archivo(server):
    url, _ = server
    songs = json.loads(get(url + "/api/songs")[0])["songs"]
    assert {s["name"] for s in songs} >= {"luna", "tormenta", "demo"}
    sources = json.loads(get(url + "/api/sources")[0])["sources"]
    assert any(s["path"] == "audio/luna.txt" for s in sources)
