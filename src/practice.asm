; =============================================================================
; practice.asm - Modo práctica: inicio adelantado (keyframes), fin del bucle y marcas A/B de la pausa
;
; La canción se repite desde un punto P hasta un fin E (cuartos de la canción o las marcas). Para empezar en P:
;   - el reloj arranca PRACTICE_PRE cuadros antes (la autopista ya trae las notas siguientes) y las notas antes de P se omiten;
;   - el scroll y las filas del fondo se calculan como si el reloj llevara corriendo desde cero (PracticeSeek);
;   - el audio parte del keyframe anterior (su registro deja el estado de los 4 canales) y avanza decodificando con el
;     APU en silencio hasta el cuadro de audio de P (AudioSeek), todo con la pantalla apagada.
; =============================================================================

SECTION "Practice", ROM0

DEF PRACTICE_PRE EQU 120        ; cuadros entre el arranque del reloj y el primer cuadro de audio
DEF PRACTICE_MIN EQU 240        ; el bucle debe durar al menos 4 s

; A = keyframe (0 a 3) -> DE = su cuadro de audio, HL = su entrada en la ficha. El banco A debe estar activo.
KfAt:
    ld c, a
    add a
    add a
    add a
    sub c                   ; 7 * k
    ld e, a
    ld d, 0
    ld hl, $4000 + SONG_KEYFRAMES
    add hl, de
    ld a, [hl+]
    ld e, a
    ld a, [hl-]
    ld d, a
    ret

; A = keyframe -> DE = su cuadro de la canción (lead-in + cuadro de audio). wLeadIn tiene que ser el de la ficha.
KfFrame:
    call KfAt
    ld a, [wLeadIn]
    add e
    ld e, a
    ld a, [wLeadIn + 1]
    adc d
    ld d, a
    ret

; Con el banco de la canción activo y wLeadIn / wEndFrame ya leídos de la ficha: decide el fin del bucle (wEndFrame) y
; el inicio adelantado. Sin inicio adelantado (wPracFromP = 0) la canción empieza en el cuadro 0 como siempre.
PracticeSetup:
    xor a
    ld [wPracFromP], a
    ld a, [wOptPractice]
    and a
    ret z
    ld b, a                 ; B = hasta cuándo (1 a 3 cuartos, 4 el final)
    cp 4
    jr z, .endDone
    call KfFrame
    ld a, e
    ld [wEndFrame], a
    ld a, d
    ld [wEndFrame + 1], a
.endDone:
    ld a, [wMarkBOn]
    and a
    jr z, .noB
    ld a, [wMarkB]
    ld [wEndFrame], a
    ld a, [wMarkB + 1]
    ld [wEndFrame + 1], a
.noB:
    ld a, [wMarkAOn]
    and a
    jr z, .noA
    ld a, [wMarkA]
    ld e, a
    ld a, [wMarkA + 1]
    ld d, a
    jr .haveP
.noA:
    ld a, [wOptStart]       ; el inicio nunca queda en o después del fin: se recorre al cuarto anterior
    ld c, a
    ld a, [wOptPractice]
    dec a
    cp c
    jr nc, .startOk
    ld c, a
.startOk:
    ld a, c
    and a
    ret z                   ; el principio: sin inicio adelantado
    call KfFrame
.haveP:
    ld a, d
    and a
    jr nz, .enough
    ld a, e
    cp PRACTICE_PRE
    ret c                   ; demasiado cerca del principio: se empieza normal
.enough:
    ld a, e
    ld [wPracP], a
    ld a, d
    ld [wPracP + 1], a
    ld hl, wLeadIn          ; cuadro de audio de P = P - lead-in
    ld a, e
    sub [hl]
    ld [wSeekA], a
    inc hl
    ld a, d
    sbc [hl]
    ld [wSeekA + 1], a
    inc de                  ; el audio normal sigue desde P + 1 (el de P ya se aplicó con AudioSeek)
    ld a, e
    ld [wLeadIn], a
    ld a, d
    ld [wLeadIn + 1], a
    ld a, e                 ; el reloj arranca en P - PRE = (P + 1) - (PRE + 1)
    sub PRACTICE_PRE + 1
    ld e, a
    ld a, d
    sbc 0
    ld d, a
    ld a, e
    ld [wT], a
    ld [wTJ], a
    ld [wJT], a
    ld a, d
    ld [wT + 1], a
    ld [wTJ + 1], a
    ld [wJT + 1], a
    ld a, 1
    ld [wPracFromP], a
    ret

; wMulF (cuadros, 16 bits) * velocidad -> wMulR (24 bits, 8.8)
MulFrames:
    ld a, [wSpeed]
    ld e, a
    ld a, [wSpeed + 1]
    ld d, a
    ld a, [wMulF]
    ld b, a
    call MulDelta
    ld a, l
    ld [wMulR], a
    ld a, h
    ld [wMulR + 1], a
    ld a, c
    ld [wMulR + 2], a
    ld a, [wMulF + 1]
    ld b, a
    call MulDelta           ; el byte alto de los cuadros pesa 256: va un byte más arriba
    ld a, [wMulR + 1]
    add l
    ld [wMulR + 1], a
    ld a, [wMulR + 2]
    adc h
    ld [wMulR + 2], a
    ret

; En HighwayInit, con el LCD apagado: coloca los cursores del chart (el de la autopista y el del juez) en la primera
; entrada con cuadro >= P y deja el scroll, SCY y la primera fila a armar como si el reloj llevara wT cuadros corriendo.
PracticeSeek:
    ld a, [wBCur]
    ld l, a
    ld a, [wBCur + 1]
    ld h, a
    xor a
    ld [wSeekF], a
    ld [wSeekF + 1], a
.scan:
    ld a, [hl+]
    ld c, a                 ; C = cuadros desde la entrada anterior
    ld a, [hl-]
    cp $FF
    jr z, .found            ; el final del chart
    ld a, [wSeekF]
    add c
    ld e, a
    ld a, [wSeekF + 1]
    adc 0
    ld d, a
    push hl
    ld hl, wPracP
    ld a, e
    sub [hl]
    inc hl
    ld a, d
    sbc [hl]
    pop hl
    jr nc, .found           ; esta entrada ya es de P o después
    ld a, e
    ld [wSeekF], a
    ld a, d
    ld [wSeekF + 1], a
    inc hl
    inc hl
    jr .scan
.found:
    ld a, l
    ld [wBCur], a
    ld [wJCur], a
    ld a, h
    ld [wBCur + 1], a
    ld [wJCur + 1], a

    ; posición de esa entrada: cuadro * velocidad
    ld a, [wSeekF]
    ld [wMulF], a
    ld a, [wSeekF + 1]
    ld [wMulF + 1], a
    call MulFrames
    ld a, [wMulR]
    ld [wBFs], a
    ld a, [wMulR + 1]
    ld [wBFs + 1], a
    ld a, [wMulR + 2]
    ld [wBFs + 2], a

    ; el scroll de wT cuadros: -(wT * velocidad)
    ld a, [wT]
    ld [wMulF], a
    ld a, [wT + 1]
    ld [wMulF + 1], a
    call MulFrames
    xor a
    ld hl, wMulR
    sub [hl]
    ld [hl+], a
    ld a, 0
    sbc [hl]
    ld [hl+], a
    ld a, 0
    sbc [hl]
    ld [hl], a
    ld a, [wMulR]
    ld [wScroll], a
    ld a, [wMulR + 1]
    ld [wScroll + 1], a
    xor a
    ld [wScrollF], a
    ld a, [wMulR]           ; SCY redondeado al píxel más cercano; DE = esa posición en píxeles (con signo, sin el módulo 256)
    add $80
    ld a, [wMulR + 1]
    adc 0
    ld e, a
    ldh [hScy], a
    ld a, [wMulR + 2]
    adc 0
    ld d, a
    sra d                   ; fila de arriba de la pantalla = píxeles / 8
    rr e
    sra d
    rr e
    sra d
    rr e
    ld hl, 17               ; la primera fila que se arma es la 17 debajo de la de arriba
    add hl, de
    ld a, l
    ld [wBuildQ], a
    ld a, h
    ld [wBuildQ + 1], a
    ret

; Con el LCD apagado: pone los 4 canales en el estado del cuadro de audio wSeekA. Parte del keyframe anterior y decodifica
; el resto, consumiendo cada cuadro con las salidas del APU apagadas (NR51 = 0).
AudioSeek:
    xor a
    ldh [rNR51], a
    ld b, 3
.pick:
    ld a, b
    push bc
    call KfAt
    pop bc
    ld a, [wSeekA]
    sub e
    ld a, [wSeekA + 1]
    sbc d
    jr nc, .picked          ; at <= wSeekA
    dec b
    jr .pick
.picked:
    ld a, b
    call KfAt               ; DE = at, HL = entrada
    ld a, [wSeekA]
    sub e
    ld [wSeekN], a
    ld a, [wSeekA + 1]
    sbc d
    ld [wSeekN + 1], a      ; cuadros por decodificar después del registro
    inc hl
    inc hl                  ; HL = banco, puntero del stream y registro
    ld a, [hl+]
    ld [wTmpBank], a
    ld a, [hl+]
    ld [wTmpPtr], a
    ld a, [hl+]
    ld [wTmpPtr + 1], a
    ld a, [hl+]
    ld [wStrPtr], a
    ld a, [hl]
    ld [wStrPtr + 1], a
    ld a, [wSongBank]       ; el registro del keyframe vive en el banco A
    ld [wStrBank], a
    ld [rROMB0], a
    call DecodeFrame
    call ConsumeSlot
    ld a, [wTmpPtr]
    ld [wStrPtr], a
    ld a, [wTmpPtr + 1]
    ld [wStrPtr + 1], a
    ld a, [wTmpBank]
    ld [wStrBank], a
    ld [rROMB0], a
.loop:
    ld a, [wSeekN]
    ld b, a
    ld a, [wSeekN + 1]
    or b
    ret z
    ld a, [wSeekN]
    sub 1
    ld [wSeekN], a
    ld a, [wSeekN + 1]
    sbc 0
    ld [wSeekN + 1], a
    call DecodeFrame
    call ConsumeSlot
    jr .loop

; ---- Marcas de la pausa ---------------------------------------------------------------------------------------
; A: el bucle empieza 2 s antes de donde pausaste; B: termina donde pausaste. Carry = 1 si la marca se aceptó.
MarkStart:
    ld a, [wSongBank]
    call SwitchBank
    ld a, [wT]
    sub 120
    ld e, a
    ld a, [wT + 1]
    sbc 0
    ld d, a
    ld a, [$4000 + SONG_LEADIN]        ; no antes del primer cuadro de audio
    ld c, a
    ld a, [$4000 + SONG_LEADIN + 1]
    ld b, a
    ld a, e
    sub c
    ld a, d
    sbc b
    jr nc, .above
    ld e, c
    ld d, b
.above:
    ld a, [wEndFrame]       ; que el bucle dure al menos PRACTICE_MIN
    sub e
    ld c, a
    ld a, [wEndFrame + 1]
    sbc d
    ld b, a
    jr c, .refuse
    ld a, b
    and a
    jr nz, .accept
    ld a, c
    cp PRACTICE_MIN
    jr c, .refuse
.accept:
    ld a, e
    ld [wMarkA], a
    ld a, d
    ld [wMarkA + 1], a
    ld a, 1
    ld [wMarkAOn], a
    scf
    ret
.refuse:
    and a
    ret

MarkEnd:
    ld a, [wT]
    ld e, a
    ld a, [wT + 1]
    ld d, a
    ld a, [wPracFromP]      ; el inicio actual del bucle
    and a
    jr z, .fromLead
    ld a, [wPracP]
    ld c, a
    ld a, [wPracP + 1]
    ld b, a
    jr .have
.fromLead:
    ld a, [wSongBank]
    call SwitchBank
    ld a, [$4000 + SONG_LEADIN]
    ld c, a
    ld a, [$4000 + SONG_LEADIN + 1]
    ld b, a
.have:
    ld a, e
    sub c
    ld c, a
    ld a, d
    sbc b
    jr c, .refuse
    jr nz, .accept
    ld a, c
    cp PRACTICE_MIN
    jr c, .refuse
.accept:
    ld a, e
    ld [wMarkB], a
    ld a, d
    ld [wMarkB + 1], a
    ld a, 1
    ld [wMarkBOn], a
    scf
    ret
.refuse:
    and a
    ret
