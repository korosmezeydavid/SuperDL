"""Beszélő médiaelemző – a SuperDL „digitális médiaközpont" minőség-ellenőrző
motorja (vakbarát, felolvasható jelentésekkel). Tisztán a beágyazott
ffmpeg/ffprobe-ra épül, nincs új függőség.

Három funkció:
  • ELLENŐRZÉS: megnyitható-e a fájl, van-e hang/videósáv, ésszerű-e a hossz,
    stimmel-e a méret, és (alapos módban) van-e dekódolási hiba.
  • HANGTECHNIKAI ELEMZÉS: integrált/pillanatnyi/rövididejű hangerő (LUFS, EBU
    R128), true peak, DC-offset, csúcs/RMS szint, clipping, mintavétel, bitmélység.
  • EBU R128 NORMALIZÁLÁS: kétmenetes loudnorm, profilonként (podcast, rádió,
    YouTube, hangoskönyv…), és elmondja, mennyit változtatott.
"""

import json
import os
import re
import subprocess
from pathlib import Path

from . import ffmpeg as ffmpeg_mod

_NOWIN = 0x08000000 if os.name == "nt" else 0


def ff() -> str | None:
    f = ffmpeg_mod.find_ffmpeg()
    if not f:
        d = ffmpeg_mod.ensure_ffmpeg()
        f = ffmpeg_mod.find_ffmpeg() if d else None
    return f


def _ffprobe(ffexe: str) -> str:
    return str(Path(ffexe).with_name("ffprobe.exe"))


def _run(cmd, timeout=1800):
    """(returncode, stdout, stderr) – az ffprobe a stdout-ra ír JSON-t, az
    ffmpeg-szűrők a stderr-re a mérési adatokat."""
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, encoding="utf-8", errors="replace",
                           creationflags=_NOWIN, timeout=timeout)
        return r.returncode, r.stdout or "", r.stderr or ""
    except (OSError, subprocess.SubprocessError) as e:
        return 1, "", str(e)


def _num(x) -> str:
    """Magyaros tizedesvessző a felolvasható számokhoz."""
    return f"{x:.1f}".replace(".", ",")


def _hms(sec: float) -> str:
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} óra {m} perc {s} másodperc"
    if m:
        return f"{m} perc {s} másodperc"
    return f"{s} másodperc"


# ---- ffprobe: fájlinformáció -----------------------------------------

def probe(ffexe: str, src: str) -> dict | None:
    rc, out, _err = _run([_ffprobe(ffexe), "-v", "error", "-show_format",
                          "-show_streams", "-of", "json", src], timeout=60)
    if rc != 0 or not out.strip():
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def _fps(r: str) -> float:
    try:
        n, d = r.split("/")
        return float(n) / float(d) if float(d) else 0.0
    except Exception:
        return 0.0


_BITS = {"u8": 8, "s16": 16, "s16p": 16, "s32": 32, "s32p": 32,
         "flt": 32, "fltp": 32, "dbl": 64, "dblp": 64, "s24": 24}


def summary(info: dict) -> str:
    """Rövid, felolvasható fájl-összegzés."""
    fmt = info.get("format", {})
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    parts = []
    cont = (fmt.get("format_name", "") or "").split(",")[0].upper()
    if cont:
        parts.append(cont)
    if v and v.get("width"):
        parts.append(f"{v.get('width')}×{v.get('height')} képpont")
        fps = _fps(v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/0")
        if fps:
            parts.append(f"{round(fps)} képkocka másodpercenként")
        parts.append(f"videó: {v.get('codec_name', '?')}")
    if a:
        ch = a.get("channels")
        chname = {1: "monó", 2: "sztereó"}.get(ch, f"{ch} csatornás")
        parts.append(f"{chname} {(a.get('codec_name', '?') or '?').upper()}")
        if a.get("sample_rate"):
            parts.append(f"{int(int(a['sample_rate']) / 1000)} kHz")
        bits = _BITS.get(a.get("sample_fmt", ""))
        if bits:
            parts.append(f"{bits} bit")
    dur = float(fmt.get("duration", 0) or 0)
    if dur > 0:
        parts.append(f"időtartam {_hms(dur)}")
    return ", ".join(parts)


# ---- ellenőrzés (#1) --------------------------------------------------

def verify(ffexe: str, src: str, expected_size: int | None = None,
           deep: bool = False) -> dict:
    info = probe(ffexe, src)
    if info is None:
        return {"ok": False, "info": None,
                "problems": ["A fájl nem nyitható meg, vagy sérült a konténer."]}
    problems = []
    streams = info.get("streams", [])
    has_v = any(s.get("codec_type") == "video" for s in streams)
    has_a = any(s.get("codec_type") == "audio" for s in streams)
    if not has_v and not has_a:
        problems.append("Nincs benne sem hang-, sem videósáv.")
    dur = float(info.get("format", {}).get("duration", 0) or 0)
    if dur <= 0:
        problems.append("Az időtartam nem állapítható meg – a fájl csonka lehet.")
    if expected_size:
        actual = int(info.get("format", {}).get("size", 0) or 0)
        if not actual and os.path.exists(src):
            actual = os.path.getsize(src)
        if actual and abs(actual - expected_size) > 1024:
            problems.append(f"A fájlméret nem a várt: {actual} bájt a "
                            f"{expected_size} helyett.")
    if deep:
        rc, _o, err = _run([ffexe, "-v", "error", "-i", src, "-f", "null", "-"],
                           timeout=3600)
        bad = [ln for ln in err.splitlines() if ln.strip()]
        if bad:
            problems.append(f"Dekódolási hiba: {bad[-1][:140]}")
    return {"ok": not problems, "info": info, "problems": problems}


# ---- hangtechnikai elemzés (#3) --------------------------------------

def loudness(ffexe: str, src: str) -> dict:
    """EBU R128 hangerő: integrált (I), hangerő-tartomány (LRA), true peak, és a
    pillanatnyi/rövididejű csúcs."""
    _rc, _o, err = _run([ffexe, "-hide_banner", "-nostats", "-i", src,
                         "-filter_complex", "ebur128=peak=true",
                         "-f", "null", "-"])
    res = {"integrated": None, "lra": None, "true_peak": None,
           "momentary_max": None, "short_max": None}
    isum = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", err)
    if isum:
        res["integrated"] = float(isum[-1])           # az utolsó = összegzés
    lra = re.findall(r"LRA:\s*(-?[\d.]+)\s*LU", err)
    if lra:
        res["lra"] = float(lra[-1])
    tp = re.findall(r"Peak:\s*(-?[\d.]+)\s*dBFS", err)
    if tp:
        res["true_peak"] = float(tp[-1])

    def _maxof(letter):
        vals = [float(x) for x in re.findall(rf"\b{letter}:\s*(-?[\d.]+)", err)
                if x not in ("-inf", "nan")]
        vals = [v for v in vals if v > -120]
        return max(vals) if vals else None
    res["momentary_max"] = _maxof("M")
    res["short_max"] = _maxof("S")
    return res


def technical(ffexe: str, src: str) -> dict:
    """astats: DC-offset, csúcs- és RMS-szint, clipping-jelzés."""
    _rc, _o, err = _run([ffexe, "-hide_banner", "-nostats", "-i", src,
                         "-filter_complex", "astats=metadata=0",
                         "-f", "null", "-"])
    tail = err.split("Overall")[-1]      # az összesített szakasz a végén

    def grab(label):
        m = re.search(re.escape(label) + r":\s*(-?[\d.]+)", tail)
        return float(m.group(1)) if m else None
    peak_db = grab("Peak level dB")
    res = {"dc_offset": grab("DC offset"), "peak_db": peak_db,
           "rms_db": grab("RMS level dB"),
           "clipping": bool(peak_db is not None and peak_db >= -0.1)}
    return res


def analyze(ffexe: str, src: str, deep: bool = False) -> tuple[str, dict]:
    """Teljes, felolvasható elemzés (ellenőrzés + technikai)."""
    v = verify(ffexe, src, deep=deep)
    lines = [f"Fájl: {os.path.basename(src)}"]
    if not v["info"]:
        lines.append("HIBA: " + "; ".join(v["problems"]))
        return "\n".join(lines), {"verify": v}
    lines.append("Jellemzők: " + summary(v["info"]))
    if v["ok"]:
        lines.append("Ellenőrzés: rendben, a fájl épnek tűnik.")
    else:
        lines.append("FIGYELEM: " + "; ".join(v["problems"]))

    has_a = any(s.get("codec_type") == "audio"
                for s in v["info"].get("streams", []))
    data = {"verify": v}
    if has_a:
        ld = loudness(ffexe, src)
        tc = technical(ffexe, src)
        data["loudness"], data["technical"] = ld, tc
        if ld["integrated"] is not None:
            lines.append(f"Integrált hangerő: {_num(ld['integrated'])} LUFS"
                         + (f", hangerő-tartomány {_num(ld['lra'])} LU"
                            if ld["lra"] is not None else "")
                         + (f", valódi csúcs {_num(ld['true_peak'])} dB"
                            if ld["true_peak"] is not None else "") + ".")
        if tc["peak_db"] is not None:
            msg = (f"Csúcsszint {_num(tc['peak_db'])} dB, "
                   f"RMS {_num(tc['rms_db'])} dB" if tc["rms_db"] is not None
                   else f"Csúcsszint {_num(tc['peak_db'])} dB")
            if tc["clipping"]:
                msg += " – FIGYELEM: torzítás (clipping) valószínű!"
            lines.append(msg + ".")
        if tc["dc_offset"] is not None and abs(tc["dc_offset"]) > 0.001:
            lines.append(f"Egyenáramú eltolás (DC-offset): "
                         f"{tc['dc_offset']:.4f} – érdemes korrigálni.")
    else:
        lines.append("Nincs hangsáv, a hangtechnikai elemzés kimarad.")
    return "\n".join(lines), data


# ---- EBU R128 normalizálás (#4) --------------------------------------

# profil -> (cél integrált LUFS, true peak max dB, hangerő-tartomány LU)
NORM_PROFILES = {
    "Podcast": (-16.0, -1.5, 11.0),
    "Internetes rádió": (-16.0, -1.0, 6.0),
    "YouTube": (-14.0, -1.0, 11.0),
    "Hangoskönyv": (-19.0, -3.0, 9.0),
    "Zenei archívum": (-14.0, -1.0, 11.0),
    "Beszédfelvétel": (-16.0, -1.5, 7.0),
    "Műsorszórás (EBU R128)": (-23.0, -1.0, 7.0),
}


def normalize(ffexe: str, src: str, out: str, profile: str,
              progress=None) -> tuple[bool, str]:
    """Kétmenetes EBU R128 normalizálás. 1. menet: mérés; 2. menet: a mért
    értékekkel pontos korrekció. Visszaad: (siker, felolvasható jelentés)."""
    if profile not in NORM_PROFILES:
        return False, "Ismeretlen normalizálási profil."
    tgt_i, tgt_tp, tgt_lra = NORM_PROFILES[profile]
    if progress:
        progress(0.1)
    # 1. menet – mérés JSON-ben
    _rc, _o, err = _run([ffexe, "-hide_banner", "-i", src, "-af",
                         f"loudnorm=I={tgt_i}:TP={tgt_tp}:LRA={tgt_lra}:"
                         "print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.DOTALL)
    if not m:
        return False, "A hangerő mérése nem sikerült (van-e hangsáv a fájlban?)."
    try:
        meas = json.loads(m.group(0))
    except json.JSONDecodeError:
        return False, "A mérési adatok nem értelmezhetők."
    if progress:
        progress(0.5)
    # 2. menet – pontos korrekció a mért értékekkel
    af = (f"loudnorm=I={tgt_i}:TP={tgt_tp}:LRA={tgt_lra}:"
          f"measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:"
          f"measured_LRA={meas['input_lra']}:measured_thresh="
          f"{meas['input_thresh']}:offset={meas['target_offset']}:linear=true")
    rc, _o2, err2 = _run([ffexe, "-y", "-i", src, "-af", af,
                         "-ar", "48000", out])
    if progress:
        progress(1.0)
    if rc != 0 or not os.path.exists(out):
        last = [ln for ln in err2.splitlines() if ln.strip()]
        return False, "A normalizálás nem sikerült" + (
            f": {last[-1][:140]}" if last else ".")
    try:
        before = float(meas["input_i"])
        change = tgt_i - before
        rep = (f"Kész. Az eredeti hangerő {_num(before)} LUFS volt; a(z) "
               f"„{profile}" + chr(34) + f" profil célja {_num(tgt_i)} LUFS. "
               f"A változás körülbelül {_num(change)} LU, a csúcsot "
               f"{_num(tgt_tp)} dB alá fogtam.")
    except Exception:
        rep = "Kész. A fájl normalizálva."
    return True, rep
