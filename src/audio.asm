; =============================================================================
; audio.asm - Reproductor del stream FRS (ver pctools/gbband_tools/audio_gb.py)
;
; Dos mitades que nunca se pisan:
;   FillAudioRing (bucle principal): lee el stream (en bancos conmutables) y lo decodifica a un ring buffer de
;                                    16 cuadros en WRAM. Cada cuadro ocupa un slot de 64 bytes.
;   AudioTick     (ISR de VBlank):   lee UN slot de WRAM y escribe sus registros en el APU. No toca ROMX.
; Slot: [0] cuenta de pares, [1] marca de wave RAM, [2-17] wave RAM, [18-63] pares (registro bajo, valor).
; =============================================================================

SECTION "Audio", ROM0

; Prepara el APU y el reproductor para empezar la canción de wSongBank. LCD apagado o ISR sin audio.
AudioInit:
    xor a
    ld [wRingRead], a
    ld [wRingWrite], a
    ld [wEmptyRun], a
    ld [wStreamEnd], a
    ld [wUnderrun], a
    ld [wMuted], a
    ld hl, wNoteOnCnt
    ld b, $28
.clearCounts:
    ld [hl+], a
    dec b
    jr nz, .clearCounts
    ld a, LOW(wAudioRing)
    ld [wRingReadPtr], a
    ld [wRingWritePtr], a
    ld a, HIGH(wAudioRing)
    ld [wRingReadPtr + 1], a
    ld [wRingWritePtr + 1], a
    ld a, $FF
    ld [wNr51Out], a

    ; APU: se apaga y se enciende (el stream supone los registros en cero, y los menús dejan el APU encendido con restos),
    ; volumen máximo, todos los canales a ambos lados, barrido de CH1 apagado
    xor a
    ldh [rNR52], a
    ld a, $80
    ldh [rNR52], a
    ld a, $77
    ldh [rNR50], a
    ld [sh_NR50], a
    ld a, $FF
    ldh [rNR51], a
    ld [sh_NR51], a
    xor a
    ldh [rNR10], a

    ; cursor del stream
    ld a, [wSongBank]
    ld [rROMB0], a
    ld a, [$4000 + SONG_STREAM]
    ld [wStrPtr], a
    ld a, [$4000 + SONG_STREAM + 1]
    ld [wStrPtr + 1], a
    ld a, [wSongBank]
    inc a
    ld [wStrBank], a
    ld a, [wPracFromP]
    and a
    call nz, AudioSeek      ; práctica con inicio adelantado
    jp FillAudioRing

; Apaga el audio (fin de la canción)
AudioStop:
    xor a
    ldh [rNR52], a
ApuOn:                      ; el APU se queda encendido y callado: los efectos de los menús lo necesitan
    ld a, $80
    ldh [rNR52], a
    ld a, $77
    ldh [rNR50], a
    ld a, $FF
    ldh [rNR51], a
    ret

; ---- Bucle principal: decodificar --------------------------------------------------------
FillAudioRing:
    ld a, [wStrBank]
    ld [rROMB0], a
.loop:
    ld a, [wRingRead]
    ld c, a
    ld a, [wRingWrite]
    sub c                   ; cuadros decodificados por delante
    cp RING_TARGET
    ret nc
    call DecodeFrame
    jr .loop

; A = siguiente byte del stream. Conserva todos los registros menos A y las banderas. Cambia de banco al
; pasar de $7FFF (el stream ocupa 2 bancos seguidos).
GetStreamByte:
    push hl
    ld a, [wStrPtr]
    ld l, a
    ld a, [wStrPtr + 1]
    ld h, a
    ld a, [hl+]
    push af
    ld a, h
    cp $80
    jr c, .same
    ld a, [wStrBank]
    inc a
    ld [wStrBank], a
    ld [rROMB0], a
    ld hl, $4000
.same:
    ld a, l
    ld [wStrPtr], a
    ld a, h
    ld [wStrPtr + 1], a
    pop af
    pop hl
    ret

; Decodifica un cuadro del stream al slot de escritura y avanza el ring.
DecodeFrame:
    ld a, [wRingWritePtr]
    ld [wDecSlot], a
    ld l, a
    ld a, [wRingWritePtr + 1]
    ld [wDecSlot + 1], a
    ld h, a
    xor a
    ld [hl+], a             ; cuenta = 0
    ld [hl], a              ; sin wave RAM
    ld a, [wEmptyRun]
    and a
    jr z, .notRun
    dec a
    ld [wEmptyRun], a
    jp .finish
.notRun:
    ld a, [wStreamEnd]
    and a
    jp nz, .finish
    call GetStreamByte
    bit 7, a
    jr z, .record
    and $7F                 ; racha de N cuadros vacíos: este es el primero, quedan N-1
    ld [wEmptyRun], a
    jp .finish

.record:
    ld d, a                 ; D = encabezado
    bit 6, d
    jr z, .noEnd
    ld a, 1
    ld [wStreamEnd], a
.noEnd:
    bit 4, d
    jr z, .noMaster
    call GetStreamByte      ; NR50 y NR51: los maneja el juego, se descartan
    call GetStreamByte
.noMaster:
    bit 5, d
    jr z, .noWave
    ld a, [wDecSlot]
    add 2
    ld l, a
    ld a, [wDecSlot + 1]
    adc 0
    ld h, a
    ld c, 16
.waveLoop:
    call GetStreamByte
    ld [hl+], a
    dec c
    jr nz, .waveLoop
    ld a, [wDecSlot]
    ld l, a
    ld a, [wDecSlot + 1]
    ld h, a
    inc hl
    ld a, 1
    ld [hl], a              ; marca de wave RAM
.noWave:
    ld a, d
    and $0F
    ld c, a                 ; C = canales presentes (se consume con srl)
    ld a, [wDecSlot]
    add RING_PAIRS_OFS
    ld l, a
    ld a, [wDecSlot + 1]
    adc 0
    ld h, a                 ; HL = donde van los pares
    ld b, 0                 ; B = cantidad de pares
    ld a, $10
    ld [wDecBase], a
    xor a
    ld [wDecCh], a
.chLoop:
    srl c
    jr nc, .nextCh
    call GetStreamByte
    ld e, a                 ; E = máscara de registros de este canal
    ld d, 0                 ; D = número de registro (0 a 4)
.regLoop:
    srl e
    jr nc, .skipReg
    call GetStreamByte      ; A = valor
    push af
    ld a, [wDecBase]
    add d
    ld [hl+], a             ; registro (byte bajo de la dirección $FFxx)
    pop af
    ld [hl+], a             ; valor
    inc b
.skipReg:
    inc d
    ld a, d
    cp 5
    jr nz, .regLoop
.nextCh:
    ld a, [wDecBase]
    add 5
    ld [wDecBase], a
    ld a, [wDecCh]
    inc a
    ld [wDecCh], a
    cp 4
    jr nz, .chLoop
    ld a, [wDecSlot]
    ld l, a
    ld a, [wDecSlot + 1]
    ld h, a
    ld [hl], b              ; cuenta de pares

.finish:
    ld a, [wDecSlot]
    ld l, a
    ld a, [wDecSlot + 1]
    ld h, a
    ld de, RING_SLOT_SIZE
    add hl, de
    ld a, h
    cp HIGH(wAudioRing) + RING_SLOTS * RING_SLOT_SIZE / 256
    jr c, .keep
    ld h, HIGH(wAudioRing)
    ld l, LOW(wAudioRing)
.keep:
    ld a, l
    ld [wRingWritePtr], a
    ld a, h
    ld [wRingWritePtr + 1], a
    ld hl, wRingWrite
    inc [hl]
    ret

; ---- ISR: reproducir un cuadro --------------------------------------------------------------
; No toca ROMX. Escribe NR51 (el silencio por fallo es del juego, no de la música) y, si ya empezó el audio
; (t >= lead_in), consume un slot del ring.
AudioTick:
    jp AudioTickStream

; Pasos de la canción de este cuadro real (0, 1 o 2 según la velocidad): por cada uno corre el audio y avanza wT.
; A 100% siempre es uno. Los ciclos de 4 cuadros: 75% = 1,1,1,0; 50% = 1,0,1,0; 125% = 2,1,1,1.
SpeedPattern:
    db 1, 1, 1, 1
    db 1, 1, 1, 0
    db 1, 0, 1, 0
    db 2, 1, 1, 1

AudioSteps:
    ld a, [wPlaying]
    and a
    ret z
    ld a, [wSpeedMode]
    and a
    ld a, 1
    jr z, .go
    ld a, [wSpeedPhase]
    ld b, a
    inc a
    ld [wSpeedPhase], a
    ld a, b
    and 3
    ld b, a
    ld a, [wSpeedMode]
    add a
    add a
    add b
    ld e, a
    ld d, 0
    ld hl, SpeedPattern
    add hl, de
    ld a, [hl]
    and a
    ret z
.go:
    ld [wStepsNow], a
.step:
    call AudioTick
    ld hl, wT
    inc [hl]
    jr nz, .noCarry
    inc hl
    inc [hl]
.noCarry:
    ld hl, wStepsNow
    dec [hl]
    jr nz, .step
    ret

AudioTickStream:
    ld a, [wNr51Out]
    ldh [rNR51], a
    ld [sh_NR51], a

    ld a, [wT]
    ld c, a
    ld a, [wT + 1]
    ld b, a
    ld a, [wLeadIn]
    ld e, a
    ld a, [wLeadIn + 1]
    ld d, a
    ld a, c
    sub e
    ld a, b
    sbc d
    ret c                   ; todavía no empieza el audio

ConsumeSlot:
    ld a, [wRingRead]
    ld b, a
    ld a, [wRingWrite]
    cp b
    jr nz, .have
    ld hl, wUnderrun        ; el bucle principal no alcanzó a decodificar
    inc [hl]
    ret
.have:
    ld a, [wRingReadPtr]
    ld l, a
    ld a, [wRingReadPtr + 1]
    ld h, a
    push hl                 ; inicio del slot, para avanzar después
    ld a, [hl+]
    ld b, a                 ; B = cuenta de pares
    ld a, [hl+]
    and a
    jr z, .noWave
    xor a
    ldh [rNR30], a          ; la wave RAM solo se escribe con el DAC del canal 3 apagado
    ld de, _AUD3WAVERAM
    ld c, 16
.waveLoop:
    ld a, [hl+]
    ld [de], a
    inc de
    dec c
    jr nz, .waveLoop
    jr .pairs
.noWave:
    ld de, 16
    add hl, de
.pairs:
    ld a, b
    and a
    jr z, .advance
.pair:
    ld a, [hl+]
    ld c, a                 ; C = byte bajo de la dirección del registro
    ld a, [hl+]             ; A = valor
    ldh [c], a
    ld e, c
    ld d, HIGH(wShadow)
    ld [de], a              ; sombra del registro
    bit 7, a
    jr z, .nextPair
    ld d, HIGH(wNoteOnCnt)  ; alta de nota (o cualquier registro con el bit 7): se cuenta por registro
    ld a, [de]
    inc a
    ld [de], a
.nextPair:
    dec b
    jr nz, .pair
.advance:
    pop hl
    ld de, RING_SLOT_SIZE
    add hl, de
    ld a, h
    cp HIGH(wAudioRing) + RING_SLOTS * RING_SLOT_SIZE / 256
    jr c, .keep
    ld h, HIGH(wAudioRing)
    ld l, LOW(wAudioRing)
.keep:
    ld a, l
    ld [wRingReadPtr], a
    ld a, h
    ld [wRingReadPtr + 1], a
    ld hl, wRingRead
    inc [hl]
    ret
