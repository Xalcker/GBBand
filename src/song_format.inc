; =============================================================================
; song_format.inc - Ficha de una canción (primer banco de su slot) y convenciones del slot
;
; Un slot son 3 bancos de 16 KB: A (ficha + charts), B y C (stream de audio, 32 KB seguidos).
; Todos los enteros son little-endian. Los punteros son direcciones dentro de $4000-$7FFF.
; =============================================================================

DEF SONG_MAGIC      EQU 0       ; "GBBS"
DEF SONG_VERSION    EQU 4
DEF SONG_TITLE      EQU 5       ; 16 caracteres ASCII, mayúsculas
DEF SONG_GAME       EQU 21      ; 16 caracteres
DEF SONG_END        EQU 37      ; 2 bytes: cuadro en que termina la canción
DEF SONG_LEADIN     EQU 39      ; 2 bytes: cuadro en que empieza el audio (las notas caen antes)
DEF SONG_BEAT       EQU 41      ; cuadros por tiempo
DEF SONG_INSTR      EQU 42      ; bits 0-3: instrumentos con chart (guitarra, teclado, bajo, batería)
DEF SONG_NBANKS     EQU 43      ; bancos del slot (3)
DEF SONG_CHARTS     EQU 44      ; 16 punteros de 2 bytes: instrumento * 4 + dificultad (0 = no hay)
DEF SONG_STREAM     EQU 76      ; 2 bytes: puntero al primer registro del stream (en el banco B)
DEF SONG_KEYFRAMES  EQU 78      ; 4 entradas de 7 bytes: cuadro (2), banco (1), puntero del stream (2), registro (2)
DEF SONG_SIZE       EQU 106

DEF KEYFRAME_SIZE   EQU 7

; Slot 0 de canción (fase 2: una sola canción). Más adelante la lista de canciones dará el banco de cada una.
DEF SONG0_BANK      EQU 16
