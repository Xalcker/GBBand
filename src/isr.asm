; =============================================================================
; isr.asm - Interrupción de VBlank, cola de VRAM y lectura del control
;
; Reglas: main_loop calcula y deja datos en buffers; la ISR solo copia. La ISR NUNCA cambia de banco de ROM
; (todo lo que lee es WRAM o código de ROM0). Orden fijo: OAM, cola de VRAM, scroll y LCDC, audio, control, contador
; de cuadros. (El audio va después de lo que debe caber en el VBlank: ver docs/decisiones.md.)
; =============================================================================

SECTION "VBlank ISR", ROM0

VBlankISR:
    push af
    push bc
    push de
    push hl
    ldh a, [rDIV]
    ldh [hIsrT0], a

    ldh a, [hMainBusy]
    and a
    jr nz, .late

    ; 0. tinte rojo del fallo (solo al empezar y al terminar)
    ldh a, [hPalFx]
    and a
    call nz, ApplyPalFx

    ld a, [wLampReq]
    and a
    call nz, ApplyLampPal

    ; 1. OAM: DMA completo (160 M) solo cuando cambió algo (aros, medidores)
    ld a, [wOamDirty]
    and a
    jr z, .noOam
    xor a
    ld [wOamDirty], a
    call hOamDma
.noOam:    ; 2. cola de VRAM
    call FlushVQueue

    ; 3. scroll y LCDC
    ldh a, [hScy]
    ldh [rSCY], a
    ldh a, [hScx]
    ldh [rSCX], a
    ldh a, [hLcdc]
    ldh [rLCDC], a
    ldh a, [hWy]
    ldh [rWY], a
    ; ¿terminamos dentro del VBlank? (LY 144-153). Si LY ya dio la vuelta, las escrituras de arriba pudieron perderse.
    ldh a, [rLY]
    cp 144
    jr nc, .inVBlank
    ld hl, wOverrun
    inc [hl]
    jr .audio
.inVBlank:
    sub 144
    ld hl, wFlushLines
    cp [hl]
    jr c, .audio
    ld [hl], a
.audio:
    ; 4. audio. Va DESPUÉS de lo que escribe en VRAM/OAM: eso tiene que caber en el VBlank y el audio no (en los
    ;    cuadros donde entran los cuatro canales a la vez tarda hasta ~400 M). La música se atrasa unas decenas
    ;    de microsegundos según el tamaño de la cola, imperceptible.
    call AudioSteps
    jr .common
.late:
    ; main_loop no terminó: no se copia nada a VRAM (podría estar a medias), pero el audio sigue
    ld a, [wLate]
    inc a
    jr z, .lateSaturated
    ld [wLate], a
.lateSaturated:
    call AudioSteps

.common:
    ; 5. control, una vez por cuadro (dos lecturas iguales)
    call ReadPad

    ; 6. contadores
    ld hl, hFrame
    inc [hl]
    jr nz, .frameDone
    inc hl
    inc [hl]
.frameDone:
    ld a, 1
    ldh [hVBlank], a

    ; tiempo que tardó la ISR (DIV cuenta cada 64 M-cycles)
    ldh a, [rDIV]
    ld b, a
    ldh a, [hIsrT0]
    ld c, a
    ld a, b
    sub c
    ld [wIsrLast], a
    ld hl, wIsrMax
    cp [hl]
    jr c, .noMax
    ld [hl], a
.noMax:
IsrEnd::                    ; (las pruebas enganchan aquí: el estado ya es el de un cuadro completo)
    pop hl
    pop de
    pop bc
    pop af
    reti

; ---- Cola de VRAM --------------------------------------------------------------------
; Vacía todas las entradas: [cuenta | $80 = banco 1][dir lo][dir hi][datos...]; un 0 marca el fin.
FlushVQueue:
    ld hl, wVQueue
    ld a, [wVQLen]
    ld [wQLast], a
    ld hl, wQMax
    cp [hl]
    jr c, .noQMax
    ld [hl], a
.noQMax:
    ld hl, wVQueue
.entry:
    ld a, [hl+]
    and a
    jr z, .done
    ld c, a                 ; C = encabezado
    and $7F
    ld b, a                 ; B = cuenta
    ld a, [hl+]
    ld e, a
    ld a, [hl+]
    ld d, a                 ; DE = destino
    bit 7, c
    jr z, .bank0
    ld a, 1
    ldh [rVBK], a
.bank0:
.copy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .copy
    bit 7, c
    jr z, .entry
    xor a
    ldh [rVBK], a
    jr .entry
.done:
    xor a
    ld [wVQueue], a
    ld [wVQLen], a
    ret

; VQAlloc: reserva una entrada en la cola.
;   in:  B = cuenta de bytes, C = $00 (banco 0) o $80 (banco 1), DE = destino en VRAM
;   out: HL = donde escribir los datos. Si la cola se llena, HL apunta a un buffer inofensivo (wVQDummy).
; Solo la usa el bucle principal.
VQAlloc:
    ld a, [wVQLen]
    add b
    jr c, .full
    add 5
    jr c, .full
    cp 250
    jr nc, .full
    ld a, [wVQLen]
    ld l, a
    ld h, HIGH(wVQueue)
    ld a, b
    or c
    ld [hl+], a
    ld a, e
    ld [hl+], a
    ld a, d
    ld [hl+], a
    ld a, [wVQLen]
    add 3
    add b
    ld [wVQLen], a
    ld a, l                 ; terminador justo después de los datos
    add b
    ld e, a
    ld d, HIGH(wVQueue)
    xor a
    ld [de], a
    ret
.full:
    ld hl, wQOverflow
    inc [hl]
    ld hl, wVQDummy
    ret

; ---- Control --------------------------------------------------------------------------
; hPad = botones apretados (activos en alto): bit 0 derecha, 1 izquierda, 2 arriba, 3 abajo,
; 4 A, 5 B, 6 Select, 7 Start. hPadNew acumula los que se apretaron (el bucle principal lo borra al leerlo).
ReadPad:
    ld d, 4                 ; hasta 4 intentos para que dos lecturas coincidan
.try:
    call ReadPadOnce
    ld e, a
    call ReadPadOnce
    cp e
    jr z, .stable
    dec d
    jr nz, .try
.stable:
    ld b, a                 ; B = estado nuevo
    ldh a, [hPad]
    cpl
    and b                   ; apretados ahora y no antes
    ld c, a
    ldh a, [hPadNew]
    or c
    ldh [hPadNew], a
    ld a, b
    ldh [hPad], a
    ret

ReadPadOnce:
    ld a, $20               ; selecciona la cruz (bit 4 en 0)
    ldh [rP1], a
    ldh a, [rP1]
    ldh a, [rP1]
    ldh a, [rP1]
    ldh a, [rP1]
    cpl
    and $0F
    ld b, a
    ld a, $10               ; selecciona los botones (bit 5 en 0)
    ldh [rP1], a
    ldh a, [rP1]
    ldh a, [rP1]
    ldh a, [rP1]
    ldh a, [rP1]
    cpl
    and $0F
    swap a
    or b
    ld b, a
    ld a, $30               ; deselecciona
    ldh [rP1], a
    ld a, b
    ret

; Rutina de OAM DMA: se copia a HRAM al arrancar (mientras corre el DMA solo se puede leer HRAM)
OamDmaCode:
    ld a, HIGH(wOam)
    ldh [rDMA], a
    ld a, 40
.wait:
    dec a
    jr nz, .wait
    ret
OamDmaCodeEnd:
