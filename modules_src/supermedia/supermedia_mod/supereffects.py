"""Super Recorder – effekt-rack definíciók (It.3).

Minden effekt egy ffmpeg AUDIO-SZŰRŐ-láncra fordul, amit a szerkesztő a kijelölt
szakaszra (vagy az egészre) alkalmaz (offline, a Core ffmpeg-jével). Egyszerű,
KIMONDHATÓ nevek; a paraméteres effekteknél egyetlen szám (pl. félhang, dB, %).

Egy effekt: (kulcs, név, param_címke|None, param_alap, build(param, dur)->af).
A `dur` a feldolgozandó szakasz hossza (a fade-hez kell).
"""


def _pitch(semi: float, freq: int = 44100) -> str:
    # hangmagasság-eltolás TEMPÓ-TARTÓ módon: asetrate (pitch+tempo) →
    # atempo visszaállítja a tempót → nettó tiszta hangmagasság-váltás
    r = 2.0 ** (semi / 12.0)
    return f"asetrate={int(freq * r)},aresample={freq},atempo={1.0 / r:.6f}"


def _tempo(percent: float) -> str:
    # tempó (sebesség) HANGMAGASSÁG-TARTÓ módon; atempo 0.5–2.0, láncolva ha kell
    ratio = max(0.25, min(4.0, percent / 100.0))
    parts = []
    r = ratio
    while r > 2.0:
        parts.append("atempo=2.0"); r /= 2.0
    while r < 0.5:
        parts.append("atempo=0.5"); r /= 0.5
    parts.append(f"atempo={r:.6f}")
    return ",".join(parts)


def _fade(p: float, dur: float) -> str:
    p = max(0.05, p)
    out = [f"afade=t=in:st=0:d={p:.3f}"]
    if dur > p:
        out.append(f"afade=t=out:st={max(0.0, dur - p):.3f}:d={p:.3f}")
    return ",".join(out)


# (kulcs, név, param_címke|None, param_alap, build(param, dur, freq)->af)
EFFECTS = [
    ("normalize", "Normalizálás (egyenletes hangerő)", None, 0,
     lambda p, d, f: "loudnorm=I=-16:TP=-1.5:LRA=11"),
    ("denoise", "Zajszűrés", None, 0,
     lambda p, d, f: "afftdn=nf=-25"),
    ("voice", "Beszédhang-kiemelés", None, 0,
     lambda p, d, f: "highpass=f=80,lowpass=f=12000,"
                     "acompressor=threshold=-20dB:ratio=2.5:attack=15:release=180"),
    ("compress", "Kompresszor (kiegyenlítés)", None, 0,
     lambda p, d, f: "acompressor=threshold=-18dB:ratio=3:attack=20:release=200"),
    ("declick", "Kattanások eltávolítása", None, 0,
     lambda p, d, f: "adeclick"),
    ("bass", "Mélyek kiemelése", "dB (−20…+20)", 6,
     lambda p, d, f: f"bass=g={p:g}"),
    ("treble", "Magasak kiemelése", "dB (−20…+20)", 6,
     lambda p, d, f: f"treble=g={p:g}"),
    ("volume", "Hangerő", "dB (−30…+30)", 0,
     lambda p, d, f: f"volume={p:g}dB"),
    ("pitch", "Hangmagasság (tempó-tartó)", "félhang (−12…+12)", 0,
     lambda p, d, f: _pitch(p, f)),
    ("tempo", "Tempó (hangmagasság-tartó)", "% (25…400)", 100,
     lambda p, d, f: _tempo(p)),
    ("fade", "Be- és kihalkítás", "mp", 0.3,
     lambda p, d, f: _fade(p, d)),
    ("reverse", "Visszafelé", None, 0,
     lambda p, d, f: "areverse"),
]


def build(key: str, param: float, dur: float, freq: int) -> str | None:
    for k, _name, _lbl, _dflt, fn in EFFECTS:
        if k == key:
            return fn(param, dur, freq)
    return None
