# Presupuesto de VRAM

La tabla real se llena en la fase 2, con las mediciones de las colocaciones A y B. Por ahora solo hay lo de
la fase 1:

| Tiles | Uso |
|---|---|
| `$00`-`$1F` | libres (reservados para autopista, gemas y aros) |
| `$20`-`$5A` | fuente ASCII en mayúsculas (`src/chr/font.tiles`) |

Todo en modo `$8000` (`LCDC.4=1`) para fondo y sprites.
