; Generado por `gbband import-song` - no editar a mano
; SONG_BANK lo define la lista de canciones (build/list.asm) antes de incluir este archivo

SECTION "Cancion titulo A", ROMX[$4000], BANK[SONG_BANK]
Song_titulo::
    db "GBBS", 1
    db "TITULO              "
    db "GBBAND          "
    dw 1008, 180
    db 24
    dw 180
    db %00001111, 3
    dw Song_titulo_guitarra_facil
    dw Song_titulo_guitarra_medio
    dw Song_titulo_guitarra_dificil
    dw Song_titulo_guitarra_experto
    dw Song_titulo_teclado_facil
    dw Song_titulo_teclado_medio
    dw Song_titulo_teclado_dificil
    dw Song_titulo_teclado_experto
    dw Song_titulo_bajo_facil
    dw Song_titulo_bajo_medio
    dw Song_titulo_bajo_dificil
    dw Song_titulo_bajo_experto
    dw Song_titulo_bateria_facil
    dw Song_titulo_bateria_medio
    dw Song_titulo_bateria_dificil
    dw Song_titulo_bateria_experto
    dw $4000
    dw 0
    db SONG_BANK + 1 + 0
    dw $4025
    dw Song_titulo_keyframe0
    dw 192
    db SONG_BANK + 1 + 0
    dw $42A9
    dw Song_titulo_keyframe1
    dw 384
    db SONG_BANK + 1 + 0
    dw $451F
    dw Song_titulo_keyframe2
    dw 576
    db SONG_BANK + 1 + 0
    dw $47A3
    dw Song_titulo_keyframe3

Song_titulo_bajo_dificil:
    INCBIN "songs/titulo/chart_bajo_dificil.bin"
Song_titulo_bajo_experto:
    INCBIN "songs/titulo/chart_bajo_experto.bin"
Song_titulo_bajo_facil:
    INCBIN "songs/titulo/chart_bajo_facil.bin"
Song_titulo_bajo_medio:
    INCBIN "songs/titulo/chart_bajo_medio.bin"
Song_titulo_bateria_dificil:
    INCBIN "songs/titulo/chart_bateria_dificil.bin"
Song_titulo_bateria_experto:
    INCBIN "songs/titulo/chart_bateria_experto.bin"
Song_titulo_bateria_facil:
    INCBIN "songs/titulo/chart_bateria_facil.bin"
Song_titulo_bateria_medio:
    INCBIN "songs/titulo/chart_bateria_medio.bin"
Song_titulo_guitarra_dificil:
    INCBIN "songs/titulo/chart_guitarra_dificil.bin"
Song_titulo_guitarra_experto:
    INCBIN "songs/titulo/chart_guitarra_experto.bin"
Song_titulo_guitarra_facil:
    INCBIN "songs/titulo/chart_guitarra_facil.bin"
Song_titulo_guitarra_medio:
    INCBIN "songs/titulo/chart_guitarra_medio.bin"
Song_titulo_teclado_dificil:
    INCBIN "songs/titulo/chart_teclado_dificil.bin"
Song_titulo_teclado_experto:
    INCBIN "songs/titulo/chart_teclado_experto.bin"
Song_titulo_teclado_facil:
    INCBIN "songs/titulo/chart_teclado_facil.bin"
Song_titulo_teclado_medio:
    INCBIN "songs/titulo/chart_teclado_medio.bin"

Song_titulo_keyframe0:
    INCBIN "songs/titulo/keyframes.bin", 0, 34
Song_titulo_keyframe1:
    INCBIN "songs/titulo/keyframes.bin", 34, 34
Song_titulo_keyframe2:
    INCBIN "songs/titulo/keyframes.bin", 68, 34
Song_titulo_keyframe3:
    INCBIN "songs/titulo/keyframes.bin", 102, 34

SECTION "Cancion titulo B", ROMX[$4000], BANK[SONG_BANK + 1]
    INCBIN "songs/titulo/stream_b.bin"

SECTION "Cancion titulo C", ROMX[$4000], BANK[SONG_BANK + 2]
    INCBIN "songs/titulo/stream_c.bin"
