; =============================================================================
; scene.asm - Dibujo de los mapas con el LCD apagado: escenario, textos y paletas
; =============================================================================

SECTION "Scene", ROM0

; Limpia los dos mapas ($9800-$9FFF), y en CGB también sus atributos (banco 1 de VRAM)
ClearMaps:
    ld hl, _SCRN0
    ld bc, $0800
    xor a
    call FillMem
    ldh a, [hCGB]
    and a
    ret z
    ld a, 1
    ldh [rVBK], a
    ld hl, _SCRN0
    ld bc, $0800
    xor a
    call FillMem
    xor a
    ldh [rVBK], a
    ret

; Dibuja las 32 filas del escenario y los carriles en el mapa $9800. El escenario se repite cada 4 filas,
; así que al dar la vuelta el fondo (32 filas) no se nota el corte.
StageDraw:
    ld hl, _SCRN0
    ld b, 0                 ; fila
.row:
    push bc
    ld a, b
    and 3
    add TILE_PANEL
    ld c, a                 ; C = tile del panel de esta fila
    ld a, TILE_FRAME
    ld [hl+], a             ; columna 0
    ld a, c
    ld [hl+], a             ; 1-3
    ld [hl+], a
    ld [hl+], a
    ld a, TILE_EDGE_L
    ld [hl+], a             ; 4
    ld d, NUM_LANES
.lane:
    ld a, TILE_LANE_L
    ld [hl+], a
    ld a, TILE_LANE_R
    ld [hl+], a
    dec d
    jr nz, .lane
    ld a, TILE_EDGE_R
    ld [hl+], a             ; 15
    ld a, c
    ld [hl+], a             ; 16-18
    ld [hl+], a
    ld [hl+], a
    ld a, TILE_FRAME
    ld [hl+], a             ; 19
    ld de, 12               ; columnas 20-31 (fuera de pantalla)
    add hl, de
    pop bc
    inc b
    ld a, b
    cp 32
    jr nz, .row
    ret

; Paletas de la CGB (BGR555): 0 = escenario y texto; 1 a 5 = verde, rojo, amarillo, azul, naranja
CgbBgPalettes:
    dw $1842, $414A, $6252, $7FFF
    dw $1842, $11C4, $2306, $7FFF
    dw $1842, $0C6E, $18DC, $7FFF
    dw $1842, $098E, $0F7F, $7FFF
    dw $1842, $38C3, $7186, $7FFF
    dw $1842, $04EE, $0A1F, $7FFF
    dw $1842, $414A, $6252, $7FFF
    dw $1842, $414A, $6252, $7FFF
CgbBgPalettesEnd:

; Sprites: los aros usan los colores de su carril (paleta 0 a 4)
CgbObjPalettes:
    dw $1842, $11C4, $2306, $7FFF
    dw $1842, $0C6E, $18DC, $7FFF
    dw $1842, $098E, $0F7F, $7FFF
    dw $1842, $38C3, $7186, $7FFF
    dw $1842, $04EE, $0A1F, $7FFF
    dw $1842, $414A, $6252, $7FFF
    dw $1842, $414A, $6252, $7FFF
    dw $1842, $6B5A, $7BDE, $7FFF          ; 7: el medidor estelar mientras el poder está activo
CgbObjPalettesEnd:

LoadPalettes:
    ld a, %11100100
    ldh [rBGP], a
    ldh [rOBP0], a
    ldh [rOBP1], a
    ldh a, [hCGB]
    and a
    ret z
    ld a, $80               ; índice 0 con autoincremento
    ldh [rBCPS], a
    ld hl, CgbBgPalettes
    ld b, CgbBgPalettesEnd - CgbBgPalettes
.bg:
    ld a, [hl+]
    ldh [rBCPD], a
    dec b
    jr nz, .bg
    ld a, $80
    ldh [rOCPS], a
    ld hl, CgbObjPalettes
    ld b, CgbObjPalettesEnd - CgbObjPalettes
.obj:
    ld a, [hl+]
    ldh [rOCPD], a
    dec b
    jr nz, .obj
    ret
