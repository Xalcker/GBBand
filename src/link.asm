; =============================================================================
; link.asm - Cable link: controlador serie, mensajes y pantalla de conexión (2 jugadores)
;
; Cada byte que cruza el cable es parte de un mensaje: el primero (el tipo) lleva el bit 7 en 1 y los datos van en 0
; (7 bits cada uno). $00 significa "nada que mandar" y $FF es lo que se lee cuando no hay nadie del otro lado: los dos
; se ignoran entre mensajes. Un mensaje se encola completo (LinkSend), así que sus bytes cruzan seguidos.
;
; El maestro (reloj interno, jugador 1) manda un byte por cuadro desde el bucle principal (LinkPoll). El esclavo (reloj
; externo) arma el siguiente byte en la ISR serie en cuanto llega uno, así siempre tiene algo listo cuando el maestro
; da el reloj. Los dos guardan lo que llega en wLinkIn y el bucle principal lo lee.
;
; Búsqueda: al entrar, cada consola espera como esclavo un rato al azar (LINK_LISTEN_MIN a +63 cuadros) y, si nadie la
; llamó, llama como maestro LINK_CALL cuadros. Mientras busca repite su saludo (MSG_HELLO). Quien recibe el saludo
; completo del otro queda conectado con el papel que tenía en ese momento.
;
; Las pruebas conectan dos PyBoy enganchándose a SerialSend, SerialArm, SerialGot y SerialOff (ver linkbridge.py).
; =============================================================================

DEF LINK_IDLE EQU $00
DEF MSG_HELLO EQU $81

DEF LINK_SEARCH EQU 0
DEF LINK_OK     EQU 1
DEF LINK_WRONG  EQU 2

DEF LINK_LISTEN_MIN EQU 30      ; cuadros esperando como esclavo: de 30 a 93 (al azar)
DEF LINK_CALL       EQU 24      ; cuadros llamando como maestro (el saludo del otro tarda a lo más 7)

DEF LINK_ROW_STATUS EQU 8

SECTION "Link", ROM0

; ---- ISR serie ----------------------------------------------------------------------------------------------------
; Terminó una transferencia: guarda el byte que llegó y, en el esclavo, arma el siguiente.
SerialISR:
    push af
    push bc
    push hl
    ldh a, [rSB]
SerialGot::                     ; (las pruebas se enganchan aquí: A = byte que llegó)
    ld b, a
    ldh a, [hLinkInW]
    ld l, a
    ld h, HIGH(wLinkIn)
    ld [hl], b
    inc a
    and $0F
    or LOW(wLinkIn)
    ldh [hLinkInW], a
    ldh a, [hLinkMaster]
    and a
    jr nz, .done
    ldh a, [hLinkOn]
    and a
    call nz, LinkArm
.done:
    pop hl
    pop bc
    pop af
    reti

; Esclavo: deja el siguiente byte en rSB y espera el reloj del otro. Usa A y HL.
LinkArm:
    call LinkNextOut
    ldh [rSB], a
SerialArm::                     ; (A = byte armado)
    ld a, $80
    ldh [rSC], a
    ret

; Maestro: manda el siguiente byte con el reloj interno. Usa A y HL.
LinkSendNext:
    call LinkNextOut
    ldh [rSB], a
SerialSend::                    ; (A = byte que sale)
    ld a, $81
    ldh [rSC], a
    ret

; Cancela la transferencia armada o en curso. Usa A.
LinkDisarm:
    xor a
    ldh [rSC], a
SerialOff::
    ret

; A = siguiente byte de wLinkOut, o LINK_IDLE si no hay nada. Usa HL.
LinkNextOut:
    ldh a, [hLinkOutW]
    ld l, a
    ldh a, [hLinkOutR]
    cp l
    ld a, LINK_IDLE
    ret z
    ldh a, [hLinkOutR]
    ld l, a
    ld h, HIGH(wLinkOut)
    inc a
    and $0F
    or LOW(wLinkOut)
    ldh [hLinkOutR], a
    ld a, [hl]
    ret

; Encola B bytes de HL (un mensaje completo). Usa A y DE.
LinkSend:
    ldh a, [hLinkOutW]
    ld e, a
    ld d, HIGH(wLinkOut)
.loop:
    ld a, [hl+]
    ld [de], a
    ld a, e
    inc a
    and $0F
    or LOW(wLinkOut)
    ld e, a
    dec b
    jr nz, .loop
    ld a, e                     ; se publica al final: la ISR nunca ve el mensaje a medias
    ldh [hLinkOutW], a
    ret

; Z = 1 si no queda nada por mandar
LinkOutEmpty:
    ldh a, [hLinkOutW]
    ld b, a
    ldh a, [hLinkOutR]
    cp b
    ret

; ---- Encender y apagar --------------------------------------------------------------------------------------------
; Deja el cable apagado: sin interrupción serie, sin transferencia y sin papel.
LinkStop:
    ldh a, [rIE]
    and ~IEF_SERIAL
    ldh [rIE], a
    xor a
    ldh [hLinkOn], a
    ldh [hLinkMaster], a
    jp LinkDisarm

; Vacía las colas y enciende la interrupción serie (todavía sin papel: ver LinkListen y LinkCall)
LinkReset:
    call LinkStop
    ld a, LOW(wLinkIn)
    ldh [hLinkInW], a
    ldh [hLinkInR], a
    ld a, LOW(wLinkOut)
    ldh [hLinkOutW], a
    ldh [hLinkOutR], a
    xor a
    ld [wLinkType], a
    ld [wLinkHeard], a
    ldh a, [rIF]
    and ~IEF_SERIAL
    ldh [rIF], a
    ldh a, [rIE]
    or IEF_SERIAL
    ldh [rIE], a
    ld a, 1
    ldh [hLinkOn], a
    ret

; Esclavo: espera el reloj del otro un rato al azar
LinkListen:
    di
    call LinkDisarm
    xor a
    ldh [hLinkMaster], a
    call LinkArm
    ei
    ldh a, [rDIV]
    ld b, a
    ldh a, [hFrame]
    xor b
    and 63
    add LINK_LISTEN_MIN
    ld [wLinkTimer], a
    ret

; Maestro: da el reloj (LinkPoll manda un byte por cuadro)
LinkCall:
    di
    call LinkDisarm
    ld a, 1
    ldh [hLinkMaster], a
    ei
    ld a, LINK_CALL
    ld [wLinkTimer], a
    ret

; ---- Una vez por cuadro -------------------------------------------------------------------------------------------
; El maestro manda el siguiente byte; luego se leen los que llegaron. Devuelve A = tipo del mensaje que se completó
; (sus datos en wLinkBuf) o 0 si no se completó ninguno; si se completa uno, los bytes que siguen esperan al otro cuadro.
LinkPoll:
    ldh a, [hLinkMaster]
    and a
    jr z, .read
    ldh a, [rSC]
    bit 7, a                    ; la anterior todavía no termina
    call z, LinkSendNext
.read:
    ldh a, [hLinkInW]
    ld b, a
    ldh a, [hLinkInR]
    cp b
    jr z, .none
    ld l, a
    ld h, HIGH(wLinkIn)
    inc a
    and $0F
    or LOW(wLinkIn)
    ldh [hLinkInR], a
    ld a, [hl]
    cp $FF
    jr z, .drop                 ; nadie del otro lado
    ld b, a
    ld a, 1
    ld [wLinkHeard], a
    bit 7, b
    jr z, .data
    ; tipo: empieza un mensaje (uno desconocido se tira)
    ld a, b
    sub MSG_HELLO
    cp LinkLensEnd - LinkLens
    jr nc, .drop
    ld a, b
    ld [wLinkType], a
    xor a
    ld [wLinkPos], a
    jr .read
.drop:
    xor a
    ld [wLinkType], a
    jr .read
.data:
    ld a, [wLinkType]
    and a
    jr z, .read                 ; "nada que mandar" o un dato suelto
    sub MSG_HELLO
    ld e, a
    ld d, 0
    ld hl, LinkLens
    add hl, de
    ld c, [hl]                  ; C = bytes de datos del mensaje
    ld a, [wLinkPos]
    ld e, a
    ld hl, wLinkBuf
    add hl, de
    ld [hl], b
    inc a
    ld [wLinkPos], a
    cp c
    jr c, .read
    ld a, [wLinkType]           ; completo
    ld b, a
    xor a
    ld [wLinkType], a
    ld a, b
    ret
.none:
    xor a
    ret

; Bytes de datos de cada tipo de mensaje, desde MSG_HELLO
LinkLens:
    db LINK_HELLO_LEN
LinkLensEnd:

HelloMsg:
    db MSG_HELLO, LINK_VERSION, SONG_LIST_HASH & $7F, (SONG_LIST_HASH >> 7) & $7F
HelloMsgEnd:

; ---- Pantalla de conexión -----------------------------------------------------------------------------------------
TxtLinkTitle:  db "2 JUGADORES", 0
TxtLinkVs:     db "VERSUS", 0
TxtLinkCoop:   db "BANDA (CO-OP)", 0
TxtLinkCancel: db "B: CANCELAR", 0

MACRO LINE20
    ASSERT STRLEN(\1) == 20, "Las líneas de estado miden 20 caracteres"
    db \1
ENDM
; Dos líneas de 20 caracteres por estado
LinkTxtSearch:
    LINE20 "  BUSCANDO AL OTRO  "
    LINE20 "     JUGADOR...     "
LinkTxtOk1:
    LINE20 "     CONECTADO      "
    LINE20 "  ERES EL JUGADOR 1 "
LinkTxtOk2:
    LINE20 "     CONECTADO      "
    LINE20 "  ERES EL JUGADOR 2 "
LinkTxtWrong:
    LINE20 "CANCIONES DISTINTAS "
    LINE20 "  EN LOS CARTUCHOS  "

EnterLink:
    call AudioStop              ; (calla el título)
    call BeginTextScreen
    ld de, _SCRN0 + 32 * 2 + 4
    ld hl, TxtLinkTitle
    call PrintStr
    ld a, [wPlayers]
    cp 2
    ld de, _SCRN0 + 32 * 4 + 7
    ld hl, TxtLinkVs
    jr nz, .mode
    ld de, _SCRN0 + 32 * 4 + 3
    ld hl, TxtLinkCoop
.mode:
    call PrintStr
    ld de, _SCRN0 + 32 * 16 + 4
    ld hl, TxtLinkCancel
    call PrintStr
    ld hl, LinkTxtSearch
    ld de, _SCRN0 + 32 * LINK_ROW_STATUS
    call .line
    ld de, _SCRN0 + 32 * (LINK_ROW_STATUS + 1)
    call .line
    xor a
    ld [wLinkState], a
    call LinkReset
    call LinkListen
    ld a, STATE_LINK
    ld [wState], a
    jp EndTextScreen
; copia 20 caracteres de HL a DE (LCD apagado)
.line:
    ld b, 20
.char:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .char
    ret

LinkFrame:
    di
    ldh a, [hPadNew]
    ld b, a
    xor a
    ldh [hPadNew], a
    ei
    bit PADB_B, b
    jr z, .noCancel
    call LinkStop
    ld a, 2
    call PlayMenuSfx            ; volver
    jp EnterTitle
.noCancel:
    ld a, [wLinkState]
    cp LINK_SEARCH
    jr nz, .poll
    ; buscando: siempre hay un saludo por mandar
    call LinkOutEmpty
    jr nz, .queued
    ld hl, HelloMsg
    ld b, HelloMsgEnd - HelloMsg
    call LinkSend
.queued:
    ; si llegó algo del otro lado se conserva el papel; si no, se cambia al acabar el tiempo
    ld hl, wLinkHeard
    ld a, [hl]
    and a
    ld [hl], 0
    jr nz, .poll
    ld hl, wLinkTimer
    dec [hl]
    jr nz, .poll
    ldh a, [hLinkMaster]
    and a
    jr nz, .toListen
    call LinkCall
    jr .poll
.toListen:
    call LinkListen
.poll:
    call LinkPoll
    cp MSG_HELLO
    ret nz
    ld a, [wLinkState]
    cp LINK_SEARCH
    ret nz                      ; (los saludos que quedaban en camino)
    ld hl, wLinkBuf
    ld de, wLinkPeer
    ld b, LINK_HELLO_LEN
.copy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .copy
    ; misma versión del protocolo y misma lista de canciones
    ld hl, HelloMsg + 1
    ld de, wLinkPeer
    ld b, LINK_HELLO_LEN
.cmp:
    ld a, [de]
    cp [hl]
    jr nz, .wrong
    inc hl
    inc de
    dec b
    jr nz, .cmp
    ld a, LINK_OK
    ld [wLinkState], a
    ldh a, [hLinkMaster]
    and a
    ld hl, LinkTxtOk1
    jr nz, LinkQueueStatus
    ld hl, LinkTxtOk2
    jr LinkQueueStatus
.wrong:
    ld a, LINK_WRONG
    ld [wLinkState], a
    ld hl, LinkTxtWrong
    ; (sigue en LinkQueueStatus)

; Encola las dos líneas de estado de HL
LinkQueueStatus:
    push hl
    ld b, 20
    ld de, _SCRN0 + 32 * LINK_ROW_STATUS
    call QueueRaw
    pop hl
    ld de, 20
    add hl, de
    ld b, 20
    ld de, _SCRN0 + 32 * (LINK_ROW_STATUS + 1)
    jp QueueRaw
