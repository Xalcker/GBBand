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
- Valor de A al arrancar: `$11` en CGB, `$01` en DMG.
