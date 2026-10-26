-- Verificación cruzada en Mesen 2 (un segundo emulador): arranca el juego, aprieta Start en el menú, deja correr
-- la canción sin tocar nada y guarda lo que quedó en WRAM más una captura de pantalla.
--
--   $env:GBBAND_OUT = "C:\ruta\absoluta\mesen.txt"; $env:GBBAND_SYM = "C:\ruta\absoluta\gbband.sym"
--   tools\mesen\Mesen.exe --testrunner C:\ruta\absoluta\build\gbband.gb C:\ruta\absoluta\tests\mesen_smoke.lua
--
-- Mesen no corre desde la carpeta del proyecto: todas las rutas llegan por variables de entorno y son absolutas.
-- Requiere Debug.ScriptWindow.AllowIoOsAccess = true en tools/mesen/settings.json. Si el script falla sin
-- llamar a emu.stop(), Mesen se queda colgado: por eso todo va dentro de pcall.
local OUT = os.getenv("GBBAND_OUT") or "mesen-smoke.txt"
local SYM = os.getenv("GBBAND_SYM")
local START_AT, READ_AT = 120, 900

local frames = 0
local symbols = {}

local function loadSymbols()
  local f = io.open(SYM, "r")
  if not f then return end
  for line in f:lines() do
    local addr, name = line:match("^%x+:(%x+)%s+(%S+)")
    if addr then symbols[name] = tonumber(addr, 16) end
  end
  f:close()
end

local function rd(name, n)
  local v = 0
  for i = (n or 1) - 1, 0, -1 do
    v = v * 256 + emu.read(symbols[name] + i, emu.memType.gameboyMemory)
  end
  return v
end

local function digits(name, n)
  local s = ""
  for i = 0, n - 1 do s = s .. tostring(emu.read(symbols[name] + i, emu.memType.gameboyMemory)) end
  return s
end

local function finish(text)
  local f = io.open(OUT, "w")
  if f then
    f:write(text)
    f:close()
  end
  emu.stop(0)
end

local function onEndFrame()
  frames = frames + 1

  if frames == READ_AT then
    local ok, err = pcall(function()
      local png = emu.takeScreenshot()
      local shot = io.open(OUT .. ".png", "wb")
      if shot then shot:write(png) shot:close() end
      finish(string.format(
        "hIsCGB=%02X state=%d playing=%d wT=%d late=%d underrun=%d misses=%s hits=%s score=%s vq_max=%d overrun=%d\n",
        rd("hIsCGB"), rd("wState"), rd("wPlaying"), rd("wT", 2), rd("wLate"), rd("wUnderrun"),
        digits("wMissDigits", 3), digits("wHitsDigits", 3), digits("wScoreDigits", 6), rd("wQMax"), rd("wOverrun")))
    end)
    if not ok then finish("ERROR: " .. tostring(err) .. "\n") end
  end
end

-- La entrada se manda en el evento inputPolled (justo antes de que el juego lea el control)
local function onInputPolled()
  if frames >= START_AT and frames < START_AT + 3 then
    emu.setInput({ start = true }, 0, 0)
  end
end

local ok, err = pcall(loadSymbols)
if not ok then finish("ERROR sym: " .. tostring(err) .. "\n") end
emu.addEventCallback(onEndFrame, emu.eventType.endFrame)
emu.addEventCallback(onInputPolled, emu.eventType.inputPolled)
