; =============================================================================
; main.asm - GBBand, fase 1: ROM "hola mundo"
;
; Comprueba lo que el resto del juego necesita: header MBC5+RAM+BATTERY y compatible con CGB, detección
; de DMG/CGB, ISR de VBlank con contador de cuadros, cambio de banco de ROM (1 y 127), SRAM con batería
; y texto con la fuente de 8x8 (el número de tile es el código ASCII).
; =============================================================================

INCLUDE "hardware.inc"

; ---- HRAM: variables de acceso rápido --------------------------------------
SECTION "HRAM", HRAM
hIsCGB::  ds 1      ; valor de A al arrancar: $11 en Game Boy Color; en DMG es otro ($01 en la DMG original)
hFrame::  ds 2      ; cuadros desde el arranque (16 bits, lo incrementa la ISR de VBlank)
hBank::   ds 1      ; banco de ROM conmutable actual

; ---- Vectores de reinicio e interrupciones ----------------------------------
SECTION "Vectores", ROM0[$0000]
    ds $40, $FF                 ; rst $00 a $38 sin usar

SECTION "Vec VBlank", ROM0[$0040]
    jp VBlankISR
    ds $08 - 3, $FF

SECTION "Vec STAT", ROM0[$0048]
    reti
    ds $08 - 1, $FF

SECTION "Vec Timer", ROM0[$0050]
    reti
    ds $08 - 1, $FF

SECTION "Vec Serie", ROM0[$0058]
    reti
    ds $08 - 1, $FF

SECTION "Vec Control", ROM0[$0060]
    reti
    ds $08 - 1, $FF

; ---- Header: rgbfix completa logo, título, tipo de cartucho y sumas ----------
SECTION "Header", ROM0[$0100]
    nop
    jp Start
    ds $0150 - @, $00

; ---- Arranque ---------------------------------------------------------------
SECTION "Arranque", ROM0[$0150]
Start:
    ldh [hIsCGB], a             ; A vale $11 al arrancar en CGB: guardarlo antes de tocar A
    di
    ld sp, $E000                ; pila al final de la WRAM

    ; Apagar el LCD solo durante VBlank (hacerlo en otro momento puede dañar una DMG)
.waitVBlank:
    ldh a, [rLY]
    cp 144
    jr c, .waitVBlank
    xor a
    ldh [rLCDC], a

    ; Limpiar la VRAM ($8000-$9FFF)
    ld hl, _VRAM
    ld bc, $2000
    xor a
    call FillMem

    ; Cargar la fuente: el tile N es el carácter ASCII N
    ld hl, _VRAM
    ld de, FontTiles
    ld bc, FontTilesEnd - FontTiles
    call CopyMem

    ; Paletas
    ld a, %11100100
    ldh [rBGP], a
    ldh a, [hIsCGB]
    cp BOOT_A_CGB
    jr nz, .noCgbPalette
    ld a, $80                   ; índice 0, autoincremento
    ldh [rBCPS], a
    ld hl, CgbPalette
    ld b, CgbPaletteEnd - CgbPalette
.palLoop:
    ld a, [hl+]
    ldh [rBCPD], a
    dec b
    jr nz, .palLoop
.noCgbPalette:

    ; Textos: rutinas en ROM0 leen cadenas de ROM0, del banco 1 y del banco 127
    ld de, _SCRN0 + 32 * 3 + 6
    ld hl, TxtTitulo
    call PrintStr

    ld de, _SCRN0 + 32 * 5 + 5
    ld hl, TxtHola
    call PrintStr

    ld de, _SCRN0 + 32 * 7 + 6
    ldh a, [hIsCGB]
    cp BOOT_A_CGB
    ld hl, TxtModoCgb
    jr z, .printModo
    ld hl, TxtModoDmg
.printModo:
    call PrintStr

    ; Banco 1 (primer banco conmutable)
    ld a, 1
    call SwitchBank
    ld de, _SCRN0 + 32 * 9 + 4
    ld hl, $4000
    call PrintStr

    ; Banco 127 (el último de los 2 MB)
    ld a, 127
    call SwitchBank
    ld de, _SCRN0 + 32 * 10 + 4
    ld hl, $4000
    call PrintStr

    ; SRAM con batería: escribir y leer de vuelta un valor
    ld a, RAMG_ENABLE
    ld [rRAMG], a
    xor a
    ld [rRAMB], a
    ld a, $5A
    ld [_SRAM], a
    ld a, [_SRAM]
    cp $5A
    ld hl, TxtSramOk
    jr z, .sramPrint
    ld hl, TxtSramFalla
.sramPrint:
    xor a
    ld [rRAMG], a               ; deshabilitar la SRAM de nuevo
    ld de, _SCRN0 + 32 * 12 + 6
    call PrintStr

    ; Encender: fondo, tiles en modo $8000, mapa $9800
    ld a, IEF_VBLANK
    ldh [rIE], a
    xor a
    ldh [hFrame], a
    ldh [hFrame + 1], a
    ldh [rIF], a
    ld a, LCDCF_ON | LCDCF_BG8000 | LCDCF_BGON
    ldh [rLCDC], a
    ei

MainLoop:
    halt                        ; esperar la siguiente interrupción (VBlank)
    nop                         ; (el nop después de halt evita un fallo conocido del hardware)
    jr MainLoop

; ---- ISR de VBlank ----------------------------------------------------------
VBlankISR:
    push af
    ldh a, [hFrame]
    inc a
    ldh [hFrame], a
    jr nz, .done
    ldh a, [hFrame + 1]
    inc a
    ldh [hFrame + 1], a
.done:
    pop af
    reti

; ---- Rutinas ----------------------------------------------------------------

; Cambia el banco de ROM conmutable ($4000-$7FFF). A = banco (0 a 255; el bit 8 queda en 0).
SwitchBank:
    ldh [hBank], a
    ld [rROMB0], a
    xor a
    ld [rROMB1], a
    ret

; Rellena BC bytes desde HL con A.
FillMem:
    ld d, a
.loop:
    ld a, d
    ld [hl+], a
    dec bc
    ld a, b
    or c
    jr nz, .loop
    ret

; Copia BC bytes de DE a HL.
CopyMem:
.loop:
    ld a, [de]
    inc de
    ld [hl+], a
    dec bc
    ld a, b
    or c
    jr nz, .loop
    ret

; Escribe la cadena terminada en 0 de HL en la dirección DE (sin esperar al LCD: solo con el LCD apagado).
PrintStr:
.loop:
    ld a, [hl+]
    and a
    ret z
    ld [de], a
    inc de
    jr .loop

; ---- Datos en ROM0 ----------------------------------------------------------
SECTION "Datos ROM0", ROM0
TxtTitulo:    db "GBBAND", 0
TxtHola:      db "HOLA MUNDO", 0
TxtModoDmg:   db "MODO DMG", 0
TxtModoCgb:   db "MODO CGB", 0
TxtSramOk:    db "SRAM OK", 0
TxtSramFalla: db "SRAM FALLA", 0

; Paleta 0 de la CGB (4 colores de 15 bits, BGR555 little-endian): blanco, gris claro, gris oscuro, negro
CgbPalette:
    dw $7FFF, $5EF7, $294A, $0000
CgbPaletteEnd:

FontTiles:
    INCBIN "chr/font.2bpp"
FontTilesEnd:

; ---- Mensajes en bancos conmutables (prueban el MBC5) -----------------------
SECTION "Mensaje banco 1", ROMX[$4000], BANK[1]
    db "BANCO 1 OK", 0

SECTION "Mensaje banco 127", ROMX[$4000], BANK[127]
    db "BANCO 127 OK", 0
