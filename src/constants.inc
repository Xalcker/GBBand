; =============================================================================
; constants.inc - Constantes del juego
; =============================================================================

; --- Opciones de compilación (rgbasm -D) --------------------------------------
; PLACEMENT_B = 1 (por defecto): gemas con 4 desplazamientos verticales (0, 2, 4, 6 px)
; PLACEMENT_B = 0: colocación A, una fila de tiles por gema (como NESBand)
IF !DEF(PLACEMENT_B)
    DEF PLACEMENT_B EQU 1
ENDC

; --- Estados del juego ----------------------------------------------------------
DEF STATE_TITLE   EQU 0
DEF STATE_MENU    EQU 1
DEF STATE_PLAY    EQU 2
DEF STATE_PAUSE   EQU 3
DEF STATE_RESULTS  EQU 4
DEF STATE_INITIALS EQU 5

; --- Vida (cada acierto suma 1; perder una nota resta 2, o 1 en fácil; un golpe al aire resta 1) -------------
DEF LIFE_MAX   EQU 40
DEF LIFE_START EQU 28           ; dos tercios
DEF LIFE_LOSS  EQU 2
DEF LIFE_GRACE EQU 8            ; cuadros después de perder vida en que los fallos no cuestan más
DEF PAUSE_WY   EQU 56           ; la Window sube a ese renglón durante la pausa y tapa la autopista

; --- Reglas ---------------------------------------------------------------------
DEF WINDOW_FRAMES EQU 6         ; tolerancia: +-6 cuadros (~100 ms), igual que NESBand
DEF NUM_LANES     EQU 5

; --- Pantalla -------------------------------------------------------------------
DEF LANE_COL0     EQU 5         ; primera columna de tiles de la autopista
DEF HIT_ROW       EQU 15        ; fila de tiles de la línea de golpe (y = 120), pegada a la Window del HUD
DEF PREFILL_ROWS  EQU 26        ; filas que se arman con el LCD apagado al empezar
DEF WINDOW_Y      EQU 128       ; la Window (HUD, 2 filas) empieza en la fila 16
DEF WINDOW_X      EQU 7

; --- Tiles (modo $8000) ----------------------------------------------------------
DEF TILE_BLANK    EQU $00
DEF TILE_LANE_L   EQU $01
DEF TILE_LANE_R   EQU $02
DEF TILE_FRAME    EQU $03
DEF TILE_PANEL    EQU $04       ; $04-$07: cuatro fases del panel del escenario
DEF TILE_EDGE_L   EQU $08
DEF TILE_EDGE_R   EQU $09
DEF TILE_RING     EQU $0A       ; sprite 8x16
DEF TILE_RING_ON  EQU $0C
DEF TILE_TAIL_L   EQU $0E       ; cola de las notas sostenidas (mitad izquierda y derecha del carril)
DEF TILE_TAIL_R   EQU $0F
DEF TILE_GEM      EQU $60       ; 14 tiles por carril (ver gemgen.py)
DEF GEM_STRIDE    EQU 14

; --- Audio ----------------------------------------------------------------------
DEF RING_SLOTS     EQU 16
DEF RING_SLOT_SIZE EQU 64       ; [0] cuenta, [1] marca de wave RAM, [2-17] wave RAM, [18-63] pares (registro, valor)
DEF RING_TARGET    EQU 14       ; el bucle principal rellena hasta tener estos cuadros decodificados por delante
DEF RING_PAIRS_OFS EQU 18

; --- Control: bits de hPad (activos en alto) ---------------------------------------
DEF PADB_RIGHT  EQU 0
DEF PADB_LEFT   EQU 1
DEF PADB_UP     EQU 2
DEF PADB_DOWN   EQU 3
DEF PADB_A      EQU 4
DEF PADB_B      EQU 5
DEF PADB_SELECT EQU 6
DEF PADB_START  EQU 7
