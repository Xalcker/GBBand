; =============================================================================
; game.asm - Estados del juego: título, menú, partida, pausa y resultados
; =============================================================================

SECTION "Game", ROM0

TxtTitle:    db "GBBAND", 0
TxtSong:     db " CANCION", 0
TxtInstr:    db " INSTRUMENTO", 0
TxtDiff:     db " DIFICULTAD", 0
TxtFail:     db " FALLO", 0
TxtPress:    db "PRESIONA START", 0
TxtBack:     db "B: VOLVER", 0
TxtSubtitle: db "RITMO PARA GAME BOY", 0
TxtNoRel:    db "PROYECTO DE AFICIONADOS", 0
TxtNoRel2:    db "SIN RELACION CON NINTENDO", 0
; 14 caracteres cada una, con relleno a 16 para indexar con (valor << 4)
DiffText:
    db "<   FACIL    >", 0, 0
    db "<   MEDIO    >", 0, 0
    db "<  DIFICIL   >", 0, 0
    db "<  EXPERTO   >", 0, 0
InstrText:
    db "<  GUITARRA  >", 0, 0
    db "<  TECLADO   >", 0, 0
    db "<    BAJO    >", 0, 0
    db "<  BATERIA   >", 0, 0
FailText:
    db "<  ACTIVADO  >", 0, 0
    db "< SIN FALLO  >", 0, 0
; NR51 con el CH1, CH2, CH3 o CH4 fuera de ambos lados: lo que se oye cuando el instrumento falla
InstrNr51Muted: db $EE, $DD, $BB, $77

DEF MENU_ROW_SONG  EQU 3        ; fila de pantalla de cada renglón del menú (el valor va 1 o 2 filas abajo)
DEF MENU_ROW_INSTR EQU 7
DEF MENU_ROW_DIFF  EQU 10
DEF MENU_ROW_FAIL  EQU 13
DEF MENU_ROWS      EQU 4
DEF MENU_ROW_RECORD EQU 15      ; el récord de lo elegido
CursorRows: db MENU_ROW_SONG, MENU_ROW_INSTR, MENU_ROW_DIFF, MENU_ROW_FAIL

; Apaga el LCD (solo en VBlank, o dañaría una DMG). Si ya estaba apagado no hace nada.
LcdOff:
    ldh a, [rLCDC]
    bit 7, a
    ret z
    ldh a, [hMainBusy]      ; mientras se espera el VBlank el bucle principal no está "ocupado": no es un cuadro atrasado
    push af
    xor a
    ldh [hMainBusy], a
.wait:
    ldh a, [rLY]
    cp 144
    jr c, .wait
    xor a
    ldh [rLCDC], a
    pop af
    ldh [hMainBusy], a
    ret

; Deja una pantalla de texto lista (LCD apagado): mapas limpios, sin scroll, sin sprites, sin Window y la cola vacía.
BeginTextScreen:
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
    ld a, 1
    ld [wOamDirty], a
    ld a, 144
    ldh [hWy], a
    ldh [rWY], a
    ret

; Enciende el LCD con solo el fondo
EndTextScreen:
    ld a, LCDCF_ON | LCDCF_BG8000 | LCDCF_BGON
    ldh [hLcdc], a
    ldh [rLCDC], a
    ret

; ---- Título -----------------------------------------------------------------------------------
EnterTitle:
    call BeginTextScreen
    ld de, _SCRN0 + 32 * 5 + 7
    ld hl, TxtTitle
    call PrintStr
    ld de, _SCRN0 + 32 * 7 + 1
    ld hl, TxtSubtitle
    call PrintStr
    ld de, _SCRN0 + 32 * 12 + 3
    ld hl, TxtPress
    call PrintStr
    ld de, _SCRN0 + 32 * 16 + 0
    ld hl, TxtNoRel
    call PrintStr
    ld de, _SCRN0 + 32 * 17 + 0
    ld hl, TxtNoRel2
    call PrintStr
    ld a, STATE_TITLE
    ld [wState], a
    jp EndTextScreen

TitleFrame:
    di
    ldh a, [hPadNew]
    ld b, a
    xor a
    ldh [hPadNew], a
    ei
    bit PADB_START, b
    ret z
    jp EnterMenu

; ---- Menú -------------------------------------------------------------------------------------
; Cuatro renglones: canción, instrumento, dificultad y fallo. ↑/↓ cambia de renglón, ←/→ el valor, Start empieza.
EnterMenu:
    call BeginTextScreen
    ld de, _SCRN0 + 32 * 1 + 7
    ld hl, TxtTitle
    call PrintStr
    ld de, _SCRN0 + 32 * MENU_ROW_SONG + 1
    ld hl, TxtSong
    call PrintStr
    ld de, _SCRN0 + 32 * MENU_ROW_INSTR + 1
    ld hl, TxtInstr
    call PrintStr
    ld de, _SCRN0 + 32 * MENU_ROW_DIFF + 1
    ld hl, TxtDiff
    call PrintStr
    ld de, _SCRN0 + 32 * MENU_ROW_FAIL + 1
    ld hl, TxtFail
    call PrintStr
    ld de, _SCRN0 + 32 * 16 + 1
    ld hl, TxtBack
    call PrintStr
    ld de, _SCRN0 + 32 * 17 + 3
    ld hl, TxtPress
    call PrintStr
    ld a, STATE_MENU
    ld [wState], a
    call EndTextScreen
    call MenuLoadSong
    call QueueSongText
    call QueueInstrument
    call QueueDifficulty
    call QueueFail
    call RefreshRecord
    jp QueueCursor

; Elige el banco de la canción (wSong), lee su ficha (instrumentos, título y juego) y deja un instrumento válido.
MenuLoadSong:
    ld a, [wSong]
    ld e, a
    ld d, 0
    ld hl, SongTable
    add hl, de
    ld a, [hl]
    ld [wSongBank], a
    call SwitchBank
    ld a, [$4000 + SONG_INSTR]
    ld [wInstrMask], a
    ld hl, wTitleBuf
    ld de, $4000 + SONG_TITLE
    ld bc, SONG_TITLE_LEN + SONG_GAME_LEN       ; el juego va justo después del título en la ficha
    call CopyMem
    call ComputeSongHash
    ld a, [wInstrument]
    call InstrAvailable
    ret c
    xor a
.find:
    ld [wInstrument], a
    push af
    call InstrAvailable
    pop bc
    ret c
    ld a, b
    inc a
    and 3
    jr .find

; A = instrumento. Carry = 1 si la canción elegida tiene su chart.
InstrAvailable:
    ld c, a
    ld a, [wInstrMask]
    inc c
.shift:
    srl a
    dec c
    jr nz, .shift
    ret

; DE = dirección en el mapa $9800 de la fila de pantalla C, columna E (el menú no tiene scroll)
MenuDest:
    push de
    ld a, c
    call RowDest            ; HL = $9800 + fila * 32 + 5
    pop de
    ld d, 0
    add hl, de
    ld de, -5
    add hl, de
    ld d, h
    ld e, l
    ret

; HL = origen, B = bytes, C = fila de pantalla, E = columna
QueueMenuAt:
    push hl
    call MenuDest
    pop hl
    jp QueueRaw

QueueSongText:
    ld c, MENU_ROW_SONG + 1
    ld e, 0
    ld hl, wTitleBuf
    ld b, SONG_TITLE_LEN
    call QueueMenuAt
    ld c, MENU_ROW_SONG + 2
    ld e, 2
    ld hl, wGameBuf
    ld b, SONG_GAME_LEN
    jr QueueMenuAt

QueueInstrument:
    ld a, [wInstrument]
    swap a
    ld e, a
    ld d, 0
    ld hl, InstrText
    add hl, de
    ld c, MENU_ROW_INSTR + 1
    ld e, 3
    ld b, 14
    jr QueueMenuAt

QueueDifficulty:
    ld a, [wDifficulty]
    swap a
    ld e, a
    ld d, 0
    ld hl, DiffText
    add hl, de
    ld c, MENU_ROW_DIFF + 1
    ld e, 3
    ld b, 14
    jr QueueMenuAt

QueueFail:
    ld a, [wNoFail]
    swap a
    ld e, a
    ld d, 0
    ld hl, FailText
    add hl, de
    ld c, MENU_ROW_FAIL + 1
    ld e, 3
    ld b, 14
    jr QueueMenuAt

; El cursor ">" de los renglones (solo el elegido lo lleva)
QueueCursor:
    ld b, 0
.row:
    push bc
    ld hl, CursorRows
    ld e, b
    ld d, 0
    add hl, de
    ld c, [hl]
    ld a, [wMenuRow]
    cp b
    ld a, ' '
    jr nz, .put
    ld a, '>'
.put:
    ld [wQDigit], a
    ld e, 0
    call MenuDest
    ld hl, wQDigit
    ld b, 1
    call QueueRaw
    pop bc
    inc b
    ld a, b
    cp MENU_ROWS
    jr nz, .row
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
    bit PADB_B, b
    jp nz, EnterTitle
    bit PADB_DOWN, b
    jr z, .notDown
    ld a, [wMenuRow]
    cp MENU_ROWS - 1
    ret nc
    inc a
    ld [wMenuRow], a
    jp QueueCursor
.notDown:
    bit PADB_UP, b
    jr z, .notUp
    ld a, [wMenuRow]
    and a
    ret z
    dec a
    ld [wMenuRow], a
    jp QueueCursor
.notUp:
    ld c, 1                 ; C = +1 (derecha) o -1 (izquierda)
    bit PADB_RIGHT, b
    jr nz, .change
    ld c, $FF
    bit PADB_LEFT, b
    ret z
.change:
    ld a, [wMenuRow]
    and a
    jr z, .song
    dec a
    jr z, .instrument
    dec a
    jr z, .difficulty
    ld a, [wNoFail]         ; renglón 3: fallo activado / sin fallo
    xor 1
    ld [wNoFail], a
    jp QueueFail
.difficulty:
    ld a, [wDifficulty]
    add c
    cp 4
    ret nc                  ; (también atrapa el -1 desde 0, que da $FF)
    ld [wDifficulty], a
    call QueueDifficulty
    jp RefreshRecord
.instrument:
    ld b, 4
.try:
    ld a, [wInstrument]
    add c
    and 3
    ld [wInstrument], a
    push bc
    call InstrAvailable
    pop bc
    jr c, .instrumentOk
    dec b
    jr nz, .try
.instrumentOk:
    call QueueInstrument
    jp RefreshRecord
.song:
    ld a, [wSong]
    add c
    cp $FF
    jr nz, .notNegative
    ld a, NUM_SONGS - 1
.notNegative:
    cp NUM_SONGS
    jr c, .songOk
    xor a
.songOk:
    ld [wSong], a
    call MenuLoadSong
    call QueueSongText
    call QueueInstrument
    jp RefreshRecord

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

    ld a, [wSongBank]
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
    ldh [hWy], a
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
    di                      ; Start pausa (se atiende antes que el juez, que consume los botones nuevos)
    ldh a, [hPadNew]
    bit PADB_START, a
    jr z, .noPause
    res PADB_START, a
    ldh [hPadNew], a
    ei
    jp EnterPause
.noPause:
    ei
    ldh a, [rLY]
    ldh [hPassLY], a
    ld a, [wSongBank]
    call SwitchBank
    call JudgeFrame
    call HighwayStep
    call HudUpdate
    call UpdateOam
    call MeterUpdate
    ld a, [wMuted]
    and a
    ld a, $FF
    jr z, .notMuted
    ld a, [wInstrument]     ; el canal del instrumento fuera de ambos lados de NR51
    ld e, a
    ld d, 0
    ld hl, InstrNr51Muted
    add hl, de
    ld a, [hl]
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
    jp nc, EnterResults
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

; ---- Pausa --------------------------------------------------------------------------------------
; Congela el reloj de la canción (la ISR deja de contar cuadros y de consumir el ring de audio), calla el APU con NR51
; y sube la Window sobre la autopista con el texto de la pausa. Al seguir, todo continúa exactamente donde iba.
EnterPause:
    xor a
    ld [wPlaying], a
    ldh [rNR51], a
    ldh a, [hLcdc]
    and ~LCDCF_OBJON        ; sin aros mientras dura la pausa
    ldh [hLcdc], a
    ld a, PAUSE_WY
    ldh [hWy], a
    ld a, STATE_PAUSE
    ld [wState], a
    ret

PauseFrame:
    di
    ldh a, [hPadNew]
    ld b, a
    xor a
    ldh [hPadNew], a
    ei
    bit PADB_START, b
    jr z, .notStart
    ld a, WINDOW_Y
    ldh [hWy], a
    ldh a, [hLcdc]
    or LCDCF_OBJON
    ldh [hLcdc], a
    ld a, [wNr51Out]
    ldh [rNR51], a
    ld a, 1
    ld [wPlaying], a
    ld a, STATE_PLAY
    ld [wState], a
    ret
.notStart:
    bit PADB_SELECT, b
    ret z
    call AudioStop          ; Select: salir al menú sin terminar la canción
    jp EnterMenu

; ---- Resultados ---------------------------------------------------------------------------------
EndFrame:
ResultsFrame:
    di
    ldh a, [hPadNew]
    ld b, a
    xor a
    ldh [hPadNew], a
    ei
    bit PADB_START, b
    ret z
    ld a, [wNewRecord]      ; un récord pide las iniciales antes de volver al menú
    and a
    jp nz, EnterInitials
    jp EnterMenu

; Encola B bytes de HL en la dirección DE de VRAM (banco 0)
QueueRaw:
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
.copy:
    ld a, [de]
    inc de
    ld [hl+], a
    dec b
    jr nz, .copy
    ret
