; Generado por `gbband import-song` - no editar a mano
; SONG_BANK lo define la lista de canciones (build/list.asm) antes de incluir este archivo

SECTION "Cancion carrera A", ROMX[$4000], BANK[SONG_BANK]
Song_carrera::
    db "GBBS", 1
    db "CARRERA DE FUEGO    "
    db "GBBAND          "
    dw 4720, 180
    db 20
    dw 180
    db %00001111, 3
    dw Song_carrera_guitarra_facil
    dw Song_carrera_guitarra_medio
    dw Song_carrera_guitarra_dificil
    dw Song_carrera_guitarra_experto
    dw Song_carrera_teclado_facil
    dw Song_carrera_teclado_medio
    dw Song_carrera_teclado_dificil
    dw Song_carrera_teclado_experto
    dw Song_carrera_bajo_facil
    dw Song_carrera_bajo_medio
    dw Song_carrera_bajo_dificil
    dw Song_carrera_bajo_experto
    dw Song_carrera_bateria_facil
    dw Song_carrera_bateria_medio
    dw Song_carrera_bateria_dificil
    dw Song_carrera_bateria_experto
    dw $4000
    dw 0
    db SONG_BANK + 1 + 0
    dw $4025
    dw Song_carrera_keyframe0
    dw 1120
    db SONG_BANK + 1 + 0
    dw $4EB9
    dw Song_carrera_keyframe1
    dw 2240
    db SONG_BANK + 1 + 0
    dw $5C52
    dw Song_carrera_keyframe2
    dw 3360
    db SONG_BANK + 1 + 0
    dw $6881
    dw Song_carrera_keyframe3

Song_carrera_bajo_dificil:
    INCBIN "songs/carrera/chart_bajo_dificil.bin"
Song_carrera_bajo_experto:
    INCBIN "songs/carrera/chart_bajo_experto.bin"
Song_carrera_bajo_facil:
    INCBIN "songs/carrera/chart_bajo_facil.bin"
Song_carrera_bajo_medio:
    INCBIN "songs/carrera/chart_bajo_medio.bin"
Song_carrera_bateria_dificil:
    INCBIN "songs/carrera/chart_bateria_dificil.bin"
Song_carrera_bateria_experto:
    INCBIN "songs/carrera/chart_bateria_experto.bin"
Song_carrera_bateria_facil:
    INCBIN "songs/carrera/chart_bateria_facil.bin"
Song_carrera_bateria_medio:
    INCBIN "songs/carrera/chart_bateria_medio.bin"
Song_carrera_guitarra_dificil:
    INCBIN "songs/carrera/chart_guitarra_dificil.bin"
Song_carrera_guitarra_experto:
    INCBIN "songs/carrera/chart_guitarra_experto.bin"
Song_carrera_guitarra_facil:
    INCBIN "songs/carrera/chart_guitarra_facil.bin"
Song_carrera_guitarra_medio:
    INCBIN "songs/carrera/chart_guitarra_medio.bin"
Song_carrera_teclado_dificil:
    INCBIN "songs/carrera/chart_teclado_dificil.bin"
Song_carrera_teclado_experto:
    INCBIN "songs/carrera/chart_teclado_experto.bin"
Song_carrera_teclado_facil:
    INCBIN "songs/carrera/chart_teclado_facil.bin"
Song_carrera_teclado_medio:
    INCBIN "songs/carrera/chart_teclado_medio.bin"

Song_carrera_keyframe0:
    INCBIN "songs/carrera/keyframes.bin", 0, 34
Song_carrera_keyframe1:
    INCBIN "songs/carrera/keyframes.bin", 34, 34
Song_carrera_keyframe2:
    INCBIN "songs/carrera/keyframes.bin", 68, 34
Song_carrera_keyframe3:
    INCBIN "songs/carrera/keyframes.bin", 102, 34

SECTION "Cancion carrera B", ROMX[$4000], BANK[SONG_BANK + 1]
    INCBIN "songs/carrera/stream_b.bin"

SECTION "Cancion carrera C", ROMX[$4000], BANK[SONG_BANK + 2]
    INCBIN "songs/carrera/stream_c.bin"
