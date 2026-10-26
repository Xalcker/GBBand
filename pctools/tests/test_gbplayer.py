"""Pruebas de gbplayer.js (el APU de "Escuchar" en el editor), con Node."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent


@pytest.fixture(scope="module")
def result():
    node = shutil.which("node")
    if not node:
        pytest.skip("hace falta Node")
    out = subprocess.run([node, str(HERE / "gbplayer_test.js")], capture_output=True, text=True, check=True).stdout
    return json.loads(out.strip().splitlines()[-1])


def test_pulso_a_440_hz(result):
    assert result["pulse_hz"] == pytest.approx(440, rel=0.02)
    assert result["other_channels_silent"]


def test_volumen_y_envolvente(result):
    assert result["half_ratio"] == pytest.approx(0.5, rel=0.05)
    assert result["env_end"] < result["env_start"] * 0.15  # la caída por hardware apaga la nota
    assert result["after_off"] < result["before_off"] * 0.02  # NRx2 = 0 apaga el canal


def test_wave_y_ruido(result):
    assert result["wave_hz"] == pytest.approx(110, rel=0.03)
    assert result["wave_rms"] > 0.01
    assert result["noise_rms"] > 0.02 and result["noise_after"] < result["noise_rms"] * 0.02


def test_la_mezcla_es_la_suma_de_los_canales(result):
    assert result["mix_error"] < 1e-6 and result["mix_peak"] <= 1.0