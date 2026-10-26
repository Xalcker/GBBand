; =============================================================================
; highway.asm - La autopista: scroll, armado de filas y colocación de las gemas
;
; Todo se mide en puntos fijos 8.8 (px por cuadro). Una nota del cuadro F está, en el fondo de 256 px, en
;     y = HIT_Y*256 - F*velocidad     (módulo 65536)
; y SCY(t) = -t*velocidad. En el cuadro t = F la nota queda en pantalla en y = HIT_Y (la línea de golpe).
; Cada fila de tiles del fondo ("fila q", con signo, q = y/8) se arma UNA vez, cuando el scroll cruza un múltiplo
; de 8 px, en la fila que está 24 filas debajo de la de arriba de la pantalla: ahí no se ve (queda detrás de la
; Window o fuera de pantalla) y tardará 8 pasos en entrar por arriba. Ver docs/diseno.md.
;
; Colocación B: la gema tiene 4 variantes (desplazamiento de 0, 2, 4 o 6 px) y con desplazamiento puede cruzar
; dos filas; la parte de abajo se escribe como un parche en la fila siguiente (ya armada).
; Colocación A (PLACEMENT_B = 0): una fila por gema, redondeada a 8 px.
; =============================================================================

SECTION "Highway", ROM0

DEF HIT_Y EQU 120               ; la línea de golpe: fila de tiles 15, justo arriba de la Window (que empieza en y = 128)

; Velocidad 8.8 de cada dificultad (px/cuadro): 120 px en 2.6, 2.2, 1.7 y 1.3 s a 59.7275 Hz.
; Debe coincidir con layout.speed_8_8 (lo comprueba una prueba de pytest).
SpeedTable:
    dw 198, 234, 303, 396
StepsPer4: db 4, 3, 2, 5        ; pasos de la canción cada 4 cuadros reales, de 100%, 75%, 50% y 125%

GemBase:    db TILE_GEM, TILE_GEM + GEM_STRIDE, TILE_GEM + 2 * GEM_STRIDE, TILE_GEM + 3 * GEM_STRIDE, TILE_GEM + 4 * GEM_STRIDE
GemTopIdx:  db 0, 2, 6, 10       ; tile de arriba izquierda de la variante 0, 2, 4, 6 px
GemBotIdx:  db 0, 4, 8, 12       ; tile de abajo izquierda (la variante 0 no tiene)

; Redondeo (en la mitad alta de q): +256 (B, a 2 px) o +1024 (A, a 8 px)
IF PLACEMENT_B
    DEF ROUND_HI EQU 1
ELSE
    DEF ROUND_HI EQU 4
ENDC

; ---- Inicio -------------------------------------------------------------------------------
; Con el LCD apagado y el banco de la canción activo.
HighwayInit:
    ld a, [wOptFall]        ; CAIDA DE NOTAS: 0 = la de la dificultad elegida; 1 a 4 = la de facil a experto
    and a
    jr z, .auto
    dec a
    jr .haveIdx
.auto:
    ld a, [wDifficulty]
.haveIdx:
    add a
    ld e, a
    ld d, 0
    ld hl, SpeedTable
    add hl, de
    ld a, [hl+]
    ld [wSpeed], a
    ld e, a
    ld a, [hl]
    ld [wSpeed + 1], a
    ld d, a
    ; avance del scroll por cuadro real (8.16) = velocidad * pasos por cuadro: 4/4, 3/4, 2/4 o 5/4 de la velocidad
    ld a, [wSpeedMode]
    ld c, a
    ld b, 0
    ld hl, StepsPer4
    add hl, bc
    ld b, [hl]
    call MulDelta           ; HL = velocidad * pasos (8.8, 4 veces el avance)
    ld a, l
    and 3
    rrca
    rrca
    ld [wStepSpd], a        ; (velocidad * pasos) * 64 = 8.16
    srl h
    rr l
    srl h
    rr l
    ld a, l
    ld [wStepSpd + 1], a
    ld a, h
    ld [wStepSpd + 2], a
    xor a
    ld [wScrollF], a
    ld [wScroll], a
    ld [wScroll + 1], a
    ldh [hScy], a
    ld [wBFs], a
    ld [wBFs + 1], a
    ld [wBFs + 2], a
    ld hl, wRowFlags
    ld b, 32
    xor a
.clearFlags:
    ld [hl+], a
    dec b
    jr nz, .clearFlags
    xor a
    ld [wTailOpen], a
    ld a, 17                ; la primera fila que se arma es la 17 (debajo de la línea de golpe)
    ld [wBuildQ], a
    xor a
    ld [wBuildQ + 1], a

    ; puntero al chart (instrumento 0 = guitarra) de la dificultad elegida
    ld a, [wInstrument]     ; puntero al chart: SONG_CHARTS + 2 * (instrumento * 4 + dificultad)
    add a
    add a
    ld b, a
    ld a, [wDifficulty]
    add b
    add a
    add SONG_CHARTS
    ld l, a
    ld h, HIGH($4000)
    ld a, [hl+]
    ld e, a
    ld a, [hl]
    ld d, a
    ld a, e
    ld [wBCur], a
    ld [wJCur], a
    ld a, d
    ld [wBCur + 1], a
    ld [wJCur + 1], a

    ld a, [wPracFromP]
    and a
    call nz, PracticeSeek
    call FetchNote
    ld b, PREFILL_ROWS
.prefill:
    push bc
    call BuildRow
    call FlushVQueue
    pop bc
    dec b
    jr nz, .prefill
    ret

; ---- Cada cuadro ----------------------------------------------------------------------------
; Avanza el scroll al cuadro siguiente (el que mostrará la próxima ISR) y arma una fila si cruzó un múltiplo de 8 px.
HighwayStep:
    ld hl, wStepSpd
    ld a, [wScrollF]
    sub [hl]
    ld [wScrollF], a
    inc hl
    ld a, [wScroll]
    sbc [hl]
    ld [wScroll], a
    inc hl
    ld a, [wScroll + 1]
    sbc [hl]
    ld [wScroll + 1], a
    ld b, a
    ld a, [wScroll]         ; SCY = scroll redondeado al píxel más cercano (truncar sesgaría todo hacia abajo)
    add $80
    ld a, b
    adc 0
    ld b, a                 ; B = SCY nuevo
    ldh a, [hScy]
    xor b
    and %11111000           ; ¿cambió la fila de tiles de arriba?
    jr z, .same
    push bc
    call BuildRow
    pop bc
.same:
    ld a, b
    ldh [hScy], a
    ret

; ---- Siguiente nota del chart ------------------------------------------------------------------
; Lee entradas de wBCur hasta una con carriles; deja wNMask, wNRow y wNOff. Sin más notas: wNMask = 0.
FetchNote:
.again:
    ld a, [wBCur]
    ld l, a
    ld a, [wBCur + 1]
    ld h, a
    ld a, [hl+]
    ld b, a                 ; B = cuadros desde la entrada anterior
    ld a, [hl+]
    cp $FF
    jp z, .end
    ld c, a                 ; C = el byte del chart: carriles ($1F), cola ($40) y fin de cola ($80)
    and $1F
    call MirrorLanes
    ld [wNMask], a
    xor a
    bit 7, c
    jr z, .notEnd
    inc a
.notEnd:
    ld [wNEnd], a           ; 1 = esta entrada cierra la cola de sus carriles
    xor a
    bit 6, c
    jr z, .noSust
    ld a, [wInstrument]     ; en la batería el bit $40 es un platillo, no una cola
    cp 3
    ld a, 0
    jr z, .noSust
    inc a
.noSust:
    ld [wNSust], a
    ld a, l
    ld [wBCur], a
    ld a, h
    ld [wBCur + 1], a
    ld a, [wSpeed]
    ld e, a
    ld a, [wSpeed + 1]
    ld d, a
    call MulDelta           ; C:H:L = B * velocidad
    ld a, [wBFs]
    add l
    ld [wBFs], a
    ld a, [wBFs + 1]
    adc h
    ld [wBFs + 1], a
    ld a, [wBFs + 2]
    adc c
    ld [wBFs + 2], a
    ld a, [wNMask]
    and a
    jr z, .again            ; entrada de relleno: solo avanza el tiempo

    ; q = HIT_Y*256 - Fs  (24 bits con signo) y se redondea
    ld hl, wBFs
    ld a, LOW(HIT_Y * 256)
    sub [hl]
    inc hl
    ld a, HIGH(HIT_Y * 256)
    sbc [hl]
    ld e, a                 ; E = byte medio
    inc hl
    ld a, 0
    sbc [hl]
    ld d, a                 ; D = byte alto
    ld a, e
    add ROUND_HI
    ld e, a
    jr nc, .noCarry
    inc d
.noCarry:
    ld h, d                 ; HL = V = (q + redondeo) >> 8, en píxeles con signo
    ld l, e
IF PLACEMENT_B
    ld a, l
    and %110
ELSE
    xor a
ENDC
    ld [wNOff], a
    srl a
    ld [wNV], a
    sra h                   ; fila = V >> 3 (aritmético)
    rr l
    sra h
    rr l
    sra h
    rr l
    ld a, l
    ld [wNRow], a
    ld a, h
    ld [wNRow + 1], a
    ret
.end:
    xor a
    ld [wNMask], a
    ret

; B * DE (B = cuadros, DE = velocidad 8.8) -> C:H:L (24 bits). Suma y desplazamiento, 8 pasos.
MACRO MulStep
    add hl, hl
    rl c
    sla b
    jr nc, .skip\@
    add hl, de
    jr nc, .skip\@
    inc c
.skip\@:
ENDM

MulDelta:
    ld hl, 0
    ld c, 0
    REPT 8
        MulStep
    ENDR
    ret

; ---- Armar una fila ----------------------------------------------------------------------------
BuildRow:
    xor a
    ld [wRowHas], a
    ; fondo por defecto: carril vacío, atributos de la paleta 0
    ld hl, wRowTiles
    ld b, NUM_LANES
.lane:
    ld a, TILE_LANE_L
    ld [hl+], a
    ld a, TILE_LANE_R
    ld [hl+], a
    dec b
    jr nz, .lane
    ld hl, wRowAttr
    ld b, 10
    xor a
.attr:
    ld [hl+], a
    dec b
    jr nz, .attr

    ld a, [wTailOpen]       ; las colas abiertas se dibujan antes que las gemas de la fila
    and a
    jr z, .notes
    ld c, a
    ld b, 0
.tailLane:
    srl c
    jr nc, .tailNext
    push bc
    call PlaceTail
    pop bc
.tailNext:
    inc b
    ld a, b
    cp NUM_LANES
    jr nz, .tailLane
.notes:
    ld a, [wNMask]
    and a
    jr z, .emit
    ld a, [wNRow]           ; ¿la nota cae en esta fila (o ya la pasamos)? diff = fila de la nota - fila actual
    ld hl, wBuildQ
    sub [hl]
    inc hl
    ld a, [wNRow + 1]
    sbc [hl]
    bit 7, a
    jr nz, .emit            ; negativo: la nota está más adelante
    ld a, [wNEnd]
    and a
    jr z, .gem
    ld a, [wNMask]          ; fin de cola: esa fila todavía lleva la barra, las siguientes ya no
    cpl
    ld b, a
    ld a, [wTailOpen]
    and b
    ld [wTailOpen], a
    jr .nextNote
.gem:
    call PlaceNote
    ld a, [wNSust]
    and a
    jr z, .nextNote
    ld a, [wNMask]          ; la cola empieza en la fila siguiente
    ld b, a
    ld a, [wTailOpen]
    or b
    ld [wTailOpen], a
.nextNote:
    call FetchNote
    jr .notes
.emit:
    ; Una fila vacía solo se escribe si la vuelta anterior dejó gemas en esa fila del fondo (ya tiene los carriles vacíos)
    ld a, [wBuildQ]
    and 31
    ld e, a
    ld d, 0
    ld hl, wRowFlags
    add hl, de
    ld a, [wRowHas]
    or [hl]
    jr z, .rowDone
    call QueueRow
    ld a, [wBuildQ]
    and 31
    ld e, a
    ld d, 0
    ld hl, wRowFlags
    add hl, de
    ld a, [wRowHas]
    ld [hl], a
.rowDone:
    ld hl, wBuildQ
    ld a, [hl]
    sub 1
    ld [hl+], a
    ld a, [hl]
    sbc 0
    ld [hl], a
    ret

; B = carril: la barra de la cola en esa fila
PlaceTail:
    ld a, b
    add a
    ld e, a
    ld d, 0
    ld hl, wRowTiles
    add hl, de
    ld a, TILE_TAIL_L
    ld [hl+], a
    ld a, TILE_TAIL_R
    ld [hl], a
    ld a, b
    inc a
    ld c, a
    ld hl, wRowAttr
    add hl, de
    ld a, c
    ld [hl+], a
    ld [hl], a
    ld a, 1
    ld [wRowHas], a
    ret

; Pone la gema de wNMask en el buffer de la fila (y el parche de abajo si cruza dos filas).
PlaceNote:
    ld a, [wNMask]
    ld c, a
    ld a, [wInstrument]
    cp 3
    jr nz, .lanes0
    bit 4, c                ; batería: el bombo (carril naranja) es una barra que cruza todo; va primero y las gemas encima
    jr z, .lanes0
    push bc
    call PlaceBar
    pop bc
    res 4, c
.lanes0:
    ld b, 0                 ; B = carril
.lane:
    srl c
    jr nc, .next
    call PlaceLane
.next:
    inc b
    ld a, b
    cp NUM_LANES
    jr nz, .lane
    ret

; B = carril. Conserva BC.
PlaceLane:
    push bc
    ld a, 1
    ld [wRowHas], a
    ld a, b
    ld [wPLane], a
    ld e, b
    ld d, 0
    ld hl, GemBase
    add hl, de
    ld a, [hl]
    ld [wPBase], a
    ld a, [wNV]
    ld e, a
    ld d, 0
    ld hl, GemTopIdx
    add hl, de
    ld a, [wPBase]
    add [hl]
    ld c, a                 ; C = tile de arriba izquierda
    ld a, [wPLane]
    add a
    ld e, a
    ld d, 0                 ; DE = 2 * carril
    ld hl, wRowTiles
    add hl, de
    ld a, c
    ld [hl+], a
    inc a
    ld [hl], a
    ld a, [wPLane]          ; atributos: paleta lane+1
    inc a
    ld c, a
    ld hl, wRowAttr
    add hl, de
    ld a, c
    ld [hl+], a
    ld [hl], a
IF PLACEMENT_B
    ld a, [wNOff]
    and a
    call nz, QueuePatch
ENDC
    pop bc
    ret

; El bombo: los 10 tiles del ancho de la autopista de la fila (y su parte de abajo, con desplazamiento, en la siguiente)
PlaceBar:
    ld a, 1
    ld [wRowHas], a
    ld a, [wNV]
    and a
    jr nz, .shifted
    ld a, TILE_BAR
    ld hl, wRowTiles
    ld b, 10
.full:
    ld [hl+], a
    dec b
    jr nz, .full
    jr .attr
.shifted:
    dec a
    add a
    add a                   ; 4 * (desplazamiento / 2 - 1)
    add TILE_BAR + 1        ; tile de arriba izquierda
    ld c, a
    ld hl, wRowTiles
    ld b, 5
.pairs:
    ld a, c
    ld [hl+], a
    inc a
    ld [hl+], a
    dec b
    jr nz, .pairs
.attr:
    ld hl, wRowAttr
    ld b, 10
    ld a, 5                 ; paleta del naranja
.attrLoop:
    ld [hl+], a
    dec b
    jr nz, .attrLoop
    ld a, [wNOff]
    and a
    ret z
    ; la parte de abajo cae en la fila siguiente
    ld a, [wBuildQ]
    inc a
    and 31
    ld e, a
    ld d, 0
    ld hl, wRowFlags
    add hl, de
    ld [hl], 1
    ld a, [wBuildQ]
    inc a
    call RowDest
    ld a, l
    ld [wQDest], a
    ld a, h
    ld [wQDest + 1], a
    ld d, h
    ld e, l
    ld b, 10
    ld c, 0
    call VQAlloc
    ld a, [wNV]
    dec a
    add a
    add a
    add TILE_BAR + 3        ; tile de abajo izquierda = el de arriba izquierda + 2
    ld c, a
    ld b, 5
.botPairs:
    ld a, c
    ld [hl+], a
    inc a
    ld [hl+], a
    dec b
    jr nz, .botPairs
    ldh a, [hCGB]
    and a
    ret z
    ld a, [wQDest]
    ld e, a
    ld a, [wQDest + 1]
    ld d, a
    ld b, 10
    ld c, $80
    call VQAlloc
    ld b, 10
    ld a, 5
.botAttr:
    ld [hl+], a
    dec b
    jr nz, .botAttr
    ret

; HL = $9800 + (A & 31) * 32 + 5  (clobbera DE)
RowDest:
    and 31
    ld l, a
    ld h, 0
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, hl
    ld de, _SCRN0 + LANE_COL0
    add hl, de
    ret

; Encola la fila armada (tiles, y atributos en CGB).
QueueRow:
    ld a, [wBuildQ]
    call RowDest
    ld a, l
    ld [wQDest], a
    ld a, h
    ld [wQDest + 1], a
    ld d, h
    ld e, l
    ld b, 10
    ld c, 0
    call VQAlloc
    ld de, wRowTiles
    ld c, 10
.copyT:
    ld a, [de]
    inc de
    ld [hl+], a
    dec c
    jr nz, .copyT
    ldh a, [hCGB]
    and a
    ret z
    ld a, [wQDest]
    ld e, a
    ld a, [wQDest + 1]
    ld d, a
    ld b, 10
    ld c, $80
    call VQAlloc
    ld de, wRowAttr
    ld c, 10
.copyA:
    ld a, [de]
    inc de
    ld [hl+], a
    dec c
    jr nz, .copyA
    ret

; La parte de abajo de la gema de wPLane cae en la fila siguiente (q+1), que ya está armada: se parchea.
QueuePatch:
    ld a, [wBuildQ]         ; la fila de abajo ahora tiene gemas en VRAM
    inc a
    and 31
    ld e, a
    ld d, 0
    ld hl, wRowFlags
    add hl, de
    ld [hl], 1
    ld a, [wBuildQ]
    inc a
    call RowDest
    ld a, [wPLane]
    add a
    ld e, a
    ld d, 0
    add hl, de              ; + 2 * carril
    ld a, l
    ld [wQDest], a
    ld a, h
    ld [wQDest + 1], a
    ld d, h
    ld e, l
    ld b, 2
    ld c, 0
    call VQAlloc
    push hl
    ld hl, GemBotIdx
    ld a, [wNV]
    ld e, a
    ld d, 0
    add hl, de
    ld a, [wPBase]
    add [hl]
    pop hl
    ld [hl+], a
    inc a
    ld [hl], a
    ldh a, [hCGB]
    and a
    ret z
    ld a, [wQDest]
    ld e, a
    ld a, [wQDest + 1]
    ld d, a
    ld b, 2
    ld c, $80
    call VQAlloc
    ld a, [wPLane]
    inc a
    ld [hl+], a
    ld [hl], a
    ret
