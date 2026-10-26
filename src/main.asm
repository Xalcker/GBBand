; =============================================================================
; main.asm - GBBand: header, vectores, arranque y bucle principal
;
; Un solo ensamblado: este archivo incluye al resto. Ver docs/diseno.md para el mapa de memoria.
; =============================================================================

INCLUDE "hardware.inc"
INCLUDE "constants.inc"
INCLUDE "song_format.inc"
INCLUDE "wram.asm"

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
    cp BOOT_A_CGB
    ld a, 0
    jr nz, .notCgb
    ld a, 1
.notCgb:
    ldh [hCGB], a
    di
    ld sp, $E000                ; pila en DF00-DFFF

    ; Apagar el LCD solo durante VBlank (hacerlo en otro momento puede dañar una DMG)
    call LcdOff

    ; Limpiar la WRAM (menos la pila) y las variables de HRAM
    ld hl, $C000
    ld bc, $1F00
    xor a
    call FillMem
    ldh [hFrame], a
    ldh [hFrame + 1], a
    ldh [hPad], a
    ldh [hPadNew], a
    ldh [hVBlank], a
    ldh [hMainBusy], a
    ldh [hScy], a

    ; Rutina de OAM DMA a HRAM
    ld hl, hOamDma
    ld de, OamDmaCode
    ld b, OamDmaCodeEnd - OamDmaCode
.copyDma:
    ld a, [de]
    inc de
    ld [hl+], a
    dec b
    jr nz, .copyDma

    ; VRAM (los dos bancos en CGB) y tiles
    ld hl, _VRAM
    ld bc, $2000
    xor a
    call FillMem
    ldh a, [hCGB]
    and a
    jr z, .tiles
    ld a, 1
    ldh [rVBK], a
    ld hl, _VRAM
    ld bc, $2000
    xor a
    call FillMem
    xor a
    ldh [rVBK], a
.tiles:
    ld hl, _VRAM
    ld de, Tiles
    ld bc, TilesEnd - Tiles
    call CopyMem

    call LoadPalettes

    xor a
    ldh [rWY], a
    ldh [rWX], a
    ldh [rSCX], a
    ld a, IEF_VBLANK
    ldh [rIE], a
    xor a
    ldh [rIF], a
    ld a, 3                     ; dificultad por omisión: experto
    ld [wDifficulty], a
    xor a
    ld [wSong], a
    ld [wInstrument], a
    ld [wMenuRow], a
    call SramInit
    call EnterTitle
    ei

MainLoop:
    di                          ; (sin carrera entre mirar el aviso y dormir)
    ldh a, [hVBlank]
    and a
    jr nz, .run
    halt                        ; con IME apagado, halt despierta con el VBlank pendiente sin atenderlo
    nop
    ei
    nop                         ; aquí se atiende la ISR
    jr MainLoop
.run:
    ei
    xor a
    ldh [hVBlank], a
    ld a, 1
    ldh [hMainBusy], a
    ld a, [wState]          ; despacho por la tabla de estados
    add a
    ld e, a
    ld d, 0
    ld hl, StateTable
    add hl, de
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld de, .done
    push de
    jp hl
.done:
    xor a
    ldh [hMainBusy], a
    jr MainLoop

; Un manejador por estado, en el orden de STATE_...
StateTable:
    dw TitleFrame, MenuFrame, PlayFrame, PauseFrame, ResultsFrame, InitialsFrame, OptionsFrame

; ---- Utilidades --------------------------------------------------------------

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

; Escribe la cadena terminada en 0 de HL en la dirección DE (solo con el LCD apagado).
PrintStr:
.loop:
    ld a, [hl+]
    and a
    ret z
    ld [de], a
    inc de
    jr .loop

INCLUDE "isr.asm"
INCLUDE "audio.asm"
INCLUDE "fx.asm"
INCLUDE "highway.asm"
INCLUDE "gameplay.asm"
INCLUDE "hud.asm"
INCLUDE "scene.asm"
INCLUDE "game.asm"
INCLUDE "options.asm"
INCLUDE "results.asm"
INCLUDE "records.asm"

; ---- Gráficos: todos los tiles juntos (build/chr/tiles.2bpp, ver `gbband build-gfx`) -----------------
SECTION "Tiles", ROM0
Tiles:
    INCBIN "chr/tiles.2bpp"
TilesEnd:

; ---- Canciones (bancos 16 en adelante): build/list.asm la genera `gbband list-songs` -------------------
INCLUDE "list.asm"

; ---- Fuerza el tamaño de 2 MB: un byte en el último banco ------------------------------------------
SECTION "Relleno banco 127", ROMX[$7FFF], BANK[127]
    db $FF
