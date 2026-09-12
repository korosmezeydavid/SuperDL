"""Végleges hangsúly-minták: BraiLab-fekvés + a stressAdd hangolása."""
import sys, subprocess, numpy as np
S = r"C:\Users\msn\AppData\Local\Temp\claude\C--Users-msn-Documents-Audacity\f2795c4b-c00d-4bf5-ad52-819a4ba3c6ae\scratchpad"
sys.path.insert(0, r"C:\Users\msn\Documents\Audacity\SuperDownloader")
sys.path.insert(0, S)
from superdl import retrovoice as RV
import kozos
from pathlib import Path

exe, data = RV._espeak()
VM = Path(r"C:\Users\msn\Documents\Audacity\SuperDownloader\bin\espeak-ng-data\voices\!v")
M = ("Üdvözöllek a szuper dé el retró játékok menüjében! "
     "Ez a hang a klatt szintetizátorral készült. "
     "Kettő, hét, kilenc. Kérlek, válassz a menüből!")

ALAP = "pitch 45 110"

VALT = {
  "H1_fekves":        ALAP,
  "H2_tagabb_dallam": "pitch 40 125",
  "H3_eros_hangsuly": ALAP + "\nstressAdd 20 20 10 10 0 0 -20 -20",
  "H4_lapos_hangsuly": ALAP + "\nstressAdd -10 -10 -10 -10 0 0 -40 -40",
  "H5_fekves_dobozos": ALAP + "\necho 12 20",
}


def dallam(x, fs):
    kl = int(0.030*fs); lep = int(0.010*fs); f0 = []
    for s in range(0, len(x)-kl, lep):
        seg = x[s:s+kl] - x[s:s+kl].mean()
        if np.sqrt((seg**2).mean()) < 0.02:
            continue
        r = np.correlate(seg, seg, "full")[len(seg)-1:]
        lo, hi = int(fs/250), int(fs/55)
        if hi >= len(r):
            break
        i = lo + int(np.argmax(r[lo:hi]))
        if r[i] > 0.35*r[0]:
            f0.append(fs/i)
    z = np.array(f0)
    if len(z) < 10:
        return None
    fh = np.log2(z/np.median(z))*12
    return np.median(z), fh.std(), np.percentile(fh, 90)-np.percentile(fh, 10)


for nev, sorok in VALT.items():
    v = "bl" + nev.split("_")[0].lower()
    VM.joinpath(v).write_text(
        "language variant\nname %s\nklatt 5\n%s\n" % (v, sorok), encoding="utf-8")
    ki = r"C:\Users\msn\Documents\hs_%s.wav" % nev
    cmd = [exe, "-v", "hu+"+v, "-p", "0", "-s", "138", "-w", ki]
    if data:
        cmd += ["--path", str(Path(data).parent)]
    cmd.append(M)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("%-20s HIBA %s" % (nev, (r.stderr or "")[:100])); continue
    d = dallam(*kozos.betolt(ki))
    print("%-20s F0 %5.1f | ingadozas %4.2f | terjedelem %4.1f felhang"
          % (nev, d[0], d[1], d[2]))
print("\nCEL (igazi BraiLab)  F0  83.3 | ingadozas 5.75 | terjedelem 10.0")
print("A MINTAD (retro)     F0  91.4 | ingadozas 5.51 | terjedelem 10.4")
