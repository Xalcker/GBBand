; Generado por `gbband import-song` - no editar a mano
; SONG_BANK lo define la lista de canciones (build/list.asm) antes de incluir este archivo

SECTION "Cancion demo A", ROMX[$4000], BANK[SONG_BANK]
Song_demo::
    db "GBBS", 1
    db "PRIMER ENSAYO       "
    db "GBBAND          "
    dw 3312, 180
    db 24
    dw 180
    db %00001111, 3
    dw Song_demo_guitarra_facil
    dw Song_demo_guitarra_medio
    dw Song_demo_guitarra_dificil
    dw Song_demo_guitarra_experto
    dw Song_demo_teclado_facil
    dw Song_demo_teclado_medio
    dw Song_demo_teclado_dificil
    dw Song_demo_teclado_experto
    dw Song_demo_bajo_facil
    dw Song_demo_bajo_medio
    dw Song_demo_bajo_dificil
    dw Song_demo_bajo_experto
    dw Song_demo_bateria_facil
    dw Song_demo_bateria_medio
    dw Song_demo_bateria_dificil
    dw Song_demo_bateria_experto
    dw $4000
    dw 0
    db SONG_BANK + 1 + 0
    dw $4025
    dw Song_demo_keyframe0
    dw 768
    db SONG_BANK + 1 + 0
    dw $4787
    dw Song_demo_keyframe1
    dw 1536
    db SONG_BANK + 1 + 0
    dw $4EB1
    dw Song_demo_keyframe2
    dw 2304
    db SONG_BANK + 1 + 0
    dw $5644
    dw Song_demo_keyframe3

Song_demo_bajo_dificil:
    INCBIN "songs/demo/chart_bajo_dificil.bin"
Song_demo_bajo_experto:
    INCBIN "songs/demo/chart_bajo_experto.bin"
Song_demo_bajo_facil:
    INCBIN "songs/demo/chart_bajo_facil.bin"
Song_demo_bajo_medio:
    INCBIN "songs/demo/chart_bajo_medio.bin"
Song_demo_bateria_dificil:
    INCBIN "songs/demo/chart_bateria_dificil.bin"
Song_demo_bateria_experto:
    INCBIN "songs/demo/chart_bateria_experto.bin"
Song_demo_bateria_facil:
    INCBIN "songs/demo/chart_bateria_facil.bin"
Song_demo_bateria_medio:
    INCBIN "songs/demo/chart_bateria_medio.bin"
Song_demo_guitarra_dificil:
    INCBIN "songs/demo/chart_guitarra_dificil.bin"
Song_demo_guitarra_experto:
    INCBIN "songs/demo/chart_guitarra_experto.bin"
Song_demo_guitarra_facil:
    INCBIN "songs/demo/chart_guitarra_facil.bin"
Song_demo_guitarra_medio:
    INCBIN "songs/demo/chart_guitarra_medio.bin"
Song_demo_teclado_dificil:
    INCBIN "songs/demo/chart_teclado_dificil.bin"
Song_demo_teclado_experto:
    INCBIN "songs/demo/chart_teclado_experto.bin"
Song_demo_teclado_facil:
    INCBIN "songs/demo/chart_teclado_facil.bin"
Song_demo_teclado_medio:
    INCBIN "songs/demo/chart_teclado_medio.bin"

Song_demo_keyframe0:
    INCBIN "songs/demo/keyframes.bin", 0, 34
Song_demo_keyframe1:
    INCBIN "songs/demo/keyframes.bin", 34, 34
Song_demo_keyframe2:
    INCBIN "songs/demo/keyframes.bin", 68, 34
Song_demo_keyframe3:
    INCBIN "songs/demo/keyframes.bin", 102, 34

SECTION "Cancion demo B", ROMX[$4000], BANK[SONG_BANK + 1]
    INCBIN "songs/demo/stream_b.bin"

SECTION "Cancion demo C", ROMX[$4000], BANK[SONG_BANK + 2]
    INCBIN "songs/demo/stream_c.bin"
