; Generado por `gbband import-song` - no editar a mano
; SONG_BANK lo define la lista de canciones (build/list.asm) antes de incluir este archivo

SECTION "Cancion tormenta A", ROMX[$4000], BANK[SONG_BANK]
Song_tormenta::
    db "GBBS", 1
    db "TORMENTA DE NEON    "
    db "GBBAND          "
    dw 4720, 180
    db 20
    dw 180
    db %00001111, 3
    dw Song_tormenta_guitarra_facil
    dw Song_tormenta_guitarra_medio
    dw Song_tormenta_guitarra_dificil
    dw Song_tormenta_guitarra_experto
    dw Song_tormenta_teclado_facil
    dw Song_tormenta_teclado_medio
    dw Song_tormenta_teclado_dificil
    dw Song_tormenta_teclado_experto
    dw Song_tormenta_bajo_facil
    dw Song_tormenta_bajo_medio
    dw Song_tormenta_bajo_dificil
    dw Song_tormenta_bajo_experto
    dw Song_tormenta_bateria_facil
    dw Song_tormenta_bateria_medio
    dw Song_tormenta_bateria_dificil
    dw Song_tormenta_bateria_experto
    dw $4000
    dw 0
    db SONG_BANK + 1 + 0
    dw $4025
    dw Song_tormenta_keyframe0
    dw 1120
    db SONG_BANK + 1 + 0
    dw $4D63
    dw Song_tormenta_keyframe1
    dw 2240
    db SONG_BANK + 1 + 0
    dw $5AB8
    dw Song_tormenta_keyframe2
    dw 3360
    db SONG_BANK + 1 + 0
    dw $65A0
    dw Song_tormenta_keyframe3

Song_tormenta_bajo_dificil:
    INCBIN "songs/tormenta/chart_bajo_dificil.bin"
Song_tormenta_bajo_experto:
    INCBIN "songs/tormenta/chart_bajo_experto.bin"
Song_tormenta_bajo_facil:
    INCBIN "songs/tormenta/chart_bajo_facil.bin"
Song_tormenta_bajo_medio:
    INCBIN "songs/tormenta/chart_bajo_medio.bin"
Song_tormenta_bateria_dificil:
    INCBIN "songs/tormenta/chart_bateria_dificil.bin"
Song_tormenta_bateria_experto:
    INCBIN "songs/tormenta/chart_bateria_experto.bin"
Song_tormenta_bateria_facil:
    INCBIN "songs/tormenta/chart_bateria_facil.bin"
Song_tormenta_bateria_medio:
    INCBIN "songs/tormenta/chart_bateria_medio.bin"
Song_tormenta_guitarra_dificil:
    INCBIN "songs/tormenta/chart_guitarra_dificil.bin"
Song_tormenta_guitarra_experto:
    INCBIN "songs/tormenta/chart_guitarra_experto.bin"
Song_tormenta_guitarra_facil:
    INCBIN "songs/tormenta/chart_guitarra_facil.bin"
Song_tormenta_guitarra_medio:
    INCBIN "songs/tormenta/chart_guitarra_medio.bin"
Song_tormenta_teclado_dificil:
    INCBIN "songs/tormenta/chart_teclado_dificil.bin"
Song_tormenta_teclado_experto:
    INCBIN "songs/tormenta/chart_teclado_experto.bin"
Song_tormenta_teclado_facil:
    INCBIN "songs/tormenta/chart_teclado_facil.bin"
Song_tormenta_teclado_medio:
    INCBIN "songs/tormenta/chart_teclado_medio.bin"

Song_tormenta_keyframe0:
    INCBIN "songs/tormenta/keyframes.bin", 0, 34
Song_tormenta_keyframe1:
    INCBIN "songs/tormenta/keyframes.bin", 34, 34
Song_tormenta_keyframe2:
    INCBIN "songs/tormenta/keyframes.bin", 68, 34
Song_tormenta_keyframe3:
    INCBIN "songs/tormenta/keyframes.bin", 102, 34

SECTION "Cancion tormenta B", ROMX[$4000], BANK[SONG_BANK + 1]
    INCBIN "songs/tormenta/stream_b.bin"

SECTION "Cancion tormenta C", ROMX[$4000], BANK[SONG_BANK + 2]
    INCBIN "songs/tormenta/stream_c.bin"
