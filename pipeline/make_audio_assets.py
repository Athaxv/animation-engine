"""
Synthesize the royalty-free sound library: public/audio/sfx/*.wav and public/audio/music/*.wav

    python pipeline/make_audio_assets.py           # (re)build everything
    python pipeline/make_audio_assets.py --only boom,whoosh

Everything is generated from scratch with numpy (no samples, no licences) into the synth/
sub-folders. Better sounds go one level up and win when they share a name:
public/audio/sfx/<name>.mp3|wav (ElevenLabs: pipeline/eleven_sfx.py, or your own files) and
public/audio/music/<mood>.mp3|wav.
"""
import argparse, wave
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SFX = ROOT / "public" / "audio" / "sfx" / "synth"
MUSIC = ROOT / "public" / "audio" / "music" / "synth"
SR = 44100
rng = np.random.default_rng(7)


# ---------------------------------------------------------------- helpers
def t_(dur):
    return np.arange(int(dur * SR)) / SR


def env(n, a=0.005, r=0.1, shape=3.0):
    """attack seconds, exponential decay over the rest."""
    e = np.ones(n)
    na = max(1, int(a * SR))
    e[:na] = np.linspace(0, 1, na)
    tail = np.arange(n - na) / SR
    e[na:] = np.exp(-tail / max(r, 1e-3) * (shape / 3.0))
    return e


def sweep(f0, f1, dur, kind="exp"):
    t = t_(dur)
    f = f0 * (f1 / f0) ** (t / dur) if kind == "exp" else np.linspace(f0, f1, len(t))
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def lowpass(x, cutoff):
    """one-pole low-pass; cutoff may be an array (sweeps)."""
    cutoff = np.broadcast_to(np.asarray(cutoff, float), x.shape)
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def highpass(x, cutoff):
    return x - lowpass(x, cutoff)


def noise(dur):
    return rng.uniform(-1, 1, int(dur * SR))


def norm(x, peak=0.9):
    m = np.max(np.abs(x)) or 1
    return x / m * peak


def save(path, x, stereo=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    x = np.clip(x, -1, 1)
    if stereo and x.ndim == 1:
        x = np.stack([x, x], 1)
    data = (x * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2 if data.ndim == 2 else 1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print("  wrote", path.relative_to(ROOT))


# ---------------------------------------------------------------- sfx
def sfx_whoosh():
    d = 0.45; n = int(d * SR)
    e = np.sin(np.linspace(0, np.pi, n)) ** 2
    return norm(lowpass(noise(d), np.linspace(400, 3500, n) * e + 300) * e, 0.8)


def sfx_pop():
    d = 0.09
    return norm(sweep(900, 250, d) * env(int(d * SR), 0.002, 0.03), 0.8)


def sfx_boing():
    d = 0.6; t = t_(d)
    f = 180 + 120 * np.sin(2 * np.pi * 14 * t) * np.exp(-t * 4) + 160 * t
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.3 * np.sin(4 * np.pi * np.cumsum(f) / SR)
    return norm(x * env(len(t), 0.003, 0.25))


def sfx_bonk():
    d = 0.35; n = int(d * SR)
    body = sweep(320, 140, d) * env(n, 0.001, 0.06)
    knock = np.sin(2 * np.pi * 780 * t_(d)) * env(n, 0.001, 0.025)
    click = highpass(noise(d), 2000) * env(n, 0.0005, 0.006)
    return norm(body + 0.6 * knock + 0.5 * click)


def sfx_ding():
    d = 1.4; t = t_(d); n = len(t)
    x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * k) for f, a, k in
            ((1318, 1.0, 2.5), (2637, 0.4, 4), (3951, 0.2, 6), (1975, 0.25, 3)))
    return norm(x * env(n, 0.002, 2.0), 0.7)


def sfx_boom():
    """the meme bass hit"""
    d = 1.5; t = t_(d); n = len(t)
    sub = sweep(95, 38, d) * np.exp(-t * 2.2)
    hit = lowpass(noise(d), 900) * env(n, 0.001, 0.08)
    x = np.tanh(2.5 * (sub + 0.5 * hit))
    return norm(x)


def sfx_thud():
    d = 0.4; t = t_(d)
    return norm(np.tanh(3 * sweep(120, 45, d) * np.exp(-t * 14)) + 0.3 * lowpass(noise(d), 500) * np.exp(-t * 30))


def sfx_riser():
    d = 2.0; n = int(d * SR); t = t_(d)
    e = (t / d) ** 2
    x = 0.6 * sweep(200, 1400, d) + lowpass(noise(d), np.linspace(300, 6000, n))
    return norm(x * e, 0.75)


def sfx_record_scratch():
    d = 0.45; t = t_(d)
    f = 900 + 700 * np.sin(2 * np.pi * 4.5 * t)
    x = lowpass(noise(d), f) * (1 + np.sign(np.sin(2 * np.pi * 9 * t))) * 0.5
    return norm(x * env(len(t), 0.005, 0.3))


def sfx_poof():
    d = 0.5; n = int(d * SR)
    return norm(lowpass(noise(d), np.linspace(2500, 300, n)) * env(n, 0.004, 0.15), 0.8)


def sfx_slide_up():
    d = 0.6
    return norm(sweep(400, 1700, d) * env(int(d * SR), 0.01, 0.5), 0.6)


def sfx_slide_down():
    d = 0.7
    return norm(sweep(1600, 300, d) * env(int(d * SR), 0.01, 0.6), 0.6)


def sfx_buzzer():
    d = 0.7; t = t_(d)
    x = np.sign(np.sin(2 * np.pi * 140 * t)) + 0.6 * np.sign(np.sin(2 * np.pi * 147 * t))
    return norm(lowpass(x, 2500) * env(len(t), 0.005, 0.6, 1.0), 0.55)


def sfx_correct():
    a, b = sfx_ding_short(1046), sfx_ding_short(1568)
    x = np.zeros(int(0.7 * SR)); x[:len(a)] += a; s = int(0.12 * SR); x[s:s + len(b)] += b
    return norm(x, 0.7)


def sfx_ding_short(f):
    d = 0.5; t = t_(d)
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * np.exp(-t * 7)


def sfx_glitch():
    d = 0.35; n = int(d * SR)
    x = np.repeat(rng.uniform(-1, 1, n // 300 + 1), 300)[:n] * (rng.uniform(size=n) > 0.3)
    x += np.sign(np.sin(2 * np.pi * 60 * t_(d))) * 0.4
    return norm(x * env(n, 0.001, 0.3, 1.0), 0.6)


def sfx_sparkle():
    d = 0.9; x = np.zeros(int(d * SR))
    for i, f in enumerate((1568, 2093, 2637, 3136, 4186)):
        s = int(i * 0.07 * SR)
        y = np.sin(2 * np.pi * f * t_(0.5)) * np.exp(-t_(0.5) * 9)
        x[s:s + len(y)] += y[:len(x) - s]
    return norm(x, 0.6)


def sfx_tick():
    d = 0.06
    return norm(highpass(noise(d), 3000) * env(int(d * SR), 0.0005, 0.008) + np.sin(2 * np.pi * 2200 * t_(d)) * env(int(d * SR), 0.0005, 0.01), 0.6)


def sfx_cartoon_run():
    d = 0.8; t = t_(d)
    x = np.sin(2 * np.pi * (500 + 250 * np.sign(np.sin(2 * np.pi * 18 * t))) * t)
    return norm(x * env(len(t), 0.01, 0.7, 1.0), 0.45)


def sfx_drum_hit():
    d = 0.6; t = t_(d)
    return norm(np.tanh(3 * sweep(160, 50, d) * np.exp(-t * 9)) + 0.5 * highpass(noise(d), 1500) * np.exp(-t * 25))


SFX_LIB = {k[4:]: v for k, v in dict(globals()).items() if k.startswith("sfx_") and k != "sfx_ding_short"}


# ---------------------------------------------------------------- music
def note_hz(n):                       # MIDI note -> Hz
    return 440.0 * 2 ** ((n - 69) / 12)


def pluck(f, dur, bright=0.5):
    """Karplus-Strong pluck (pizzicato / ukulele-ish)."""
    n = int(dur * SR); p = max(2, int(SR / f))
    buf = rng.uniform(-1, 1, p)
    out = np.empty(n)
    decay = 0.996 - (1 - bright) * 0.01
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = decay * 0.5 * (buf[i % p] + buf[(i + 1) % p])
    return out * env(n, 0.002, dur * 0.6)


def soft_synth(f, dur, cutoff=1800):
    t = t_(dur)
    x = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t + 0.3) + 0.15 * np.sin(6 * np.pi * f * t)
    return x * env(len(t), 0.01, dur * 0.5)


def pad(freqs, dur):
    t = t_(dur)
    x = sum(np.sin(2 * np.pi * f * t + i) + 0.4 * np.sin(2 * np.pi * f * 1.004 * t) for i, f in enumerate(freqs))
    e = np.minimum(1, np.minimum(t / 0.4, (dur - t) / 0.4))
    return x * e / len(freqs)


def hat(dur=0.05):
    return highpass(noise(dur), 6000) * env(int(dur * SR), 0.0005, 0.015)


def kick():
    d = 0.3; t = t_(d)
    return np.tanh(2.5 * sweep(120, 45, d) * np.exp(-t * 12))


def mix_in(buf, x, at, gain=1.0):
    s = int(at * SR)
    e = min(len(buf), s + len(x))
    if s < len(buf):
        buf[s:e] += x[:e - s] * gain


def music_quirky():
    """bouncy pizzicato, 116 BPM, C major - sitcom / 'In this town' energy"""
    bpm = 116; beat = 60 / bpm; bars = 8
    buf = np.zeros(int(bars * 4 * beat * SR) + SR)
    prog = [(48, [60, 64, 67]), (53, [60, 65, 69]), (55, [59, 62, 67]), (48, [60, 64, 67]),
            (45, [57, 60, 64]), (53, [57, 60, 65]), (55, [59, 62, 65]), (48, [55, 60, 64])]
    mel = [72, 74, 76, 79, 76, 74, 72, None, 77, 76, 74, 72, 74, None, 71, None]
    for b, (root, chord) in enumerate(prog):
        t0 = b * 4 * beat
        for k in range(4):
            mix_in(buf, pluck(note_hz(root - 12 + (7 if k % 2 else 0)), beat * 0.9, 0.3), t0 + k * beat, 0.9)
            mix_in(buf, kick(), t0 + k * beat, 0.5 if k % 2 == 0 else 0.0)
            for h in (0, 0.5):
                mix_in(buf, hat(), t0 + (k + h) * beat, 0.25)
            for nn in chord:
                mix_in(buf, pluck(note_hz(nn), beat * 0.4, 0.8), t0 + (k + 0.5) * beat, 0.22)
        for k in range(8):
            nn = mel[(b * 8 + k) % len(mel)]
            if nn and (b % 2 == 0 or k % 2 == 0):
                mix_in(buf, pluck(note_hz(nn + (0 if b < 4 else 2)), beat * 0.45, 0.9), t0 + k * beat / 2, 0.45)
    return norm(buf[: int(bars * 4 * beat * SR)], 0.8)


def music_curious():
    """mysterious-but-light arpeggio, 92 BPM, A minor - 'What if' explainer vibe"""
    bpm = 92; beat = 60 / bpm; bars = 8
    buf = np.zeros(int(bars * 4 * beat * SR) + SR)
    prog = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]] * 2
    for b, chord in enumerate(prog):
        t0 = b * 4 * beat
        mix_in(buf, pad([note_hz(n - 12) for n in chord], 4 * beat), t0, 0.35)
        mix_in(buf, soft_synth(note_hz(chord[0] - 24), 4 * beat * 0.95), t0, 0.5)
        arp = chord + [chord[0] + 12] + chord[::-1][1:] + [chord[1] + 12]
        for k in range(16):
            mix_in(buf, soft_synth(note_hz(arp[k % len(arp)] + 12), beat * 0.35), t0 + k * beat / 4, 0.28)
        for k in range(4):
            mix_in(buf, kick(), t0 + k * beat, 0.35 if k in (0, 2) else 0.0)
            mix_in(buf, hat(0.04), t0 + (k + 0.5) * beat, 0.18)
    return norm(lowpass(buf, 5000)[: int(bars * 4 * beat * SR)], 0.8)


def music_tension():
    """low drone + ticking pulse for the twist / cliffhanger"""
    bpm = 100; beat = 60 / bpm; bars = 4
    dur = bars * 4 * beat
    t = t_(dur)
    x = 0.5 * pad([note_hz(40), note_hz(47), note_hz(52)], dur)
    x += 0.25 * np.sin(2 * np.pi * note_hz(28) * t) * (0.6 + 0.4 * np.sin(2 * np.pi * t / (2 * beat)))
    for k in range(bars * 4 * 2):
        mix_in(x, hat(0.03) * 2, k * beat / 2, 0.35 if k % 2 == 0 else 0.15)
    for k in range(bars):
        mix_in(x, kick(), k * 4 * beat, 0.6)
    return norm(x, 0.8)


MUSIC_LIB = {k[6:]: v for k, v in dict(globals()).items() if k.startswith("music_")}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    only = set(filter(None, a.only.split(",")))
    print("sfx:")
    for name, fn in SFX_LIB.items():
        if not only or name in only:
            save(SFX / f"{name}.wav", fn())
    print("music:")
    for name, fn in MUSIC_LIB.items():
        if not only or name in only:
            save(MUSIC / f"{name}.wav", fn(), stereo=True)
