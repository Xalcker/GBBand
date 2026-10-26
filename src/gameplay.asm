; =============================================================================
; gameplay.asm - Ventana de acierto, puntaje, combo y silencio al fallar
;
; Todo se mide en cuadros. Una nota del cuadro F se acierta si el botón se apretó en un cuadro t con
; |t - F| <= WINDOW_FRAMES. t es el cuadro de la ISR que leyó el control (wTJ = wT - 1).
; Las notas pendientes viven en una cola de 8 entradas (cuadro, carriles); cada carril de una entrada se
; acierta o se pierde por separado.
; =============================================================================

SECTION "Gameplay", ROM0

LaneBit: db %00001, %00010, %00100, %01000, %10000

GameplayInit:
    xor a
    ld [wJFrame], a
    ld [wJFrame + 1], a
    ld [wJEnd], a
    ld [wJQHead], a
    ld [wJQCount], a
    ld [wHeldPrev], a
    ld [wHeld], a
    ld [wAirCount], a
    ld [wScoreUnits], a
    ld [wScoreUnits + 1], a
    ld hl, wScoreDigits
    ld b, 6 + 3 + 3 + 3 + 3
.clear:
    ld [hl+], a
    dec b
    jr nz, .clear
    ld a, 1
    ld [wMult], a
    ld a, $03
    ld [wHudDirty], a
    jp JudgeFeed

; Llena la cola con las siguientes entradas del chart (el banco de la canción debe estar activo).
JudgeFeed:
.loop:
    ld a, [wJEnd]
    and a
    ret nz
    ld a, [wJQCount]
    cp 8
    ret nc
    ld a, [wJCur]
    ld l, a
    ld a, [wJCur + 1]
    ld h, a
    ld a, [hl+]
    ld b, a                 ; B = cuadros desde la entrada anterior
    ld a, [hl+]
    ld c, a
    ld a, l
    ld [wJCur], a
    ld a, h
    ld [wJCur + 1], a
    ld a, c
    cp $FF
    jr nz, .note
    ld a, 1
    ld [wJEnd], a
    ret
.note:
    ld a, [wJFrame]
    add b
    ld [wJFrame], a
    jr nc, .noCarry
    ld hl, wJFrame + 1
    inc [hl]
.noCarry:
    ld a, c
    and $1F
    jr z, .loop             ; entrada de relleno
    ld c, a
    ld a, [wJQHead]
    ld hl, wJQCount
    add [hl]
    and 7
    ld e, a
    ld d, 0
    ld hl, wJQMask
    add hl, de
    ld [hl], c
    ld hl, wJQFLo
    add hl, de
    ld a, [wJFrame]
    ld [hl], a
    ld hl, wJQFHi
    add hl, de
    ld a, [wJFrame + 1]
    ld [hl], a
    ld hl, wJQCount
    inc [hl]
    jr .loop

; BC = (cuadro de la entrada E) - wTJ, con signo. Clobbera A, D, HL.
JQDiff:
    ld d, 0
    ld hl, wJQFHi
    add hl, de
    ld b, [hl]
    ld hl, wJQFLo
    add hl, de
    ld c, [hl]
    ld hl, wTJ
    ld a, c
    sub [hl]
    ld c, a
    inc hl
    ld a, b
    sbc [hl]
    ld b, a
    ret

; A = 0 si BC (= F - t) está dentro de la ventana, 1 si la nota está en el futuro, 2 si ya pasó.
ClassifyDiff:
    bit 7, b
    jr nz, .negative
    ld a, b
    and a
    jr nz, .future
    ld a, c
    cp WINDOW_FRAMES + 1
    jr nc, .future
    xor a
    ret
.future:
    ld a, 1
    ret
.negative:
    ld a, b
    cp $FF
    jr nz, .past
    ld a, c
    cp 256 - WINDOW_FRAMES
    jr c, .past
    xor a
    ret
.past:
    ld a, 2
    ret

; Lo que cambia por cuadro de juego: expira notas, procesa los botones nuevos y rellena la cola.
JudgeFrame:
    ld a, [wT]
    sub 1
    ld [wTJ], a
    ld a, [wT + 1]
    sbc 0
    ld [wTJ + 1], a

    ; 1. notas que se pasaron de la ventana: se pierden
.expire:
    ld a, [wJQCount]
    and a
    jr z, .press
    ld a, [wJQHead]
    ld e, a
    ld d, 0
    ld hl, wJQMask
    add hl, de
    ld a, [hl]
    and a
    jr z, .popHead          ; sin carriles pendientes
    call JQDiff             ; E sigue siendo el índice
    call ClassifyDiff
    cp 2
    jr nz, .press
    ld a, [wJQHead]
    ld e, a
    ld d, 0
    ld hl, wJQMask
    add hl, de
    ld a, [hl]
    ld b, 5
.countLanes:
    srl a
    jr nc, .laneDone
    push af
    push bc
    call MissNote
    pop bc
    pop af
.laneDone:
    dec b
    jr nz, .countLanes
.popHead:
    ld a, [wJQHead]
    inc a
    and 7
    ld [wJQHead], a
    ld hl, wJQCount
    dec [hl]
    jr .expire

    ; 2. botones apretados desde el último cuadro
.press:
    di
    ldh a, [hPadNew]
    ld b, a
    xor a
    ldh [hPadNew], a
    ei
    ld a, b
    call PadToLanes
    ld [wPressLanes], a
    ld c, a
    ld b, 0
.lanes:
    srl c
    jr nc, .nextLane
    push bc
    ld a, b
    call TryHit
    pop bc
.nextLane:
    inc b
    ld a, b
    cp NUM_LANES
    jr nz, .lanes

    ; los carriles mantenidos (para los aros)
    ldh a, [hPad]
    call PadToLanes
    ld [wHeld], a

    ; 3. quitar del frente las entradas ya resueltas
.popZeros:
    ld a, [wJQCount]
    and a
    jr z, .feed
    ld a, [wJQHead]
    ld e, a
    ld d, 0
    ld hl, wJQMask
    add hl, de
    ld a, [hl]
    and a
    jr nz, .feed
    ld a, [wJQHead]
    inc a
    and 7
    ld [wJQHead], a
    ld hl, wJQCount
    dec [hl]
    jr .popZeros
.feed:
    jp JudgeFeed

; Carril apretado A (0 a 4): busca la primera nota pendiente de ese carril dentro de la ventana.
TryHit:
    ld e, a
    ld d, 0
    ld hl, LaneBit
    add hl, de
    ld a, [hl]
    ld [wTryBit], a
    xor a
    ld [wScanI], a
.scan:
    ld a, [wScanI]
    ld hl, wJQCount
    cp [hl]
    jr nc, .air
    ld hl, wJQHead
    add [hl]
    and 7
    ld e, a
    ld [wScanE], a
    call JQDiff
    call ClassifyDiff
    cp 1
    jr z, .air              ; las demás están más adelante
    cp 2
    jr z, .nextI            ; ya pasó (no debería quedar: se expiró arriba)
    ld a, [wScanE]
    ld e, a
    ld d, 0
    ld hl, wJQMask
    add hl, de
    ld a, [wTryBit]
    and [hl]
    jr z, .nextI            ; esta entrada no tiene ese carril
    ld a, [wTryBit]
    cpl
    and [hl]
    ld [hl], a              ; carril acertado
    jp HitNote
.nextI:
    ld hl, wScanI
    inc [hl]
    jr .scan
.air:
    jp AirStrum

; A = botones (bits de hPad) -> A = carriles (bit 0 verde ... bit 4 naranja)
PadToLanes:
    ld b, a
    xor a
    bit PADB_LEFT, b
    jr z, .l1
    or %00001
.l1:
    bit PADB_DOWN, b
    jr z, .l2
    or %00010
.l2:
    bit PADB_RIGHT, b
    jr z, .l3
    or %00100
.l3:
    bit PADB_B, b
    jr z, .l4
    or %01000
.l4:
    bit PADB_A, b
    ret z
    or %10000
    ret

; ---- Puntaje y combo --------------------------------------------------------------------------
HitNote:
    ld hl, wHitsDigits + 2
    call Inc3Digits
    ld hl, wComboDigits + 2
    call Inc3Digits
    ; combo máximo = max(combo máximo, combo)
    ld hl, wComboDigits
    ld de, wMaxComboDigits
    ld b, 3
.cmp:
    ld a, [de]
    cp [hl]
    jr c, .copy             ; máximo < combo
    jr nz, .maxDone
    inc hl
    inc de
    dec b
    jr nz, .cmp
    jr .maxDone
.copy:
    ld hl, wComboDigits
    ld de, wMaxComboDigits
    ld b, 3
.copyLoop:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .copyLoop
.maxDone:
    ; multiplicador: x1 con 0-9, x2 con 10-19, x3 con 20-29, x4 con 30 o más
    ld a, [wComboDigits]
    and a
    jr nz, .x4
    ld a, [wComboDigits + 1]
    cp 3
    jr nc, .x4
    inc a
    jr .setMult
.x4:
    ld a, 4
.setMult:
    ld [wMult], a
    ; puntaje += 50 * multiplicador (en decenas: 5 * m)
    ld b, a
    add a
    add a
    add b
    call ScoreAddTens
    ld a, [wMult]
    ld hl, wScoreUnits
    add [hl]
    ld [hl+], a
    jr nc, .unitsDone
    inc [hl]
.unitsDone:
    xor a
    ld [wMuted], a
    ld a, $03
    ld [wHudDirty], a
    ret

MissNote:
    ld hl, wMissDigits + 2
    call Inc3Digits
    jr BreakCombo

AirStrum:
    ld hl, wAirCount
    inc [hl]
BreakCombo:
    xor a
    ld hl, wComboDigits
    ld [hl+], a
    ld [hl+], a
    ld [hl], a
    inc a
    ld [wMult], a
    ld [wMuted], a
    ld a, $03
    ld [wHudDirty], a
    ret

; Suma 1 a tres dígitos decimales; HL apunta al menos significativo. Se queda en 999.
Inc3Digits:
    ld b, 3
.digit:
    ld a, [hl]
    inc a
    cp 10
    jr c, .store
    xor a
    ld [hl-], a
    dec b
    jr nz, .digit
    ld a, 9                 ; se pasó de 999
    inc hl
    ld [hl+], a
    ld [hl+], a
    ld [hl], a
    ret
.store:
    ld [hl], a
    ret

; Suma A decenas (A <= 29) al puntaje de 6 dígitos.
ScoreAddTens:
    ld hl, wScoreDigits + 4
    ld b, 5
.digit:
    add [hl]
    ld c, 0
.sub:
    cp 10
    jr c, .store
    sub 10
    inc c
    jr .sub
.store:
    ld [hl], a
    ld a, c
    and a
    ret z
    dec hl
    dec b
    jr nz, .digit
    ret
