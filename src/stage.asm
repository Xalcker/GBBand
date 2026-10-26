; =============================================================================
; stage.asm - El escenario vivo: el público de la Window y los reflectores de las torres, al ritmo de los tiempos
;
; En cada tiempo de la canción (SONG_BEAT cuadros) el público cambia de pose (brazos abajo / arriba, alternando las
; columnas) y los reflectores se encienden o se apagan (se copia sobre su tile la versión clara u oscura) y, en CGB, cambian de
; color. Cada cosa va en un cuadro distinto para no pasar de la cuota de VRAM de la ISR.
; =============================================================================

SECTION "Stage", ROM0

DEF BEAT_CROWD_L EQU 0
DEF BEAT_CROWD_R EQU 1
DEF BEAT_LAMP    EQU 2
DEF BEAT_PAL     EQU 3

; Color (claro, medio) de los reflectores en cada paso del ciclo de 8
LampHues:
    dw $211F, $0852                 ; rojo
    dw $129F, $0552                 ; naranja
    dw $1BFF, $0A94                 ; amarillo
    dw $23EA, $0E44                 ; verde
    dw $7F66, $51C2                 ; cian
    dw $7D48, $4883                 ; azul
    dw $7D1F, $4872                 ; magenta
    dw $629F, $3954                 ; rosa

; Pone el público en las filas de la Window (LCD apagado) y, en CGB, su paleta
CrowdDraw:
    xor a
    ld [wCrowdPhase], a
    ld c, 0
    ld hl, HUD_ROW0
    call CrowdTopFill
    ld c, 15
    ld hl, HUD_ROW0 + 15
    call CrowdTopFill
    ld hl, HUD_ROW1
    call CrowdBodyFill
    ld hl, HUD_ROW1 + 15
    call CrowdBodyFill
    ldh a, [hCGB]
    and a
    ret z
    ld a, 1
    ldh [rVBK], a
    ld a, 6
    ld hl, HUD_ROW0
    call CrowdAttrFill
    ld hl, HUD_ROW0 + 15
    call CrowdAttrFill
    ld hl, HUD_ROW1
    call CrowdAttrFill
    ld hl, HUD_ROW1 + 15
    call CrowdAttrFill
    xor a
    ldh [rVBK], a
    ret

; HL = destino, C = paridad de la primera columna: 5 tiles de arriba
CrowdTopFill:
    ld b, 5
.loop:
    ld a, c
    and 1
    add TILE_CROWD_DOWN
    ld [hl+], a
    inc c
    dec b
    jr nz, .loop
    ret

CrowdBodyFill:
    ld a, TILE_CROWD_BODY
    ld b, 5
.loop:
    ld [hl+], a
    dec b
    jr nz, .loop
    ret

CrowdAttrFill:
    ld b, 5
.loop:
    ld [hl+], a
    dec b
    jr nz, .loop
    ret

; Al empezar una partida (LCD apagado, banco de la canción activo, wT ya puesto): el primer tiempo y los reflectores encendidos
StageBeatInit:
    xor a
    ld [wBeatPending], a
    ld [wLampHue], a
    ld a, 1
    ld [wLampLit], a
    ld a, [$4000 + SONG_BEAT]
    ld [wBeatLen], a
    ld a, [$4000 + SONG_FIRSTBEAT]
    ld [wBeatNext], a
    ld a, [$4000 + SONG_FIRSTBEAT + 1]
    ld [wBeatNext + 1], a
.catchUp:                    ; con la práctica adelantada el primer tiempo es el siguiente a wT
    ld hl, wBeatNext
    ld a, [wT]
    sub [hl]
    inc hl
    ld a, [wT + 1]
    sbc [hl]
    jr c, .ready
    ld a, [wBeatLen]
    dec hl
    add [hl]
    ld [hl+], a
    ld a, 0
    adc [hl]
    ld [hl], a
    jr .catchUp
.ready:
    ld hl, _VRAM + TILE_LAMP * 16       ; la VRAM guarda el reflector como lo dejó la partida anterior: encendido
    ld de, Tiles + TILE_LAMP * 16
    ld bc, 16
    call CopyMem
    ld a, 1
    ld [wLampReq], a                    ; el primer color del ciclo
    ret

; Cada cuadro de juego
StageBeat:
    ld a, [wBeatPending]
    and a
    jr z, .detect
    bit BEAT_CROWD_L, a
    jr z, .notCrowdL
    res BEAT_CROWD_L, a
    ld [wBeatPending], a
    ld c, 0
    ld de, HUD_ROW0
    jr CrowdQueue
.notCrowdL:
    bit BEAT_CROWD_R, a
    jr z, .notCrowdR
    res BEAT_CROWD_R, a
    ld [wBeatPending], a
    ld c, 15
    ld de, HUD_ROW0 + 15
    jr CrowdQueue
.notCrowdR:
    bit BEAT_LAMP, a
    jr z, .notLamp
    res BEAT_LAMP, a
    ld [wBeatPending], a
    ld hl, Tiles + TILE_LAMP * 16       ; encendido
    ld a, [wLampLit]
    and a
    jr nz, .lampSrc
    ld hl, Tiles + TILE_LAMP_OFF * 16   ; apagado
.lampSrc:
    ld de, _VRAM + TILE_LAMP * 16
    ld b, 16
    jp QueueRaw
.notLamp:
    res BEAT_PAL, a                     ; (el color de los reflectores lo cambia la ISR)
    ld [wBeatPending], a
    ld a, [wLampHue]
    inc a
    ld [wLampReq], a
    ret
.detect:
    ld hl, wBeatNext
    ld a, [wT]
    sub [hl]
    inc hl
    ld a, [wT + 1]
    sbc [hl]
    ret c                               ; todavía no es el tiempo
    ld a, [wBeatLen]
    dec hl
    add [hl]
    ld [hl+], a
    ld a, 0
    adc [hl]
    ld [hl], a
    ld a, [wCrowdPhase]
    xor 1
    ld [wCrowdPhase], a
    ld a, [wLampLit]
    xor 1
    ld [wLampLit], a
    ld a, [wLampHue]
    inc a
    and 7
    ld [wLampHue], a
    ld a, (1 << BEAT_CROWD_L) | (1 << BEAT_CROWD_R) | (1 << BEAT_LAMP) | (1 << BEAT_PAL)
    ld [wBeatPending], a
    ret

; C = paridad de la primera columna (la de DE, más la fase del público), DE = destino en la Window: encola los 5 tiles de arriba
CrowdQueue:
    ld a, [wCrowdPhase]
    add c
    ld c, a
    ld hl, wCrowdBuf
    ld b, 5
.loop:
    ld a, c
    and 1
    add TILE_CROWD_DOWN
    ld [hl+], a
    inc c
    dec b
    jr nz, .loop
    ld hl, wCrowdBuf
    ld b, 5
    jp QueueRaw

; ISR: A = paso del ciclo + 1. Cambia el color de la paleta 7 (reflectores) en CGB.
ApplyLampPal:
    ld b, a
    xor a
    ld [wLampReq], a
    ldh a, [hCGB]
    and a
    ret z
    ld a, b
    dec a
    and 7
    add a
    add a                   ; 4 bytes por paso
    ld e, a
    ld d, 0
    ld hl, LampHues
    add hl, de
    ld a, $80 | (7 * 8 + 2) ; paleta 7, color 1, con autoincremento
    ldh [rBCPS], a
    ld b, 4
.loop:
    ld a, [hl+]
    ldh [rBCPD], a
    dec b
    jr nz, .loop
    ret
