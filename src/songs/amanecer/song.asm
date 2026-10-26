; Generado por `gbband import-song` - no editar a mano
; SONG_BANK lo define la lista de canciones (build/list.asm) antes de incluir este archivo

SECTION "Cancion amanecer A", ROMX[$4000], BANK[SONG_BANK]
Song_amanecer::
    db "GBBS", 1
    db "AMANECER DIGITAL    "
    db "GBBAND          "
    dw 5616, 180
    db 28
    dw 180
    db %00001111, 3
    dw Song_amanecer_guitarra_facil
    dw Song_amanecer_guitarra_medio
    dw Song_amanecer_guitarra_dificil
    dw Song_amanecer_guitarra_experto
    dw Song_amanecer_teclado_facil
    dw Song_amanecer_teclado_medio
    dw Song_amanecer_teclado_dificil
    dw Song_amanecer_teclado_experto
    dw Song_amanecer_bajo_facil
    dw Song_amanecer_bajo_medio
    dw Song_amanecer_bajo_dificil
    dw Song_amanecer_bajo_experto
    dw Song_amanecer_bateria_facil
    dw Song_amanecer_bateria_medio
    dw Song_amanecer_bateria_dificil
    dw Song_amanecer_bateria_experto
    dw $4000
    dw 0
    db SONG_BANK + 1 + 0
    dw $4020
    dw Song_amanecer_keyframe0
    dw 1344
    db SONG_BANK + 1 + 0
    dw $4E44
    dw Song_amanecer_keyframe1
    dw 2688
    db SONG_BANK + 1 + 0
    dw $5A47
    dw Song_amanecer_keyframe2
    dw 4032
    db SONG_BANK + 1 + 0
    dw $6622
    dw Song_amanecer_keyframe3

Song_amanecer_bajo_dificil:
    INCBIN "songs/amanecer/chart_bajo_dificil.bin"
Song_amanecer_bajo_experto:
    INCBIN "songs/amanecer/chart_bajo_experto.bin"
Song_amanecer_bajo_facil:
    INCBIN "songs/amanecer/chart_bajo_facil.bin"
Song_amanecer_bajo_medio:
    INCBIN "songs/amanecer/chart_bajo_medio.bin"
Song_amanecer_bateria_dificil:
    INCBIN "songs/amanecer/chart_bateria_dificil.bin"
Song_amanecer_bateria_experto:
    INCBIN "songs/amanecer/chart_bateria_experto.bin"
Song_amanecer_bateria_facil:
    INCBIN "songs/amanecer/chart_bateria_facil.bin"
Song_amanecer_bateria_medio:
    INCBIN "songs/amanecer/chart_bateria_medio.bin"
Song_amanecer_guitarra_dificil:
    INCBIN "songs/amanecer/chart_guitarra_dificil.bin"
Song_amanecer_guitarra_experto:
    INCBIN "songs/amanecer/chart_guitarra_experto.bin"
Song_amanecer_guitarra_facil:
    INCBIN "songs/amanecer/chart_guitarra_facil.bin"
Song_amanecer_guitarra_medio:
    INCBIN "songs/amanecer/chart_guitarra_medio.bin"
Song_amanecer_teclado_dificil:
    INCBIN "songs/amanecer/chart_teclado_dificil.bin"
Song_amanecer_teclado_experto:
    INCBIN "songs/amanecer/chart_teclado_experto.bin"
Song_amanecer_teclado_facil:
    INCBIN "songs/amanecer/chart_teclado_facil.bin"
Song_amanecer_teclado_medio:
    INCBIN "songs/amanecer/chart_teclado_medio.bin"

Song_amanecer_keyframe0:
    INCBIN "songs/amanecer/keyframes.bin", 0, 31
Song_amanecer_keyframe1:
    INCBIN "songs/amanecer/keyframes.bin", 31, 31
Song_amanecer_keyframe2:
    INCBIN "songs/amanecer/keyframes.bin", 62, 31
Song_amanecer_keyframe3:
    INCBIN "songs/amanecer/keyframes.bin", 93, 31

SECTION "Cancion amanecer B", ROMX[$4000], BANK[SONG_BANK + 1]
    INCBIN "songs/amanecer/stream_b.bin"

SECTION "Cancion amanecer C", ROMX[$4000], BANK[SONG_BANK + 2]
    INCBIN "songs/amanecer/stream_c.bin"
