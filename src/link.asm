; =============================================================================
; link.asm - Cable link: controlador serie, mensajes y pantalla de conexión (2 jugadores)
;
; Cada byte que cruza el cable es parte de un mensaje: el primero (el tipo) lleva el bit 7 en 1 y los datos van en 0
; (7 bits cada uno). $80 significa "nada que mandar" y $FF es lo que se lee cuando no hay nadie del otro lado: como
; llevan el bit 7, los dos cortan el mensaje que se estuviera recibiendo, así que si se pierde un byte el mensaje se
; tira en vez de completarse con basura. Un mensaje se encola completo (LinkSend), así que sus bytes cruzan seguidos.
;
; El maestro (reloj interno, jugador 1) manda un byte por cuadro desde el bucle principal (LinkPoll). El esclavo (reloj
; externo) arma el siguiente byte en la ISR serie en cuanto llega uno, así siempre tiene algo listo cuando el maestro
; da el reloj. Los dos guardan lo que llega en wLinkIn y el bucle principal lo lee.
;
; Búsqueda: al entrar, cada consola espera como esclavo un rato al azar (LINK_LISTEN_MIN a +63 cuadros) y, si nadie la
; llamó, llama como maestro LINK_CALL cuadros. Mientras busca repite su saludo (MSG_HELLO). Quien recibe el saludo
; completo del otro queda conectado con el papel que tenía en ese momento.
;
; Conectados, LinkTick corre en cada cuadro desde el bucle principal (en cualquier estado): el maestro manda un byte y
; los mensajes que se completan quedan en variables (wLinkPeer, wPeerMenu) con su bit en wLinkGot. Si en LINK_TIMEOUT
; cuadros no llega nada, se da la conexión por perdida.
;
; Menú de 2 jugadores: cada consola manda su estado (MSG_MENU) cuando cambia y cada LINK_REFRESH cuadros. El jugador 2
; sigue la canción del 1 (y en VS, su dificultad). Start marca "listo"; con los dos listos empieza el arranque
; sincronizado (ver LinkWaitFrame). Todo lo que importa se repite hasta que el otro contesta, así que perder un byte no
; atora nada.
;
; Las pruebas conectan dos PyBoy enganchándose a SerialSend, SerialArm, SerialGot y SerialOff (ver linkbridge.py).
; =============================================================================

DEF LINK_IDLE EQU $80           ; "nada que mandar": con el bit 7, así corta un mensaje al que se le perdió un byte
DEF MSG_HELLO EQU $81           ; versión, hash de la lista de canciones (2 bytes)
DEF MSG_MENU  EQU $82           ; canción, instrumento, dificultad, banderas (bit 0 listo, bit 1 sin fallo)
DEF MSG_START EQU $83           ; canción (el 1 al 2: prepárala; se repite hasta que el 2 contesta MSG_SET)
DEF MSG_SET   EQU $84           ; el 2 al 1: 0 = ya preparé la canción, 1 = ya tengo la cuenta regresiva
DEF MSG_GO    EQU $85           ; cuadros que faltan para echarla a andar (el 1 al 2; se repite hasta llegar a 0)
DEF MSG_SCORE EQU $86           ; jugando y en resultados: puntaje (6 dígitos, dos por byte) y banderas (RIVALB_...)

DEF GOTB_HELLO EQU 0            ; bits de wLinkGot
DEF GOTB_MENU  EQU 1
DEF GOTB_START EQU 2
DEF GOTB_SET   EQU 3
DEF GOTB_GO    EQU 4
DEF GOTB_SCORE EQU 5
DEF GOTB_EVENTS EQU 6           ; Co-Op (coop.asm)
DEF GOTB_BAND  EQU 7

DEF RIVALB_FAILED   EQU 0       ; banderas de MSG_SCORE: se le acabó la vida
DEF RIVALB_MUTED    EQU 1       ; su instrumento está callado (falló)
DEF RIVALB_FINISHED EQU 2       ; ya terminó (está en resultados): el puntaje es el final

DEF LINK_SEARCH EQU 0
DEF LINK_OK     EQU 1
DEF LINK_WRONG  EQU 2

DEF LINK_LISTEN_MIN EQU 30      ; cuadros esperando como esclavo: de 30 a 93 (al azar)
DEF LINK_CALL       EQU 24      ; cuadros llamando como maestro (el saludo del otro tarda a lo más 7)
DEF LINK_TO_MENU    EQU 60      ; cuadros con "CONECTADO" en pantalla antes de pasar al menú
DEF LINK_TIMEOUT    EQU 120     ; cuadros sin oír al otro para dar la conexión por perdida
DEF LINK_REFRESH    EQU 8       ; cuadros entre dos MSG_MENU aunque nada cambie (si uno se pierde, el siguiente lo repara)
DEF LINK_COUNTDOWN  EQU 45      ; cuadros desde que el jugador 1 da la salida hasta que los dos empiezan
DEF LINK_DEADLINE   EQU 15      ; cuadros antes del final en que el 1 decide si el 2 tiene la cuenta (ver LinkWaitFrame):
                                ; antes, ~10 cuentas y confirmaciones; después, ~5 cuentas nuevas si la vuelve a empezar
DEF LINK_SET0_FRESH EQU 4       ; un MSG_SET 0 de hace a lo más estos cuadros dice que el 2 sigue sin cuenta (sin
                                ; cuenta, el 2 lo repite cada ~3 cuadros; con cuenta, deja de mandarlo)

DEF LINK_ROW_STATUS EQU 8
DEF LINK_SEND_LY    EQU 64      ; línea de la pantalla en que el maestro manda su byte (ver StatISR)

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

; ISR de STAT (LYC = LINK_SEND_LY), solo en el maestro: un byte por cuadro, siempre en el mismo punto del cuadro. Si lo
; mandara el bucle principal, un cuadro que se atrasa juntaría dos envíos sin que el esclavo alcanzara a volver a armarse.
; Va a media pantalla porque el byte tarda ~9 líneas (1 ms) en cruzar: así termina dentro del mismo cuadro, también en
; el puente de las pruebas, que avanza las consolas de cuadro en cuadro. No toca VRAM ni cambia de banco.
StatISR:
    push af
    push hl
    ldh a, [hLinkMaster]
    and a
    call nz, LinkIsrSend
    pop hl
    pop af
    reti

LinkIsrSend:
    ldh a, [rSC]
    bit 7, a                    ; la anterior todavía no termina
    ret nz
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

; Encola el mensaje de B bytes de HL (tipo y datos) y, al final, su suma de comprobación: (tipo + datos) & $7F.
; Usa A, C y DE.
LinkSend:
    ldh a, [hLinkOutW]
    ld e, a
    ld d, HIGH(wLinkOut)
    ld c, 0
.loop:
    ld a, [hl+]
    ld [de], a
    add c
    ld c, a
    call .next
    dec b
    jr nz, .loop
    ld a, c
    and $7F
    ld [de], a
    call .next
    ld a, e                     ; se publica al final: la ISR nunca ve el mensaje a medias
    ldh [hLinkOutW], a
    ret
.next:
    ld a, e
    inc a
    and $0F
    or LOW(wLinkOut)
    ld e, a
    ret

; Tira lo que queda por mandar. Un mensaje a medias se corta solo: el siguiente tipo lo descarta del otro lado.
LinkOutClear:
    di
    ldh a, [hLinkOutW]
    ldh [hLinkOutR], a
    reti                        ; (ret con ei)

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
    and ~(IEF_SERIAL | IEF_STAT)
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
    ld [wLinkGot], a
    ld [wLinkSilence], a
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
    ldh a, [rIE]                ; (el esclavo no manda: sin la interrupción de STAT)
    and ~IEF_STAT
    ldh [rIE], a
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

; Maestro: da el reloj (StatISR manda un byte por cuadro)
LinkCall:
    di
    call LinkDisarm
    ld a, 1
    ldh [hLinkMaster], a
    ld a, LINK_SEND_LY
    ldh [rLYC], a
    ld a, STATF_LYC
    ldh [rSTAT], a
    ldh a, [rIF]
    and ~IEF_STAT
    ldh [rIF], a
    ldh a, [rIE]
    or IEF_STAT
    ldh [rIE], a
    ei
    ld a, LINK_CALL
    ld [wLinkTimer], a
    ret

; ---- Una vez por cuadro -------------------------------------------------------------------------------------------
; Bucle principal, antes del manejador del estado, mientras el cable está encendido
LinkTick:
    call LinkPoll
    call CoopTick               ; (antes que el puntaje: en resultados, los eventos que quedaban salen primero)
    call LinkScoreTick
    ld a, [wLinkState]
    cp LINK_OK
    ret nz
    ; si llega un saludo estando conectados, el otro sigue buscando (no completó el nuestro): se le contesta
    ld hl, wLinkGot
    bit GOTB_HELLO, [hl]
    jr z, .noHello
    res GOTB_HELLO, [hl]
    call LinkOutEmpty
    jr nz, .noHello
    ld hl, HelloMsg
    ld b, HelloMsgEnd - HelloMsg
    call LinkSend
.noHello:
    ld hl, wLinkHeard
    ld a, [hl]
    ld [hl], 0
    and a
    ld hl, wLinkSilence
    jr z, .silent
    ld [hl], 0
    ret
.silent:
    inc [hl]
    ld a, [hl]
    cp LINK_TIMEOUT
    ret c
    ; se perdió la conexión: en el menú se vuelve al título; jugando, se sigue solo
    call LinkStop
    xor a
    ld [wPlayers], a
    ld a, [wState]
    cp STATE_MENU
    jp z, EnterTitle
    cp STATE_LINK
    jp z, EnterTitle
    ret

; Jugando y en resultados: desempaca el puntaje del otro cuando llega y manda el propio cada vez que la cola se vacía
; (unas 10 veces por segundo)
LinkScoreTick:
    ld hl, wLinkGot
    bit GOTB_SCORE, [hl]
    jr z, .send
    res GOTB_SCORE, [hl]
    ld hl, wRivalMsg            ; tres bytes de dos dígitos (0 a 99) y las banderas
    ld de, wRivalDigits
    ld b, 3
.unpack:
    ld a, [hl+]
    ld c, 0
.tens:
    cp 10
    jr c, .ones
    sub 10
    inc c
    jr .tens
.ones:
    push af
    ld a, c
    ld [de], a
    inc de
    pop af
    ld [de], a
    inc de
    dec b
    jr nz, .unpack
    ld a, [hl]
    ld [wRivalFlags], a
    ld a, 1
    ld [wRivalDirty], a
    ld hl, wHudDirty
    set 3, [hl]
.send:
    ld a, [wCoopGame]           ; Co-Op: jugando van los eventos y la banda (coop.asm); en resultados, este mensaje
    and a                       ; lleva los aciertos y el total de notas en vez del puntaje
    jr z, .notCoop
    ld a, [wState]
    cp STATE_PLAY
    ret z
.notCoop:
    ld a, [wState]
    ld c, 0
    cp STATE_PLAY
    jr z, .build
    ld c, 1 << RIVALB_FINISHED
    cp STATE_RESULTS
    jr z, .build
    cp STATE_INITIALS
    ret nz
.build:
    call LinkOutEmpty
    ret nz
    ld a, [wFailed]
    and a
    jr z, .notFailed
    set RIVALB_FAILED, c
.notFailed:
    ld a, [wMuted]
    and a
    jr z, .notMuted
    set RIVALB_MUTED, c
.notMuted:
    ld de, wScoreDigits
    ld a, [wCoopGame]
    and a
    jr z, .source
    ld hl, wHitsDigits
    ld de, wCoopTmp
    ld b, 3
    call .copy3
    ld hl, wTotalDigits
    ld b, 3
    call .copy3
    ld de, wCoopTmp
.source:
    ld hl, wMenuMsg
    ld a, MSG_SCORE
    ld [hl+], a
    ld b, 3
.pack:
    ld a, [de]                  ; decenas * 10 (con [hl] de apoyo) + unidades
    inc de
    add a
    ld [hl], a
    add a
    add a
    add [hl]
    ld [hl], a
    ld a, [de]
    inc de
    add [hl]
    ld [hl+], a
    dec b
    jr nz, .pack
    ld [hl], c
    ld hl, wMenuMsg
    ld b, LINK_SCORE_LEN + 1
    jp LinkSend
.copy3:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .copy3
    ret

; Z = 1 si hay una partida de VS por cable
LinkIsVs:
    ldh a, [hLinkOn]
    and a
    jr z, .no
    ld a, [wPlayers]
    cp 1
    ret
.no:
    inc a
    ret

; PlayFrame: carry = 1 si la partida de 2 jugadores debe cortarse: en VS, porque alguien perdió (con fallo activado);
; en Co-Op, porque cayeron los dos
LinkVsCut:
    call CoopCut
    jr nz, .cut
    call LinkIsVs
    jr nz, .no
    ld a, [wRivalFlags]
    and 1 << RIVALB_FAILED
    ld b, a
    ld a, [wFailed]
    or b
    jr z, .no
.cut:
    ld a, 1
    ld [wVsCut], a
    scf
    ret
.no:
    and a
    ret

; PlayFrame: A = NR51; si el otro está fallando con otro instrumento, también se calla su canal
LinkMuteRival:
    ld b, a
    ldh a, [hLinkOn]
    and a
    jr z, .keep
    ld a, [wRivalFlags]
    bit RIVALB_MUTED, a
    jr z, .keep
    ld a, [wInstrument]
    ld c, a
    ld a, [wPeerMenu + 1]
    cp c
    jr z, .keep                 ; (el mismo instrumento: su canal es el propio)
    cp 4
    jr nc, .keep
    ld e, a
    ld d, 0
    ld hl, InstrNr51Muted
    add hl, de
    ld a, b
    and [hl]
    ret
.keep:
    ld a, b
    ret

; El maestro manda el siguiente byte; luego se leen los que llegaron. Cada mensaje completo se copia a su variable y
; enciende su bit en wLinkGot.
LinkPoll:
.read:
    ldh a, [hLinkInW]
    ld b, a
    ldh a, [hLinkInR]
    cp b
    ret z                       ; no queda nada por leer
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
    jr z, .read                 ; un dato suelto (de un mensaje cortado)
    sub MSG_HELLO
    ld e, a
    ld d, 0
    ld hl, LinkLens
    add hl, de
    ld c, [hl]                  ; C = bytes de datos del mensaje
    inc c                       ; (más la suma de comprobación)
    ld a, [wLinkPos]
    ld e, a
    ld hl, wLinkBuf
    add hl, de
    ld [hl], b
    inc a
    ld [wLinkPos], a
    cp c
    jr c, .read
    ; completo: la suma de comprobación debe coincidir (si no, se perdieron bytes de dos mensajes y se pegaron)
    dec c                       ; C = bytes de datos
    ld a, [wLinkType]
    ld b, a
    ld e, c
    ld hl, wLinkBuf
.sum:
    ld a, [hl+]
    add b
    ld b, a
    dec e
    jr nz, .sum
    ld a, b
    and $7F
    cp [hl]
    jr z, .valid
    xor a
    ld [wLinkType], a
    jp .read
.valid:
    ; los datos van a su variable (tabla LinkDest) y se enciende su bit en wLinkGot
    ld a, [wLinkType]
    sub MSG_HELLO
    ld b, a
    add a
    add b                       ; * 3
    ld e, a
    ld d, 0
    ld hl, LinkDest
    add hl, de
    ld a, [hl+]
    ld e, a
    ld a, [hl+]
    ld d, a
    ld b, [hl]                  ; B = bit de wLinkGot
    ld hl, wLinkBuf
.copy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec c
    jr nz, .copy
    ld a, [wLinkGot]
    or b
    ld [wLinkGot], a
    xor a
    ld [wLinkType], a
    jp .read

; Bytes de datos de cada tipo de mensaje (sin la suma de comprobación), desde MSG_HELLO
LinkLens:
    db LINK_HELLO_LEN, LINK_MENU_LEN, 1, 1, 1, LINK_SCORE_LEN, LINK_EVENTS_LEN, LINK_BAND_LEN
LinkLensEnd:
; A dónde se copian sus datos y qué bit encienden en wLinkGot
LinkDest:
    dw wLinkPeer
    db 1 << GOTB_HELLO
    dw wPeerMenu
    db 1 << GOTB_MENU
    dw wPeerStart
    db 1 << GOTB_START
    dw wPeerSet
    db 1 << GOTB_SET
    dw wPeerGo
    db 1 << GOTB_GO
    dw wRivalMsg
    db 1 << GOTB_SCORE
    dw wPeerEvents
    db 1 << GOTB_EVENTS
    dw wPeerBand
    db 1 << GOTB_BAND

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
    cp LINK_WRONG
    jr z, .poll
    ; buscando y recién conectados: siempre hay un saludo por mandar (conectados, para que el otro también lo complete).
    ; A veces se deja un hueco al azar antes de repetirlo: así una falla periódica del cable no corta siempre el mismo
    ; byte del saludo.
    call LinkOutEmpty
    jr nz, .queued
    ldh a, [rDIV]
    and 8
    jr nz, .queued
    ld hl, HelloMsg
    ld b, HelloMsgEnd - HelloMsg
    call LinkSend
.queued:
    ld a, [wLinkState]
    cp LINK_SEARCH
    jr nz, .poll
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
    ld a, [wLinkState]
    cp LINK_OK
    jr nz, .notOk
    ld hl, wLinkTimer           ; conectados: "CONECTADO" un momento y al menú
    dec [hl]
    ret nz
    jp EnterMenu
.notOk:
    ld hl, wLinkGot
    bit GOTB_HELLO, [hl]
    ret z
    res GOTB_HELLO, [hl]
    cp LINK_SEARCH
    ret nz                      ; (los saludos que quedaban en camino)
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
    ld a, LINK_TO_MENU
    ld [wLinkTimer], a
    xor a
    ld [wLinkSilence], a
    ld [wReady], a
    ld [wLinkStarting], a
    ld hl, wPeerMenu            ; todavía no se sabe qué eligió el otro
    ld a, $FF
    ld [hl+], a
    ld [hl+], a
    ld [hl+], a
    ld [hl], 0
    ld [wPeerInstrSeen], a
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

; ---- Menú de 2 jugadores ----------------------------------------------------------------------------------------
; Fila 16: lo que eligió el otro ("J2 GUITARRA LISTO"); fila 17: "PRESIONA START" o "LISTO".
TxtReady:     db "    LISTO     ", 0      ; (14 caracteres, como TxtPress)
TxtPeerJ1:    db "J1 "
TxtPeerJ2:    db "J2 "
TxtPeerReady: db "LISTO   "
TxtBlank8:    db "        "

; EnterMenu, antes de leer la canción: el jugador 2 toma la del 1 (y en VS su dificultad)
MenuLinkEnter:
    xor a
    ld [wReady], a
    ld [wLinkStarting], a
    ld a, LINK_REFRESH
    ld [wMenuRefresh], a
    ld a, $FF
    ld [wPeerDiffSeen], a
    ld [wMenuSent], a           ; el primer cuadro manda el estado completo
    ldh a, [hLinkMaster]
    and a
    jr nz, .line
    ld a, [wPeerMenu]
    cp NUM_SONGS
    jr nc, .line
    ld [wSong], a
    ld a, [wPlayers]
    cp 1
    jr nz, .line
    ld a, [wPeerMenu + 2]
    cp 4
    jr nc, .line
    ld [wDifficulty], a
.line:
    jp QueuePeerLine

; MenuFrame con el cable encendido
MenuFrameLink:
    call MenuLinkSync
    ld a, [wState]
    cp STATE_MENU
    ret nz                      ; (empezó la canción)
    di
    ldh a, [hPadNew]
    ld b, a
    xor a
    ldh [hPadNew], a
    ei
    bit PADB_B, b
    jr z, .noB
    ld a, 2
    call PlayMenuSfx            ; volver
    ld a, [wReady]
    and a
    jr z, .leave
    xor a                       ; B quita el "listo"
    ld [wReady], a
    jp QueueReadyLine
.leave:
    call LinkStop               ; el otro se da cuenta al no oír nada (LINK_TIMEOUT)
    xor a
    ld [wPlayers], a
    jp EnterTitle
.noB:
    ld a, [wReady]
    and a
    ret nz                      ; listo: ya no se cambia nada
    bit PADB_START, b
    jr z, .noStart
    ld a, [wPlayers]            ; Co-Op: no se puede tocar el instrumento del otro
    cp 2
    jr nz, .ready
    ld a, [wPeerMenu + 1]
    ld c, a
    ld a, [wInstrument]
    cp c
    jr nz, .ready
    ld a, 2
    jp PlayMenuSfx
.ready:
    ld a, 1
    ld [wReady], a
    call PlayMenuSfx            ; aceptar
    jp QueueReadyLine
.noStart:
    ; el jugador 2 no cambia la canción (ni, en VS, la dificultad)
    ldh a, [hLinkMaster]
    and a
    jr nz, .input
    ld a, [wMenuRow]
    and a
    jr z, .lock
    cp 2
    jr nz, .input
    ld a, [wPlayers]
    cp 1
    jr nz, .input
.lock:
    ld a, b
    and LOW(~((1 << PADB_LEFT) | (1 << PADB_RIGHT)))
    ld b, a
.input:
    ld a, b                     ; (sin opciones con 2 jugadores: cambiarían la velocidad de uno solo)
    and LOW(~((1 << PADB_START) | (1 << PADB_B) | (1 << PADB_SELECT)))
    ld b, a
    jp MenuInput

; Lo que llegó del otro, el estado propio si cambió y, en el jugador 1, la salida con los dos listos
MenuLinkSync:
    ld hl, wLinkGot
    bit GOTB_MENU, [hl]
    jr z, .noMenu
    res GOTB_MENU, [hl]
    call MenuApplyPeer
    call QueuePeerLine
.noMenu:
    ld hl, wLinkGot
    bit GOTB_START, [hl]
    jr z, .noStartMsg
    res GOTB_START, [hl]
    ldh a, [hLinkMaster]
    and a
    jp z, StartSongLink         ; el jugador 2 prepara la canción en cuanto lo recibe
.noStartMsg:
    ; el estado propio, si cambió o toca repetirlo, y si la cola está libre (si no, en el cuadro siguiente)
    ld hl, wMenuRefresh
    dec [hl]
    jr nz, .noRefresh
    ld [hl], LINK_REFRESH
    ld a, $FF
    ld [wMenuSent], a
.noRefresh:
    call LinkOutEmpty
    jr nz, .sent
    call MenuBuildState
    jr z, .sent
    ld hl, wMenuMsg + 1
    ld de, wMenuSent
    ld b, LINK_MENU_LEN
.save:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .save
    ld hl, wMenuMsg
    ld b, LINK_MENU_LEN + 1
    call LinkSend
.sent:
    ; el jugador 1 da la salida: los dos listos, la misma canción y, en VS, la misma dificultad (en Co-Op, instrumentos
    ; distintos)
    ldh a, [hLinkMaster]
    and a
    ret z
    ld a, [wReady]
    and a
    ret z
    ld a, [wPeerMenu + 3]
    bit 0, a
    ret z
    ld a, [wPeerMenu]
    ld b, a
    ld a, [wSong]
    cp b
    ret nz
    ld a, [wPlayers]
    cp 1
    jr nz, .coop
    ld a, [wPeerMenu + 2]
    ld b, a
    ld a, [wDifficulty]
    cp b
    ret nz
    jr .go
.coop:
    ld a, [wPeerMenu + 1]
    ld b, a
    ld a, [wInstrument]
    cp b
    ret z
.go:
    jp StartSongLink            ; (MSG_START lo repite LinkWaitFrame hasta que el 2 conteste)

; Arma MSG_MENU en wMenuMsg con lo elegido. Z = 1 si es lo mismo que ya se mandó.
MenuBuildState:
    ld hl, wMenuMsg
    ld a, MSG_MENU
    ld [hl+], a
    ld a, [wSong]
    ld [hl+], a
    ld a, [wInstrument]
    ld [hl+], a
    ld a, [wDifficulty]
    ld [hl+], a
    ld a, [wNoFail]
    add a
    ld b, a
    ld a, [wReady]
    or b
    ld [hl], a
    ld hl, wMenuMsg + 1
    ld de, wMenuSent
    ld b, LINK_MENU_LEN
.cmp:
    ld a, [de]
    cp [hl]
    ret nz
    inc hl
    inc de
    dec b
    jr nz, .cmp
    ret

; Jugador 2: sigue la canción del 1 y, en VS, su dificultad; cuando el 1 cambia de instrumento en VS, lo copia (y luego
; puede cambiarlo). Si cambia la canción o la dificultad, deja de estar "listo".
MenuApplyPeer:
    call LinkIsCoop             ; Co-Op: el récord de banda depende de la dificultad más alta de los dos
    jr nz, .notCoop
    ld a, [wPeerMenu + 2]
    ld hl, wPeerDiffSeen
    cp [hl]
    jr z, .notCoop
    ld [hl], a
    call RefreshRecord
.notCoop:
    ldh a, [hLinkMaster]
    and a
    ret nz
    ld a, [wPeerMenu]
    cp NUM_SONGS
    ret nc
    ld b, a
    ld a, [wSong]
    cp b
    jr z, .sameSong
    ld a, b
    ld [wSong], a
    call MenuLoadSong
    call QueueSongText
    call QueueInstrument
    call RefreshRecord
    call .unready
.sameSong:
    ld a, [wPlayers]
    cp 1
    ret nz                      ; Co-Op: cada quien su dificultad y su instrumento
    ld a, [wPeerMenu + 2]
    cp 4
    jr nc, .instr
    ld b, a
    ld a, [wDifficulty]
    cp b
    jr z, .instr
    ld a, b
    ld [wDifficulty], a
    call QueueDifficulty
    call RefreshRecord
    call .unready
.instr:
    ld a, [wPeerMenu + 1]
    ld hl, wPeerInstrSeen
    cp [hl]
    ret z
    ld [hl], a
    cp 4
    ret nc
    ld b, a
    call InstrAvailable
    ret nc
    ld a, b
    ld [wInstrument], a
    call QueueInstrument
    jp RefreshRecord
.unready:
    ld a, [wReady]
    and a
    ret z
    xor a
    ld [wReady], a
    jp QueueReadyLine

QueueReadyLine:
    ld a, [wReady]
    and a
    ld hl, TxtPress
    jr z, .put
    ld hl, TxtReady
.put:
    ld b, 14
    ld de, _SCRN0 + 32 * 17 + 3
    jp QueueRaw

; Fila 16: "J2 GUITARRA LISTO" (el número del otro, su instrumento y si está listo)
QueuePeerLine:
    ld de, wPeerLine
    ldh a, [hLinkMaster]
    and a
    ld hl, TxtPeerJ2            ; esta consola es el jugador 1: el otro es el 2
    jr nz, .num
    ld hl, TxtPeerJ1
.num:
    ld b, 3
    call .copy
    ld a, [wPeerMenu + 1]
    cp 4
    ld hl, TxtBlank8
    jr nc, .instr
    swap a
    add 3                       ; el nombre dentro de "<  GUITARRA  >"
    ld c, a
    ld b, 0
    ld hl, InstrText
    add hl, bc
.instr:
    ld b, 8
    call .copy
    ld a, ' '
    ld [de], a
    inc de
    ld a, [wPeerMenu + 3]
    bit 0, a
    ld hl, TxtPeerReady
    jr nz, .ready
    ld hl, TxtBlank8
.ready:
    ld b, 8
    call .copy
    ld hl, wPeerLine
    ld b, 20
    ld de, _SCRN0 + 32 * 16
    jp QueueRaw
.copy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .copy
    ret

; El 1 con los dos listos y el 2 al recibir MSG_START: prepara la canción y espera en LinkWaitFrame (BeginPlay)
StartSongLink:
    xor a
    ld [wLinkStarting], a
    ld [wReady], a
    ld [wPeerMenu + 3], a       ; el otro deja de estar "listo" hasta que lo vuelva a decir
    ld [wOptSpeed], a           ; a velocidad normal y sin práctica: si no, las consolas se desincronizan
    ld [wOptPractice], a
    ld [wRivalFlags], a         ; el otro empieza en ceros
    ld [wRivalDirty], a
    ld [wVsCut], a
    ld hl, wRivalDigits
    ld b, 6
.zero:
    ld [hl+], a
    dec b
    jr nz, .zero
    ld a, $FF
    ld [wMenuSent], a
    ld a, [wLinkGot]
    and LOW(~((1 << GOTB_START) | (1 << GOTB_SET) | (1 << GOTB_GO)))
    ld [wLinkGot], a
    jp StartSong

; ---- Resultados de VS ---------------------------------------------------------------------------------------------
; Fila 7: el puntaje del otro; fila 16: quién ganó. Hasta que llega el puntaje final del otro, "ESPERANDO A J2...".
DEF VS_ROW_RIVAL EQU 7
DEF VS_ROW_LINE  EQU 16

TxtRivalLbl: db "PUNTOS J", 0
TxtVsWait:   db "ESPERANDO A J", 0
TxtVsWins:   db "GANA J", 0
TxtVsBy:     db " POR ", 0
TxtVsDash:   db " - J", 0
TxtVsLost:   db " PERDIO", 0
TxtVsTie:    db "       EMPATE", 0

; EnterResults (LCD apagado): el renglón del otro y la línea de VS
ResultsVsDraw:
    ld de, _SCRN0 + 32 * VS_ROW_RIVAL + 1
    ld hl, TxtRivalLbl
    call PrintStr
    call VsNumbers
    ld a, c
    ld [de], a
    ld de, _SCRN0 + 32 * VS_ROW_RIVAL + 12
    ld hl, wRivalDigits
    ld b, 6
    call PrintDigits
    xor a
    ld [wRivalDirty], a
    call VsBuildLine
    ld hl, wPeerLine
    ld de, _SCRN0 + 32 * VS_ROW_LINE
    ld b, 20
    jp CopyToMap

; ResultsFrame: si llegó otro puntaje del otro, se vuelven a encolar su renglón y la línea
ResultsVsUpdate:
    ld a, [wRivalDirty]
    and a
    ret z
    xor a
    ld [wRivalDirty], a
    ld hl, wRivalDigits
    ld de, _SCRN0 + 32 * VS_ROW_RIVAL + 12
    ld b, 6
    call QueueDigits
    call VsBuildLine
    ld hl, wPeerLine
    ld de, _SCRN0 + 32 * VS_ROW_LINE
    ld b, 20
    jp QueueRaw

; B = el número de esta consola ('1' o '2') y C = el del otro
VsNumbers:
    ldh a, [hLinkMaster]
    and a
    ld bc, ('1' << 8) | '2'
    ret nz
    ld bc, ('2' << 8) | '1'
    ret

; Arma en wPeerLine (20 caracteres) quién ganó: si alguien perdió (se le acabó la vida), gana el otro; si no, el de más
; puntos ("GANA J1 POR 001230") o "EMPATE".
VsBuildLine:
    ld hl, wPeerLine
    ld b, 20
    ld a, ' '
.fill:
    ld [hl+], a
    dec b
    jr nz, .fill
    call VsNumbers
    ld de, wPeerLine
    ld a, [wRivalFlags]
    bit RIVALB_FINISHED, a
    jr nz, .final
    ld hl, TxtVsWait            ; "ESPERANDO A J2..."
    call VsPut
    ld a, c
    ld [de], a
    inc de
    ld a, '.'
    ld [de], a
    inc de
    ld [de], a
    inc de
    ld [de], a
    ret
.final:
    ld a, [wRivalFlags]
    and 1 << RIVALB_FAILED
    ld h, a                     ; H = el otro perdió
    ld a, [wFailed]
    and a
    jr z, .meAlive
    ld a, h
    and a
    jr nz, .byScore             ; perdieron los dos: decide el puntaje
    ld a, c                     ; esta consola perdió: gana el otro
    ld c, b
    ld b, a
    jr .lostLine
.meAlive:
    ld a, h
    and a
    jr z, .byScore
.lostLine:
    ; B = el que ganó, C = el que perdió: "GANA J1 - J2 PERDIO"
    ld hl, TxtVsWins
    call VsPut
    ld a, b
    ld [de], a
    inc de
    ld hl, TxtVsDash
    call VsPut
    ld a, c
    ld [de], a
    inc de
    ld hl, TxtVsLost
    jp VsPut
.byScore:
    push bc
    call VsCompare              ; (usa DE: la línea se vuelve a escribir desde el principio)
    pop bc
    ld de, wPeerLine
    jr nz, .notTie
    ld hl, TxtVsTie
    jp VsPut
.notTie:
    jr c, .rivalWins
    ld hl, TxtVsWins            ; gana esta consola: la diferencia es el propio menos el del otro
    call VsPut
    ld a, b
    ld [de], a
    ld hl, wScoreDigits
    ld de, wRivalDigits
    jr .by
.rivalWins:
    ld hl, TxtVsWins
    call VsPut
    ld a, c
    ld [de], a
    ld hl, wRivalDigits
    ld de, wScoreDigits
.by:
    push hl
    push de
    ld hl, TxtVsBy
    ld de, wPeerLine + 7
    call VsPut
    pop de
    pop hl
    ; (sigue en VsDiff)

; Escribe HL - DE (6 dígitos, HL el mayor) como caracteres en wPeerLine + 12
VsDiff:
    push de
    ld de, wPeerLine + 12
    ld b, 6
.copy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .copy
    pop de
    ld hl, 5
    add hl, de
    ld d, h
    ld e, l                     ; DE = último dígito del menor
    ld hl, wPeerLine + 17
    ld bc, $0600                ; B = dígitos, C = lo que se pide prestado
.sub:
    ld a, [de]
    add c
    ld c, a
    ld a, [hl]
    sub c
    ld c, 0
    jr nc, .digit
    add 10
    ld c, 1
.digit:
    add '0'
    ld [hl-], a
    dec de
    dec b
    jr nz, .sub
    ret

; Z = 1 si los dos puntajes son iguales; si no, carry = 1 si el propio es menor
VsCompare:
    ld hl, wScoreDigits
    ld de, wRivalDigits
    ld b, 6
.loop:
    ld a, [de]
    ld c, a
    ld a, [hl]
    cp c
    ret nz
    inc hl
    inc de
    dec b
    jr nz, .loop
    ret

; Copia la cadena terminada en 0 de HL a DE (deja DE después de lo copiado)
VsPut:
    ld a, [hl+]
    and a
    ret z
    ld [de], a
    inc de
    jr VsPut

; ---- Arranque sincronizado ----------------------------------------------------------------------------------------
; Cada consola tarda distinto en preparar la canción con el LCD apagado (la CGB limpia dos bancos de VRAM), así que
; BeginPlay no la echa a andar: espera aquí con la autopista en pantalla. El jugador 1 repite MSG_START hasta que el 2
; contesta MSG_SET 0 (ya preparó la suya); entonces cuenta LINK_COUNTDOWN cuadros y repite MSG_GO con los que faltan.
; El 2 toma la cuenta del último que le llegó y contesta MSG_SET 1 mientras cuenta (y MSG_SET 0 mientras no la tiene).
; Los dos echan a andar la canción al llegar a 0. A LINK_DEADLINE cuadros del final, si el 2 nunca confirmó y hace muy
; poco dijo MSG_SET 0 (sigue sin cuenta), el 1 la vuelve a empezar; el 2 nunca empieza sin cuenta.
LinkWaitFrame:
    di
    xor a
    ldh [hPadNew], a            ; (los botones no hacen nada mientras tanto)
    ei
    ldh a, [hLinkMaster]
    and a
    jr nz, .master
    ; jugador 2
    ld hl, wLinkGot
    bit GOTB_GO, [hl]
    jr z, .noGo
    res GOTB_GO, [hl]
    ld a, [wPeerGo]
    and a
    jr nz, .take
    inc a
.take:
    ld b, a
    ld a, [wLinkStarting]
    and a
    ld a, b
    ld [wLinkStarting], a
    ; con la primera cuenta, lo que quedaba por mandar (un MSG_SET 0) ya no vale: se tira y se confirma enseguida
    call z, LinkOutClear
.noGo:
    ld a, [wLinkStarting]
    and a
    jr z, .slaveReply
    dec a
    ld [wLinkStarting], a
    jp z, .play
.slaveReply:
    call LinkOutEmpty           ; MSG_SET: 0 = ya preparé la canción, 1 = ya tengo la cuenta
    ret nz
    ld a, [wLinkStarting]
    and a
    jr z, .set
    ld a, 1
.set:
    ld b, a
    ld a, MSG_SET
    jr .send
.master:
    ld hl, wLinkGot
    bit GOTB_SET, [hl]
    jr z, .noSet
    res GOTB_SET, [hl]
    ld a, [wLinkStarting]
    and a
    jr nz, .ack
    ld a, LINK_COUNTDOWN        ; el 2 ya preparó la canción: empieza la cuenta
    ld [wLinkStarting], a
    xor a                       ; todavía no confirma que le llegó (y acaba de decir que no la tiene)
    ld [wLinkAcked], a
    ld [wLinkSet0Age], a
    ret
.ack:
    ld a, [wPeerSet]            ; 1 = el 2 tiene la cuenta (ya no se olvida en esta cuenta)
    and a
    jr z, .set0
    ld [wLinkAcked], a
    jr .noSet
.set0:
    ld [wLinkSet0Age], a        ; 0 = el 2 acaba de decir que no la tiene
.noSet:
    ld hl, wLinkSet0Age         ; cuadros desde el último MSG_SET 0 (se queda en 255)
    inc [hl]
    jr nz, .aged
    dec [hl]
.aged:
    ld a, [wLinkStarting]
    and a
    jr nz, .count
    call LinkOutEmpty           ; todavía sin respuesta: repite MSG_START
    ret nz
    ld a, [wSong]
    ld b, a
    ld a, MSG_START
    jr .send
.count:
    dec a
    ld [wLinkStarting], a
    jr z, .play
    cp LINK_DEADLINE
    jr nz, .repeatGo
    ; el 2 no confirmó y hace poco dijo que no tiene la cuenta: se vuelve a empezar. (Si no dijo nada en un rato, lo
    ; más probable es que ya la tenga y se hayan perdido sus confirmaciones: se sigue.)
    ld a, [wLinkAcked]
    and a
    jr nz, .repeatGo
    ld a, [wLinkSet0Age]
    cp LINK_SET0_FRESH + 1
    jr nc, .repeatGo
    ld a, LINK_COUNTDOWN
    ld [wLinkStarting], a
    call LinkOutClear           ; la cuenta vieja que iba saliendo ya no vale: la nueva sale enseguida
.repeatGo:
    ; repite la cuenta cada vez que se vacía la cola. Si aquí faltan K cuadros, el mensaje termina de salir (con su suma
    ; de comprobación) en el LinkPoll de dentro de 3 cuadros, cuando falten K - 3; el 2 lo atiende en ese mismo cuadro y
    ; descuenta uno, así que se manda K - 2.
    call LinkOutEmpty
    ret nz
    ld a, [wLinkStarting]
    sub 2
    ret c
    ret z
    ld b, a
    ld a, MSG_GO
; A = tipo, B = dato: encola un mensaje de un byte de datos
.send:
    ld [wMenuMsg], a
    ld a, b
    ld [wMenuMsg + 1], a
    ld hl, wMenuMsg
    ld b, 2
    jp LinkSend
.play:
    ld a, 1
    ld [wPlaying], a
    ld a, STATE_PLAY
    ld [wState], a
    ret
