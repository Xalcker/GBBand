// Pruebas de gbplayer.js con Node: lo que se oye en "Escuchar" corresponde a lo que dicen los registros.
const GbPlayer = require("../gbband_tools/gbplayer.js");

const SR = 44100;
const rms = (a, from, to) => { let s = 0; for (let i = from; i < to; i++) s += a[i] * a[i]; return Math.sqrt(s / Math.max(to - from, 1)); };
const crossings = (a, from, to) => { let c = 0; for (let i = from + 1; i < to; i++) if (a[i - 1] < 0 && a[i] >= 0) c++; return c * SR / (to - from); };
const frameAt = (f) => Math.round(f * SR / GbPlayer.FPS);

(async () => {
  const result = {};
  // CH1: 440 Hz, duty 50 %, volumen 12 fijo
  let r = await GbPlayer.render({ frames: [[0, null, [[0x11, 0x80], [0x12, 0xC0], [0x13, 0xD6], [0x14, 0x86]]]] }, 30, { sampleRate: SR });
  result.pulse_hz = crossings(r.stems[0], frameAt(5), frameAt(30));
  result.pulse_rms = rms(r.stems[0], frameAt(5), frameAt(30));
  result.other_channels_silent = [1, 2, 3].every((c) => rms(r.stems[c], 0, r.stems[c].length) < 1e-6);
  // el mismo con volumen 6: la mitad de amplitud
  r = await GbPlayer.render({ frames: [[0, null, [[0x11, 0x80], [0x12, 0x60], [0x13, 0xD6], [0x14, 0x86]]]] }, 30, { sampleRate: SR });
  result.half_ratio = rms(r.stems[0], frameAt(5), frameAt(30)) / result.pulse_rms;
  // envolvente por hardware: volumen 15 que cae con periodo 1 (un paso cada 1/64 s): se apaga en ~0.23 s
  r = await GbPlayer.render({ frames: [[0, null, [[0x11, 0x80], [0x12, 0xF1], [0x13, 0xD6], [0x14, 0x86]]]] }, 30, { sampleRate: SR });
  result.env_start = rms(r.stems[0], 0, frameAt(3));
  result.env_end = rms(r.stems[0], frameAt(20), frameAt(30));
  // NRx2 = 0 apaga el DAC: silencio
  r = await GbPlayer.render({ frames: [[0, null, [[0x11, 0x80], [0x12, 0xC0], [0x13, 0xD6], [0x14, 0x86]]], [10, null, [[0x12, 0x00]]]] }, 30, { sampleRate: SR });
  result.after_off = rms(r.stems[0], frameAt(12), frameAt(30));
  result.before_off = rms(r.stems[0], frameAt(2), frameAt(9));
  // CH3: 110 Hz con el triángulo de la wave RAM
  const tri = []; for (let i = 0; i < 16; i += 1) tri.push(((15 - 2 * i < 0 ? 0 : 15 - 2 * i) << 4) | (15 - 2 * i - 1 < 0 ? 0 : 15 - 2 * i - 1));
  const wave = [0xFE, 0xDC, 0xBA, 0x98, 0x76, 0x54, 0x32, 0x10, 0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF];
  r = await GbPlayer.render({ frames: [[0, wave, [[0x1A, 0x80], [0x1C, 0x20], [0x1D, 0xAC], [0x1E, 0x85]]]] }, 40, { sampleRate: SR });
  result.wave_hz = crossings(r.stems[2], frameAt(5), frameAt(40));
  result.wave_rms = rms(r.stems[2], frameAt(5), frameAt(40));
  // CH4: ruido con energía y silencio al apagar
  r = await GbPlayer.render({ frames: [[0, null, [[0x21, 0xF0], [0x22, 0x43], [0x23, 0x80]]], [10, null, [[0x21, 0x00]]]] }, 20, { sampleRate: SR });
  result.noise_rms = rms(r.stems[3], frameAt(1), frameAt(9));
  result.noise_after = rms(r.stems[3], frameAt(12), frameAt(20));
  // la mezcla es la suma de los canales
  r = await GbPlayer.render({ frames: [[0, null, [[0x11, 0x80], [0x12, 0xC0], [0x13, 0xD6], [0x14, 0x86], [0x21, 0xF0], [0x22, 0x43], [0x23, 0x80]]]] }, 10, { sampleRate: SR });
  let maxDiff = 0; for (let i = 0; i < r.audio.length; i++) maxDiff = Math.max(maxDiff, Math.abs(r.audio[i] - r.stems.reduce((s, st) => s + st[i], 0)));
  result.mix_error = maxDiff;
  result.mix_peak = Math.max(...r.audio.map(Math.abs));
  console.log(JSON.stringify(result));
})();