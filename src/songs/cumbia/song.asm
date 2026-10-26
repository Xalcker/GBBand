; Generado por `gbband import-song` - no editar a mano
; SONG_BANK lo define la lista de canciones (build/list.asm) antes de incluir este archivo

SECTION "Cancion cumbia A", ROMX[$4000], BANK[SONG_BANK]
Song_cumbia::
    db "GBBS", 1
    db "CUMBIA DEL CARTUCHO "
    db "GBBAND          "
    dw 6000, 180
    db 36
    dw 180
    db %00001111, 3
    dw Song_cumbia_guitarra_facil
    dw Song_cumbia_guitarra_medio
    dw Song_cumbia_guitarra_dificil
    dw Song_cumbia_guitarra_experto
    dw Song_cumbia_teclado_facil
    dw Song_cumbia_teclado_medio
    dw Song_cumbia_teclado_dificil
    dw Song_cumbia_teclado_experto
    dw Song_cumbia_bajo_facil
    dw Song_cumbia_bajo_medio
    dw Song_cumbia_bajo_dificil
    dw Song_cumbia_bajo_experto
    dw Song_cumbia_bateria_facil
    dw Song_cumbia_bateria_medio
    dw Song_cumbia_bateria_dificil
    dw Song_cumbia_bateria_experto
    dw $4000
    dw 0
    db SONG_BANK + 1 + 0
    dw $4025
    dw Song_cumbia_keyframe0
    dw 1440
    db SONG_BANK + 1 + 0
    dw $48A9
    dw Song_cumbia_keyframe1
    dw 2880
    db SONG_BANK + 1 + 0
    dw $515E
    dw Song_cumbia_keyframe2
    dw 4320
    db SONG_BANK + 1 + 0
    dw $59CD
    dw Song_cumbia_keyframe3

Song_cumbia_bajo_dificil:
    INCBIN "songs/cumbia/chart_bajo_dificil.bin"
Song_cumbia_bajo_experto:
    INCBIN "songs/cumbia/chart_bajo_experto.bin"
Song_cumbia_bajo_facil:
    INCBIN "songs/cumbia/chart_bajo_facil.bin"
Song_cumbia_bajo_medio:
    INCBIN "songs/cumbia/chart_bajo_medio.bin"
Song_cumbia_bateria_dificil:
    INCBIN "songs/cumbia/chart_bateria_dificil.bin"
Song_cumbia_bateria_experto:
    INCBIN "songs/cumbia/chart_bateria_experto.bin"
Song_cumbia_bateria_facil:
    INCBIN "songs/cumbia/chart_bateria_facil.bin"
Song_cumbia_bateria_medio:
    INCBIN "songs/cumbia/chart_bateria_medio.bin"
Song_cumbia_guitarra_dificil:
    INCBIN "songs/cumbia/chart_guitarra_dificil.bin"
Song_cumbia_guitarra_experto:
    INCBIN "songs/cumbia/chart_guitarra_experto.bin"
Song_cumbia_guitarra_facil:
    INCBIN "songs/cumbia/chart_guitarra_facil.bin"
Song_cumbia_guitarra_medio:
    INCBIN "songs/cumbia/chart_guitarra_medio.bin"
Song_cumbia_teclado_dificil:
    INCBIN "songs/cumbia/chart_teclado_dificil.bin"
Song_cumbia_teclado_experto:
    INCBIN "songs/cumbia/chart_teclado_experto.bin"
Song_cumbia_teclado_facil:
    INCBIN "songs/cumbia/chart_teclado_facil.bin"
Song_cumbia_teclado_medio:
    INCBIN "songs/cumbia/chart_teclado_medio.bin"

Song_cumbia_keyframe0:
    INCBIN "songs/cumbia/keyframes.bin", 0, 34
Song_cumbia_keyframe1:
    INCBIN "songs/cumbia/keyframes.bin", 34, 34
Song_cumbia_keyframe2:
    INCBIN "songs/cumbia/keyframes.bin", 68, 34
Song_cumbia_keyframe3:
    INCBIN "songs/cumbia/keyframes.bin", 102, 34

SECTION "Cancion cumbia B", ROMX[$4000], BANK[SONG_BANK + 1]
    INCBIN "songs/cumbia/stream_b.bin"

SECTION "Cancion cumbia C", ROMX[$4000], BANK[SONG_BANK + 2]
    INCBIN "songs/cumbia/stream_c.bin"
