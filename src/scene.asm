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
    ld [hl+], a             ; columna 0: torre del escenario (marco, celosía y reflector)
    ld a, TILE_TRUSS
    ld [hl+], a
    ld [hl+], a
    call .lampTile
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
    call .lampTile
    ld [hl+], a             ; 16
    ld a, TILE_TRUSS
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
    jr StageAttrs

; A = tile del reflector de la fila B (uno cada dos filas, con su soporte entre ellos)
.lampTile:
    ld a, b
    and 1
    ld a, TILE_LAMP
    ret z
    ld a, TILE_STEM
    ret

; CGB: los atributos de las torres (paleta 6 y, en los reflectores, la 7 que cambia de color con cada tiempo)
StageAttrs:
    ldh a, [hCGB]
    and a
    ret z
    ld a, 1
    ldh [rVBK], a
    ld hl, _SCRN0
    ld b, 0
.arow:
    ld a, 6
    ld [hl+], a             ; 0-2
    ld [hl+], a
    ld [hl+], a
    ld a, b
    and 1
    ld a, 7
    jr z, .lamp0
    ld a, 6
.lamp0:
    ld [hl+], a             ; 3
    inc hl                  ; 4 a 15: fondo de los carriles (paleta 0)
    ld de, 11
    add hl, de
    ld a, b
    and 1
    ld a, 7
    jr z, .lamp1
    ld a, 6
.lamp1:
    ld [hl+], a             ; 16
    ld a, 6
    ld [hl+], a             ; 17-19
    ld [hl+], a
    ld [hl+], a
    ld de, 12
    add hl, de
    inc b
    ld a, b
    cp 32
    jr nz, .arow
    xor a
    ldh [rVBK], a
    ret

; Paletas de la CGB (BGR555): 0 = escenario y texto; 1 a 5 = verde, rojo, amarillo, azul, naranja
CgbBgPalettes:
    dw $1842, $414A, $6252, $7FFF
    dw $1842, $11C4, $2306, $7FFF
    dw $1842, $0C6E, $18DC, $7FFF
    dw $1842, $098E, $0F7F, $7FFF
    dw $1842, $38C3, $7186, $7FFF
    dw $1842, $04EE, $0A1F, $7FFF
    dw $1042, $5ED6, $3D8C, $0C21         ; 6: torres del escenario y público (acero)
    dw $1042, $211F, $0852, $0C21         ; 7: reflectores (cambian de color con cada tiempo)
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
