# Compila la ROM: src/main.asm -> build/gbband.gb (+ .sym y .map con símbolos para depurar)
# Uso:  .\build.ps1
#       .\build.ps1 -Release [-Version 0.1.0]
# -Release arma la ROM para publicar en build\release\gbband-v<versión>.gb con su suma de verificación
#   (.sha256) y la licencia. La versión sale del archivo VERSION si no se indica. (Cuando haya canciones,
#   solo entrarán las que git versiona: la música de juegos comerciales no se distribuye.)
# -Nombre prueba deja build\gbband-prueba.gb sin pisar build\gbband.gb.
# -Colocacion A|B elige como se colocan las gemas (B por omision: 4 desplazamientos verticales; A: una fila de tiles).
# -Solo <patrón>[,<patrón>] queda reservado para compilar un subconjunto de canciones (fase 3); por ahora no hace nada.
param([switch]$Release, [string]$Version = '', [string]$Nombre = '', [string[]]$Solo = @(), [ValidateSet('A','B')][string]$Colocacion = 'B')
$ErrorActionPreference = 'Continue'   # (los avisos de rgbasm van a stderr: se revisa $LASTEXITCODE)
$root = $PSScriptRoot
if ($Release -and -not $Version) { $Version = (Get-Content (Join-Path $root 'VERSION') -TotalCount 1).Trim() }

# Usa RGBDS de tools/rgbds si existe; si no, el que esté en el PATH. Las rutas van con / para que el mismo
# script sirva con pwsh en macOS y Linux
function Buscar-Rgbds($nombre) {
    foreach ($exe in "$nombre.exe", $nombre) {
        $ruta = Join-Path $root "tools/rgbds/$exe"
        if (Test-Path $ruta -PathType Leaf) { return $ruta }
    }
    return $nombre
}
$rgbasm = Buscar-Rgbds 'rgbasm'
$rgblink = Buscar-Rgbds 'rgblink'
$rgbfix = Buscar-Rgbds 'rgbfix'

if ($Solo.Count -gt 0) { Write-Host '-Solo aun no hace nada (no hay lista de canciones)' -ForegroundColor Yellow }

$out = if ($Release) { Join-Path $root 'build/release' } else { Join-Path $root 'build' }
New-Item -ItemType Directory -Force $out | Out-Null
$base = if ($Release) { "gbband-v$Version" } elseif ($Nombre) { "gbband-$Nombre" } else { 'gbband' }

# Gráficos: src/chr/*.tiles -> build/chr/*.2bpp (y PNG de contacto para revisarlos)
& uv run --project $root gbband build-gfx | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host 'Error al convertir los graficos' -ForegroundColor Red; exit 1 }

$obj = "$out/$base.o"
$opciones = @(); if ($Colocacion -eq 'A') { $opciones += '-D', 'PLACEMENT_B=0' }
& $rgbasm @opciones -I (Join-Path $root 'src') -I (Join-Path $root 'build') -o $obj (Join-Path $root 'src/main.asm')
if ($LASTEXITCODE -ne 0) { Write-Host 'Error al ensamblar' -ForegroundColor Red; exit 1 }

$rom = "$out/$base.gb"
& $rgblink -n "$out/$base.sym" -m "$out/$base.map" -p 0xFF -o $rom $obj
if ($LASTEXITCODE -ne 0) { Write-Host 'Error al enlazar' -ForegroundColor Red; exit 1 }

# Header: logo y sumas (-v), relleno $FF (-p), compatible con CGB (-c), no japonés (-j), MBC5 con 8 KB de SRAM con batería
& $rgbfix -v -p 0xFF -c -j -t GBBAND -m MBC5+RAM+BATTERY -r 2 $rom
if ($LASTEXITCODE -ne 0) { Write-Host 'Error al ajustar el header' -ForegroundColor Red; exit 1 }
Remove-Item $obj

if ($Release) {
    $hash = (Get-FileHash $rom -Algorithm SHA256).Hash.ToLower()
    [IO.File]::WriteAllText("$rom.sha256", "$hash  $base.gb`n")
    Copy-Item (Join-Path $root 'LICENSE') "$out/LICENSE"
    Write-Host "Release: $rom ($hash)"
} else {
    Write-Host "OK: $rom ($((Get-Item $rom).Length) bytes)"
}
