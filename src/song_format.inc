; =============================================================================
; song_format.inc - Ficha de una canción (primer banco de su slot) y convenciones del slot
;
; Un slot son 3 bancos de 16 KB: A (ficha + charts + keyframes), B y C (stream de audio, 32 KB seguidos).
; El banco de la canción lo define la lista de canciones (SONG_BANK, ver `gbband list-songs`).
; Todos los enteros son little-endian. Los punteros son direcciones dentro de $4000-$7FFF.
; =============================================================================

DEF SONG_MAGIC      EQU 0       ; "GBBS"
DEF SONG_VERSION    EQU 4
DEF SONG_TITLE      EQU 5       ; 20 caracteres ASCII, mayúsculas, con relleno de espacios
DEF SONG_GAME       EQU 25      ; 16 caracteres
DEF SONG_END        EQU 41      ; 2 bytes: cuadro en que termina la canción
DEF SONG_LEADIN     EQU 43      ; 2 bytes: cuadro en que empieza el audio (las notas caen antes)
DEF SONG_BEAT       EQU 45      ; cuadros por tiempo
DEF SONG_FIRSTBEAT  EQU 46      ; 2 bytes: cuadro del primer tiempo (contando el lead-in)
DEF SONG_INSTR      EQU 48      ; bits 0-3: instrumentos con chart (guitarra, teclado, bajo, batería)
DEF SONG_NBANKS     EQU 49      ; bancos del slot (3)
DEF SONG_CHARTS     EQU 50      ; 16 punteros de 2 bytes: instrumento * 4 + dificultad (0 = no hay)
DEF SONG_STREAM     EQU 82      ; 2 bytes: puntero al primer registro del stream (en el banco B)
DEF SONG_KEYFRAMES  EQU 84      ; 4 entradas de 7 bytes: cuadro (2), banco (1), puntero del stream (2), registro (2)
DEF SONG_SIZE       EQU 112

DEF KEYFRAME_SIZE   EQU 7
DEF SONG_TITLE_LEN  EQU 20
DEF SONG_GAME_LEN   EQU 16

DEF FIRST_SONG_BANK EQU 16      ; la canción n ocupa los bancos 16 + 3n a 18 + 3n
DEF BANKS_PER_SONG  EQU 3
DEF MAX_SONGS       EQU 32
