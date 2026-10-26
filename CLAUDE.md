# CLAUDE.md - GBBand

Juego de ritmo (estilo Guitar Hero / Rock Band) para **Game Boy Color con compatibilidad DMG**, equivalente de
[NESBand](https://github.com/Xalcker/NESBand). Todo el código lo escribe la IA; el usuario solo pone ideas y no
conoce SM83. Diseño en `docs/diseno.md`, decisiones en `docs/decisiones.md`.

## Convenciones

- **Idioma:** documentación, comentarios y commits en español de México (tuteo, sin voseo ni modismos
  regionales). Identificadores de código en inglés. Textos del juego sin acentos (fuente ASCII de 8×8).
- **Licencia:** GPL-2.0-or-later. Solo canciones y arte originales en git; la música comercial va a
  `songs_src/` y `src/songs/*` (ignorados) y nunca a git ni a Releases.
- **Fines de línea:** LF, excepto `.ps1`, `.bat`, `.cmd` (CRLF). Los `.ps1` van con BOM UTF-8 (PowerShell 5.1
  lee como ANSI los que no lo tienen).
- **Escritura de archivos:** con las herramientas Write/Edit, nunca con heredoc ni redirecciones.
- **Reglas de oro del hardware:** la ISR de VBlank no cambia de banco; VRAM y OAM solo se escriben desde la ISR
  de VBlank; el LCD solo se apaga durante VBlank; no usar el "zombie mode" del APU.
- **No afirmar que algo funciona sin ejecutarlo** (build y emulador). Marcar lo que solo se probó en emulador.
- Se trabaja por fases; al terminar cada una: compilar, probar, capturas, commit, resumen y detenerse.

## Comandos

```bash
.\build.ps1                 # Windows -> build/gbband.gb (+ .sym, .map)      ./build.sh en macOS / Linux
.\build.ps1 -Release        # build/release/gbband-v<versión>.gb + .sha256 + LICENSE   (./build.sh --release)
.\tests\run_tests.ps1       # build + pytest (gráficos y ROM en PyBoy, DMG y CGB)       ./tests/run_tests.sh
uv run gbband build-gfx     # src/chr/*.tiles -> build/chr/*.2bpp y PNG de contacto
uv run gbband build-font    # regenera src/chr/font.tiles (necesita Pillow, grupo dev)
uv run gbband smoke build/gbband.gb   # corre el ROM en DMG y CGB y deja capturas en build/smoke-*/
uv run gbband build-gems    # regenera src/chr/gems.tiles (gemas con sus 4 desplazamientos)
uv run gbband measure-placement   # error y conflictos de las colocaciones A y B con los charts de NESBand
uv run python audio/tormenta.py   # regenera audio/tormenta.txt (proyecto de FamiStudio en texto, componido en Python)
uv run gbband import-song audio/tormenta.txt --name tormenta --title "Tormenta de Neon" --game GBBand   # o un .nsf
uv run gbband reimport [nombre]   # vuelve a importar con las opciones de import.json (conserva drums.json y edits.json)
uv run gbband list-songs          # regenera build/list.asm (el build lo corre solo; --solo / --release)
uv run gbband edit-chart [nombre] # editor visual de charts con "Escuchar" (el mismo stream de la ROM)
GBBAND_COMPLETA=1 .\tests\run_tests.ps1   # las diez canciones (sin la variable, tres representativas)
.\build.ps1 -Colocacion A -Nombre A   # ROM con la colocación A (COLOCACION=A NOMBRE=A ./build.sh)
```

Herramientas (en `tools/`, ignorado por git; cada máquina baja las suyas): RGBDS v1.0.4 en `tools/rgbds/`,
Mesen 2 en `tools/mesen/`. En macOS: `brew install rgbds uv powershell`.
Mesen de pruebas: `tools\mesen\Mesen.exe --testrunner <rom absoluta> <script.lua absoluto>` con
`GBBAND_OUT` apuntando a un archivo absoluto (ver `tests/mesen_smoke.lua`).

## Lecciones aprendidas

- Git Bash convierte los argumentos que empiezan con `/` en rutas de Windows: en patrones de git usar sin barra
  inicial o `MSYS_NO_PATHCONV=1`. Antes de `git clean -x`, correr con `-n`.
- PyBoy sin `bootrom=` corre la animación real del logo de la consola: esperar con `Runner.boot()` antes de
  medir cuadros. `cgb=False` fuerza DMG.
- `rgbfix -p` no basta para 2 MB: hace falta que el banco 127 tenga contenido (ver `docs/decisiones.md`).
- Mesen 2 `--testrunner`: usar rutas absolutas, `emu.memType.gameboyMemory`, y asegurarse de llamar a
  `emu.stop()` incluso si el script falla (si no, queda colgado).
- **PowerShell 5.1 y archivos de código:** nunca usar `Get-Content`/`Set-Content` para editar fuentes (lee como ANSI y
  escribe UTF-8 con BOM: rompe los acentos y rgbasm falla con "Invalid characters 0xEF 0xBB 0xBF"). Usar Edit/Write, o
  `[IO.File]::ReadAllText(ruta, [Text.Encoding]::UTF8)` y `WriteAllText` con `UTF8Encoding($false)`.
- **PyBoy: hooks y entrada.** El tick de PyBoy puede terminar a la mitad de la ISR de VBlank: para ver un estado de
  cuadro completo, enganchar `IsrEnd` con `hook_register(0, addr, cb, ctx)`. Dentro del hook, `button_press` se pierde
  (PyBoy vacía los eventos al final del tick): usar `send_input(WindowEvent.PRESS_..., 1)`; lo lee la ISR del cuadro `wT`.
- **rgbasm:** `INCLUDE` dos veces el mismo `.inc` repite los `DEF ... EQU` y falla. Un caracter suelto se escribe `'0'`, no `"0"`.
- **Alineación en WRAM:** las secciones con dirección fija (`WRAM0[$C700]`) fallan al enlazar si otra sección flotante
  las pisa; las variables van desde `$C900`.
- La ISR de VBlank tiene ~1140 M-cycles: la cola de VRAM debe terminar antes (`wOverrun` lo cuenta). El audio con los 4 canales
  (18 escrituras) y la fila nueva juntos son el peor cuadro.
- **PowerShell y mis scripts de edición:** `R` es un alias de `Invoke-History` y gana a una función con ese nombre (usar `Rep` o
  `Swap`). Una cadena de PowerShell entre comillas simples no admite `'''`. Varios here-strings (`@'...'@`) en un mismo comando
  con llamadas a funciones entre ellos pueden pegarse (me dejó texto de un test dentro de `cli.py`): los archivos largos se
  escriben con Write, no con here-strings.
- **IR y charts:** los charts y el audio nacen de la IR (`ir.py`), nunca uno del otro. Cambiar el generador de charts o de audio
  obliga a `gbband reimport` y a commitear `src/songs/*` (son datos generados, pero van en git: la ROM de release sale de ahí).
- **ISR:** el orden es OAM, cola de VRAM, scroll, audio, control. `wOverrun` y `wFlushLines` miden si la cola cabe en el VBlank.
- **PyBoy y bots:** el menú se maneja con botones de verdad (`playtest.select_in_menu`), no escribiendo en WRAM, porque
  `MenuLoadSong` es lo que fija el banco de la canción.
- Valor de A al arrancar: `$11` en CGB, `$01` en DMG.
