; =============================================================================
; game.asm - Estados del juego: menú de dificultad, partida y fin
; =============================================================================

SECTION "Game", ROM0

TxtTitle:    db "GBBAND", 0
TxtChoose:   db "ELIGE DIFICULTAD", 0
TxtPress:    db "PRESIONA START", 0
TxtEnd:      db "FIN DE LA CANCION", 0
; 14 caracteres cada una, con relleno a 16 para indexar con (dificultad << 4)
DiffText:
    db "<   FACIL    >", 0, 0
    db "<   MEDIO    >", 0, 0
    db "<  DIFICIL   >", 0, 0
    db "<  EXPERTO   >", 0, 0

; Apaga el LCD (solo en VBlank, o dañaría una DMG). Si ya estaba apagado no hace nada.
LcdOff:
    ldh a, [rLCDC]
    bit 7, a
    ret z
.wait:
    ldh a, [rLY]
    cp 144
    jr c, .wait
    xor a
    ldh [rLCDC], a
    ret

; ---- Menú -------------------------------------------------------------------------------------
EnterMenu:
    call LcdOff
    call ClearMaps
    xor a
    ld [wPlaying], a
    ldh [hScy], a
    ldh [rSCY], a
    ld [wVQLen], a
    ld [wVQueue], a
    ld hl, wOam
    ld b, 160
.clearOam:
    ld [hl+], a
    dec b
    jr nz, .clearOam
    inc a
    ld [wOamDirty], a
    ld de, _SCRN0 + 32 * 4 + 7
    ld hl, TxtTitle
    call PrintStr
    ld de, _SCRN0 + 32 * 7 + 2
    ld hl, TxtChoose
    call PrintStr
    ld de, _SCRN0 + 32 * 14 + 3
    ld hl, TxtPress
    call PrintStr
    ld a, LCDCF_ON | LCDCF_BG8000 | LCDCF_BGON
    ldh [hLcdc], a
    ldh [rLCDC], a
    ld a, STATE_MENU
    ld [wState], a
    jr QueueDifficulty

; Escribe el texto de la dificultad elegida (por la cola de VRAM)
QueueDifficulty:
    ld a, [wDifficulty]
    swap a                  ; * 16
    ld e, a
    ld d, 0
    ld hl, DiffText
    add hl, de
    ld a, l
    ld [wQSrc], a
    ld a, h
    ld [wQSrc + 1], a
    ld de, _SCRN0 + 32 * 10 + 3
    ld b, 14
    ld c, 0
    call VQAlloc
    ld a, [wQSrc]
    ld e, a
    ld a, [wQSrc + 1]
    ld d, a
    ld b, 14
.copy:
    ld a, [de]
    inc de
    ld [hl+], a
    dec b
    jr nz, .copy
    ret

MenuFrame:
    di
    ldh a, [hPadNew]
    ld b, a
    xor a
    ldh [hPadNew], a
    ei
    bit PADB_START, b
    jp nz, StartSong
    ld a, [wDifficulty]
    bit PADB_RIGHT, b
    jr z, .notRight
    cp 3
    jr nc, .notRight
    inc a
    ld [wDifficulty], a
    jr QueueDifficulty
.notRight:
    bit PADB_LEFT, b
    ret z
    and a
    ret z
    dec a
    ld [wDifficulty], a
    jr QueueDifficulty

; ---- Partida ------------------------------------------------------------------------------------
StartSong:
    call LcdOff
    call ClearMaps
    call StageDraw
    call HudDraw

    xor a
    ld [wPlaying], a
    ld [wT], a
    ld [wT + 1], a
    ld [wTJ], a
    ld [wTJ + 1], a
    ld [wLate], a
    ld [wQMax], a
    ld [wQLast], a
    ld [wQOverflow], a
    ld [wOverrun], a
    ld [wFlushLines], a
    ld [wIsrMax], a
    ld [wCpuMax], a
    ld [wCpuFrames], a
    ld [wCpuFrames + 1], a
    ld hl, wCpuSum
    ld [hl+], a
    ld [hl+], a
    ld [hl+], a
    ld [hl], a
    ld [wVQLen], a
    ld [wVQueue], a
    ldh [hPadNew], a

    ld a, SONG0_BANK
    call SwitchBank
    ld a, [$4000 + SONG_LEADIN]
    ld [wLeadIn], a
    ld a, [$4000 + SONG_LEADIN + 1]
    ld [wLeadIn + 1], a
    ld a, [$4000 + SONG_END]
    ld [wEndFrame], a
    ld a, [$4000 + SONG_END + 1]
    ld [wEndFrame + 1], a

    call HighwayInit
    call GameplayInit
    call OamInit
    call AudioInit

    ld a, WINDOW_Y
    ldh [rWY], a
    ld a, WINDOW_X
    ldh [rWX], a
    ld a, LCDCF_ON | LCDCF_BG8000 | LCDCF_BGON | LCDCF_WINON | LCDCF_WIN9C00 | LCDCF_OBJ16 | LCDCF_OBJON
    ldh [hLcdc], a
    ldh [rLCDC], a
    ld a, 1
    ld [wPlaying], a
    ld a, STATE_PLAY
    ld [wState], a
    ret

; Un cuadro de juego (después de cada VBlank). Orden: juzgar, avanzar la autopista, HUD, aros, silencio,
; y al final rellenar el audio (que cambia de banco: nada de lo anterior puede ir después).
PlayFrame:
    ldh a, [rLY]
    ldh [hPassLY], a
    ld a, SONG0_BANK
    call SwitchBank
    call JudgeFrame
    call HighwayStep
    call HudUpdate
    call UpdateOam
    ld a, [wMuted]
    and a
    ld a, $FF
    jr z, .notMuted
    ld a, $EE               ; CH1 (el instrumento) fuera de ambos lados: bits 0 y 4 de NR51
.notMuted:
    ld [wNr51Out], a
    call FillAudioRing

    ld a, [wT]
    ld c, a
    ld a, [wT + 1]
    ld b, a
    ld a, [wEndFrame]
    ld e, a
    ld a, [wEndFrame + 1]
    ld d, a
    ld a, c
    sub e
    ld a, b
    sbc d
    jr c, .playing
    call EndSong
.playing:
    ; cuánto tardó este cuadro, en líneas de pantalla (114 M-cycles cada una)
    ldh a, [rLY]
    ld b, a
    ldh a, [hPassLY]
    ld c, a
    ld a, b
    sub c
    jr nc, .positive
    add 154
.positive:
    ld hl, wCpuMax
    cp [hl]
    jr c, .noMax
    ld [hl], a
.noMax:
    ld hl, wCpuSum
    add [hl]
    ld [hl+], a
    ld a, 0
    adc [hl]
    ld [hl+], a
    ld a, 0
    adc [hl]
    ld [hl+], a
    ld a, 0
    adc [hl]
    ld [hl], a
    ld hl, wCpuFrames
    inc [hl]
    ret nz
    inc hl
    inc [hl]
    ret

EndSong:
    xor a
    ld [wPlaying], a
    call AudioStop
    ld a, STATE_END
    ld [wState], a
    ldh a, [hScy]           ; el texto va en la fila 6 de la pantalla: con el scroll, es otra fila del mapa
    srl a
    srl a
    srl a
    add 6
    call RowDest            ; HL = $9800 + fila * 32 + 5
    ld de, -4
    add hl, de              ; columna 1
    ld d, h
    ld e, l
    ld b, 17
    ld c, 0
    call VQAlloc
    ld de, TxtEnd
.copy:
    ld a, [de]
    inc de
    ld [hl+], a
    dec b
    jr nz, .copy
    ret

EndFrame:
    di
    ldh a, [hPadNew]
    ld b, a
    xor a
    ldh [hPadNew], a
    ei
    bit PADB_START, b
    ret z
    jp EnterMenu
