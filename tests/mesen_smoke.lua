-- Prueba de humo en Mesen 2: espera N cuadros, lee variables de HRAM y deja el resultado en build/mesen-smoke.txt.
-- Uso: tools\mesen\Mesen.exe --testrunner build\gbband.gb tests\mesen_smoke.lua
-- (requiere Debug.ScriptWindow.AllowIoOsAccess = true en tools/mesen/settings.json)
local frames = 0
-- Mesen no corre desde la carpeta del proyecto: la ruta de salida llega por la variable GBBAND_OUT (absoluta)
local OUT = os.getenv("GBBAND_OUT") or "mesen-smoke.txt"

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
  if frames == 240 then
    local ok, err = pcall(function()
      local names = {}
      for k, _ in pairs(emu.memType) do names[#names + 1] = k end
      table.sort(names)
      local isCgb = emu.read(0xFF80, emu.memType.gameboyMemory)
      local lo = emu.read(0xFF81, emu.memType.gameboyMemory)
      local hi = emu.read(0xFF82, emu.memType.gameboyMemory)
      finish(string.format("hIsCGB=%02X hFrame=%d\nmemTypes: %s\n", isCgb, hi * 256 + lo, table.concat(names, " ")))
    end)
    if not ok then finish("ERROR: " .. tostring(err) .. "\n") end
  end
end

emu.addEventCallback(onEndFrame, emu.eventType.endFrame)
