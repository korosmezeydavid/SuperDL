"""A `pitch <also> <felso>` sor kalibrálása: cél F0 83 Hz, 10 félhang terjedelem."""
import sys, subprocess, numpy as np
S = r"C:\Users\msn\AppData\Local\Temp\claude\C--Users-msn-Documents-Audacity\f2795c4b-c00d-4bf5-ad52-819a4ba3c6ae\scratchpad"
sys.path.insert(0, r"C:\Users\msn\Documents\Audacity\SuperDownloader")
sys.path.insert(0, S)
from superdl import retrovoice as RV
import kozos
from pathlib import Path

exe, data = RV._espeak()
VM = Path(r"C:\Users\msn\Documents\Audacity\SuperDownloader\bin\espeak-ng-data\voices\!v")
M = "Üdvözöllek a szuper dé el retró játékok menüjében! Kettő, hét, kilenc."


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


def proba(cim, sorok, p=50):
    VM.joinpath("blx").write_text(
        "language variant\nname blx\nklatt 5\n%s\n" % sorok, encoding="utf-8")
    ki = S + r"\px.wav"
    cmd = [exe, "-v", "hu+blx", "-p", str(p), "-s", "145", "-w", ki]
    if data:
        cmd += ["--path", str(Path(data).parent)]
    cmd.append(M)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("%-34s HIBA %s" % (cim, (r.stderr or "")[:80])); return
    d = dallam(*kozos.betolt(ki))
    if d is None:
        print("%-34s nem merheto" % cim); return
    print("%-34s F0 %5.1f | ingadozas %4.2f | terjedelem %4.1f felhang"
          % (cim, d[0], d[1], d[2]))


print("CEL (igazi BraiLab):               F0  83.3 | ingadozas 5.75 | terjedelem 10.0\n")
proba("nincs pitch sor (-p 12)", "", 12)
for also, felso in ((60, 100), (60, 130), (60, 160), (70, 140), (50, 120)):
    proba("pitch %d %d" % (also, felso), "pitch %d %d" % (also, felso))

print()
for sor in ("pitch 60 130", "pitch 50 120", "pitch 45 110"):
    for p in (0, 10, 25):
        proba("%s + -p %d" % (sor, p), sor, p)
