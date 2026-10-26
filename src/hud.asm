; =============================================================================
; hud.asm - El marcador de la Window (filas 16 y 17, mapa $9C00) y los aros de los carriles (sprites)
; =============================================================================

SECTION "HUD", ROM0

DEF HUD_ROW0 EQU _SCRN1               ; PUNTOS 000000  X1
DEF HUD_ROW1 EQU _SCRN1 + 32          ; COMBO 000 MAX 000

HudText0: db "000000  X1", 0
HudText1: db "COMBO  000", 0
TxtFailed: db " FALLASTE "
; Más abajo en el mapa de la Window (no se ve salvo en la pausa, cuando la Window sube a PAUSE_WY)
TxtPaused:   db "PAUSA", 0
TxtResume:   db "START: SEGUIR", 0
TxtQuit:     db "SELECT: SALIR", 0
TxtMarkA:    db "A: INICIO AQUI", 0
TxtMarkB:    db "B: FIN AQUI", 0

; Escribe el texto fijo del HUD (LCD apagado)
HudDraw:
    ld de, HUD_ROW0 + 5          ; el marcador ocupa el ancho de la autopista; a los lados, el público
    ld hl, HudText0
    call PrintStr
    ld de, HUD_ROW1 + 5
    ld hl, HudText1
    call PrintStr
    call CrowdDraw
    ld de, _SCRN1 + 32 * 3 + 7
    ld hl, TxtPaused
    call PrintStr
    ld de, _SCRN1 + 32 * 5 + 3
    ld hl, TxtResume
    call PrintStr
    ld de, _SCRN1 + 32 * 6 + 3
    ld hl, TxtQuit
    call PrintStr
    ld a, [wOptPractice]    ; las marcas solo existen en la práctica
    and a
    ret z
    ld de, _SCRN1 + 32 * 8 + 3
    ld hl, TxtMarkA
    call PrintStr
    ld de, _SCRN1 + 32 * 9 + 3
    ld hl, TxtMarkB
    jp PrintStr

; Encola UN grupo de dígitos por cuadro (el primero que haya cambiado), para no pasar de la cuota de VRAM de la ISR.
; wHudDirty: bit 0 puntaje y multiplicador, bit 1 combo y máximo. (Aciertos y fallos solo salen al final de la canción.)
HudUpdate:
    ld a, [wHudDirty]
    bit 0, a
    jr z, .notScore
    res 0, a
    ld [wHudDirty], a
    ld hl, wScoreDigits
    ld de, HUD_ROW0 + 5
    ld b, 6
    call QueueDigits
    ld a, [wMult]
    ld b, a
    ld a, [wStarActive]     ; con el poder estelar el multiplicador que se ve es el doble
    and a
    ld a, b
    jr z, .multShown
    add a
.multShown:
    ld [wQDigit], a
    ld hl, wQDigit
    ld de, HUD_ROW0 + 14
    ld b, 1
    jp QueueDigits
.notScore:
    bit 2, a
    jr z, .notFail
    res 2, a
    ld [wHudDirty], a
    ld hl, TxtFailed          ; "FALLASTE": reemplaza el renglón del combo
    ld de, HUD_ROW1 + 5
    ld b, 10
    jp QueueRaw
.notFail:
    bit 1, a
    jr z, .notCombo
    ld c, a
    ld a, [wFailed]
    and a
    ld a, c
    jr nz, .notCombo          ; con la derrota ya no se actualiza el combo
    res 1, a
    ld [wHudDirty], a
    ld hl, wComboDigits
    ld de, HUD_ROW1 + 12
    ld b, 3
    jp QueueDigits
.notCombo:
    ret

; Encola B dígitos (decimales, de HL) como caracteres en la dirección DE de VRAM
QueueDigits:
    ld a, l
    ld [wQSrc], a
    ld a, h
    ld [wQSrc + 1], a
    ld c, 0
    call VQAlloc
    ld a, [wQSrc]
    ld e, a
    ld a, [wQSrc + 1]
    ld d, a
.loop:
    ld a, [de]
    inc de
    add '0'
    ld [hl+], a
    dec b
    jr nz, .loop
    ret

; ---- Aros (sprites 8x16) ---------------------------------------------------------------------
; 5 sprites, uno por carril, centrados en el carril, en la línea de golpe. Presionados cambian de tile.
OamInit:
    ld hl, wOam
    ld b, 160
    xor a
.clear:
    ld [hl+], a
    dec b
    jr nz, .clear
    xor a
    ld [wHeld], a
    cpl
    ld [wHeldPrev], a        ; distinto de wHeld: fuerza a UpdateOam a escribirlo todo
    call UpdateOam
    call MeterInit
    call MeterUpdate
    ld a, 1                  ; el primer cuadro copia todo el OAM por DMA
    ld [wOamDirty], a
    ret

; Reescribe los aros si cambió qué carriles están apretados
UpdateOam:
    ld a, [wHeld]
    ld b, a
    ld a, [wHeldPrev]
    cp b
    ret z
UpdateOamForce:
    ld a, [wHeld]
    ld [wHeldPrev], a
    ld c, a
    ld hl, wOam
    ld b, 0
.sprite:
    ld a, HIT_ROW * 8 + 16
    ld [hl+], a              ; Y
    ld a, b
    swap a                   ; 16 * carril
    add 40 + 4 + 8
    ld [hl+], a              ; X
    srl c
    ld a, TILE_RING
    jr nc, .tile
    ld a, TILE_RING_ON
.tile:
    ld [hl+], a
    ld a, b
    ld [hl+], a              ; atributos: paleta de sprites = carril (CGB)
    inc b
    ld a, b
    cp NUM_LANES
    jr nz, .sprite
    ld a, 1
    ld [wOamDirty], a
    ret

; ---- Medidores de vida (derecha) y de poder estelar (izquierda): 5 sprites de 8x16 apilados cada uno ---------------
; Los sprites 5 a 9 son el de vida y 10 a 14 el estelar; el primero de cada grupo es el de abajo.
DEF OAM_LIFE   EQU wOam + 4 * NUM_LANES
DEF OAM_STAR   EQU wOam + 4 * (NUM_LANES + 5)
DEF METER_TOP  EQU 24 + 16          ; Y (de OAM) del sprite de arriba

MeterInit:
    ld a, [wNoFail]          ; "sin fallo": no hay medidor de vida (sus sprites se quedan ocultos con Y = 0)
    and a
    jr nz, .star
    ld hl, OAM_LIFE
    ld d, 128 + 8
    call .column
.star:
    ld hl, OAM_STAR
    ld d, 24 + 8
.column:
    ld b, 0                  ; k = 0 (el de abajo) a 4 (el de arriba)
.sprite:
    ld a, b
    swap a                   ; 16 * k
    ld e, a
    ld a, METER_TOP + 64
    sub e
    ld [hl+], a              ; Y
    ld a, d
    ld [hl+], a              ; X
    ld a, TILE_METER
    ld [hl+], a
    xor a
    ld [hl+], a
    inc b
    ld a, b
    cp 5
    jr nz, .sprite
    ret
; Los niveles de los dos medidores según la vida y la energía estelar
MeterUpdate:
    ld a, [wNoFail]
    and a
    jr nz, .noLife
    ld a, [wLife]
    add a
    ld b, a                  ; píxeles llenos: 2 por unidad de vida (40 = 80 px)
    ld c, 0                  ; paleta de sprites 0: verde
    ld a, [wLife]
    cp 20
    jr nc, .lifeColor
    ld c, 2                  ; amarillo
    cp 10
    jr nc, .lifeColor
    ld c, 1                  ; rojo
.lifeColor:
    ld hl, OAM_LIFE
    call MeterFill
.noLife:
    ld a, [wStarEnergy]
    ld b, a
    srl a
    srl a
    add b                    ; energía * 5 / 4 = píxeles (64 -> 80)
    ld b, a
    ld a, [wStarActive]
    and a
    ld c, 3                  ; azul
    jr z, .starColor
    ld c, 7                  ; activo: blanco brillante
.starColor:
    ld hl, OAM_STAR
    jp MeterFill

; HL = primer sprite del medidor (el de abajo), B = píxeles llenos (0 a 80), C = paleta de sprites.
; Escribe el tile de nivel (0, 4, 8, 12 o 16 px) y la paleta de cada segmento; si algo cambió pide un OAM DMA.
MeterFill:
    ld d, 5
.sprite:
    ld a, b
    cp 16
    jr c, .partial
    sub 16
    ld b, a
    ld e, 16
    jr .level
.partial:
    ld e, a
    ld b, 0
.level:
    ld a, e
    add 2
    srl a
    srl a                    ; nivel = (px + 2) / 4
    add a
    add TILE_METER
    inc hl
    inc hl                   ; HL -> tile
    cp [hl]
    jr z, .sameTile
    ld [hl], a
    ld a, 1
    ld [wOamDirty], a
.sameTile:
    inc hl                   ; HL -> atributos
    ld a, c
    cp [hl]
    jr z, .sameAttr
    ld [hl], a
    ld a, 1
    ld [wOamDirty], a
.sameAttr:
    inc hl                   ; siguiente sprite
    dec d
    jr nz, .sprite
    ret
