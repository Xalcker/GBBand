; =============================================================================
; fx.asm - Efecto al fallar: temblor de la autopista, tinte rojo y un efecto de sonido
;
; MissFx arranca el efecto (con 20 cuadros de enfriamiento: a lo más 3 por segundo). FxFrame corre en cada cuadro de
; juego y mueve SCX; la ISR copia hScx y aplica el tinte (hPalFx). El sonido corre en la ISR (SfxTick, después del
; stream): pisa un canal de pulso que no sea el del instrumento que falló y al terminar lo restaura con la sombra.
; =============================================================================

DEF FX_COOL  EQU 20
DEF FX_SHAKE EQU 6

SECTION "Fx", ROM0

; Paleta de fondo 0 teñida de rojo (BGR555)
CgbRedPal0:
    dw $0004, $0010, $0018, $001F

SfxTable:
    dw SfxClank, SfxThud, SfxBwomp, SfxMove, SfxAccept, SfxBack

; len, NRx1 (ciclo de trabajo), NRx2 (envolvente), len frecuencias de 11 bits
SfxClank:
    db 8, $80, $F1
    dw $7C6, $7B0, $7C6, $7B0, $7C6, $7B0, $7C6, $7B0
SfxThud:
    db 10, $40, $F2
    dw $3C0, $3B8, $3B0, $3A8, $3A0, $398, $390, $388, $380, $378
SfxBwomp:
    db 12, $80, $F1
    dw $64B, $630, $610, $5F0, $5C8, $5A0, $578, $550, $528, $500, $4D0, $4A0

; Menú
SfxMove:
    db 3, $80, $A1
    dw $7A0, $7A8, $7B0
SfxAccept:
    db 6, $80, $C1
    dw $7B0, $7B0, $7B0, $7D0, $7D0, $7D0
SfxBack:
    db 5, $80, $B1
    dw $7B0, $7A0, $790, $780, $770

; A = 0 mover, 1 aceptar, 2 volver: suena en el canal 1. Conserva todos los registros.
PlayMenuSfx:
    push af
    push bc
    push de
    push hl
    ld b, a
    ld a, $10
    ld [wSfxBase], a
    ld a, b
    add 3
    call SfxStart
    pop hl
    pop de
    pop bc
    pop af
    ret

; Se llama al romper el combo (nota perdida o golpe al aire)
MissFx:
    ld a, [wOptFx]
    cp 2
    ret nc                  ; NO
    ld a, [wFxCool]
    and a
    ret nz
    ld a, FX_COOL
    ld [wFxCool], a
    ld a, [wOptFx]
    and a
    jr nz, .sound           ; SOLO SONIDO: sin temblor ni rojo
    ld a, FX_SHAKE
    ld [wShake], a
    ld a, 1
    ldh [hPalFx], a
.sound:
    ldh a, [hFrame]
.mod:
    cp 3
    jr c, .picked
    sub 3
    jr .mod
.picked:
    ld b, a
    ld a, [wSfxLast]
    cp b
    jr nz, .new
    inc b                   ; el mismo que el anterior: se pasa al siguiente
    ld a, b
    cp 3
    jr c, .new
    ld b, 0
.new:
    ld a, b
    ld [wSfxLast], a
    ld a, [wInstrument]     ; la guitarra suena en CH1: el efecto va en CH2; los demás, en CH1
    and a
    ld a, $10
    jr nz, .base
    ld a, $15
.base:
    ld [wSfxBase], a
    ld a, b
SfxStart:                   ; A = efecto (índice de SfxTable), wSfxBase ya puesto
    add a
    ld e, a
    ld d, 0
    ld hl, SfxTable
    add hl, de
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld a, [hl+]
    inc a
    ld [wSfxLeft], a        ; len + 1 (el último cuadro restaura el canal)
    ld a, [hl+]
    ld [wSfxDuty], a
    ld a, [hl+]
    ld [wSfxEnv], a
    ld a, l
    ld [wSfxPtr], a
    ld a, h
    ld [wSfxPtr + 1], a
    ld a, 1
    ld [wSfxFirst], a
    ret

; Un cuadro de juego: enfriamiento y temblor
FxFrame:
    ld a, [wFxCool]
    and a
    jr z, .noCool
    dec a
    ld [wFxCool], a
.noCool:
    ld a, [wShake]
    and a
    ret z
    dec a
    ld [wShake], a
    jr z, .end
    ld e, a
    ld d, 0
    ld hl, ShakeTable
    add hl, de
    ld a, [hl]
    ldh [hScx], a
    ret
.end:
    xor a
    ldh [hScx], a
    ld a, 2
    ldh [hPalFx], a
    ret
ShakeTable: db 0, 2, $FF, 1, $FE, 2

; Quita el temblor y el rojo (al pausar, al empezar y al terminar una partida) y calla el efecto de sonido
FxClear:
    xor a
    ld [wFxCool], a
    ld [wSfxLeft], a
    ldh [hScx], a
    ld a, [wShake]
    and a
    ret z
    xor a
    ld [wShake], a
    ld a, 2
    ldh [hPalFx], a
    ret

; ISR. A = 1 (rojo) o 2 (normal). En DMG invierte la paleta del fondo; en CGB cambia la paleta 0.
ApplyPalFx:
    ld b, a
    xor a
    ldh [hPalFx], a
    ldh a, [hCGB]
    and a
    jr nz, .cgb
    ld a, b
    cp 1
    ld a, %11100100
    jr nz, .dmgSet
    ld a, %00011011
.dmgSet:
    ldh [rBGP], a
    ret
.cgb:
    ld a, $80
    ldh [rBCPS], a
    ld hl, CgbBgPalettes
    ld a, b
    cp 1
    jr nz, .copy
    ld hl, CgbRedPal0
.copy:
    ld b, 8
.loop:
    ld a, [hl+]
    ldh [rBCPD], a
    dec b
    jr nz, .loop
    ret

; ISR, después de las escrituras del stream. Primer cuadro: ciclo, envolvente y alta; los demás, solo la frecuencia.
SfxTick:
    ld a, [wSfxLeft]
    and a
    ret z
    dec a
    ld [wSfxLeft], a
    ld a, [wSfxBase]
    ld c, a
    jr z, .restore
    ld a, [wSfxPtr]
    ld l, a
    ld a, [wSfxPtr + 1]
    ld h, a
    ld a, [wSfxFirst]
    ld e, a
    and a
    jr z, .freq
    xor a
    ld [wSfxFirst], a
    inc c
    ld a, [wSfxDuty]
    ldh [c], a
    inc c
    ld a, [wSfxEnv]
    ldh [c], a
    dec c
    dec c
.freq:
    inc c
    inc c
    inc c                   ; NRx3
    ld a, [hl+]
    ldh [c], a
    inc c                   ; NRx4
    ld a, [hl+]
    ld b, a
    ld a, e
    and a
    ld a, b
    jr z, .noTrigger
    or $80
.noTrigger:
    ldh [c], a
    ld a, l
    ld [wSfxPtr], a
    ld a, h
    ld [wSfxPtr + 1], a
    ret
.restore:
    ; el stream sigue escribiendo la sombra: se vuelve a tocar lo que sonaba en ese canal
    ld d, HIGH(wShadow)
    inc c
    ld e, c
    ld a, [de]
    ldh [c], a              ; NRx1
    inc c
    inc e
    ld a, [de]
    ldh [c], a              ; NRx2
    inc c
    inc e
    ld a, [de]
    ldh [c], a              ; NRx3
    inc c
    inc e
    ld a, [de]
    or $80
    ldh [c], a              ; NRx4 con alta
    ret
