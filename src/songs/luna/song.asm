; Generado por `gbband import-song` - no editar a mano
; SONG_BANK lo define la lista de canciones (build/list.asm) antes de incluir este archivo

SECTION "Cancion luna A", ROMX[$4000], BANK[SONG_BANK]
Song_luna::
    db "GBBS", 1
    db "LUZ DE LUNA         "
    db "GBBAND          "
    dw 5872, 180
    db 32
    dw 180
    db %00001111, 3
    dw Song_luna_guitarra_facil
    dw Song_luna_guitarra_medio
    dw Song_luna_guitarra_dificil
    dw Song_luna_guitarra_experto
    dw Song_luna_teclado_facil
    dw Song_luna_teclado_medio
    dw Song_luna_teclado_dificil
    dw Song_luna_teclado_experto
    dw Song_luna_bajo_facil
    dw Song_luna_bajo_medio
    dw Song_luna_bajo_dificil
    dw Song_luna_bajo_experto
    dw Song_luna_bateria_facil
    dw Song_luna_bateria_medio
    dw Song_luna_bateria_dificil
    dw Song_luna_bateria_experto
    dw $4000
    dw 0
    db SONG_BANK + 1 + 0
    dw $4025
    dw Song_luna_keyframe0
    dw 1408
    db SONG_BANK + 1 + 0
    dw $45CE
    dw Song_luna_keyframe1
    dw 2816
    db SONG_BANK + 1 + 0
    dw $4BFC
    dw Song_luna_keyframe2
    dw 4224
    db SONG_BANK + 1 + 0
    dw $5229
    dw Song_luna_keyframe3

Song_luna_bajo_dificil:
    INCBIN "songs/luna/chart_bajo_dificil.bin"
Song_luna_bajo_experto:
    INCBIN "songs/luna/chart_bajo_experto.bin"
Song_luna_bajo_facil:
    INCBIN "songs/luna/chart_bajo_facil.bin"
Song_luna_bajo_medio:
    INCBIN "songs/luna/chart_bajo_medio.bin"
Song_luna_bateria_dificil:
    INCBIN "songs/luna/chart_bateria_dificil.bin"
Song_luna_bateria_experto:
    INCBIN "songs/luna/chart_bateria_experto.bin"
Song_luna_bateria_facil:
    INCBIN "songs/luna/chart_bateria_facil.bin"
Song_luna_bateria_medio:
    INCBIN "songs/luna/chart_bateria_medio.bin"
Song_luna_guitarra_dificil:
    INCBIN "songs/luna/chart_guitarra_dificil.bin"
Song_luna_guitarra_experto:
    INCBIN "songs/luna/chart_guitarra_experto.bin"
Song_luna_guitarra_facil:
    INCBIN "songs/luna/chart_guitarra_facil.bin"
Song_luna_guitarra_medio:
    INCBIN "songs/luna/chart_guitarra_medio.bin"
Song_luna_teclado_dificil:
    INCBIN "songs/luna/chart_teclado_dificil.bin"
Song_luna_teclado_experto:
    INCBIN "songs/luna/chart_teclado_experto.bin"
Song_luna_teclado_facil:
    INCBIN "songs/luna/chart_teclado_facil.bin"
Song_luna_teclado_medio:
    INCBIN "songs/luna/chart_teclado_medio.bin"

Song_luna_keyframe0:
    INCBIN "songs/luna/keyframes.bin", 0, 34
Song_luna_keyframe1:
    INCBIN "songs/luna/keyframes.bin", 34, 34
Song_luna_keyframe2:
    INCBIN "songs/luna/keyframes.bin", 68, 34
Song_luna_keyframe3:
    INCBIN "songs/luna/keyframes.bin", 102, 34

SECTION "Cancion luna B", ROMX[$4000], BANK[SONG_BANK + 1]
    INCBIN "songs/luna/stream_b.bin"

SECTION "Cancion luna C", ROMX[$4000], BANK[SONG_BANK + 2]
    INCBIN "songs/luna/stream_c.bin"
