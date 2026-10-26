; Generado por audio/demo.py - no editar a mano
; (song_format.inc ya lo incluye main.asm)

SECTION "Cancion demo A", ROMX[$4000], BANK[16]
SongDemo::
    db "GBBS", 1
    db "ENSAYO          "
    db "GBBAND          "
    dw 2180, 200
    db 30, %0001, 3
    dw DemoChartGuitarFacil
    dw DemoChartGuitarMedio
    dw DemoChartGuitarDificil
    dw DemoChartGuitarExperto
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw 0
    dw $4000
    dw 0
    db 17
    dw $401C
    dw DemoKeyframe0
    dw 480
    db 17
    dw $415D
    dw DemoKeyframe1
    dw 960
    db 17
    dw $4391
    dw DemoKeyframe2
    dw 1440
    db 17
    dw $4601
    dw DemoKeyframe3

DemoChartGuitarFacil:
    INCBIN "songs/demo/chart_guitarra_facil.bin"
DemoChartGuitarMedio:
    INCBIN "songs/demo/chart_guitarra_medio.bin"
DemoChartGuitarDificil:
    INCBIN "songs/demo/chart_guitarra_dificil.bin"
DemoChartGuitarExperto:
    INCBIN "songs/demo/chart_guitarra_experto.bin"

DemoKeyframe0:
    INCBIN "songs/demo/keyframes.bin", 0, 32
DemoKeyframe1:
    INCBIN "songs/demo/keyframes.bin", 32, 36
DemoKeyframe2:
    INCBIN "songs/demo/keyframes.bin", 68, 36
DemoKeyframe3:
    INCBIN "songs/demo/keyframes.bin", 104, 36

SECTION "Cancion demo B", ROMX[$4000], BANK[17]
    INCBIN "songs/demo/stream_b.bin"

SECTION "Cancion demo C", ROMX[$4000], BANK[18]
    INCBIN "songs/demo/stream_c.bin"
