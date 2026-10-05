"""
Generates video/music.wav: an upbeat, warm, royalty-free track synced to
timeline.json. Every bar there has a chord and a drum "energy":

    none   pad + sparse arpeggio
    riser  noise riser into the next section
    light  kick on 1 and 3, soft clap, quarter-note bass
    full   four-on-the-floor groove, bass, 16th arpeggio, hook melody
    calm   half-time and gentle (used for complaint and prayer)
    build  snare roll + riser into a drop
    end    final hit and tail

    python music.py

Everything is synthesized with numpy, so there is nothing to license.
"""

import json
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
TL = json.loads((HERE / "timeline.json").read_text(encoding="utf-8"))

SR = 48000
DUR = TL["duration"]
N = int(SR * DUR)
BEAT = 60 / TL["bpm"]
BAR = BEAT * 4
S16 = BEAT / 4

rng = np.random.default_rng(11)

BUSES = {name: np.zeros((2, N)) for name in ("music", "drums", "fx")}
kicks = []  # (time, amount) for sidechain ducking

CHORDS = {"D": (50, "maj"), "Bm": (47, "min"), "G": (55, "maj"), "Em": (52, "min"), "A": (57, "maj")}


# ---------------------------------------------------------------- helpers

def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def tones(chord):
    root, quality = CHORDS[chord]
    third = 3 if quality == "min" else 4
    return root, [root, root + third, root + 7, root + 12]


def timeline(seconds):
    return np.arange(int(seconds * SR)) / SR


def add(signal, start, bus="music", pan=0.0):
    i = int(round(start * SR))
    if i >= N or i < 0:
        return
    signal = signal[: N - i]
    gl = np.cos((pan + 1) * np.pi / 4)
    gr = np.sin((pan + 1) * np.pi / 4)
    BUSES[bus][0, i : i + len(signal)] += signal * gl
    BUSES[bus][1, i : i + len(signal)] += signal * gr


def smooth(x, width):
    width = max(1, int(width))
    return np.convolve(x, np.ones(width) / width, mode="same")


def noise(n):
    return rng.standard_normal(n)


def env_adsr(n, attack=0.005, release=0.03):
    env = np.ones(n)
    a = min(int(attack * SR), n)
    r = min(int(release * SR), n)
    if a:
        env[:a] = np.linspace(0, 1, a)
    if r:
        env[n - r :] *= np.linspace(1, 0, r)
    return env


# ---------------------------------------------------------------- instruments

def kick(amp):
    t = timeline(0.45)
    freq = 46 + 120 * np.exp(-t * 30)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    body = np.sin(phase) * np.exp(-t * 7)
    click = noise(len(t)) * np.exp(-t * 500) * 0.25
    return np.tanh((body + click) * 1.6) * amp


def clap(amp):
    t = timeline(0.35)
    n = noise(len(t))
    band = smooth(n - smooth(n, 10), 3)
    env = np.zeros(len(t))
    for offset in (0, 0.009, 0.019):
        k = t >= offset
        env[k] = np.maximum(env[k], np.exp(-(t[k] - offset) * (70 if offset < 0.019 else 16)))
    return band * env * amp * 1.8


def hat(amp, open_=False):
    t = timeline(0.3 if open_ else 0.07)
    n = noise(len(t))
    high = n - smooth(n, 3)
    return high * np.exp(-t * (13 if open_ else 70)) * amp


def bass(freq, seconds, amp):
    t = timeline(seconds)
    wave_ = sum(np.sin(2 * np.pi * freq * k * t) / k * np.exp(-0.35 * k) for k in range(1, 8))
    wave_ += 0.35 * np.sin(2 * np.pi * freq * t)  # sub weight
    decay = 0.55 + 0.45 * np.exp(-t * 6)
    return np.tanh(wave_ * 0.9) * decay * env_adsr(len(t), 0.004, 0.04) * amp


def pluck(freq, amp, decay=5.0, seconds=0.8):
    t = timeline(seconds)
    tone = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t * 8)
    return tone * np.exp(-t * decay) * np.minimum(1, t / 0.003) * amp


def lead(freq, seconds, amp):
    t = timeline(seconds + 0.25)
    vibrato = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t / 0.2)
    phase = 2 * np.pi * np.cumsum(freq * vibrato) / SR
    tone = np.sin(phase) + 0.28 * np.sin(3 * phase) + 0.12 * np.sin(5 * phase)
    env = np.minimum(1, t / 0.012) * np.where(t < seconds, 1.0, np.exp(-(t - seconds) * 18))
    env *= 0.75 + 0.25 * np.exp(-t * 6)
    return tone * env * amp


def bell(freq, amp, seconds=2.5):
    t = timeline(seconds)
    partials = [(1, 1), (2.0, 0.35), (2.76, 0.18), (5.4, 0.06)]
    tone = sum(w * np.sin(2 * np.pi * freq * m * t) * np.exp(-t * (1.8 + m * 0.8)) for m, w in partials)
    return tone * np.minimum(1, t / 0.003) * amp


def pad_voice(freq, seconds, amp):
    t = timeline(seconds)
    wave_ = (
        np.sin(2 * np.pi * freq * t)
        + 0.6 * np.sin(2 * np.pi * freq * 1.004 * t + 1.3)
        + 0.6 * np.sin(2 * np.pi * freq * 0.996 * t + 2.1)
        + 0.2 * np.sin(2 * np.pi * freq * 2 * t)
    )
    return wave_ / 2.4 * amp * env_adsr(len(t), 0.25, 0.6)


def riser(seconds, amp):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    raw = noise(n)
    out = np.zeros(n)
    chunk = 2048
    for i in range(0, n, chunk):
        k = i / n
        width = int(40 - 37 * k)
        out[i : i + chunk] = (raw - smooth(raw, width))[i : i + chunk] * (0.3 + 0.7 * k)
    sweep = 2 * np.pi * np.cumsum(220 * 2 ** (3 * t / seconds)) / SR
    return (out * 0.6 + 0.25 * np.sin(sweep)) * (t / seconds) ** 2 * amp


def impact(amp):
    t = timeline(1.8)
    freq = 34 + 40 * np.exp(-t * 8)
    boom = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 2.2)
    crash = noise(len(t))
    crash = (crash - smooth(crash, 2)) * np.exp(-t * 3.5) * 0.35
    return (np.tanh(boom * 1.4) + crash) * amp


def swish(amp, seconds=0.28):
    n = int(seconds * SR)
    x = noise(n)
    x = x - smooth(x, 6)
    return x * np.sin(np.linspace(0, np.pi, n)) ** 2 * amp


def tick(amp, freq=2300):
    t = timeline(0.05)
    return (0.6 * np.sin(2 * np.pi * freq * t) + 0.4 * noise(len(t))) * np.exp(-t * 90) * amp


# ---------------------------------------------------------------- arrangement

MOTIF = [  # (16th step, midi, length in 16ths) over two bars, D major pentatonic
    (0, 74, 2), (3, 76, 1), (4, 78, 2), (8, 81, 3), (12, 78, 2), (14, 76, 2),
    (16, 74, 2), (19, 71, 1), (20, 74, 2), (24, 76, 3), (28, 69, 2), (30, 71, 2),
]
LEAD_BARS = {5, 6, 9, 10, 15, 16, 26, 27, 28}
ARP_PATTERN = [0, 1, 2, 3, 2, 1, 2, 3]

bars = TL["bars"]

for b, bar in enumerate(bars):

    t0 = b * BAR
    kind = bar["drums"]
    root, notes = tones(bar["chord"])

    # pad: every bar, louder when calm
    pad_amp = 0.085 if kind == "calm" else 0.06
    for k, note in enumerate(notes):
        add(pad_voice(hz(note), BAR + 0.5, pad_amp), t0, pan=(-0.5, 0.5, -0.25, 0.25)[k])

    # drums
    if kind == "full":
        for beat in range(4):
            add(kick(0.72), t0 + beat * BEAT, "drums")
            kicks.append((t0 + beat * BEAT, 0.5))
            add(hat(0.2), t0 + (beat + 0.5) * BEAT, "drums", pan=0.25)
            add(hat(0.08), t0 + (beat + 0.25) * BEAT, "drums", pan=-0.2)
            add(hat(0.08), t0 + (beat + 0.75) * BEAT, "drums", pan=-0.2)
        add(clap(0.36), t0 + BEAT, "drums")
        add(clap(0.36), t0 + 3 * BEAT, "drums")
        add(hat(0.12, open_=True), t0 + 3.5 * BEAT, "drums", pan=0.3)

    if kind == "light":
        for beat in (0, 2):
            add(kick(0.6), t0 + beat * BEAT, "drums")
            kicks.append((t0 + beat * BEAT, 0.35))
        add(clap(0.22), t0 + 3 * BEAT, "drums")
        for e in range(8):
            add(hat(0.09), t0 + e * BEAT / 2 + BEAT / 4, "drums", pan=0.2)

    if kind == "calm":
        add(kick(0.32), t0, "drums")
        kicks.append((t0, 0.15))
        for e in range(8):
            add(hat(0.04), t0 + e * BEAT / 2, "drums", pan=0.35 * (-1) ** e)

    if kind == "build":
        for beat in range(4):
            add(kick(0.65), t0 + beat * BEAT, "drums")
            kicks.append((t0 + beat * BEAT, 0.4))
        for s in range(16):  # 8ths then 16ths, crescendo
            if s < 8 and s % 2:
                continue
            add(clap(0.1 + 0.32 * s / 15), t0 + s * S16, "drums")
        add(riser(BAR, 0.24), t0, "fx")

    if kind == "riser":
        add(riser(BAR, 0.2), t0, "fx")

    if kind == "end":
        add(impact(0.6), t0, "fx")
        add(kick(0.75), t0, "drums")
        for i, note in enumerate([62, 66, 69, 74, 78, 81, 86]):
            add(bell(hz(note + 12), 0.09, 3.5), t0 + 0.05 + i * 0.07, "fx", pan=(i - 3) * 0.15)

    # bass
    low = root - 12 if root >= 50 else root
    if kind in ("full", "build"):
        pattern = [0, 0, 12, 0, 0, 0, 12, 7]
        for e, offset in enumerate(pattern):
            add(bass(hz(low + offset - 12), BEAT / 2 * 0.9, 0.17), t0 + e * BEAT / 2)
    elif kind == "light":
        for beat in range(4):
            add(bass(hz(low - 12), BEAT * 0.9, 0.15), t0 + beat * BEAT)
    elif kind in ("calm", "none", "riser"):
        add(bass(hz(low - 12), BAR * 0.95, 0.1), t0)
    elif kind == "end":
        add(bass(hz(low - 12), BAR, 0.15), t0)

    # arpeggio
    if kind in ("full", "build"):
        step, amp, decay = S16, 0.065, 7
    elif kind in ("light", "riser", "none"):
        step, amp, decay = BEAT / 2, 0.065, 5
    elif kind == "calm":
        step, amp, decay = BEAT, 0.05, 3
    else:
        step = None
    if step:
        k = 0
        t = t0
        while t < t0 + BAR - 1e-6:
            note = notes[ARP_PATTERN[k % 8]] + 12
            add(pluck(hz(note), amp, decay), t, pan=0.4 * np.sin(k * 1.3))
            t += step
            k += 1

    # hook melody: two-bar motif, first half on even bars of each pair
    if b in LEAD_BARS:
        second_half = (b in (6, 10, 16, 27))
        for step16, note, length in MOTIF:
            if (step16 >= 16) == second_half:
                add(lead(hz(note), length * S16 * 0.95, 0.12), t0 + (step16 % 16) * S16, pan=0.1)

# ---------------------------------------------------------------- hits synced to visuals

s = TL["scenes"]

add(bell(hz(74 + 12), 0.12), 0.15, "fx")                       # coin flip lands
add(swish(0.14, 0.6), 0.0, "fx")
add(impact(0.3), s["hook"][0], "fx")
add(impact(0.5), s["options"][0], "fx")                         # drop into the options
add(impact(0.4), s["how"][0], "fx")
add(impact(0.6), s["cta"][0], "fx")

for i in range(3):                                              # hook lines on the beat
    add(pluck(hz(74 + i * 2), 0.11, 4), s["hook"][0] + i * BEAT * 2, "fx", pan=(i - 1) * 0.3)

for i, option in enumerate(TL["options"]):                      # 3D flip-in of each tile
    t0 = s["options"][0] + i * TL["optionLength"]
    add(swish(0.12), t0 - 0.12, "fx", pan=0.3)
    if option["type"] not in ("complaint", "prayer"):
        add(bell(hz(86), 0.06), t0 + 0.05, "fx", pan=-0.2)

spot = TL["chipSpotlight"]                                     # chip spotlight switches
for i, option in enumerate(TL["options"]):
    if len(option["chips"]) < 2:
        continue
    t0 = s["options"][0] + i * TL["optionLength"]
    calm = option["type"] in spot["calmTypes"]
    step = (spot["calmBeatsPerStep"] if calm else spot["beatsPerStep"]) * BEAT
    k = 0
    while spot["start"] + k * step < spot["end"]:
        at = t0 + spot["start"] + k * step
        if calm:
            add(bell(hz(81 + (k % 2) * 4), 0.035, 1.5), at, "fx", pan=0.2)
        else:
            add(pluck(hz((86, 88, 90, 93)[k % 4]), 0.06, 9, 0.3), at, "fx", pan=0.25 * (-1) ** k)
        k += 1

how0 = s["how"][0]
add(tick(0.12), how0 + 1.5, "fx")                               # tap card
t = how0 + 2.6
while t < how0 + 4.6:                                           # typing
    add(tick(0.045, 2600 + rng.integers(-300, 300)), t, "fx", pan=rng.uniform(-0.2, 0.2))
    t += 0.07 + rng.uniform(0, 0.05)
add(tick(0.14), how0 + 5.0, "fx")                               # tap send
for i, note in enumerate([69, 73, 76, 81]):                     # sent chime
    add(bell(hz(note + 12), 0.1), how0 + 5.5 + i * 0.07, "fx", pan=(i - 1.5) * 0.25)

for i in range(4):                                              # promise cube turns
    add(swish(0.11, 0.22), s["promise"][0] + i * BEAT * 2 - 0.05, "fx")
    add(tick(0.08, 900), s["promise"][0] + i * BEAT * 2 + 0.12, "fx")

# ---------------------------------------------------------------- sidechain

duck = np.ones(N)
span = int(0.4 * SR)
curve = np.exp(-np.arange(span) / SR / 0.11)
for t, depth in kicks:
    i = int(t * SR)
    seg = duck[i : i + span]
    duck[i : i + span] = np.minimum(seg, 1 - depth * curve[: len(seg)])

# ---------------------------------------------------------------- reverb + mix

def impulse(seconds, seed):
    n = int(seconds * SR)
    r = np.random.default_rng(seed).standard_normal(n)
    return r * np.exp(-np.linspace(0, 7, n))


def convolve(x, ir):
    size = 1 << int(np.ceil(np.log2(len(x) + len(ir))))
    return np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x)]


def reverb(bus, seconds, mix):
    out = np.zeros_like(bus)
    for ch in range(2):
        wet = convolve(bus[ch], impulse(seconds, ch + 1))
        scale = np.max(np.abs(bus[ch])) / (np.max(np.abs(wet)) + 1e-9)
        out[ch] = bus[ch] + mix * wet * scale
    return out


music = reverb(BUSES["music"], 2.2, 0.3) * duck
drums = reverb(BUSES["drums"], 0.8, 0.08)
fx = reverb(BUSES["fx"], 2.6, 0.35)

mix = music * 1.0 + drums * 0.85 + fx * 0.9

fade_in = int(0.15 * SR)
fade_out = int(2.4 * SR)
mix[:, :fade_in] *= np.linspace(0, 1, fade_in)
mix[:, -fade_out:] *= np.cos(np.linspace(0, np.pi / 2, fade_out)) ** 2

# soft bus limiter, then about -14 LUFS (check with ffmpeg ebur128)
GAIN = 0.7
mix = np.tanh(mix / np.max(np.abs(mix)) * 1.6) / np.tanh(1.6) * GAIN

pcm = (mix.T * 32767).astype(np.int16)
with wave.open(str(HERE / "music.wav"), "wb") as f:
    f.setnchannels(2)
    f.setsampwidth(2)
    f.setframerate(SR)
    f.writeframes(pcm.tobytes())

print(f"wrote {HERE / 'music.wav'} ({DUR}s, {TL['bpm']} bpm)")
