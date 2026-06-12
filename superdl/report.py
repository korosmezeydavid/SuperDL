"""Emberi nyelvű, felolvasható összefoglaló a letöltések állapotáról.

A `build_summary` egész, kimondható magyar mondatot ad vissza, például:
  "Jelenleg 3 letöltés fut, 1 várakozik. Összesen 42 százalék kész,
   együttes sebesség 5,3 MB másodpercenként, hátralévő idő körülbelül
   8 perc. Eddig 2 letöltés készült el."
Így a képernyőolvasó vagy a beszédmotor egyetlen, értelmes szöveget kap.
"""


def human_bytes(n: float) -> str:
    for unit in ("bájt", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "bájt" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def human_time(seconds: float) -> str:
    if seconds < 60:
        return "kevesebb mint egy perc"
    if seconds < 3600:
        return f"körülbelül {round(seconds / 60)} perc"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if m:
        return f"körülbelül {h} óra {m} perc"
    return f"körülbelül {h} óra"


def build_summary(jobs) -> str:
    """Felolvasható összefoglaló a job-lista pillanatnyi állapotáról."""
    n = {"letöltés": 0, "várakozik": 0, "ütemezve": 0, "seedelés": 0,
         "kész": 0, "hiba": 0, "leállítva": 0}
    total = downloaded = speed = 0.0
    for j in jobs:
        p = j.progress
        n[p.status] = n.get(p.status, 0) + 1
        if p.status == "letöltés" and p.total:
            total += p.total
            downloaded += p.downloaded
            speed += p.speed

    aktiv = n["letöltés"] + n["várakozik"] + n["ütemezve"] + n["seedelés"]
    if aktiv == 0:
        parts = ["Nincs aktív letöltés."]
        if n["kész"]:
            parts.append(f"{n['kész']} letöltés elkészült.")
        if n["hiba"]:
            parts.append(f"{n['hiba']} hibára futott.")
        return " ".join(parts)

    segs = []
    if n["letöltés"]:
        segs.append(f"{n['letöltés']} letöltés fut")
    if n["várakozik"]:
        segs.append(f"{n['várakozik']} várakozik")
    if n["ütemezve"]:
        segs.append(f"{n['ütemezve']} időzítve")
    if n["seedelés"]:
        segs.append(f"{n['seedelés']} seedelés alatt")
    sentence = "Jelenleg " + ", ".join(segs) + "."

    if total and n["letöltés"]:
        pct = downloaded / total * 100
        extra = f" Összesen {pct:.0f} százalék kész"
        if speed > 0:
            extra += f", együttes sebesség {human_bytes(speed)} másodpercenként"
            remaining = total - downloaded
            if remaining > 0:
                extra += f", hátralévő idő {human_time(remaining / speed)}"
        sentence += extra + "."

    if n["kész"]:
        sentence += f" Eddig {n['kész']} letöltés készült el."
    if n["hiba"]:
        sentence += f" {n['hiba']} hibára futott."
    return sentence
