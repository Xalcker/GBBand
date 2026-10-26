; Generado por `gbband import-song` - no editar a mano
; SONG_BANK lo define la lista de canciones (build/list.asm) antes de incluir este archivo

SECTION "Cancion brisa A", ROMX[$4000], BANK[SONG_BANK]
Song_brisa::
    db "GBBS", 1
    db "BRISA DE VERANO     "
    db "GBBAND          "
    dw 6064, 180
    db 28
    dw 180
    db %00001111, 3
    dw Song_brisa_guitarra_facil
    dw Song_brisa_guitarra_medio
    dw Song_brisa_guitarra_dificil
    dw Song_brisa_guitarra_experto
    dw Song_brisa_teclado_facil
    dw Song_brisa_teclado_medio
    dw Song_brisa_teclado_dificil
    dw Song_brisa_teclado_experto
    dw Song_brisa_bajo_facil
    dw Song_brisa_bajo_medio
    dw Song_brisa_bajo_dificil
    dw Song_brisa_bajo_experto
    dw Song_brisa_bateria_facil
    dw Song_brisa_bateria_medio
    dw Song_brisa_bateria_dificil
    dw Song_brisa_bateria_experto
    dw $4000
    dw 0
    db SONG_BANK + 1 + 0
    dw $4020
    dw Song_brisa_keyframe0
    dw 1456
    db SONG_BANK + 1 + 0
    dw $4B95
    dw Song_brisa_keyframe1
    dw 2912
    db SONG_BANK + 1 + 0
    dw $558D
    dw Song_brisa_keyframe2
    dw 4368
    db SONG_BANK + 1 + 0
    dw $5DF0
    dw Song_brisa_keyframe3

Song_brisa_bajo_dificil:
    INCBIN "songs/brisa/chart_bajo_dificil.bin"
Song_brisa_bajo_experto:
    INCBIN "songs/brisa/chart_bajo_experto.bin"
Song_brisa_bajo_facil:
    INCBIN "songs/brisa/chart_bajo_facil.bin"
Song_brisa_bajo_medio:
    INCBIN "songs/brisa/chart_bajo_medio.bin"
Song_brisa_bateria_dificil:
    INCBIN "songs/brisa/chart_bateria_dificil.bin"
Song_brisa_bateria_experto:
    INCBIN "songs/brisa/chart_bateria_experto.bin"
Song_brisa_bateria_facil:
    INCBIN "songs/brisa/chart_bateria_facil.bin"
Song_brisa_bateria_medio:
    INCBIN "songs/brisa/chart_bateria_medio.bin"
Song_brisa_guitarra_dificil:
    INCBIN "songs/brisa/chart_guitarra_dificil.bin"
Song_brisa_guitarra_experto:
    INCBIN "songs/brisa/chart_guitarra_experto.bin"
Song_brisa_guitarra_facil:
    INCBIN "songs/brisa/chart_guitarra_facil.bin"
Song_brisa_guitarra_medio:
    INCBIN "songs/brisa/chart_guitarra_medio.bin"
Song_brisa_teclado_dificil:
    INCBIN "songs/brisa/chart_teclado_dificil.bin"
Song_brisa_teclado_experto:
    INCBIN "songs/brisa/chart_teclado_experto.bin"
Song_brisa_teclado_facil:
    INCBIN "songs/brisa/chart_teclado_facil.bin"
Song_brisa_teclado_medio:
    INCBIN "songs/brisa/chart_teclado_medio.bin"

Song_brisa_keyframe0:
    INCBIN "songs/brisa/keyframes.bin", 0, 31
Song_brisa_keyframe1:
    INCBIN "songs/brisa/keyframes.bin", 31, 34
Song_brisa_keyframe2:
    INCBIN "songs/brisa/keyframes.bin", 65, 31
Song_brisa_keyframe3:
    INCBIN "songs/brisa/keyframes.bin", 96, 31

SECTION "Cancion brisa B", ROMX[$4000], BANK[SONG_BANK + 1]
    INCBIN "songs/brisa/stream_b.bin"

SECTION "Cancion brisa C", ROMX[$4000], BANK[SONG_BANK + 2]
    INCBIN "songs/brisa/stream_c.bin"
