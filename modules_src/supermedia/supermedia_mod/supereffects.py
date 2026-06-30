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
    # --- bővített effekt-arzenál ---
    ("echo", "Visszhang (terem)", None, 0,
     lambda p, d, f: "aecho=0.8:0.88:60:0.4"),
    ("echo_big", "Visszhang (nagy terem)", None, 0,
     lambda p, d, f: "aecho=0.8:0.9:1000:0.3"),
    ("chorus", "Kórus", None, 0,
     lambda p, d, f: "chorus=0.5:0.9:50|60|40:0.4|0.32|0.3:0.25|0.4|0.3:2|2.3|1.3"),
    ("flanger", "Flanger", None, 0,
     lambda p, d, f: "flanger"),
    ("tremolo", "Tremoló (remegő hangerő)", "frekv. Hz", 5,
     lambda p, d, f: f"tremolo=f={max(0.1, p):g}:d=0.7"),
    ("vibrato", "Vibrato (remegő hangmagasság)", "frekv. Hz", 6,
     lambda p, d, f: f"vibrato=f={max(0.1, p):g}:d=0.5"),
    ("phone", "Telefonhang", None, 0,
     lambda p, d, f: "highpass=f=300,lowpass=f=3400"),
    ("radio", "Régi rádió", None, 0,
     lambda p, d, f: "highpass=f=200,lowpass=f=5000,acrusher=bits=8:mode=log"),
    ("lofi", "Lo-fi / torzítás", "bitmélység (2–12)", 4,
     lambda p, d, f: f"acrusher=bits={max(1, min(16, int(p)))}:samples=2:mode=log"),
    ("muffle", "Tompa (aluláteresztő)", "vágás Hz", 3000,
     lambda p, d, f: f"lowpass=f={max(200, int(p))}"),
]


def build(key: str, param: float, dur: float, freq: int) -> str | None:
    for k, _name, _lbl, _dflt, fn in EFFECTS:
        if k == key:
            return fn(param, dur, freq)
    return None
