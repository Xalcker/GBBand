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

; Con ESPEJO el chart se traduce al leerlo: verde <-> naranja y rojo <-> azul (el amarillo se queda). La batería lo ignora.
MirrorTab:
FOR i, 32
    db ((i & 1) << 4) | ((i & 2) << 2) | (i & 4) | ((i & 8) >> 2) | ((i & 16) >> 4)
ENDR

; A = carriles del chart -> A = carriles en pantalla. Conserva todo lo demás.
MirrorLanes:
    push hl
    push de
    ld e, a
    ld a, [wMirrorOn]
    and a
    ld a, e
    jr z, .done
    ld d, 0
    ld hl, MirrorTab
    add hl, de
    ld a, [hl]
.done:
    pop de
    pop hl
    ret

GameplayInit:
    xor a
    ld [wJFrame], a
    ld [wJFrame + 1], a
    ld [wJEnd], a
    ld [wHold], a
    ld hl, wHoldTick
    ld [hl+], a
    ld [hl+], a
    ld [hl+], a
    ld [hl+], a
    ld [hl], a
    ld [wJQHead], a
    ld [wJQCount], a
    ld [wHeldPrev], a
    ld [wHeld], a
    ld [wAirCount], a
    ld [wFailed], a
    ld [wLifeGrace], a
    ld [wStarEnergy], a
    ld [wStarActive], a
    ld [wStarRun], a
    ld [wStarFail], a
    ld [wScoreUnits], a
    ld [wScoreUnits + 1], a
    ld hl, wScoreDigits
    ld b, 6 + 3 + 3 + 3 + 3
.clear:
    ld [hl+], a
    dec b
    jr nz, .clear
    ld a, LIFE_START
    ld [wLife], a
    ld a, 1
    ld [wMult], a
    ld a, $03
    ld [wHudDirty], a
    ld a, [wPracFromP]      ; el juez parte de la entrada que dejó PracticeSeek
    and a
    jp z, JudgeFeed
    ld a, [wSeekF]
    ld [wJFrame], a
    ld a, [wSeekF + 1]
    ld [wJFrame + 1], a
    jp JudgeFeed

; Llena la cola con las siguientes entradas del chart (el banco de la canción debe estar activo).
; Una entrada con el bit $40 es una nota con cola (salvo en la batería, donde es un platillo); una con el bit $80 es el fin
; de la cola de sus carriles y no entra a la cola de notas: solo anota en wTailEnd el cuadro en que termina.
JudgeFeed:
.loop:
    ld a, [wJEnd]
    and a
    ret nz
    ld a, [wJQCount]
    cp 16
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
    bit 7, c
    jr z, .lanesEntry
    ld a, [wJFrame]         ; fin de cola
    ld e, a
    ld a, [wJFrame + 1]
    ld d, a
    ld a, c
    and $1F
    call MirrorLanes
    call SetTailEnd
    jp .loop
.lanesEntry:
    ld a, c
    and $1F
    jp z, .loop             ; entrada de relleno
    call MirrorLanes
    ld b, a                 ; B = carriles
    xor a
    bit 5, c                ; nota de una frase estelar
    jr z, .notStar
    inc a
.notStar:
    ld [wTmpStar], a
    xor a
    bit 6, c
    jr z, .noSust
    ld a, [wInstrument]
    cp 3
    ld a, 0
    jr z, .noSust
    inc a
.noSust:
    ld c, a                 ; C = la entrada tiene cola
    and a
    jr z, .push
    ld de, $FFFF            ; la cola de estos carriles termina en algún cuadro que todavía no se lee
    ld a, b
    push bc
    call SetTailEnd
    pop bc
.push:
    ld a, [wJQHead]
    ld hl, wJQCount
    add [hl]
    and 15
    ld e, a
    ld d, 0
    ld hl, wJQMask
    add hl, de
    ld [hl], b
    ld hl, wJQSus
    add hl, de
    ld [hl], c
    ld hl, wJQStar
    add hl, de
    ld a, [wTmpStar]
    ld [hl], a
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
    jp .loop

; A = carriles, DE = cuadro: lo anota como el fin de la cola de esos carriles
SetTailEnd:
    ld c, a
    ld hl, wTailEnd
    ld b, NUM_LANES
.lane:
    srl c
    jr nc, .next
    ld a, e
    ld [hl+], a
    ld a, d
    ld [hl-], a
.next:
    inc hl
    inc hl
    dec b
    jr nz, .lane
    ret

; Sostener: cada cuadro con el botón de un carril con cola apretado y antes de su fin suma 10 puntos cada 8 cuadros y
; 1 de vida cada 32; soltar antes solo deja de sumar (no rompe el combo ni calla al instrumento). No cuenta para las
; estrellas (esas salen solo de las notas).
HoldFrame:
    ld a, [wHold]
    and a
    ret z
    ld c, a
    ld b, 0
.lane:
    srl c
    jr nc, .next
    push bc
    call HoldLane
    pop bc
.next:
    inc b
    ld a, b
    cp NUM_LANES
    jr nz, .lane
    ret

; B = carril que se está sosteniendo
HoldLane:
    ld e, b
    ld d, 0
    ld hl, LaneBit
    add hl, de
    ld a, [hl]
    ld [wTryBit], a
    ld hl, wHeld
    and [hl]
    jr z, .stop             ; soltó el botón
    ld a, b
    add a
    ld e, a
    ld hl, wTailEnd
    add hl, de
    ld a, [hl+]
    ld e, a
    ld d, [hl]
    ld a, [wTJ]
    sub e
    ld a, [wTJ + 1]
    sbc d
    jr nc, .stop            ; llegó al fin de la cola
    ld e, b
    ld d, 0
    ld hl, wHoldTick
    add hl, de
    inc [hl]
    ld c, [hl]
    ld a, c
    and 7
    jr nz, .noScore
    push bc
    ld a, 1
    call ScoreAddTens
    ld hl, wHudDirty
    set 0, [hl]
    pop bc
.noScore:
    ld a, c
    and 31
    ret nz
    jp LifeGain
.stop:
    ld a, [wTryBit]
    cpl
    ld hl, wHold
    and [hl]
    ld [hl], a
    ld e, b
    ld d, 0
    ld hl, wHoldTick
    add hl, de
    ld [hl], 0
    ret
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
    call StarTick
    ld a, [wLifeGrace]
    and a
    jr z, .noGrace
    dec a
    ld [wLifeGrace], a
.noGrace:
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
    push af
    ld a, [wJQHead]         ; la entrada que se pierde: ¿era una nota estelar?
    ld [wScanE], a
    call StarNoteMiss
    pop af
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
    and 15
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
    bit PADB_SELECT, b      ; Select activa el poder estelar
    jr z, .noStar
    push bc
    call StarActivate
    pop bc
.noStar:
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
    call HoldFrame

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
    and 15
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
    and 15
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
    ld a, [wScanE]          ; ¿la entrada tiene cola? entonces el carril se empieza a sostener
    ld e, a
    ld d, 0
    ld hl, wJQSus
    add hl, de
    ld a, [hl]
    and a
    jr z, .noHold
    ld a, [wTryBit]
    ld hl, wHold
    or [hl]
    ld [hl], a
.noHold:
    call StarNoteHit
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
    ; puntaje += 50 * multiplicador (en decenas: 5 * m); con el poder estelar activo el multiplicador vale el doble
    ld b, a
    ld a, [wStarActive]
    and a
    ld a, b
    jr z, .notDoubled
    add a
.notDoubled:
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
    call LifeGain
    ld a, [wFailed]         ; tras perder, el instrumento no vuelve a sonar
    and a
    jr nz, .failed
    ld [wMuted], a
.failed:
    ld a, $03
    ld [wHudDirty], a
    ret

MissNote:
    ld hl, wMissDigits + 2
    call Inc3Digits
    ld a, [wDifficulty]     ; perder una nota cuesta 2 de vida (1 en fácil)
    and a
    ld b, LIFE_LOSS
    jr nz, .loss
    ld b, 1
.loss:
    call LifeLoss
    jr BreakCombo

AirStrum:
    ld hl, wAirCount
    inc [hl]
    ld b, 1
    call LifeLoss
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
    push af
    push bc
    push de
    push hl
    call MissFx
    pop hl
    pop de
    pop bc
    pop af
    ret

; ---- Poder estelar -------------------------------------------------------------------------------
; Las notas con el bit $20 forman frases de 4: si aciertas las 4 sin fallar ninguna, la barra sube STAR_PHRASE (un cuarto).
; Con la mitad o más, Select la activa: el multiplicador vale el doble y la barra se vacía (una llena dura unos 13 s).

; wScanE = índice de la entrada resuelta
StarNoteHit:
    ld a, [wScanE]
    ld e, a
    ld d, 0
    ld hl, wJQStar
    add hl, de
    ld a, [hl]
    and a
    ret z
    ld hl, wStarRun
    inc [hl]
    jr StarCheckEnd

StarNoteMiss:
    ld a, [wScanE]
    ld e, a
    ld d, 0
    ld hl, wJQStar
    add hl, de
    ld a, [hl]
    and a
    ret z
    ld a, 1
    ld [wStarFail], a
StarCheckEnd:
    ld a, [wScanE]          ; la frase sigue si la entrada que viene también es estelar
    inc a
    and 15
    ld e, a
    ld a, [wJQHead]
    ld d, a
    ld a, e
    sub d
    and 15
    ld hl, wJQCount
    cp [hl]
    jr nc, .phraseEnd       ; no hay más entradas en la cola: fin de la frase
    ld d, 0
    ld hl, wJQStar
    add hl, de
    ld a, [hl]
    and a
    ret nz
.phraseEnd:
    ld a, [wStarFail]
    and a
    jr nz, .reset
    ld a, [wStarRun]
    and a
    jr z, .reset
    ld a, [wStarEnergy]
    add STAR_PHRASE
    cp STAR_MAX + 1
    jr c, .store
    ld a, STAR_MAX
.store:
    ld [wStarEnergy], a
.reset:
    xor a
    ld [wStarRun], a
    ld [wStarFail], a
    ret

StarActivate:
    ld a, [wStarActive]
    and a
    ret nz
    ld a, [wStarEnergy]
    cp STAR_MIN
    ret c
    ld a, 1
    ld [wStarActive], a
    ld a, STAR_DRAIN
    ld [wStarTimer], a
    ld hl, wHudDirty        ; el multiplicador de la pantalla cambia
    set 0, [hl]
    ret

StarTick:
    ld a, [wStarActive]
    and a
    ret z
    ld hl, wStarTimer
    dec [hl]
    ret nz
    ld [hl], STAR_DRAIN
    ld hl, wStarEnergy
    dec [hl]
    ret nz
    xor a                   ; se acabó la barra
    ld [wStarActive], a
    ld hl, wHudDirty
    set 0, [hl]
    ret

; ---- Vida --------------------------------------------------------------------------------------
LifeGain:
    ld a, [wNoFail]
    and a
    ret nz
    ld a, [wLife]
    cp LIFE_MAX
    ret nc
    inc a
    ld [wLife], a
    ret

; B = cuánta vida se pierde. Tras perder vida hay un respiro de LIFE_GRACE cuadros en que los fallos no cuestan más
; (notas repetidas en un carril que caen antes de poder tocarlas se cobran una sola vez).
LifeLoss:
    ld a, [wNoFail]
    and a
    ret nz
    ld a, [wLifeGrace]
    and a
    ret nz
    ld a, LIFE_GRACE
    ld [wLifeGrace], a
    ld a, [wLife]
    sub b
    jr nc, .store
    xor a
.store:
    ld [wLife], a
    ret nz
    ld a, 1                 ; se acabó la vida: pierdes, el instrumento calla hasta el final
    ld [wFailed], a
    ld [wMuted], a
    ld hl, wHudDirty
    set 2, [hl]
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
