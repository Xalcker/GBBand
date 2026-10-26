# Decisiones

Decisiones menores que tomé yo, con su motivo. Las de gran tamaño se proponen aquí antes de implementarse.

## Fase 1

1. **RGBDS fijo en v1.0.4.** La sintaxis cambió entre 0.x y 1.0 (por eso se usa `DEF ... EQU`). `tools/` está en
   `.gitignore`: cada máquina baja su RGBDS (Windows: zip en `tools/rgbds/`; macOS: `brew install rgbds`).
2. **WRAM sin SVBK.** Se usa `C000-DFFF` como un solo bloque; DMG y CGB comparten mapa.
3. **ROM de 2 MB forzado con un mensaje en el banco 127.** `rgblink -p` solo rellena hasta el último banco usado y
   `rgbfix -p` hasta una potencia de 2. Poner un dato (el mensaje de prueba del MBC5) en el banco 127 hace que el
   enlazador genere los 128 bancos. Cuando existan las canciones, un archivo `rom_size.asm` hará este trabajo.
4. **Texto: tile = código ASCII.** La fuente (Bongo-8 Mono, CC0) ocupa los tiles `$20`-`$5A` y solo tiene
   mayúsculas, sin acentos. Se dibuja en color 3 (el más oscuro).
5. **Gráficos como texto.** `src/chr/*.tiles` (`.`, `0`-`3` por píxel) se convierte con `gbband build-gfx` a
   `build/chr/*.2bpp` más un PNG de contacto para revisarlos. El 2bpp del GB entrelaza los planos por fila
   (distinto del NES). El PNG se escribe con la biblioteca estándar, sin Pillow.
6. **`hIsCGB` guarda el valor crudo de A al arrancar** (`$11` en CGB, `$01` en la DMG original; otros modelos
   dan otros valores). Solo se compara contra `$11`.
7. **Comando de PC `gbband`** (`uv run gbband ...`), equivalente a `nesband`.
8. **Pruebas con PyBoy como juez principal y Mesen 2 como verificación cruzada.**
   - PyBoy 2.8.1 sin `bootrom=` corre la animación real del logo de la consola, así que los primeros cuadros no
     son del juego. El corredor espera con `Runner.boot()` hasta que `hFrame` cuenta un cuadro.
   - `cgb=False` fuerza DMG aunque el header sea compatible con CGB.
   - Mesen 2 2.1.1 en `--testrunner`: el script de Lua no corre con la carpeta del proyecto como directorio de
     trabajo, así que la salida va a una ruta absoluta (`GBBAND_OUT`). El tipo de memoria es
     `emu.memType.gameboyMemory` (no `gbMemory`). Se necesita `Debug.ScriptWindow.AllowIoOsAccess=true` en
     `tools/mesen/settings.json`. Un script que falla sin llamar a `emu.stop` deja a Mesen colgado.
9. **`-Solo` / `SOLO`** se aceptan pero no hacen nada hasta que exista la lista de canciones (fase 3).
