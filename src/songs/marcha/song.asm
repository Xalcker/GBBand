; Generado por `gbband import-song` - no editar a mano
; SONG_BANK lo define la lista de canciones (build/list.asm) antes de incluir este archivo

SECTION "Cancion marcha A", ROMX[$4000], BANK[SONG_BANK]
Song_marcha::
    db "GBBS", 1
    db "MARCHA DEL CARTUCHO "
    db "GBBAND          "
    dw 5616, 180
    db 28
    dw 180
    db %00001111, 3
    dw Song_marcha_guitarra_facil
    dw Song_marcha_guitarra_medio
    dw Song_marcha_guitarra_dificil
    dw Song_marcha_guitarra_experto
    dw Song_marcha_teclado_facil
    dw Song_marcha_teclado_medio
    dw Song_marcha_teclado_dificil
    dw Song_marcha_teclado_experto
    dw Song_marcha_bajo_facil
    dw Song_marcha_bajo_medio
    dw Song_marcha_bajo_dificil
    dw Song_marcha_bajo_experto
    dw Song_marcha_bateria_facil
    dw Song_marcha_bateria_medio
    dw Song_marcha_bateria_dificil
    dw Song_marcha_bateria_experto
    dw $4000
    dw 0
    db SONG_BANK + 1 + 0
    dw $4020
    dw Song_marcha_keyframe0
    dw 1344
    db SONG_BANK + 1 + 0
    dw $493D
    dw Song_marcha_keyframe1
    dw 2688
    db SONG_BANK + 1 + 0
    dw $52A2
    dw Song_marcha_keyframe2
    dw 4032
    db SONG_BANK + 1 + 0
    dw $5C09
    dw Song_marcha_keyframe3

Song_marcha_bajo_dificil:
    INCBIN "songs/marcha/chart_bajo_dificil.bin"
Song_marcha_bajo_experto:
    INCBIN "songs/marcha/chart_bajo_experto.bin"
Song_marcha_bajo_facil:
    INCBIN "songs/marcha/chart_bajo_facil.bin"
Song_marcha_bajo_medio:
    INCBIN "songs/marcha/chart_bajo_medio.bin"
Song_marcha_bateria_dificil:
    INCBIN "songs/marcha/chart_bateria_dificil.bin"
Song_marcha_bateria_experto:
    INCBIN "songs/marcha/chart_bateria_experto.bin"
Song_marcha_bateria_facil:
    INCBIN "songs/marcha/chart_bateria_facil.bin"
Song_marcha_bateria_medio:
    INCBIN "songs/marcha/chart_bateria_medio.bin"
Song_marcha_guitarra_dificil:
    INCBIN "songs/marcha/chart_guitarra_dificil.bin"
Song_marcha_guitarra_experto:
    INCBIN "songs/marcha/chart_guitarra_experto.bin"
Song_marcha_guitarra_facil:
    INCBIN "songs/marcha/chart_guitarra_facil.bin"
Song_marcha_guitarra_medio:
    INCBIN "songs/marcha/chart_guitarra_medio.bin"
Song_marcha_teclado_dificil:
    INCBIN "songs/marcha/chart_teclado_dificil.bin"
Song_marcha_teclado_experto:
    INCBIN "songs/marcha/chart_teclado_experto.bin"
Song_marcha_teclado_facil:
    INCBIN "songs/marcha/chart_teclado_facil.bin"
Song_marcha_teclado_medio:
    INCBIN "songs/marcha/chart_teclado_medio.bin"

Song_marcha_keyframe0:
    INCBIN "songs/marcha/keyframes.bin", 0, 31
Song_marcha_keyframe1:
    INCBIN "songs/marcha/keyframes.bin", 31, 34
Song_marcha_keyframe2:
    INCBIN "songs/marcha/keyframes.bin", 65, 31
Song_marcha_keyframe3:
    INCBIN "songs/marcha/keyframes.bin", 96, 31

SECTION "Cancion marcha B", ROMX[$4000], BANK[SONG_BANK + 1]
    INCBIN "songs/marcha/stream_b.bin"

SECTION "Cancion marcha C", ROMX[$4000], BANK[SONG_BANK + 2]
    INCBIN "songs/marcha/stream_c.bin"
