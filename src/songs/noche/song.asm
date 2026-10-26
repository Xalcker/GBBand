; Generado por `gbband import-song` - no editar a mano
; SONG_BANK lo define la lista de canciones (build/list.asm) antes de incluir este archivo

SECTION "Cancion noche A", ROMX[$4000], BANK[SONG_BANK]
Song_noche::
    db "GBBS", 1
    db "NOCHE SIN ESTRELLAS "
    db "GBBAND          "
    dw 5232, 180
    db 24
    dw 180
    db %00001111, 3
    dw Song_noche_guitarra_facil
    dw Song_noche_guitarra_medio
    dw Song_noche_guitarra_dificil
    dw Song_noche_guitarra_experto
    dw Song_noche_teclado_facil
    dw Song_noche_teclado_medio
    dw Song_noche_teclado_dificil
    dw Song_noche_teclado_experto
    dw Song_noche_bajo_facil
    dw Song_noche_bajo_medio
    dw Song_noche_bajo_dificil
    dw Song_noche_bajo_experto
    dw Song_noche_bateria_facil
    dw Song_noche_bateria_medio
    dw Song_noche_bateria_dificil
    dw Song_noche_bateria_experto
    dw $4000
    dw 0
    db SONG_BANK + 1 + 0
    dw $4025
    dw Song_noche_keyframe0
    dw 1248
    db SONG_BANK + 1 + 0
    dw $4F2C
    dw Song_noche_keyframe1
    dw 2496
    db SONG_BANK + 1 + 0
    dw $5BB6
    dw Song_noche_keyframe2
    dw 3744
    db SONG_BANK + 1 + 0
    dw $67AF
    dw Song_noche_keyframe3

Song_noche_bajo_dificil:
    INCBIN "songs/noche/chart_bajo_dificil.bin"
Song_noche_bajo_experto:
    INCBIN "songs/noche/chart_bajo_experto.bin"
Song_noche_bajo_facil:
    INCBIN "songs/noche/chart_bajo_facil.bin"
Song_noche_bajo_medio:
    INCBIN "songs/noche/chart_bajo_medio.bin"
Song_noche_bateria_dificil:
    INCBIN "songs/noche/chart_bateria_dificil.bin"
Song_noche_bateria_experto:
    INCBIN "songs/noche/chart_bateria_experto.bin"
Song_noche_bateria_facil:
    INCBIN "songs/noche/chart_bateria_facil.bin"
Song_noche_bateria_medio:
    INCBIN "songs/noche/chart_bateria_medio.bin"
Song_noche_guitarra_dificil:
    INCBIN "songs/noche/chart_guitarra_dificil.bin"
Song_noche_guitarra_experto:
    INCBIN "songs/noche/chart_guitarra_experto.bin"
Song_noche_guitarra_facil:
    INCBIN "songs/noche/chart_guitarra_facil.bin"
Song_noche_guitarra_medio:
    INCBIN "songs/noche/chart_guitarra_medio.bin"
Song_noche_teclado_dificil:
    INCBIN "songs/noche/chart_teclado_dificil.bin"
Song_noche_teclado_experto:
    INCBIN "songs/noche/chart_teclado_experto.bin"
Song_noche_teclado_facil:
    INCBIN "songs/noche/chart_teclado_facil.bin"
Song_noche_teclado_medio:
    INCBIN "songs/noche/chart_teclado_medio.bin"

Song_noche_keyframe0:
    INCBIN "songs/noche/keyframes.bin", 0, 34
Song_noche_keyframe1:
    INCBIN "songs/noche/keyframes.bin", 34, 34
Song_noche_keyframe2:
    INCBIN "songs/noche/keyframes.bin", 68, 34
Song_noche_keyframe3:
    INCBIN "songs/noche/keyframes.bin", 102, 34

SECTION "Cancion noche B", ROMX[$4000], BANK[SONG_BANK + 1]
    INCBIN "songs/noche/stream_b.bin"

SECTION "Cancion noche C", ROMX[$4000], BANK[SONG_BANK + 2]
    INCBIN "songs/noche/stream_c.bin"
