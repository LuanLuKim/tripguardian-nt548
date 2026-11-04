// The tour's finishing chime, made with Web Audio (no sound file): C5 E5 G5 C6 climbing, then one high sparkle, ~1.2 s, quiet.
// It only plays from the "Xong" click (a user gesture, so the browser allows it).
const KEY = 'tg-tour-muted'

export function isMuted(): boolean {
  try { return localStorage.getItem(KEY) === '1' } catch { return false }
}

export function setMuted(muted: boolean): void {
  try { if (muted) localStorage.setItem(KEY, '1'); else localStorage.removeItem(KEY) } catch { /* storage blocked: the choice lasts until reload */ }
}

let ctx: AudioContext | null = null

export function playCheer(): void {
  if (isMuted()) return
  try {
    const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    ctx ??= new AC()
    void ctx.resume()
    const c = ctx
    const t0 = c.currentTime + 0.03
    const tone = (freq: number, at: number, len: number, type: OscillatorType, peak: number) => {
      const osc = c.createOscillator()
      const gain = c.createGain()
      osc.type = type
      osc.frequency.value = freq
      gain.gain.setValueAtTime(0.0001, t0 + at)
      gain.gain.exponentialRampToValueAtTime(peak, t0 + at + 0.015)
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + at + len)
      osc.connect(gain).connect(c.destination)
      osc.start(t0 + at)
      osc.stop(t0 + at + len + 0.05)
    }
    ;[523.25, 659.25, 783.99, 1046.5].forEach((f, i) => {
      tone(f, i * 0.09, i === 3 ? 0.6 : 0.3, 'sine', 0.13)
      tone(f * 2, i * 0.09, 0.2, 'triangle', 0.025)
    })
    tone(2093, 0.4, 0.7, 'triangle', 0.045)
  } catch { /* no audio on this device: the celebration stays silent */ }
}
