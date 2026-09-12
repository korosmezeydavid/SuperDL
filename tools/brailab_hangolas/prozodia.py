"""Melyik szabályzóval tágítható a klatt5 dallama a BraiLab 10 félhangjára?"""
import sys, subprocess, numpy as np
S = r"C:\Users\msn\AppData\Local\Temp\claude\C--Users-msn-Documents-Audacity\f2795c4b-c00d-4bf5-ad52-819a4ba3c6ae\scratchpad"
sys.path.insert(0, r"C:\Users\msn\Documents\Audacity\SuperDownloader")
sys.path.insert(0, S)
from superdl import retrovoice as RV
import kozos
from pathlib import Path

exe, data = RV._espeak()
M = "Üdvözöllek a szuper dé el retró játékok menüjében! Kettő, hét, kilenc."


def dallam(x, fs):
    kl = int(0.030 * fs); lep = int(0.010 * fs); f0 = []
    for s in range(0, len(x) - kl, lep):
        seg = x[s:s + kl] - x[s:s + kl].mean()
        if np.sqrt((seg ** 2).mean()) < 0.02:
            continue
        r = np.correlate(seg, seg, "full")[len(seg) - 1:]
        lo, hi = int(fs / 250), int(fs / 55)
        if hi >= len(r):
            break
        i = lo + int(np.argmax(r[lo:hi]))
        if r[i] > 0.35 * r[0]:
            f0.append(fs / i)
    z = np.array(f0)
    if len(z) < 10:
        return None
    fh = np.log2(z / np.median(z)) * 12
    return (np.median(z), fh.std(),
            np.percentile(fh, 90) - np.percentile(fh, 10))


def probal(cim, szoveg, extra=()):
    ki = S + r"\pr.wav"
    cmd = [exe, "-v", "hu+klatt5", "-p", "12", "-s", "145", "-w", ki]
    cmd += list(extra)
    if data:
        cmd += ["--path", str(Path(data).parent)]
    cmd.append(szoveg)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("%-28s HIBA %s" % (cim, (r.stderr or "")[:90]))
        return
    x, fs = kozos.betolt(ki)
    d = dallam(x, fs)
    if d is None:
        print("%-28s (nem merheto)" % cim); return
    print("%-28s F0 %5.1f | ingadozas %4.2f | terjedelem %4.1f felhang"
          % (cim, d[0], d[1], d[2]))


print("CEL (igazi BraiLab):         F0  83.3 | ingadozas 5.75 | terjedelem 10.0 felhang\n")
probal("nyers klatt5", M)
for r in ("120%", "200%", "300%", "0%"):
    probal("SSML range=%s" % r,
           "<prosody range='%s'>%s</prosody>" % (r, M), extra=("-m",))
for p in ("50%", "150%"):
    probal("SSML pitch=%s" % p,
           "<prosody pitch='%s'>%s</prosody>" % (p, M), extra=("-m",))
probal("szohatar-szunet (-g 8)", M, extra=("-g", "8"))
probal("nagybetu-jelzes (-k 20)", M, extra=("-k", "20"))
