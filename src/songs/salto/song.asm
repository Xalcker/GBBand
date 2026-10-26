; Generado por `gbband import-song` - no editar a mano
; SONG_BANK lo define la lista de canciones (build/list.asm) antes de incluir este archivo

SECTION "Cancion salto A", ROMX[$4000], BANK[SONG_BANK]
Song_salto::
    db "GBBS", 1
    db "SALTO MORTAL        "
    db "GBBAND          "
    dw 6384, 180
    db 32
    dw 180
    db %00001111, 3
    dw Song_salto_guitarra_facil
    dw Song_salto_guitarra_medio
    dw Song_salto_guitarra_dificil
    dw Song_salto_guitarra_experto
    dw Song_salto_teclado_facil
    dw Song_salto_teclado_medio
    dw Song_salto_teclado_dificil
    dw Song_salto_teclado_experto
    dw Song_salto_bajo_facil
    dw Song_salto_bajo_medio
    dw Song_salto_bajo_dificil
    dw Song_salto_bajo_experto
    dw Song_salto_bateria_facil
    dw Song_salto_bateria_medio
    dw Song_salto_bateria_dificil
    dw Song_salto_bateria_experto
    dw $4000
    dw 0
    db SONG_BANK + 1 + 0
    dw $401A
    dw Song_salto_keyframe0
    dw 1536
    db SONG_BANK + 1 + 0
    dw $4BCB
    dw Song_salto_keyframe1
    dw 3072
    db SONG_BANK + 1 + 0
    dw $570B
    dw Song_salto_keyframe2
    dw 4608
    db SONG_BANK + 1 + 0
    dw $60CA
    dw Song_salto_keyframe3

Song_salto_bajo_dificil:
    INCBIN "songs/salto/chart_bajo_dificil.bin"
Song_salto_bajo_experto:
    INCBIN "songs/salto/chart_bajo_experto.bin"
Song_salto_bajo_facil:
    INCBIN "songs/salto/chart_bajo_facil.bin"
Song_salto_bajo_medio:
    INCBIN "songs/salto/chart_bajo_medio.bin"
Song_salto_bateria_dificil:
    INCBIN "songs/salto/chart_bateria_dificil.bin"
Song_salto_bateria_experto:
    INCBIN "songs/salto/chart_bateria_experto.bin"
Song_salto_bateria_facil:
    INCBIN "songs/salto/chart_bateria_facil.bin"
Song_salto_bateria_medio:
    INCBIN "songs/salto/chart_bateria_medio.bin"
Song_salto_guitarra_dificil:
    INCBIN "songs/salto/chart_guitarra_dificil.bin"
Song_salto_guitarra_experto:
    INCBIN "songs/salto/chart_guitarra_experto.bin"
Song_salto_guitarra_facil:
    INCBIN "songs/salto/chart_guitarra_facil.bin"
Song_salto_guitarra_medio:
    INCBIN "songs/salto/chart_guitarra_medio.bin"
Song_salto_teclado_dificil:
    INCBIN "songs/salto/chart_teclado_dificil.bin"
Song_salto_teclado_experto:
    INCBIN "songs/salto/chart_teclado_experto.bin"
Song_salto_teclado_facil:
    INCBIN "songs/salto/chart_teclado_facil.bin"
Song_salto_teclado_medio:
    INCBIN "songs/salto/chart_teclado_medio.bin"

Song_salto_keyframe0:
    INCBIN "songs/salto/keyframes.bin", 0, 28
Song_salto_keyframe1:
    INCBIN "songs/salto/keyframes.bin", 28, 31
Song_salto_keyframe2:
    INCBIN "songs/salto/keyframes.bin", 59, 28
Song_salto_keyframe3:
    INCBIN "songs/salto/keyframes.bin", 87, 31

SECTION "Cancion salto B", ROMX[$4000], BANK[SONG_BANK + 1]
    INCBIN "songs/salto/stream_b.bin"

SECTION "Cancion salto C", ROMX[$4000], BANK[SONG_BANK + 2]
    INCBIN "songs/salto/stream_c.bin"
