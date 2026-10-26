// gbplayer.js - un APU de Game Boy mínimo para "Escuchar" en el editor de charts.
//
// Toca el MISMO stream de registros (FRS) que la ROM: el servidor lo decodifica a escrituras por cuadro
// (player = {frames: [[cuadro, wave|null, [[registro, valor], ...]], ...]}, el registro es el byte bajo de $FF10-$FF23)
// y esto las aplica cuadro por cuadro y sintetiza el audio. No es una emulación exacta del chip: no hay barrido,
// contadores de longitud ni mezcla analógica (el juego no usa ni los barridos ni las longitudes), y la envolvente
// corre a 64 Hz de reloj global. Alcanza para oír lo mismo que en el cartucho: alturas, duty, volumen y batería.
//
// GbPlayer.render(player, frames, {sampleRate, stems, onProgress, yieldFn}) -> {audio, stems, sampleRate}
// con `stems` = 4 Float32Array (CH1 a CH4) cuya suma es `audio`.

const GbPlayer = (() => {
  const FPS = 4194304 / 70224;
  const DUTY = [[0, 0, 0, 0, 0, 0, 0, 1], [1, 0, 0, 0, 0, 0, 0, 1], [1, 0, 0, 0, 0, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 0]];
  const CH_BASE = [0x10, 0x15, 0x1A, 0x1F]; // registro bajo de NRx0 de cada canal

  function newPulse() {
    return { on: false, dac: false, x: 0, duty: 0, vol: 0, envVol: 0, envPeriod: 0, envUp: false, envCount: 0, phase: 0 };
  }

  function createApu(sampleRate) {
    const apu = {
      sr: sampleRate,
      p1: newPulse(), p2: newPulse(),
      wave: { on: false, dac: false, x: 0, code: 0, phase: 0, ram: new Uint8Array(32) },
      noise: { on: false, dac: false, vol: 0, envVol: 0, envPeriod: 0, envUp: false, envCount: 0, shift: 0, width: false, div: 0, lfsr: 0x7FFF, clock: 0 },
      envClock: 0, // muestras acumuladas hacia el siguiente reloj de 64 Hz
    };
    return apu;
  }

  function writeEnv(ch, v) {
    ch.envVol = v >> 4; ch.envUp = !!(v & 8); ch.envPeriod = v & 7;
    ch.dac = (v & 0xF8) !== 0;
    if (!ch.dac) ch.on = false;
  }

  function trigger(ch) {
    if (!ch.dac) return;
    ch.on = true; ch.vol = ch.envVol; ch.envCount = ch.envPeriod;
  }

  function write(apu, reg, v) {
    switch (reg) {
      case 0x11: apu.p1.duty = v >> 6; break;
      case 0x12: writeEnv(apu.p1, v); break;
      case 0x13: apu.p1.x = (apu.p1.x & 0x700) | v; break;
      case 0x14: apu.p1.x = (apu.p1.x & 0xFF) | (v & 7) << 8; if (v & 0x80) trigger(apu.p1); break;
      case 0x16: apu.p2.duty = v >> 6; break;
      case 0x17: writeEnv(apu.p2, v); break;
      case 0x18: apu.p2.x = (apu.p2.x & 0x700) | v; break;
      case 0x19: apu.p2.x = (apu.p2.x & 0xFF) | (v & 7) << 8; if (v & 0x80) trigger(apu.p2); break;
      case 0x1A: apu.wave.dac = !!(v & 0x80); if (!apu.wave.dac) apu.wave.on = false; break;
      case 0x1C: apu.wave.code = (v >> 5) & 3; break;
      case 0x1D: apu.wave.x = (apu.wave.x & 0x700) | v; break;
      case 0x1E: apu.wave.x = (apu.wave.x & 0xFF) | (v & 7) << 8; if ((v & 0x80) && apu.wave.dac) apu.wave.on = true; break;
      case 0x21: writeEnv(apu.noise, v); break;
      case 0x22: apu.noise.shift = v >> 4; apu.noise.width = !!(v & 8); apu.noise.div = v & 7; break;
      case 0x23:
        if (v & 0x80) { trigger(apu.noise); apu.noise.lfsr = 0x7FFF; }
        break;
      default: break;
    }
  }

  function envelopeTick(ch) {
    if (!ch.on || !ch.envPeriod) return;
    if (--ch.envCount <= 0) {
      ch.envCount = ch.envPeriod;
      if (ch.envUp && ch.vol < 15) ch.vol++;
      else if (!ch.envUp && ch.vol > 0) ch.vol--;
    }
  }

  function pulseSample(p, sr) {
    if (!p.on) return 0;
    const s = DUTY[p.duty][Math.floor(p.phase * 8) & 7] * (p.vol / 15);
    p.phase += (131072 / (2048 - p.x)) / sr;
    if (p.phase >= 1) p.phase -= Math.floor(p.phase);
    return s;
  }

  // Sintetiza `n` muestras de cada canal en out[0..3] a partir de `at`
  function synth(apu, out, at, n) {
    const sr = apu.sr;
    for (let i = 0; i < n; i++) {
      apu.envClock += 64;
      if (apu.envClock >= sr) {
        apu.envClock -= sr;
        envelopeTick(apu.p1); envelopeTick(apu.p2); envelopeTick(apu.noise);
      }
      out[0][at + i] = pulseSample(apu.p1, sr);
      out[1][at + i] = pulseSample(apu.p2, sr);
      const w = apu.wave;
      let s = 0;
      if (w.on && w.code) {
        s = (w.ram[Math.floor(w.phase * 32) & 31] >> (w.code - 1)) / 15;
        w.phase += (65536 / (2048 - w.x)) / sr;
        if (w.phase >= 1) w.phase -= Math.floor(w.phase);
      }
      out[2][at + i] = s;
      const z = apu.noise;
      s = 0;
      if (z.on) {
        s = (z.lfsr & 1 ? 0 : 1) * (z.vol / 15);
        z.clock += (262144 / ((z.div || 0.5) * Math.pow(2, z.shift))) / sr;
        while (z.clock >= 1) {
          z.clock -= 1;
          const bit = (z.lfsr ^ (z.lfsr >> 1)) & 1;
          z.lfsr = (z.lfsr >> 1) | (bit << 14);
          if (z.width) z.lfsr = (z.lfsr & ~0x40) | (bit << 6);
        }
      }
      out[3][at + i] = s;
    }
  }

  async function render(player, frames, opts = {}) {
    const sr = opts.sampleRate || 44100;
    const apu = createApu(sr);
    const total = Math.round(frames * sr / FPS);
    const out = [0, 1, 2, 3].map(() => new Float32Array(total));
    const list = player.frames;
    let next = 0, last = 0;
    for (let f = 0; f < frames; f++) {
      while (next < list.length && list[next][0] <= f) {
        const [, wave, regs] = list[next++];
        if (wave) for (let i = 0; i < 16; i++) { apu.wave.ram[2 * i] = wave[i] >> 4; apu.wave.ram[2 * i + 1] = wave[i] & 15; }
        for (const [reg, value] of regs) write(apu, reg, value);
      }
      const end = Math.round((f + 1) * sr / FPS);
      synth(apu, out, last, end - last);
      last = end;
      if (opts.onProgress && f % 300 === 0) { opts.onProgress(f / frames); if (opts.yieldFn) await opts.yieldFn(); }
    }
    // quita la componente continua de cada canal (el chip tiene una salida acoplada en alterna)
    const stems = out.map((x) => {
      const y = new Float32Array(x.length);
      let prevX = 0, prevY = 0;
      for (let i = 0; i < x.length; i++) {
        prevY = x[i] - prevX + 0.995 * prevY;
        prevX = x[i];
        y[i] = prevY * 0.25; // cuatro canales: la suma nunca pasa de 1
      }
      return y;
    });
    const audio = new Float32Array(total);
    for (const stem of stems) for (let i = 0; i < total; i++) audio[i] += stem[i];
    return { audio, stems, sampleRate: sr };
  }

  return { FPS, render, createApu, write, synth };
})();
if (typeof module !== "undefined") module.exports = GbPlayer;
