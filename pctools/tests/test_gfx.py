import pytest

from gbband_tools import gfx


def test_encode_tile_entrelaza_planos():
    # Fila 0: colores 0,1,2,3,0,1,2,3 -> plano 0 = 01010101, plano 1 = 00110011
    rows = ["01230123"] + ["........"] * 7
    data = gfx.encode_tile(rows)
    assert len(data) == 16
    assert data[0] == 0b01010101 and data[1] == 0b00110011
    assert data[2:] == bytes(14)


def test_ida_y_vuelta():
    art = {0: ["01230123"] * 8, 3: ["3......1"] * 8}
    decoded = gfx.decode_2bpp(gfx.build_2bpp(art))
    assert len(decoded) == 4
    assert decoded[0] == ["01230123"] * 8
    assert decoded[3] == ["30000001"] * 8
    assert decoded[1] == ["00000000"] * 8  # hueco en blanco


def test_parse_numeracion_y_arroba():
    text = "# c\n@20 ; ' '\n" + "........\n" * 8 + "11111111\n" * 8 + "@30\n" + "22222222\n" * 8
    tiles = gfx.parse_tiles(text)
    assert sorted(tiles) == [0x20, 0x21, 0x30]


def test_parse_errores():
    with pytest.raises(ValueError):
        gfx.parse_tiles("@0\n........\n")  # tile incompleto
    with pytest.raises(ValueError):
        gfx.parse_tiles("@0\n" + "9.......\n" * 8)  # color inválido


def test_fuente_versionada_es_valida():
    from pathlib import Path

    font = Path(__file__).resolve().parents[2] / "src" / "chr" / "font.tiles"
    tiles = gfx.parse_tiles(font.read_text(encoding="utf-8"), font.name)
    assert 0x41 in tiles and 0x5A in tiles  # A y Z
