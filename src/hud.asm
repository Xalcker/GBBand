; =============================================================================
; hud.asm - El marcador de la Window (filas 16 y 17, mapa $9C00) y los aros de los carriles (sprites)
; =============================================================================

SECTION "HUD", ROM0

DEF HUD_ROW0 EQU _SCRN1               ; PUNTOS 000000  X1
DEF HUD_ROW1 EQU _SCRN1 + 32          ; COMBO 000 MAX 000

HudText0: db "PUNTOS 000000  X1", 0
HudText1: db "COMBO 000 MAX 000", 0

; Escribe el texto fijo del HUD (LCD apagado)
HudDraw:
    ld de, HUD_ROW0
    ld hl, HudText0
    call PrintStr
    ld de, HUD_ROW1
    ld hl, HudText1
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
    ld de, HUD_ROW0 + 7
    ld b, 6
    call QueueDigits
    ld a, [wMult]
    ld [wQDigit], a
    ld hl, wQDigit
    ld de, HUD_ROW0 + 16
    ld b, 1
    jp QueueDigits
.notScore:
    bit 1, a
    jr z, .notCombo
    res 1, a
    ld [wHudDirty], a
    ld hl, wComboDigits
    ld de, HUD_ROW1 + 6
    ld b, 3
    call QueueDigits
    ld hl, wMaxComboDigits
    ld de, HUD_ROW1 + 14
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
    jr UpdateOam

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
