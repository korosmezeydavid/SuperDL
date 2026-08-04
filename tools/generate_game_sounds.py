"""Generates short royalty-free game sound effects as WAV files for SuperDL."""
import math
import random
import struct
import wave
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "src" / "main" / "res" / "raw"
SAMPLE_RATE = 22050


def write_wav(path: Path, samples):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        frames = b"".join(struct.pack("<h", max(-32767, min(32767, int(s)))) for s in samples)
        wf.writeframes(frames)


def envelope(i, total, attack=0.02, release=0.25):
    t = i / SAMPLE_RATE
    dur = total / SAMPLE_RATE
    att = attack
    rel = release
    if t < att:
        return t / att
    if t > dur - rel:
        return max(0.0, (dur - t) / rel)
    return 1.0


def noise_burst(duration, volume=0.35, decay=0.92):
    total = int(SAMPLE_RATE * duration)
    samples = []
    amp = volume
    for i in range(total):
        env = envelope(i, total, 0.001, 0.08)
        samples.append(amp * env * (random.random() * 2 - 1) * 32767)
        amp *= decay
    return samples


def tone(freq, duration, volume=0.28, attack=0.01, release=0.12):
    total = int(SAMPLE_RATE * duration)
    return [
        volume * envelope(i, total, attack, release) * math.sin(2 * math.pi * freq * (i / SAMPLE_RATE)) * 32767
        for i in range(total)
    ]


def thud(duration=0.07, volume=0.4):
    total = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(total):
        t = i / SAMPLE_RATE
        env = envelope(i, total, 0.002, 0.05)
        freq = 180 - t * 900
        samples.append(volume * env * math.sin(2 * math.pi * freq * t) * 32767)
    return samples


def card_flick():
    s = noise_burst(0.06, 0.25, 0.85)
    s += tone(1200, 0.03, 0.08)
    return s


def card_place():
    return thud(0.08, 0.45)


def card_deal():
    s = []
    for _ in range(2):
        s += thud(0.05, 0.3)
        s += [0.0] * int(SAMPLE_RATE * 0.03)
    return s


def game_win():
    s = []
    for freq in (523, 659, 784, 1047):
        s += tone(freq, 0.14, 0.22, 0.01, 0.08)
        s += [0.0] * int(SAMPLE_RATE * 0.02)
    return s


def game_lose():
    s = []
    for freq in (392, 330, 262, 196):
        s += tone(freq, 0.16, 0.2, 0.01, 0.1)
        s += [0.0] * int(SAMPLE_RATE * 0.03)
    return s


def slot_lever():
    s = tone(220, 0.05, 0.35, 0.001, 0.03)
    s += thud(0.06, 0.5)
    return s


def slot_spin():
    total = int(SAMPLE_RATE * 0.55)
    samples = []
    for i in range(total):
        t = i / SAMPLE_RATE
        env = envelope(i, total, 0.02, 0.08)
        freq = 80 + t * 180 + math.sin(t * 40) * 30
        click = 1.0 if int(t * 28) % 2 == 0 else 0.55
        samples.append(env * click * 0.22 * math.sin(2 * math.pi * freq * t) * 32767)
        if i % 97 == 0:
            samples[-1] += 0.15 * 32767
    return samples


def slot_reel_stop():
    s = tone(640, 0.04, 0.3, 0.001, 0.04)
    s += thud(0.04, 0.35)
    return s


def slot_win():
    s = []
    for freq in (440, 554, 659, 880, 1108):
        s += tone(freq, 0.1, 0.24)
        s += [0.0] * int(SAMPLE_RATE * 0.015)
    return s


def slot_jackpot():
    s = []
    for freq in (523, 659, 784, 988, 1175, 1568):
        s += tone(freq, 0.12, 0.26)
        s += tone(freq * 1.25, 0.08, 0.14)
        s += [0.0] * int(SAMPLE_RATE * 0.01)
    return s


def slot_lose():
    s = tone(180, 0.2, 0.25, 0.01, 0.15)
    s += tone(140, 0.25, 0.2, 0.01, 0.2)
    return s


def mb_flat_tire():
    s = tone(420, 0.04, 0.35, 0.001, 0.03)
    s += noise_burst(0.12, 0.55, 0.88)
    s += tone(180, 0.18, 0.3, 0.01, 0.14)
    s += [0.0] * int(SAMPLE_RATE * 0.02)
    s += tone(95, 0.22, 0.28, 0.01, 0.18)
    return s


def mb_accident():
    s = []
    for freq in (880, 520, 280, 140):
        s += tone(freq, 0.05, 0.42, 0.001, 0.04)
    s += noise_burst(0.2, 0.65, 0.9)
    for _ in range(4):
        s += thud(0.07, 0.55)
        s += [0.0] * int(SAMPLE_RATE * 0.025)
    s += tone(110, 0.35, 0.32, 0.01, 0.22)
    return s


def mb_green_light():
    s = tone(330, 0.06, 0.2, 0.005, 0.05)
    s += tone(440, 0.08, 0.24, 0.005, 0.06)
    total = int(SAMPLE_RATE * 0.35)
    for i in range(total):
        t = i / SAMPLE_RATE
        env = envelope(i, total, 0.02, 0.12)
        freq = 120 + t * 220
        s.append(env * 0.28 * math.sin(2 * math.pi * freq * t) * 32767)
        if i % 41 == 0:
            s[-1] += 0.12 * 32767
    s += tone(660, 0.1, 0.22, 0.01, 0.08)
    return s


def mb_stop():
    total = int(SAMPLE_RATE * 0.45)
    samples = []
    for i in range(total):
        t = i / SAMPLE_RATE
        env = envelope(i, total, 0.005, 0.18)
        freq = 2200 - t * 3600
        samples.append(env * 0.35 * math.sin(2 * math.pi * max(80, freq) * t) * 32767)
    s = samples
    s += thud(0.09, 0.5)
    return s


def mb_out_of_gas():
    s = tone(260, 0.12, 0.28, 0.01, 0.08)
    s += tone(200, 0.14, 0.24, 0.01, 0.1)
    s += noise_burst(0.08, 0.3, 0.8)
    s += tone(150, 0.2, 0.26, 0.01, 0.16)
    s += [0.0] * int(SAMPLE_RATE * 0.04)
    s += tone(120, 0.25, 0.22, 0.01, 0.2)
    return s


def mb_speed_limit():
    s = []
    for freq in (880, 880, 660):
        s += tone(freq, 0.09, 0.3, 0.002, 0.05)
        s += [0.0] * int(SAMPLE_RATE * 0.06)
    return s


def mb_mileage():
    total = int(SAMPLE_RATE * 0.28)
    samples = []
    for i in range(total):
        t = i / SAMPLE_RATE
        env = envelope(i, total, 0.01, 0.1)
        freq = 300 + t * 500
        samples.append(env * 0.26 * math.sin(2 * math.pi * freq * t) * 32767)
    s = samples
    s += tone(740, 0.06, 0.18, 0.005, 0.05)
    return s


def mb_safety():
    s = []
    for freq in (523, 784, 1047):
        s += tone(freq, 0.11, 0.26, 0.005, 0.07)
        s += [0.0] * int(SAMPLE_RATE * 0.015)
    return s


def main():
    sounds = {
        "snd_card_flick.wav": card_flick,
        "snd_card_place.wav": card_place,
        "snd_card_deal.wav": card_deal,
        "snd_game_win.wav": game_win,
        "snd_game_lose.wav": game_lose,
        "snd_slot_lever.wav": slot_lever,
        "snd_slot_spin.wav": slot_spin,
        "snd_slot_reel_stop.wav": slot_reel_stop,
        "snd_slot_win.wav": slot_win,
        "snd_slot_jackpot.wav": slot_jackpot,
        "snd_slot_lose.wav": slot_lose,
        "snd_mb_flat_tire.wav": mb_flat_tire,
        "snd_mb_accident.wav": mb_accident,
        "snd_mb_green_light.wav": mb_green_light,
        "snd_mb_stop.wav": mb_stop,
        "snd_mb_out_of_gas.wav": mb_out_of_gas,
        "snd_mb_speed_limit.wav": mb_speed_limit,
        "snd_mb_mileage.wav": mb_mileage,
        "snd_mb_safety.wav": mb_safety,
    }
    for name, builder in sounds.items():
        write_wav(OUT / name, builder())
        print(f"Wrote {OUT / name}")


if __name__ == "__main__":
    main()