; =============================================================================
; coop.asm - Co-Op por cable link: el marcador de la banda
;
; El jugador 1 (maestro) es la autoridad de lo de la banda: puntaje, combo, multiplicador, barra estelar. Su juez lo
; suma directo (Band... en gameplay.asm) y aplica igual los eventos que le manda el 2 (MSG_EVENTS: aciertos, fallos,
; frases estelares, colas sostenidas y Select). El 2 no suma nada a la banda: muestra el estado que le manda el 1
; (MSG_BAND, ~4 veces por segundo). La vida es de cada quien: quien cae deja de sumar y sus fallos ya no rompen el combo;
; quien sigue en pie lo revive con Select gastando media barra; si caen los dos, la banda pierde.
;
; Los ganchos Coop... los llama el juez: carry = 1 quiere decir "esto no se suma aquí a la banda".
; =============================================================================

DEF MSG_EVENTS EQU $87          ; el 2 al 1, jugando: aciertos antes y después del último fallo, banderas, frases, colas
DEF MSG_BAND   EQU $88          ; el 1 al 2: el estado de la banda (ver CoopSendBand)

DEF EVB_MISS   EQU 0            ; banderas de MSG_EVENTS: hubo un fallo en el lote
DEF EVB_SELECT EQU 1            ; apretó Select (poder estelar, o revivir al 1 si cayó)
DEF EVB_FAILED EQU 2            ; cayó
DEF EVB_MUTED  EQU 3            ; su instrumento está callado

DEF BANDB_FAILED EQU 0          ; banderas de MSG_BAND: el 1 cayó
DEF BANDB_MUTED  EQU 1          ; el instrumento del 1 está callado
DEF BANDB_ACTIVE EQU 2          ; el poder estelar está activo
DEF BANDB_FINAL  EQU 3          ; el 1 ya está en resultados: es el estado final
DEF BANDB_REVIVE EQU 4          ; (bits 4 y 5) cuenta de veces que el 1 revivió al 2

DEF COOP_EV_PERIOD EQU 8        ; el 2 manda sus banderas al menos cada tantos cuadros, aunque no haya eventos

SECTION "Coop", ROM0

; Z = 1 si hay Co-Op por cable (en el menú o jugando)
LinkIsCoop:
    ldh a, [hLinkOn]
    and a
    jr z, .no
    ld a, [wPlayers]
    cp 2
    ret
.no:
    inc a
    ret

; BeginPlay: ¿esta partida es de Co-Op? Y todo lo de la banda en ceros
CoopBegin:
    call LinkIsCoop
    ld a, 0
    jr nz, .set
    inc a
.set:
    ld [wCoopGame], a
    xor a
    ld hl, wEvHitsA
    ld b, wPeerDiffSeen - wEvHitsA      ; (los contadores, lo recibido y las banderas de resultados)
.clear:
    ld [hl+], a
    dec b
    jr nz, .clear
    ld a, COOP_EV_PERIOD
    ld [wEvTimer], a
    ret

; A = 0 sin Co-Op (o se perdió el cable), 1 jugador 1, 2 jugador 2. Usa solo A.
CoopRole:
    ld a, [wCoopGame]
    and a
    ret z
    ldh a, [hLinkOn]
    and a
    ret z
    ldh a, [hLinkMaster]
    and a
    ld a, 1
    ret nz
    inc a
    ret

; ---- Ganchos del juez ---------------------------------------------------------------------------------------------
; Acierto. Usa A, C y HL.
CoopHit:
    ld hl, wEvHitsA
    jr CoopCount

; Una decena de puntos de una cola sostenida
CoopSustain:
    ld hl, wEvTens
    jr CoopCount

; Una frase estelar completa
CoopPhrase:
    ld hl, wEvPhrases
; Sin Co-Op o en el 1: carry = 0 (se suma normal). Quien cayó: carry = 1 (no suma). El 2: cuenta el evento en [HL] (los
; aciertos van a wEvHitsB si ya hubo un fallo en el lote) y carry = 1.
CoopCount:
    call CoopRole
    and a
    ret z
    ld c, a
    ld a, [wFailed]
    and a
    jr nz, .skip
    ld a, c
    dec a
    ret z                       ; (carry = 0 del `and a`)
    ld a, l
    cp LOW(wEvHitsA)
    jr nz, .count
    ld a, [wEvFlags]
    bit EVB_MISS, a
    jr z, .count
    ld hl, wEvHitsB
.count:
    ld a, [hl]
    cp 127                      ; (7 bits: se manda mucho antes de llegar)
    jr nc, .skip
    inc [hl]
.skip:
    scf
    ret

; Fallo (nota perdida o golpe al aire): rompe el combo de la banda, salvo de quien ya cayó
CoopBreak:
    call CoopRole
    and a
    ret z
    ld c, a
    ld a, [wFailed]
    and a
    jr nz, .skip
    ld a, c
    dec a
    ret z
    ld hl, wEvFlags             ; el 2: los aciertos de después del fallo anterior pasan a ser "de antes"
    bit EVB_MISS, [hl]
    set EVB_MISS, [hl]
    jr z, .skip
    ld a, [wEvHitsB]
    ld c, a
    ld a, [wEvHitsA]
    add c
    cp 128
    jr c, .merged
    ld a, 127
.merged:
    ld [wEvHitsA], a
    xor a
    ld [wEvHitsB], a
.skip:
    scf
    ret

; Select. El 2 se lo manda al 1. El 1: si el 2 cayó, lo revive con media barra; si no, carry = 0 (poder estelar).
CoopSelect:
    call CoopRole
    and a
    ret z
    ld c, a
    ld a, [wFailed]             ; quien cayó no activa ni revive nada
    and a
    jr nz, .done
    ld a, c
    dec a
    jr nz, .slave
    ld a, [wRivalFlags]
    bit RIVALB_FAILED, a
    ret z                       ; (carry = 0 del `and a`)
    ld a, [wStarEnergy]
    sub STAR_MIN
    jr c, .done                 ; no alcanza la barra
    ld [wStarEnergy], a
    ld hl, wReviveSeq
    inc [hl]
    ld hl, wRivalFlags          ; (hasta que el 2 lo confirme, ya no cuenta como caído)
    res RIVALB_FAILED, [hl]
    res RIVALB_MUTED, [hl]
    jr .done
.slave:
    ld hl, wEvFlags
    set EVB_SELECT, [hl]
.done:
    scf
    ret

; Esta consola vuelve a la partida con media vida (la revivió el otro)
CoopReviveSelf:
    xor a
    ld [wFailed], a
    ld [wMuted], a
    ld a, LIFE_MAX / 2
    ld [wLife], a
    ld a, LIFE_GRACE
    ld [wLifeGrace], a
    ld hl, HudText1             ; "COMBO" otra vez en lugar de "FALLASTE"
    ld de, HUD_ROW1 + 5
    ld b, 10
    call QueueRaw
    ld hl, wHudDirty
    set 1, [hl]
    ret

; ---- Una vez por cuadro (LinkTick, jugando) ----------------------------------------------------------------------
CoopTick:
    call CoopRole
    and a
    ret z
    dec a
    jr nz, .slave
    ; el 1: aplica los eventos del 2 y le manda el estado de la banda cada vez que se vacía la cola
    ld hl, wLinkGot
    bit GOTB_EVENTS, [hl]
    jr z, .noEvents
    res GOTB_EVENTS, [hl]
    call CoopApplyEvents
.noEvents:
    ld a, [wState]
    cp STATE_PLAY
    jr z, .band
    cp STATE_RESULTS
    jr z, .final
    cp STATE_INITIALS
    ret nz
.final:
    ; en resultados se turnan el estado final de la banda y el MSG_SCORE con los aciertos (LinkScoreTick)
    call LinkOutEmpty
    ret nz
    ld hl, wCoopAlt
    ld a, [hl]
    xor 1
    ld [hl], a
    ret z
    jp CoopSendBand
.band:
    call LinkOutEmpty
    ret nz
    jp CoopSendBand
.slave:
    ld hl, wLinkGot
    bit GOTB_BAND, [hl]
    jr z, .noBand
    res GOTB_BAND, [hl]
    call CoopApplyBand
.noBand:
    ld a, [wState]
    cp STATE_PLAY
    jr z, .events
    ; en resultados: primero se mandan los eventos que hayan quedado
    ld a, [wEvHitsA]
    ld hl, wEvHitsB
    or [hl]
    ld hl, wEvPhrases
    or [hl]
    ld hl, wEvTens
    or [hl]
    ld hl, wEvFlags
    or [hl]
    ret z
.events:
    ld hl, wEvTimer
    dec [hl]
    call LinkOutEmpty
    ret nz
    ld a, [wEvHitsA]
    ld hl, wEvHitsB
    or [hl]
    ld hl, wEvPhrases
    or [hl]
    ld hl, wEvTens
    or [hl]
    ld hl, wEvFlags
    or [hl]
    jr nz, CoopSendEvents
    ld a, [wEvTimer]
    bit 7, a                    ; (sin eventos: las banderas cada COOP_EV_PERIOD cuadros)
    ret z
; El 2: manda lo acumulado y empieza otro lote
CoopSendEvents:
    ld a, COOP_EV_PERIOD
    ld [wEvTimer], a
    ld hl, wMenuMsg
    ld a, MSG_EVENTS
    ld [hl+], a
    ld a, [wEvHitsA]
    ld [hl+], a
    ld a, [wEvHitsB]
    ld [hl+], a
    ld a, [wEvFlags]
    and (1 << EVB_MISS) | (1 << EVB_SELECT)
    ld b, a
    ld a, [wFailed]
    and a
    jr z, .notFailed
    set EVB_FAILED, b
.notFailed:
    ld a, [wMuted]
    and a
    jr z, .notMuted
    set EVB_MUTED, b
.notMuted:
    ld [hl], b
    inc hl
    ld a, [wEvPhrases]
    ld [hl+], a
    ld a, [wEvTens]
    ld [hl], a
    xor a
    ld [wEvHitsA], a
    ld [wEvHitsB], a
    ld [wEvFlags], a
    ld [wEvPhrases], a
    ld [wEvTens], a
    ld hl, wMenuMsg
    ld b, LINK_EVENTS_LEN + 1
    jp LinkSend

; El 1: lo que hizo el 2 se aplica a la banda como si fuera propio
CoopApplyEvents:
    ld a, [wState]              ; (en resultados todavía cuentan los eventos que quedaban)
    cp STATE_PLAY
    jr z, .apply
    cp STATE_RESULTS
    ret nz
.apply:
    ld a, [wPeerEvents]         ; aciertos antes del fallo
    call .hits
    ld a, [wPeerEvents + 2]
    bit EVB_MISS, a
    call nz, BandBreak
    ld a, [wPeerEvents + 1]     ; aciertos después del fallo
    call .hits
    ld a, [wPeerEvents + 3]     ; frases estelares
.phrases:
    and a
    jr z, .tens
    push af
    call BandPhrase
    pop af
    dec a
    jr .phrases
.tens:
    ld a, [wPeerEvents + 4]     ; decenas de las colas
    and a
    jr z, .select
    call ScoreAddTens
.select:
    ld a, [wPeerEvents + 2]
    bit EVB_SELECT, a
    jr z, .flags
    ld a, [wFailed]             ; el 1 cayó: el 2 lo revive con media barra; si no, es el poder estelar
    and a
    jr z, .star
    ld a, [wStarEnergy]
    sub STAR_MIN
    jr c, .flags
    ld [wStarEnergy], a
    call CoopReviveSelf
    jr .flags
.star:
    call BandStar
.flags:
    ; las banderas del 2 (cayó, callado) quedan en wRivalFlags, como las del rival de VS
    ld a, [wPeerEvents + 2]
    ld b, 0
    bit EVB_FAILED, a
    jr z, .notFailed
    set RIVALB_FAILED, b
.notFailed:
    bit EVB_MUTED, a
    jr z, .notMuted
    set RIVALB_MUTED, b
.notMuted:
    ld a, [wRivalFlags]
    and 1 << RIVALB_FINISHED
    or b
    ld [wRivalFlags], a
    ld a, [wHudDirty]
    or $03
    ld [wHudDirty], a
    ld a, 1
    ld [wRivalDirty], a
    ret
; A aciertos de la banda
.hits:
    and a
    ret z
    push af
    call BandHit
    pop af
    dec a
    jr .hits

; El 1: manda el estado de la banda (12 bytes: puntaje en tres de dos dígitos, combo y combo máximo en dos cada uno
; (decenas y centenas juntas, unidades), multiplicador, barra, banderas y las unidades del puntaje en dos de 7 bits)
CoopSendBand:
    ld hl, wMenuMsg
    ld a, MSG_BAND
    ld [hl+], a
    ld de, wScoreDigits
    ld b, 3
    call CoopPackPairs
    ld de, wComboDigits
    call CoopPack3
    ld de, wMaxComboDigits
    call CoopPack3
    ld a, [wMult]
    ld [hl+], a
    ld a, [wStarEnergy]
    ld [hl+], a
    ld a, [wReviveSeq]
    and 3
    swap a                      ; bits 4 y 5
    ld b, a
    ld a, [wFailed]
    and a
    jr z, .notFailed
    set BANDB_FAILED, b
.notFailed:
    ld a, [wMuted]
    and a
    jr z, .notMuted
    set BANDB_MUTED, b
.notMuted:
    ld a, [wStarActive]
    and a
    jr z, .notActive
    set BANDB_ACTIVE, b
.notActive:
    ld a, [wState]              ; final: el 1 ya terminó y ya le llegó lo último del 2 (el 2 manda sus eventos
    cp STATE_PLAY               ; pendientes antes que su MSG_SCORE final)
    jr z, .playing
    push bc
    push hl
    call CoopResultsReady
    pop hl
    pop bc
    jr nc, .playing
    set BANDB_FINAL, b
.playing:
    ld [hl], b
    inc hl
    ld a, [wScoreUnits]
    and $7F
    ld [hl+], a
    ld a, [wScoreUnits + 1]     ; los 7 bits de arriba
    ld b, a
    ld a, [wScoreUnits]
    rla
    ld a, b
    rla
    and $7F
    ld [hl], a
    ld hl, wMenuMsg
    ld b, LINK_BAND_LEN + 1
    jp LinkSend

; Empaca B pares de dígitos de DE (decenas, unidades) en bytes de HL
CoopPackPairs:
    ld a, [de]
    inc de
    ld c, a
    add a
    add a
    add c
    add a                       ; * 10
    ld c, a
    ld a, [de]
    inc de
    add c
    ld [hl+], a
    dec b
    jr nz, CoopPackPairs
    ret

; Empaca los 3 dígitos de DE en dos bytes de HL: centenas y decenas juntas, unidades
CoopPack3:
    ld b, 1
    call CoopPackPairs
    ld a, [de]
    ld [hl+], a
    ret

; Desempaca B bytes de HL (0 a 99) en pares de dígitos en DE
CoopUnpackPairs:
    ld a, [hl+]
    ld c, 0
.tens:
    cp 10
    jr c, .ones
    sub 10
    inc c
    jr .tens
.ones:
    push af
    ld a, c
    ld [de], a
    inc de
    pop af
    ld [de], a
    inc de
    dec b
    jr nz, CoopUnpackPairs
    ret

; El 2: lo que manda el 1 es el estado de la banda
CoopApplyBand:
    ld hl, wPeerBand
    ld de, wScoreDigits
    ld b, 3
    call CoopUnpackPairs
    ld de, wComboDigits
    call .three
    ld de, wMaxComboDigits
    call .three
    ld a, [hl+]
    ld [wMult], a
    ld a, [hl+]
    ld [wStarEnergy], a
    ld a, [hl+]                 ; banderas
    ld b, a
    xor a
    bit BANDB_ACTIVE, b
    jr z, .active
    inc a
.active:
    ld [wStarActive], a
    ld a, [hl+]                 ; unidades del puntaje
    ld c, a
    ld a, [hl]
    srl a
    ld [wScoreUnits + 1], a
    ld a, c
    jr nc, .lowBit
    or $80
.lowBit:
    ld [wScoreUnits], a
    ; las banderas del 1 quedan en wRivalFlags
    ld c, 0
    bit BANDB_FAILED, b
    jr z, .notFailed
    set RIVALB_FAILED, c
.notFailed:
    bit BANDB_MUTED, b
    jr z, .notMuted
    set RIVALB_MUTED, c
.notMuted:
    bit BANDB_FINAL, b
    jr z, .notFinal
    set RIVALB_FINISHED, c
    ld a, 1
    ld [wBandFinal], a
.notFinal:
    ld a, c
    ld [wRivalFlags], a
    ; ¿el 1 me revivió?
    ld a, b
    swap a
    and 3
    ld hl, wReviveSeq
    cp [hl]
    jr z, .noRevive
    ld [hl], a
    ld a, [wFailed]
    and a
    call nz, CoopReviveSelf
.noRevive:
    ld a, [wHudDirty]
    or $03
    ld [wHudDirty], a
    ld a, 1
    ld [wRivalDirty], a
    ret
; dos bytes de HL a los 3 dígitos de DE
.three:
    ld b, 1
    call CoopUnpackPairs
    ld a, [hl+]
    ld [de], a
    ret

; ---- Resultados -----------------------------------------------------------------------------------------------------
TxtCoopWait:  db "ESPERANDO A J", 0
TxtCoopPeer:  db "J  NOTAS", 0         ; (las que acertó el compañero, de su total)
TxtBandLost:  db "LA BANDA PERDIO", 0

; EnterResults: en Co-Op, mientras no lleguen los datos finales del otro, se espera con "ESPERANDO A J2..." (carry = 1)
CoopResultsWait:
    call CoopResultsReady
    ccf
    ret nc
    call BeginTextScreen
    ld de, _SCRN0 + 32 * 8 + 2
    ld hl, TxtCoopWait
    call PrintStr
    call VsNumbers
    ld a, c
    ld [de], a
    inc de
    ld a, '.'
    ld [de], a
    inc de
    ld [de], a
    inc de
    ld [de], a
    ld a, 1
    ld [wCoopWaiting], a
    ld a, STATE_RESULTS
    ld [wState], a
    call EndTextScreen
    scf
    ret

; Carry = 1 si ya están los datos finales del otro (o no hace falta esperarlos)
CoopResultsReady:
    ld a, [wCoopGame]
    and a
    jr z, .ready
    ldh a, [hLinkOn]
    and a
    jr z, .ready                ; (se perdió el cable: se muestra lo que haya)
    ld a, [wRivalFlags]
    bit RIVALB_FINISHED, a
    jr z, .wait
    ld a, [wRivalDigits + 3]    ; el MSG_SCORE final del otro trae su total de notas: si no ha llegado, sigue en ceros
    ld b, a
    ld a, [wRivalDigits + 4]
    or b
    ld b, a
    ld a, [wRivalDigits + 5]
    or b
    jr z, .wait
    ldh a, [hLinkMaster]
    and a
    jr nz, .ready
    ld a, [wBandFinal]          ; el 2 también espera el estado final de la banda
    and a
    jr z, .wait
.ready:
    scf
    ret
.wait:
    and a
    ret

; ComputeResults: en Co-Op, el máximo posible (y las estrellas) salen de las notas de los dos
CoopAddPeerNotes:
    ld a, [wCoopGame]
    and a
    ret z
    ld hl, wRivalDigits + 3
    call DigitsToBin
    ld a, [wNotesTotal]
    add l
    ld [wNotesTotal], a
    ld a, [wNotesTotal + 1]
    adc h
    ld [wNotesTotal + 1], a
    ret

; EnterResults (LCD apagado): los aciertos del compañero y, si la banda perdió, "LA BANDA PERDIO"
ResultsCoopDraw:
    ld de, _SCRN0 + 32 * VS_ROW_RIVAL + 1
    ld hl, TxtCoopPeer
    call PrintStr
    call VsNumbers
    ld a, c
    ld [_SCRN0 + 32 * VS_ROW_RIVAL + 2], a
    ld de, _SCRN0 + 32 * VS_ROW_RIVAL + 12
    ld hl, wRivalDigits
    ld b, 3
    call PrintDigits
    ld a, '/'
    ld [de], a
    inc de
    ld hl, wRivalDigits + 3
    ld b, 3
    call PrintDigits
    ld a, [wVsCut]
    and a
    ret z
    ld de, _SCRN0 + 32 * VS_ROW_LINE + 2
    ld hl, TxtBandLost
    jp PrintStr

; Co-Op: si los dos cayeron, la banda pierde (la partida se corta)
CoopCut:
    call CoopRole
    and a
    ret z
    ld a, [wFailed]
    and a
    ret z
    ld a, [wRivalFlags]
    bit RIVALB_FAILED, a
    ret
