"""Kozos meromodul: ugyanaz a merce a valodi felvetelre es a sajat hangunkra."""
import numpy as np, wave

CEL = {"f0": 83.3, "b": {1000: -15.8, 2000: -26.5, 3000: -36.0, 4000: -44.5},
       "doles": -11.4, "f1": 422, "f2": 1448, "f3": 2414,
       "bw1": 20, "bw2": 66, "bw3": 67}

def betolt(p):
    w = wave.open(p, "rb"); fs = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float)/32768.0
    if w.getnchannels() == 2: x = x.reshape(-1, 2).mean(axis=1)
    return x, fs

def savprofil(x, fs):
    """Sav-energiak a csucshoz kepest (dB) + spektralis doles."""
    n = 512
    ker = int(0.02*fs)
    e = np.sqrt(np.convolve(x**2, np.ones(ker)/ker, "same"))
    S = [np.abs(np.fft.rfft(x[s:s+n]*np.hanning(n)))
         for s in range(0, len(x)-n, n//2) if e[s+n//2] > 0.06*e.max()]
    S = np.mean(S, axis=0); frek = np.fft.rfftfreq(n, 1/fs)
    db = 20*np.log10(S/S.max()+1e-9)
    ki = {}
    for hat in (1000, 2000, 3000, 4000):
        m = (frek >= hat-500) & (frek < hat+500)
        ki[hat] = float(db[m].mean()) if m.any() else -60.0
    m = (frek > 300) & (frek < min(5000, fs/2-200))
    doles = float(np.polyfit(np.log10(frek[m]), db[m], 1)[0]*np.log10(2))
    return ki, doles

def f0_median(x, fs):
    kl = int(0.04*fs); ki = []
    for s in range(0, len(x)-kl, kl//2):
        seg = x[s:s+kl] - x[s:s+kl].mean()
        if np.sqrt((seg**2).mean()) < 0.01: continue
        r = np.correlate(seg, seg, "full")[len(seg)-1:]
        lo, hi = int(fs/400), int(fs/60)
        if hi >= len(r): continue
        i = lo + int(np.argmax(r[lo:hi]))
        if r[i] > 0.3*r[0]: ki.append(fs/i)
    return float(np.median(ki)) if ki else 0.0

def pontszam(x, fs):
    """Kisebb = kozelebb a valodi BraiLabhoz."""
    b, doles = savprofil(x, fs)
    p = sum(abs(b[k]-CEL["b"][k]) for k in CEL["b"])/4.0
    p += abs(doles-CEL["doles"])*0.8
    p += abs(f0_median(x, fs)-CEL["f0"])*0.15
    return p, b, doles

def _lpc(sig, rend):
    sig = sig*np.hanning(len(sig))
    r = np.correlate(sig, sig, "full")[len(sig)-1:len(sig)+rend]
    if r[0] <= 0: return None
    a = np.zeros(rend+1); a[0] = 1.0; e = r[0]
    for i in range(1, rend+1):
        k = -(a[:i] @ r[i:0:-1])/e
        a[1:i+1] += k*a[i-1::-1]; e *= (1-k*k)
        if e <= 0: return None
    return a

def formansok(x, fs):
    """F1..F3 mediánja és a sávszélességük mediánja (a csengés mércéje)."""
    kl = int(0.032*fs); tal = []
    for s in range(0, len(x)-kl, kl//2):
        seg = x[s:s+kl]
        if np.sqrt((seg**2).mean()) < 0.05: continue
        pre = np.append(seg[0], seg[1:]-0.97*seg[:-1])
        a = _lpc(pre, 12)
        if a is None: continue
        gy = np.roots(a); gy = gy[np.imag(gy) > 0.01]
        f = np.angle(gy)*fs/(2*np.pi)
        bw = -0.5*(fs/(2*np.pi))*np.log(np.abs(gy))
        jo = sorted([(fi, bi) for fi, bi in zip(f, bw)
                     if 200 < fi < min(5000, fs/2-200) and bi < 700])
        if len(jo) >= 3: tal.append(jo[:3])
    if not tal: return None
    return {("f%d" % (i+1)): float(np.median([t[i][0] for t in tal]))
            for i in range(3)} | {
           ("bw%d" % (i+1)): float(np.median([t[i][1] for t in tal]))
            for i in range(3)}

def teljes_pont(x, fs):
    """Színkép + csengés együtt. Kisebb = közelebb a valódihoz."""
    p, b, d = pontszam(x, fs)
    fm = formansok(x, fs)
    if fm is None: return p + 20, b, d, None
    cseng = sum(abs(fm["bw%d" % i] - CEL["bw%d" % i]) for i in (1, 2, 3))/3.0
    return p + 0.10*cseng, b, d, fm
