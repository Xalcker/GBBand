; =============================================================================
; results.asm - Pantalla de resultados: puntaje, precisión, combo máximo y estrellas
;
; Las estrellas salen del PUNTAJE (qué porcentaje del máximo posible lograste), no de las notas acertadas: machacando
; botones se aciertan notas de suerte, pero el combo nunca sube y el puntaje se queda abajo. El máximo posible con n
; notas es, en unidades de 50 puntos (la nota i vale su multiplicador, 1 a 4):
;     n < 10: n      n < 20: 2n - 9      n < 30: 3n - 28      si no: 4n - 57
; Estrellas = cuántos umbrales de 20, 40, 60, 80 y 95 % se alcanzaron.
; =============================================================================

SECTION "Resultados", ROM0

StarThresholds: db 20, 40, 60, 80, 95

TxtResults:   db "RESULTADOS", 0
TxtScoreLbl:  db "PUNTOS", 0
TxtHitsLbl:   db "ACIERTOS", 0
TxtPrecision: db "PRECISION", 0
TxtComboMax:  db "COMBO MAXIMO", 0
TxtStarsLbl:  db "ESTRELLAS", 0
TxtLost:      db "FALLASTE", 0
TxtNoFailRes: db "SIN FALLO: NO HAY RECORD", 0
TxtContinue:  db "START: CONTINUAR", 0

; Escribe B dígitos (decimales) de HL como caracteres en DE (LCD apagado)
PrintDigits:
.loop:
    ld a, [hl+]
    add '0'
    ld [de], a
    inc de
    dec b
    jr nz, .loop
    ret

EnterResults:
    xor a
    ld [wPlaying], a
    call AudioStop
    call ComputeResults     ; (los aciertos y el total propios: en Co-Op se mandan al compañero mientras se espera)
    call CoopResultsWait    ; Co-Op: "ESPERANDO A J2..." hasta que lleguen sus datos finales (carry = 1)
    ret c
; (ResultsFrame vuelve aquí cuando llegan)
ResultsShow:
    xor a
    ld [wCoopWaiting], a
    call ComputeResults
    call CheckNewRecord
    call BeginTextScreen
    ld de, _SCRN0 + 32 * 1 + 5
    ld hl, TxtResults
    call PrintStr
    ld de, _SCRN0 + 32 * 3 + 0
    ld hl, wTitleBuf
    ld b, SONG_TITLE_LEN
    call CopyToMap
    ld de, _SCRN0 + 32 * 6 + 1
    ld hl, TxtScoreLbl
    call PrintStr
    ld de, _SCRN0 + 32 * 6 + 12
    ld hl, wScoreDigits
    ld b, 6
    call PrintDigits
    ld de, _SCRN0 + 32 * 8 + 1
    ld hl, TxtHitsLbl
    call PrintStr
    ld de, _SCRN0 + 32 * 8 + 12
    ld hl, wHitsDigits
    ld b, 3
    call PrintDigits
    ld a, '/'
    ld [_SCRN0 + 32 * 8 + 15], a
    ld hl, wTotalDigits
    ld de, _SCRN0 + 32 * 8 + 16
    ld b, 3
    call PrintDigits
    ld de, _SCRN0 + 32 * 9 + 1
    ld hl, TxtPrecision
    call PrintStr
    ld hl, wPctDigits
    ld de, _SCRN0 + 32 * 9 + 12
    ld b, 3
    call PrintDigits
    ld a, '%'
    ld [_SCRN0 + 32 * 9 + 15], a
    ld de, _SCRN0 + 32 * 10 + 1
    ld hl, TxtComboMax
    call PrintStr
    ld de, _SCRN0 + 32 * 10 + 15
    ld hl, wMaxComboDigits
    ld b, 3
    call PrintDigits
    ld de, _SCRN0 + 32 * 12 + 1
    ld hl, TxtStarsLbl
    call PrintStr
    ld a, [wStars]
    and a
    jr z, .noStars
    ld b, a
    ld hl, _SCRN0 + 32 * 12 + 11
    ld a, '*'
.star:
    ld [hl+], a
    dec b
    jr nz, .star
.noStars:
    ld a, [wFailed]
    and a
    jr z, .notLost
    ld de, _SCRN0 + 32 * 14 + 6
    ld hl, TxtLost
    call PrintStr
    jr .footer
.notLost:
    ld a, [wNoFail]
    and a
    jr z, .footer
    ld de, _SCRN0 + 32 * 14 + 0
    ld hl, TxtNoFailRes
    call PrintStr
.footer:
    ld a, [wNewRecord]
    and a
    jr z, .noRecord
    ld de, _SCRN0 + 32 * 15 + 4
    ld hl, TxtNewRecord
    call PrintStr
.noRecord:
    ld a, [wVsGame]
    and a
    call nz, ResultsVsDraw  ; VS: el puntaje del otro y quién ganó (link.asm)
    ld a, [wCoopGame]
    and a
    call nz, ResultsCoopDraw ; Co-Op: los aciertos del compañero y si la banda perdió (coop.asm)
    ld de, _SCRN0 + 32 * 17 + 2
    ld hl, TxtContinue
    call PrintStr
    ld a, STATE_RESULTS
    ld [wState], a
    jp EndTextScreen

; Copia B bytes de HL al mapa en DE (LCD apagado)
CopyToMap:
.loop:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .loop
    ret

; ---- Cálculo ---------------------------------------------------------------------------------------
; Calcula wNotesTotal, wPerfectUnits, wPct (con sus dígitos) y wStars a partir de lo jugado.
ComputeResults:
    ; notas = aciertos + fallos
    ld hl, wHitsDigits
    call DigitsToBin
    push hl
    ld hl, wMissDigits
    call DigitsToBin
    pop de
    add hl, de
    ld a, l
    ld [wNotesTotal], a
    ld a, h
    ld [wNotesTotal + 1], a
    call TotalToDigits
    call CoopAddPeerNotes   ; Co-Op: las estrellas de la banda salen de las notas de los dos
    ; puntaje máximo posible con n notas (en unidades de 50)
    ld hl, wNotesTotal
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld a, h
    and a
    jr nz, .x4
    ld a, l
    cp 10
    jr c, .done
    cp 20
    jr c, .lt20
    cp 30
    jr c, .lt30
.x4:
    add hl, hl
    add hl, hl
    ld de, -57
    add hl, de
    jr .done
.lt30:
    ld d, h
    ld e, l
    add hl, hl
    add hl, de
    ld de, -28
    add hl, de
    jr .done
.lt20:
    add hl, hl
    ld de, -9
    add hl, de
.done:
    ld a, l
    ld [wPerfectUnits], a
    ld a, h
    ld [wPerfectUnits + 1], a
    or l
    jr z, .noNotes
    ; porcentaje = unidades * 100 / máximo
    xor a
    ld [wDivA], a
    ld [wDivA + 1], a
    ld [wDivA + 2], a
    ld a, [wScoreUnits]
    ld l, a
    ld a, [wScoreUnits + 1]
    ld h, a
    ld b, 100
.times100:
    ld a, [wDivA]
    add l
    ld [wDivA], a
    ld a, [wDivA + 1]
    adc h
    ld [wDivA + 1], a
    ld a, [wDivA + 2]
    adc 0
    ld [wDivA + 2], a
    dec b
    jr nz, .times100
    ld a, [wPerfectUnits]
    ld [wDivB], a
    ld a, [wPerfectUnits + 1]
    ld [wDivB + 1], a
    call Div24By16
    ld a, [wDivA]
    cp 101
    jr c, .pctOk
    ld a, 100
.pctOk:
    ld [wPct], a
    jr .stars
.noNotes:
    xor a
    ld [wPct], a
.stars:
    call PctToDigits
    ld a, [wPct]
    ld c, a
    ld hl, StarThresholds
    ld b, 5
    ld d, 0
.threshold:
    ld a, [hl+]
    cp c
    jr z, .reached
    jr nc, .skip
.reached:
    inc d
.skip:
    dec b
    jr nz, .threshold
    ld a, d
    ld [wStars], a
    ret

; Un paso de DigitsToBin: HL = HL * 10 + el siguiente dígito (apuntado por BC)
MACRO DigitStep
    ld d, h
    ld e, l
    add hl, hl
    add hl, hl
    add hl, de
    add hl, hl
    ld a, [bc]
    inc bc
    ld e, a
    ld d, 0
    add hl, de
ENDM

; HL = tres dígitos decimales (centenas primero) -> HL = el número (0 a 999)
DigitsToBin:
    ld b, h
    ld c, l
    ld hl, 0
    DigitStep
    DigitStep
    DigitStep
    ret

; HL = número (0 a 999) -> tres dígitos decimales en DE
BinToDigits3:
    ld bc, -100
    ld a, -1
.hundreds:
    inc a
    add hl, bc
    jr c, .hundreds
    ld bc, 100
    add hl, bc
    ld [de], a
    inc de
    ld bc, -10
    ld a, -1
.tens:
    inc a
    add hl, bc
    jr c, .tens
    ld bc, 10
    add hl, bc
    ld [de], a
    inc de
    ld a, l
    ld [de], a
    ret

TotalToDigits:
    ld a, [wNotesTotal]
    ld l, a
    ld a, [wNotesTotal + 1]
    ld h, a
    ld de, wTotalDigits
    jr BinToDigits3

PctToDigits:
    ld a, [wPct]
    ld l, a
    ld h, 0
    ld de, wPctDigits
    jr BinToDigits3
; Dividir el dividendo de 24 bits (wDivA) entre wDivB: cociente en wDivA, resto en wDivR
Div24By16:
    xor a
    ld [wDivR], a
    ld [wDivR + 1], a
    ld b, 24
.loop:
    ld hl, wDivA
    sla [hl]
    inc hl
    rl [hl]
    inc hl
    rl [hl]
    ld hl, wDivR
    rl [hl]
    inc hl
    rl [hl]
    ld a, [wDivR]
    ld hl, wDivB
    sub [hl]
    ld e, a
    ld a, [wDivR + 1]
    inc hl
    sbc [hl]
    jr c, .skip
    ld d, a
    ld a, e
    ld [wDivR], a
    ld a, d
    ld [wDivR + 1], a
    ld hl, wDivA
    set 0, [hl]
.skip:
    dec b
    jr nz, .loop
    ret
