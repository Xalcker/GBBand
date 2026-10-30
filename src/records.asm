; =============================================================================
; records.asm - Récords en la SRAM con batería (MBC5, 8 KB en $A000) y la pantalla de iniciales
;
; Hay un récord por canción, instrumento y dificultad. La canción se identifica por un hash de su título y su juego (no por
; su lugar en el menú), así los récords no se mezclan si se agregan o se quitan canciones.
;
;   $A000  "GBBR"          marca
;   $A004  versión (1)
;   $A005  cantidad de récords (2 bytes)
;   $A007  suma de verificación de la región de récords (2 bytes: suma de todos sus bytes)
;   $A009  últimas iniciales usadas (3 bytes)
;   $A010  récords de 10 bytes: hash (2), clave = instrumento * 4 + dificultad (1), puntaje en BCD de 6 dígitos (3),
;          iniciales (3), estrellas (1)
;
; Si la marca o la suma no coinciden (RAM nueva o dañada) la tabla se borra y se empieza vacía.
; Hay lugar para 817 récords: de sobra para 32 canciones x 4 instrumentos x 4 dificultades = 512.
; =============================================================================

SECTION "Records", ROM0

DEF SRAM_HEADER   EQU _SRAM
DEF SRAM_VERSION  EQU _SRAM + 4
DEF SRAM_COUNT    EQU _SRAM + 5
DEF SRAM_SUM      EQU _SRAM + 7
DEF SRAM_INITIALS EQU _SRAM + 9
DEF SRAM_RECORDS  EQU _SRAM + $10
DEF SRAM_ENTRY    EQU 10
DEF SRAM_MAX      EQU (8192 - $10) / SRAM_ENTRY
DEF SRAM_LAST     EQU _SRAM + 8192

SramMagic: db "GBBR", 1
TxtRecordLbl: db "RECORD ", 0
TxtNewRecord: db "NUEVO RECORD", 0
TxtInitials:  db "ESCRIBE TUS INICIALES", 0
TxtInitHelp1: db "ARRIBA/ABAJO: LETRA", 0
TxtInitHelp2: db "A O START: LISTO", 0

SramEnable:
    ld a, RAMG_ENABLE
    ld [rRAMG], a
    xor a
    ld [rRAMB], a
    ret

SramDisable:
    xor a
    ld [rRAMG], a
    ret

; Al arrancar: revisa la marca y la suma; si no coinciden, borra la tabla
SramInit:
    call SramEnable
    ld hl, SramMagic
    ld de, SRAM_HEADER
    ld b, 5
.magic:
    ld a, [de]
    cp [hl]
    jr nz, .format
    inc hl
    inc de
    dec b
    jr nz, .magic
    call SramSum            ; DE = suma de la región
    ld a, [SRAM_SUM]
    cp e
    jr nz, .format
    ld a, [SRAM_SUM + 1]
    cp d
    jp z, SramDisable
.format:
    ld hl, SRAM_HEADER
    ld bc, 8192
    xor a
    call FillMem
    ld hl, SramMagic
    ld de, SRAM_HEADER
    ld bc, 5
    call CopyMemRev
    ld a, 'A'
    ld hl, SRAM_INITIALS
    ld [hl+], a
    ld [hl+], a
    ld [hl], a
    jp SramDisable

; HL <- BC bytes de DE... (CopyMem copia de DE a HL; aquí el origen es HL y el destino DE)
CopyMemRev:
.loop:
    ld a, [hl+]
    ld [de], a
    inc de
    dec bc
    ld a, b
    or c
    jr nz, .loop
    ret

; DE = suma de los bytes de la región de récords
SramSum:
    ld hl, SRAM_RECORDS
    ld de, 0
.loop:
    ld a, [hl+]
    add e
    ld e, a
    jr nc, .noCarry
    inc d
.noCarry:
    ld a, h
    cp HIGH(SRAM_LAST)
    jr nz, .loop
    ret

; DE = suma de los 10 bytes de la entrada en HL (conserva HL)
SramEntrySum:
    push hl
    ld de, 0
    ld b, SRAM_ENTRY
.loop:
    ld a, [hl+]
    add e
    ld e, a
    jr nc, .noCarry
    inc d
.noCarry:
    dec b
    jr nz, .loop
    pop hl
    ret

; Hash de 16 bits del título y el juego de la canción elegida (wTitleBuf y wGameBuf van seguidos):
; por cada byte, h = rotar_izquierda_1(h + byte)
ComputeSongHash:
    ld hl, wTitleBuf
    ld de, 0                ; DE = hash
    ld b, SONG_TITLE_LEN + SONG_GAME_LEN
.byte:
    ld a, [hl+]
    add e
    ld e, a
    jr nc, .added
    inc d
.added:
    sla e
    rl d
    jr nc, .rotated
    set 0, e
.rotated:
    dec b
    jr nz, .byte
    ld a, e
    ld [wRecHash], a
    ld a, d
    ld [wRecHash + 1], a
    ret

; Clave del récord de lo elegido en el menú
ComputeRecordKey:
    ld a, [wInstrument]
    add a
    add a
    ld b, a
    ld a, [wDifficulty]
    add b
    ld [wRecKey], a
    ret

; Carry = 1 si hay récord (wRecHash, wRecKey); HL = su entrada. (La SRAM debe estar habilitada.)
SramFind:
    ld hl, SRAM_RECORDS
    ld a, [SRAM_COUNT]
    ld c, a
    ld a, [SRAM_COUNT + 1]
    ld b, a
    or c
    jr z, .none
.loop:
    push hl
    ld a, [wRecHash]
    cp [hl]
    jr nz, .no
    inc hl
    ld a, [wRecHash + 1]
    cp [hl]
    jr nz, .no
    inc hl
    ld a, [wRecKey]
    cp [hl]
    jr nz, .no
    pop hl
    scf
    ret
.no:
    pop hl
    ld de, SRAM_ENTRY
    add hl, de
    dec bc
    ld a, b
    or c
    jr nz, .loop
.none:
    and a
    ret

; Lee el récord de lo elegido: wRecFound, wRecScore (3 bytes BCD), wRecInit (3) y wRecStars
SramLoadRecord:
    call ComputeRecordKey
    xor a
    ld [wRecFound], a
    call SramEnable
    call SramFind
    jp nc, SramDisable
    inc hl
    inc hl
    inc hl
    ld de, wRecScore
    ld b, 7
.copy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .copy
    ld a, 1
    ld [wRecFound], a
    jp SramDisable

; wScoreDigits (6 dígitos, uno por byte) -> wNewScore (3 bytes BCD)
PackScore:
    ld hl, wScoreDigits
    ld de, wNewScore
    ld b, 3
.pair:
    ld a, [hl+]
    swap a
    ld c, a
    ld a, [hl+]
    or c
    ld [de], a
    inc de
    dec b
    jr nz, .pair
    ret

; Carry = 1 si wNewScore es mayor que wRecScore
NewScoreIsHigher:
    ld hl, wNewScore
    ld de, wRecScore
    ld b, 3
.cmp:
    ld a, [de]
    cp [hl]
    jr c, .higher           ; el guardado es menor
    ret nz                  ; mayor: no es récord (carry = 0)
    inc hl
    inc de
    dec b
    jr nz, .cmp
    and a                   ; iguales: tampoco
    ret
.higher:
    scf
    ret

; Decide si la partida que acaba de terminar es récord: sin perder, sin "sin fallo", sin opciones y con más puntaje
CheckNewRecord:
    xor a
    ld [wNewRecord], a
    ld a, [wFailed]
    ld b, a
    ld a, [wNoFail]
    or b
    ld b, a
    ld a, [wOptionsUsed]
    or b
    ld b, a
    ld a, [wVsCut]          ; VS cortado porque alguien perdió: la canción no se terminó
    or b
    ret nz
    call PackScore
    call SramLoadRecord
    ld a, [wRecFound]
    and a
    jr z, .isNew
    call NewScoreIsHigher
    ret nc
.isNew:
    ld a, 1
    ld [wNewRecord], a
    ret

; Guarda wNewScore con wInitials y wStars como récord de lo elegido
SramSaveRecord:
    call ComputeRecordKey
    call SramEnable
    call SramFind
    jr c, .have
    ld hl, SRAM_COUNT       ; récord nuevo: va al final de la tabla
    ld a, [hl+]
    ld c, a
    ld b, [hl]
    ld hl, SRAM_RECORDS
    ld de, SRAM_ENTRY
    ld a, b
    or c
    jr z, .atEnd
    push bc
.skip:
    add hl, de
    dec bc
    ld a, b
    or c
    jr nz, .skip
    pop bc
.atEnd:
    inc bc
    ld a, c
    ld [SRAM_COUNT], a
    ld a, b
    ld [SRAM_COUNT + 1], a
    push hl
    ld b, SRAM_ENTRY        ; la entrada nueva se parte de ceros (la suma vieja de esa entrada es 0)
    xor a
.zero:
    ld [hl+], a
    dec b
    jr nz, .zero
    pop hl
.have:
    call SramEntrySum       ; DE = suma vieja; se resta de la suma total
    ld a, [SRAM_SUM]
    sub e
    ld [SRAM_SUM], a
    ld a, [SRAM_SUM + 1]
    sbc d
    ld [SRAM_SUM + 1], a
    ld a, [wRecHash]
    ld [hl+], a
    ld a, [wRecHash + 1]
    ld [hl+], a
    ld a, [wRecKey]
    ld [hl+], a
    ld de, wNewScore
    ld b, 3
.score:
    ld a, [de]
    ld [hl+], a
    inc de
    dec b
    jr nz, .score
    ld de, wInitials
    ld b, 3
.init:
    ld a, [de]
    ld [hl+], a
    inc de
    dec b
    jr nz, .init
    ld a, [wStars]
    ld [hl], a
    ld de, -9
    add hl, de              ; de vuelta al inicio de la entrada
    call SramEntrySum       ; suma nueva
    ld a, [SRAM_SUM]
    add e
    ld [SRAM_SUM], a
    ld a, [SRAM_SUM + 1]
    adc d
    ld [SRAM_SUM + 1], a
    ld hl, wInitials        ; y las iniciales quedan como las últimas usadas
    ld de, SRAM_INITIALS
    ld bc, 3
    call CopyMemRev
    jp SramDisable

; ---- Récord en el menú ---------------------------------------------------------------------------
; Arma en wRecText (20 caracteres) "RECORD 029920 ABC 5*" o "RECORD ---"
FormatRecord:
    ld hl, wRecText
    ld b, 20
    ld a, ' '
.blank:
    ld [hl+], a
    dec b
    jr nz, .blank
    ld hl, wRecText
    ld de, TxtRecordLbl
    ld b, 7
.label:
    ld a, [de]
    inc de
    ld [hl+], a
    dec b
    jr nz, .label
    ld a, [wRecFound]
    and a
    jr nz, .found
    ld a, '-'
    ld [hl+], a
    ld [hl+], a
    ld [hl], a
    ret
.found:
    ld de, wRecScore
    ld b, 3
.digits:
    ld a, [de]
    inc de
    ld c, a
    swap a
    and $0F
    add '0'
    ld [hl+], a
    ld a, c
    and $0F
    add '0'
    ld [hl+], a
    dec b
    jr nz, .digits
    inc hl
    ld de, wRecInit
    ld b, 3
.init:
    ld a, [de]
    inc de
    ld [hl+], a
    dec b
    jr nz, .init
    inc hl
    ld a, [wRecStars]
    add '0'
    ld [hl+], a
    ld a, '*'
    ld [hl], a
    ret

; Lee el récord de la selección actual y lo escribe en el menú
RefreshRecord:
    call SramLoadRecord
    call FormatRecord
    ld hl, wRecText
    ld b, 20
    ld c, MENU_ROW_RECORD
    ld e, 0
    jp QueueMenuAt

; ---- Pantalla de iniciales -----------------------------------------------------------------------
EnterInitials:
    call BeginTextScreen
    ld de, _SCRN0 + 32 * 3 + 4
    ld hl, TxtNewRecord
    call PrintStr
    ld de, _SCRN0 + 32 * 5 + 0
    ld hl, TxtInitials
    call PrintStr
    ld de, _SCRN0 + 32 * 13 + 1
    ld hl, TxtInitHelp1
    call PrintStr
    ld de, _SCRN0 + 32 * 14 + 1
    ld hl, TxtInitHelp2
    call PrintStr
    call SramEnable
    ld hl, SRAM_INITIALS    ; arranca con las últimas iniciales
    ld de, wInitials
    ld bc, 3
    call CopyMemRev
    call SramDisable
    xor a
    ld [wInitPos], a
    ld a, STATE_INITIALS
    ld [wState], a
    call EndTextScreen
    jp QueueInitials

; Las tres letras y el cursor debajo de la letra elegida
QueueInitials:
    ld hl, wInitBuf
    ld a, [wInitials]
    ld [hl+], a
    ld a, ' '
    ld [hl+], a
    ld a, [wInitials + 1]
    ld [hl+], a
    ld a, ' '
    ld [hl+], a
    ld a, [wInitials + 2]
    ld [hl], a
    ld hl, wInitBuf
    ld b, 5
    ld c, 8
    ld e, 7
    call QueueMenuAt
    ld hl, wInitBuf         ; cursor: 5 caracteres con una "^" bajo la letra elegida
    ld a, ' '
    ld b, 5
.blank:
    ld [hl+], a
    dec b
    jr nz, .blank
    ld a, [wInitPos]
    add a
    ld e, a
    ld d, 0
    ld hl, wInitBuf
    add hl, de
    ld [hl], '^'
    ld hl, wInitBuf
    ld b, 5
    ld c, 9
    ld e, 7
    jp QueueMenuAt

InitialsFrame:
    di
    ldh a, [hPadNew]
    ld b, a
    xor a
    ldh [hPadNew], a
    ei
    bit PADB_START, b
    jr nz, .done
    bit PADB_A, b
    jr nz, .done
    ld a, [wInitPos]
    ld e, a
    ld d, 0
    ld hl, wInitials
    add hl, de
    bit PADB_UP, b
    jr z, .notUp
    ld a, [hl]
    inc a
    cp 'Z' + 1
    jr c, .store
    ld a, 'A'
    jr .store
.notUp:
    bit PADB_DOWN, b
    jr z, .notDown
    ld a, [hl]
    dec a
    cp 'A'
    jr nc, .store
    ld a, 'Z'
    jr .store
.notDown:
    ld a, [wInitPos]
    bit PADB_RIGHT, b
    jr z, .notRight
    cp 2
    ret nc
    inc a
    ld [wInitPos], a
    jp QueueInitials
.notRight:
    bit PADB_LEFT, b
    ret z
    and a
    ret z
    dec a
    ld [wInitPos], a
    jp QueueInitials
.store:
    ld [hl], a
    jp QueueInitials
.done:
    call SramSaveRecord
    jp EnterMenu
