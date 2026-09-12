"""Egytényezős választék a NYERS klatt5 körül – csak olyan szabályzókkal,
amelyekről MÉRÉSSEL igazoltuk, hogy ez az eSpeak tényleg figyelembe veszi."""
import sys, subprocess, wave, numpy as np
S = r"C:\Users\msn\AppData\Local\Temp\claude\C--Users-msn-Documents-Audacity\f2795c4b-c00d-4bf5-ad52-819a4ba3c6ae\scratchpad"
sys.path.insert(0, r"C:\Users\msn\Documents\Audacity\SuperDownloader")
sys.path.insert(0, S)
from superdl import retrovoice as RV
import kozos
from pathlib import Path

exe, data = RV._espeak()
VMAPPA = Path(r"C:\Users\msn\Documents\Audacity\SuperDownloader\bin\espeak-ng-data\voices\!v")
M = ("Üdvözöllek a szuper dé el retró játékok menüjében! "
     "Ez a hang a klatt szintetizátorral készült. "
     "Kettő, hét, kilenc. Kérlek, válassz a menüből!")

# nev -> (a valtozat-fajl sorai, hangmagassag, tempo, minta-tartas)
SOR = {
    "1_alap":       ("", 12, 145, 1),
    "2_monoton":    ("pitch 74 12", 12, 145, 1),
    "3_melyebb":    ("", 0, 145, 1),
    "4_lassabb":    ("", 12, 118, 1),
    "5_formansok":  ("formant 1 79 100 100\nformant 2 75 100 100\n"
                     "formant 3 79 100 100", 12, 145, 1),
    "6_nincs_remeges": ("flutter 0", 12, 145, 1),
    "7_kemeny_massalhangzo": ("consonants 130 130", 12, 145, 1),
    "8_dobozos":    ("echo 12 20", 12, 145, 1),
    "9_szemcses":   ("", 12, 145, 2),
}


def ment(x, fs, p):
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(fs)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


for nev, (sorok, hm, temp, tart) in SOR.items():
    valt = "klatt5"
    if sorok:
        valt = "bl" + nev.split("_")[0]
        (VMAPPA / valt).write_text(
            "language variant\nname %s\nklatt 5\n%s\n" % (valt, sorok),
            encoding="utf-8")
    ki = r"C:\Users\msn\Documents\bl_%s.wav" % nev
    cmd = [exe, "-v", "hu+" + valt, "-p", str(hm), "-s", str(temp), "-w", ki]
    if data:
        cmd += ["--path", str(Path(data).parent)]
    cmd.append(M)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("%-22s HIBA: %s" % (nev, (r.stderr or "")[:120]))
        continue
    x, fs = kozos.betolt(ki)
    if tart > 1:                       # minta-tartás: enyhe „lépcsőzés”
        n = (len(x) // tart) * tart
        y = x[:n].reshape(-1, tart)
        x = np.repeat(y[:, 0], tart)
        ment(x, fs, ki)
    pt, b, d, fm = kozos.teljes_pont(x, fs)
    print("%-22s pont %5.2f | F0 %5.1f | %4.1f mp | F %.0f/%.0f/%.0f"
          % (nev, pt, kozos.f0_median(x, fs), len(x) / fs,
             fm["f1"], fm["f2"], fm["f3"]))
