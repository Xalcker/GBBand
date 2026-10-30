; =============================================================================
; hardware.inc - Direcciones y bits de los registros del Game Boy
; (escrito para GBBand; referencia: Pan Docs, https://gbdev.io/pandocs/)
; =============================================================================

; --- Control del LCD ---------------------------------------------------------
DEF rDIV  EQU $FF04     ; contador que sube cada 256 ciclos T (64 M-cycles)
DEF rLCDC EQU $FF40     ; control de pantalla
DEF rSTAT EQU $FF41     ; estado y fuentes de la interrupción STAT
DEF rSCY  EQU $FF42     ; scroll vertical del fondo
DEF rSCX  EQU $FF43     ; scroll horizontal del fondo
DEF rLY   EQU $FF44     ; línea que se está dibujando (144 a 153 = VBlank)
DEF rLYC  EQU $FF45     ; línea que dispara la interrupción STAT
DEF rDMA  EQU $FF46     ; OAM DMA: byte alto de la dirección de origen
DEF rBGP  EQU $FF47     ; paleta del fondo (DMG)
DEF rOBP0 EQU $FF48     ; paleta de sprites 0 (DMG)
DEF rOBP1 EQU $FF49     ; paleta de sprites 1 (DMG)
DEF rWY   EQU $FF4A     ; posición Y de la Window
DEF rWX   EQU $FF4B     ; posición X de la Window + 7

DEF LCDCF_ON      EQU %10000000
DEF LCDCF_WIN9C00 EQU %01000000   ; la Window usa el mapa $9C00
DEF LCDCF_WINON   EQU %00100000
DEF LCDCF_BG8000  EQU %00010000   ; datos de tiles del fondo en modo $8000
DEF LCDCF_BG9C00  EQU %00001000   ; el fondo usa el mapa $9C00
DEF LCDCF_OBJ16   EQU %00000100   ; sprites de 8x16
DEF LCDCF_OBJON   EQU %00000010
DEF LCDCF_BGON    EQU %00000001

; --- Color de la CGB ---------------------------------------------------------
DEF rVBK   EQU $FF4F    ; banco de VRAM (0 o 1)
DEF rBCPS  EQU $FF68    ; índice de paleta de fondo (bit 7 = autoincremento)
DEF rBCPD  EQU $FF69    ; dato de paleta de fondo
DEF rOCPS  EQU $FF6A
DEF rOCPD  EQU $FF6B
DEF rSVBK  EQU $FF70    ; banco de WRAM (GBBand no lo usa)

; --- Control, interrupciones, sonido -----------------------------------------
DEF rP1   EQU $FF00
DEF rIF   EQU $FF0F
DEF rIE   EQU $FFFF
DEF IEF_VBLANK EQU %00000001
DEF IEF_STAT   EQU %00000010
DEF IEF_SERIAL EQU %00001000

; --- Puerto serie (cable link) --------------------------------------------------
DEF rSB   EQU $FF01         ; byte que sale y, al terminar la transferencia, el que llegó
DEF rSC   EQU $FF02         ; bit 7 = transfiriendo, bit 0 = reloj interno (1, maestro) o externo (0, esclavo)

DEF rNR10 EQU $FF10
DEF rNR11 EQU $FF11
DEF rNR12 EQU $FF12
DEF rNR13 EQU $FF13
DEF rNR14 EQU $FF14
DEF rNR21 EQU $FF16
DEF rNR22 EQU $FF17
DEF rNR23 EQU $FF18
DEF rNR24 EQU $FF19
DEF rNR30 EQU $FF1A
DEF rNR31 EQU $FF1B
DEF rNR32 EQU $FF1C
DEF rNR33 EQU $FF1D
DEF rNR34 EQU $FF1E
DEF rNR41 EQU $FF20
DEF rNR42 EQU $FF21
DEF rNR43 EQU $FF22
DEF rNR44 EQU $FF23
DEF rNR50 EQU $FF24
DEF rNR51 EQU $FF25
DEF rNR52 EQU $FF26
DEF _AUD3WAVERAM EQU $FF30

; --- Memoria -----------------------------------------------------------------
DEF _VRAM   EQU $8000
DEF _SCRN0  EQU $9800   ; mapa del fondo
DEF _SCRN1  EQU $9C00   ; mapa de la Window
DEF _SRAM   EQU $A000
DEF _OAMRAM EQU $FE00

; --- Cartucho MBC5 -----------------------------------------------------------
DEF rRAMG    EQU $0000  ; $0A habilita la SRAM
DEF rROMB0   EQU $2000  ; banco de ROM, bits 0-7
DEF rROMB1   EQU $3000  ; banco de ROM, bit 8
DEF rRAMB    EQU $4000  ; banco de SRAM (0 a 15)
DEF RAMG_ENABLE EQU $0A

; Valor de A al arrancar en una Game Boy Color
DEF BOOT_A_CGB EQU $11
