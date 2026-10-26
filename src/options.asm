; =============================================================================
; options.asm - Pantalla de opciones (Select en el menú)
;
; Seis renglones: espejo, velocidad, caída de notas, práctica, inicio de la práctica y efecto al fallar. Los valores
; viven seguidos en wOpt (el renglón indexa), se quedan hasta apagar la consola y valen para todas las canciones.
; Con cualquier opción distinta de la normal (menos el efecto al fallar) no se guardan récords.
; =============================================================================

SECTION "Options", ROM0

DEF OPT_COUNT EQU 6
DEF OPT_ROW0  EQU 4            ; fila de pantalla del primer renglón (cada uno ocupa 2 filas)
DEF OPT_VALUE_COL EQU 11
DEF OPT_VALUE_LEN EQU 9

; Un texto de 9 caracteres con espacios y 16 bytes de paso (el valor indexa con swap)
MACRO OptVal
    db \1
    ds OPT_VALUE_LEN - STRLEN(\1), $20
    ds 16 - OPT_VALUE_LEN, 0
ENDM

TxtOptions: db "OPCIONES", 0
TxtOptBack: db "B: VOLVER", 0

OptLabels:
    OptVal "ESPEJO"
    OptVal "VELOCIDAD"
    OptVal "CAIDA"
    OptVal "PRACTICA"
    OptVal "INICIO"
    OptVal "AL FALLAR"

OptCount: db 2, 4, 5, 5, 4, 3

OptTables: dw OptMirror, OptSpeed, OptFall, OptPractice, OptStart, OptFx

OptMirror:
    OptVal "NO"
    OptVal "SI"
OptSpeed:
    OptVal "100%"
    OptVal "75%"
    OptVal "50%"
    OptVal "125%"
OptFall:
    OptVal "AUTO"
    OptVal "FACIL"
    OptVal "MEDIO"
    OptVal "DIFICIL"
    OptVal "EXPERTO"
OptPractice:
    OptVal "NO"
    OptVal "HASTA 1/4"
    OptVal "HASTA 1/2"
    OptVal "HASTA 3/4"
    OptVal "FINAL"
OptStart:
    OptVal "PRINCIPIO"
    OptVal "1/4"
    OptVal "1/2"
    OptVal "3/4"
OptFx:
    OptVal "SI"
    OptVal "SOLO SON."
    OptVal "NO"

EnterOptions:
    call BeginTextScreen
    ld de, _SCRN0 + 32 * 1 + 6
    ld hl, TxtOptions
    call PrintStr
    ld de, _SCRN0 + 32 * 17 + 1
    ld hl, TxtOptBack
    call PrintStr
    ld b, 0
.labels:
    push bc
    ld a, b
    add a
    add OPT_ROW0
    ld c, a
    ld e, 1
    call MenuDest           ; DE = dirección en el mapa (el LCD está apagado: se escribe directo)
    ld a, b
    swap a
    ld c, a
    ld b, 0
    ld hl, OptLabels
    add hl, bc
    call PrintStr
    pop bc
    inc b
    ld a, b
    cp OPT_COUNT
    jr nz, .labels
    ld a, STATE_OPTIONS
    ld [wState], a
    call EndTextScreen
    ld b, 0
.values:
    push bc
    ld a, b
    call QueueOptValue
    pop bc
    inc b
    ld a, b
    cp OPT_COUNT
    jr nz, .values
    jp QueueOptCursor

; A = renglón: encola el texto de su valor
QueueOptValue:
    ld b, a
    ld e, a
    ld d, 0
    ld hl, wOpt
    add hl, de
    ld a, [hl]
    ld c, a                 ; C = valor
    ld a, b
    add a
    ld e, a
    ld hl, OptTables
    add hl, de
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld a, c
    swap a
    ld e, a
    ld d, 0
    add hl, de
    ld a, b
    add a
    add OPT_ROW0
    ld c, a                 ; C = fila de pantalla
    ld e, OPT_VALUE_COL
    ld b, OPT_VALUE_LEN
    jp QueueMenuAt

; El ">" del renglón elegido
QueueOptCursor:
    ld b, 0
.row:
    push bc
    ld a, b
    add a
    add OPT_ROW0
    ld c, a
    ld a, [wOptRow]
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
    cp OPT_COUNT
    jr nz, .row
    ret

OptionsFrame:
    di
    ldh a, [hPadNew]
    ld b, a
    xor a
    ldh [hPadNew], a
    ei
    ld a, b
    and (1 << PADB_B) | (1 << PADB_START) | (1 << PADB_SELECT)
    jp nz, EnterMenu
    bit PADB_DOWN, b
    jr z, .notDown
    ld a, [wOptRow]
    cp OPT_COUNT - 1
    ret nc
    inc a
    ld [wOptRow], a
    jp QueueOptCursor
.notDown:
    bit PADB_UP, b
    jr z, .notUp
    ld a, [wOptRow]
    and a
    ret z
    dec a
    ld [wOptRow], a
    jp QueueOptCursor
.notUp:
    ld c, 1
    bit PADB_RIGHT, b
    jr nz, .change
    ld c, $FF
    bit PADB_LEFT, b
    ret z
.change:
    ld a, [wOptRow]
    ld e, a
    ld d, 0
    ld hl, OptCount
    add hl, de
    ld b, [hl]              ; B = cuántos valores tiene
    ld hl, wOpt
    add hl, de
    ld a, [hl]
    add c
    cp b
    ret nc                  ; (también atrapa el -1 desde 0)
    ld [hl], a
    ld a, [wOptRow]
    jp QueueOptValue
