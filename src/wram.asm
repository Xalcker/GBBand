; =============================================================================
; wram.asm - Mapa de WRAM y HRAM
;
; Solo se usa C000-DEFF como un bloque (sin SVBK); DF00-DFFF queda para la pila.
; =============================================================================

SECTION "WRAM ring de audio", WRAM0[$C000]
wAudioRing:: ds RING_SLOTS * RING_SLOT_SIZE      ; 1024 bytes: C000-C3FF

SECTION "WRAM OAM", WRAM0[$C400]
wOam:: ds 160                                    ; origen del OAM DMA (byte alto $C4)

SECTION "WRAM cola de VRAM", WRAM0[$C500]
wVQueue:: ds 256                                 ; entradas: [cuenta | $80 si banco 1][dir lo][dir hi][datos...], 0 = fin

; Sombra de los registros del APU: la dirección es wShadow + byte bajo del registro (sh_NR10 = $C710 para $FF10),
; así la ISR la calcula con un solo `ld e, c`. Los contadores van en la página siguiente con el mismo índice.
SECTION "WRAM sombra del APU", WRAM0[$C700]
wShadow:: ds $10
sh_NR10:: ds 5
sh_NR20:: ds 1
sh_NR21:: ds 4
sh_NR30:: ds 5
sh_NR40:: ds 1
sh_NR41:: ds 4
sh_NR50:: ds 1
sh_NR51:: ds 1
sh_NR52:: ds 1

; Altas de nota (escrituras con el bit 7 en 1) por registro: wNoteOnCnt + byte bajo del registro.
; Las que interesan son NR14 ($14), NR24 ($19), NR34 ($1E) y NR44 ($23); las demás cuentas son ruido.
SECTION "WRAM contadores de notas", WRAM0[$C800]
wNoteOnCnt:: ds $28

SECTION "WRAM variables", WRAM0[$C900]
wState::        ds 1
wDifficulty::   ds 1     ; 0 facil, 1 medio, 2 dificil, 3 experto
wSong::         ds 1     ; canción elegida (lugar en la lista)
wInstrument::   ds 1     ; 0 guitarra, 1 teclado, 2 bajo, 3 bateria
wMenuRow::      ds 1     ; renglón del menú: 0 canción, 1 instrumento, 2 dificultad, 3 fallo
wNoFail::       ds 1     ; 1 = "sin fallo": no se puede perder (y no hay récord)
wLife::         ds 1
wLifeGrace::    ds 1
wFailed::       ds 1     ; 1 = se acabó la vida: el instrumento calla hasta el final y no hay récord
wPct::          ds 1     ; porcentaje del puntaje máximo (0 a 100)
wStars::        ds 1
wDivA::         ds 3     ; dividendo y cociente de Div24By16
wDivB::         ds 2     ; divisor
wDivR::         ds 2     ; resto
wNotesTotal::   ds 2     ; notas de la partida (aciertos + fallos)
wRecHash::      ds 2     ; hash del título y el juego de la canción elegida
wRecKey::       ds 1     ; instrumento * 4 + dificultad
wRecFound::     ds 1
wRecScore::     ds 3     ; el récord leído: puntaje en BCD (3 bytes), iniciales (3) y estrellas (van seguidos: se copian juntos)
wRecInit::      ds 3
wRecStars::     ds 1
wNewScore::     ds 3     ; el puntaje de la partida, en BCD
wNewRecord::    ds 1
wInitials::     ds 3
wInitPos::      ds 1
wInitBuf::      ds 5
wRecText::      ds 20
wOptionsUsed::  ds 1     ; 1 si se jugó con alguna opción distinta de la normal (no hay récord)
wTotalDigits::  ds 3
wPctDigits::    ds 3
wPerfectUnits:: ds 2     ; unidades de puntaje máximo posible con esas notas
wSongBank::     ds 1     ; banco A de la canción elegida
wInstrMask::    ds 1     ; instrumentos con chart en esa canción
wTitleBuf::     ds SONG_TITLE_LEN
wGameBuf::      ds SONG_GAME_LEN
wPlaying::      ds 1     ; 1 mientras suena la canción (la ISR corre el audio y cuenta cuadros)
wT::            ds 2     ; cuadro de la canción: ISRs de VBlank desde el inicio (la ISR lo incrementa al final)
wTJ::           ds 2     ; cuadro con el que se juzga (wT - 1)
wLeadIn::       ds 2
wEndFrame::     ds 2

; --- cola de VRAM y estadísticas de la ISR ---
wVQLen::        ds 1
wQLast::        ds 1     ; bytes de VRAM copiados en el último cuadro
wQMax::         ds 1
wQOverflow::    ds 1
wOverrun::      ds 1     ; la cola de VRAM terminó fuera del VBlank (LY < 144): error
wFlushLines::   ds 1     ; líneas de VBlank que gastó la ISR hasta terminar la cola (máximo)
wLate::         ds 1     ; cuadros atrasados (la ISR llegó con main_loop sin terminar)
wIsrMax::       ds 1     ; tiempo máximo de la ISR en unidades de 64 M-cycles (DIV)
wIsrLast::      ds 1     ; tiempo de la última ISR (para ver la distribución en las pruebas)
wCpuMax::       ds 1     ; líneas de pantalla máximas que tardó el bucle principal en un cuadro de juego
wCpuSum::       ds 4     ; suma de líneas
wCpuFrames::    ds 2
wOamDirty::     ds 1

; --- audio ---
wRingRead::     ds 1     ; contadores libres de 8 bits: la ISR avanza uno, el bucle principal el otro
wRingWrite::    ds 1
wRingReadPtr::  ds 2
wRingWritePtr:: ds 2
wStrBank::      ds 1
wStrPtr::       ds 2
wEmptyRun::     ds 1
wStreamEnd::    ds 1
wUnderrun::     ds 1
wDecSlot::      ds 2
wDecBase::      ds 1
wDecCh::        ds 1
wMuted::        ds 1     ; 1 = el instrumento (CH1) está callado por un fallo
wNr51Out::      ds 1

; --- autopista ---
wSpeed::        ds 2     ; px por cuadro, punto fijo 8.8
wScrollF::      ds 1     ; byte bajo del scroll (va justo antes de wScroll)
wScroll::       ds 2     ; posición del scroll, 8.8 (SCY = byte alto; los 8 bits de abajo van en wScrollF)
wBuildQ::       ds 2     ; fila (con signo) que se arma ahora
wBCur::         ds 2     ; cursor del chart del armador de filas
wBFs::          ds 3     ; cuadro de la siguiente nota por la velocidad, 24 bits 8.8
wNMask::        ds 1     ; carriles de la siguiente nota (0 = no hay más)
wNRow::         ds 2     ; su fila de tiles (con signo)
wNOff::         ds 1     ; y su desplazamiento (0, 2, 4 o 6 px)
wNV::           ds 1     ; desplazamiento / 2
wPLane::        ds 1
wPBase::        ds 1
wQDest::        ds 2
wRowHas::       ds 1     ; la fila que se arma tiene gemas
wRowFlags::     ds 32    ; por fila del fondo: 1 si en VRAM tiene gemas (si no, armar una fila vacía no escribe nada)
wRowTiles::     ds 10
wRowAttr::      ds 10

; --- juez ---
wJCur::         ds 2
wJFrame::       ds 2
wJEnd::         ds 1
wJQHead::       ds 1
wJQCount::      ds 1
wJQFLo::        ds 16
wJQFHi::        ds 16
wJQMask::       ds 16
wJQSus::        ds 16    ; la entrada es de notas sostenidas (con cola)
wTailEnd::      ds 10    ; por carril: cuadro en que termina su cola ($FFFF = todavía no se sabe)
wHold::         ds 1     ; carriles que se están sosteniendo
wJQStar::       ds 16    ; la entrada es una nota de frase estelar
wTmpStar::      ds 1
wStarEnergy::   ds 1
wStarActive::   ds 1
wStarTimer::    ds 1
wStarRun::      ds 1     ; aciertos de la frase estelar en curso
wStarFail::     ds 1     ; ya se falló una nota de la frase en curso
wHoldTick::     ds 5
wNEnd::         ds 1     ; la entrada que se leyó es un fin de cola
wNSust::        ds 1     ; la nota que se leyó tiene cola
wTailOpen::     ds 1     ; carriles con una cola abierta en la fila que se arma
wPressLanes::   ds 1
wTryBit::       ds 1
wScanI::        ds 1
wScanE::        ds 1
wHeldPrev::     ds 1
wHeld::         ds 1

; --- puntaje (dígitos decimales, el primero es el más significativo) ---
wScoreDigits::  ds 6
wComboDigits::  ds 3
wMaxComboDigits:: ds 3
wHitsDigits::   ds 3
wMissDigits::   ds 3
wAirCount::     ds 1
wMult::         ds 1
wScoreUnits::   ds 2     ; suma de multiplicadores de las notas acertadas (unidades de 50 puntos)
wHudDirty::     ds 1
wQSrc::         ds 2
wQDigit::       ds 1

; --- opciones (seis valores seguidos: el índice del renglón de la pantalla de opciones indexa wOpt) ---
wOpt::
wOptMirror::    ds 1     ; ESPEJO: 0 no, 1 si
wOptSpeed::     ds 1     ; VELOCIDAD: 0 100%, 1 75%, 2 50%, 3 125%
wOptFall::      ds 1     ; CAIDA DE NOTAS: 0 auto, 1 a 4 la de facil, medio, dificil, experto
wOptPractice::  ds 1     ; PRACTICA: 0 no, 1 hasta 1/4, 2 hasta 1/2, 3 hasta 3/4, 4 hasta el final
wOptStart::     ds 1     ; INICIO DE LA PRACTICA: 0 principio, 1 a 3 un cuarto, la mitad, tres cuartos
wOptFx::        ds 1     ; EFECTO AL FALLAR: 0 si, 1 solo sonido, 2 no
wOptRow::       ds 1     ; renglón de la pantalla de opciones
wMirrorOn::     ds 1     ; espejo activo en esta partida (la batería lo ignora)
wSpeedMode::    ds 1     ; velocidad de la partida (copia de wOptSpeed)
wSpeedPhase::   ds 1     ; cuadro dentro del ciclo de 4 de la velocidad
wStepsNow::     ds 1
wJT::           ds 2     ; el wT de la última vez que se juzgó
wTSave::        ds 2
wStepSpd::      ds 3     ; avance del scroll por cuadro real, 8.16

; --- efecto al fallar ---
wFxCool::       ds 1     ; cuadros hasta poder repetir el efecto
wShake::        ds 1     ; cuadros que le quedan al temblor y al tinte rojo
wSfxLast::      ds 1     ; el último efecto de sonido (para no repetirlo)
wSfxLeft::      ds 1     ; cuadros que le quedan al efecto de sonido (+1: el último restaura el canal)
wSfxPtr::       ds 2
wSfxBase::      ds 1     ; byte bajo de NRx0 del canal que usa el efecto
wSfxFirst::     ds 1
wSfxDuty::      ds 1
wSfxEnv::       ds 1

wVQDummy::      ds 128   ; destino inofensivo cuando la cola se llena

; ---- HRAM --------------------------------------------------------------------
SECTION "HRAM", HRAM
hIsCGB::     ds 1        ; valor de A al arrancar: $11 en Game Boy Color; en DMG es otro ($01 en la DMG original)
hFrame::     ds 2        ; cuadros desde el arranque (16 bits, lo incrementa la ISR de VBlank)
hBank::      ds 1        ; banco de ROM conmutable actual
hCGB::       ds 1        ; 1 si es Game Boy Color
hPad::       ds 1        ; botones apretados en el último VBlank (activos en alto)
hPadNew::    ds 1        ; botones que se apretaron desde que el bucle principal lo borró
hVBlank::    ds 1        ; la ISR lo pone en 1; el bucle principal lo borra
hMainBusy::  ds 1        ; 1 mientras el bucle principal trabaja (si llega un VBlank, es un cuadro atrasado)
hScy::       ds 1
hLcdc::      ds 1
hWy::        ds 1        ; WY de la Window (la ISR lo copia: sube durante la pausa)
hIsrT0::     ds 1
hPassLY::    ds 1
hScx::       ds 1        ; SCX de la autopista (el temblor al fallar)
hPalFx::     ds 1        ; 1 = la ISR pone el tinte rojo, 2 = vuelve a lo normal, 0 = nada
hOamDma::    ds 10       ; copia de la rutina de OAM DMA (corre desde HRAM)
