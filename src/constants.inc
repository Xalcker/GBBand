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
DEF STATE_OPTIONS EQU 6
DEF STATE_LINK    EQU 7         ; conexión por cable link (2 jugadores)
DEF STATE_LINKWAIT EQU 8        ; 2 jugadores: canción preparada, esperando la salida sincronizada

; --- Cable link (ver link.asm) -----------------------------------------------------------------------------------
DEF LINK_VERSION   EQU 1        ; sube cuando cambie el protocolo: dos versiones distintas no se conectan
DEF LINK_MAX_DATA  EQU 12       ; bytes de datos del mensaje más largo (MSG_BAND); más la suma, cabe en la cola de 16
DEF LINK_HELLO_LEN EQU 3        ; saludo: versión y hash de la lista de canciones en dos bytes de 7 bits
DEF LINK_MENU_LEN  EQU 4        ; estado del menú: canción, instrumento, dificultad, banderas
DEF LINK_SCORE_LEN EQU 4        ; puntaje (3 bytes de dos dígitos) y banderas
DEF LINK_EVENTS_LEN EQU 5       ; Co-Op, el 2 al 1: aciertos antes y después del fallo, banderas, frases, colas
DEF LINK_BAND_LEN  EQU 12       ; Co-Op, el 1 al 2: el estado de la banda

; --- Vida (cada acierto suma 1; perder una nota resta 2, o 1 en fácil; un golpe al aire resta 1) -------------
DEF LIFE_MAX   EQU 40
DEF LIFE_START EQU 28           ; dos tercios
DEF LIFE_LOSS  EQU 2
DEF LIFE_GRACE EQU 8            ; cuadros después de perder vida en que los fallos no cuestan más
; --- Poder estelar (la barra llena son 64; cada frase de 4 notas suma 16; con la mitad se puede activar) --------
DEF STAR_MAX   EQU 64
DEF STAR_PHRASE EQU 16
DEF STAR_MIN   EQU 32
DEF STAR_DRAIN EQU 12           ; cuadros por unidad de barra mientras está activo (la barra llena dura ~13 s)
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
DEF TILE_TRUSS    EQU $1A       ; torres del escenario: celosía, reflector y su soporte
DEF TILE_LAMP     EQU $1B
DEF TILE_STEM     EQU $1C
DEF TILE_CROWD_DOWN EQU $1D     ; público: arriba con los brazos abajo / arriba, y los cuerpos
DEF TILE_CROWD_UP EQU $1E
DEF TILE_CROWD_BODY EQU $1F
DEF TILE_LAMP_OFF EQU $B3       ; (no se dibuja: se copia sobre TILE_LAMP en cada tiempo)
DEF TILE_FLAME    EQU $B4       ; llamarada al acertar: 3 cuadros de animación de 8x16 ($B4-$B9)
DEF FLAME_TIME    EQU 12        ; cuadros que dura (4 por cuadro de animación)
DEF FLAME_ATTR    EQU $15       ; paleta de sprites 5 (fuego) en CGB, OBP1 en DMG
DEF FLAME_ATTR_STAR EQU $06     ; con el poder estelar: paleta 6 (fuego azul) en CGB, OBP0 en DMG
DEF TILE_METER    EQU $10       ; 5 pares de tiles (sprites 8x16): segmento de medidor con 0, 4, 8, 12 y 16 px llenos
DEF TILE_TAIL_L   EQU $0E       ; cola de las notas sostenidas (mitad izquierda y derecha del carril)
DEF TILE_TAIL_R   EQU $0F
DEF TILE_GEM      EQU $60       ; 14 tiles por carril (ver gemgen.py)
DEF TILE_BAR      EQU $A6       ; el bombo: 13 tiles (llena y, por desplazamiento, arriba/abajo izquierda/derecha)
DEF TILE_LOGO     EQU $C0       ; 16 tiles: bloques de 4x4 px del logo del título (ver logo.tiles)
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
