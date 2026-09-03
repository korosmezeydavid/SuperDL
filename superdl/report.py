"""Emberi nyelvű, felolvasható összefoglaló a letöltések állapotáról.

A `build_summary` egész, kimondható magyar mondatot ad vissza, például:
  "Jelenleg 3 letöltés fut, 1 várakozik. Összesen 42 százalék kész,
   együttes sebesség 5,3 MB másodpercenként, hátralévő idő körülbelül
   8 perc. Eddig 2 letöltés készült el."
Így a képernyőolvasó vagy a beszédmotor egyetlen, értelmes szöveget kap.

MK5 óta a modul a KÖZÖS szókincsre épül: az időt a `retrypolicy.emberi_ido()`,
a méretet a `lemezhely.emberi_meret()` adja. Enélkül a program kétféleképpen
mondaná ugyanazt.
"""

from . import lemezhely
from . import retrypolicy


def human_bytes(n: float) -> str:
    """Méret A SZEMNEK: rövid, a lista oszlopába való („5.3 MB").

    ⚠️ **Ez NEM felolvasásra való.** A tizedespontot a felolvasó mondatvégi
    pontnak mondja, a „MB"-t pedig betűzi. Kimondott mondatba a
    `mondott_meret()` kell (MK5)."""
    for unit in ("bájt", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "bájt" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def mondott_meret(n: float) -> str:
    """Méret A FÜLNEK: „5,3 megabájt" – tizedesvesszővel, kiírt egységgel.

    A `lemezhely.emberi_meret()`-re épül, hogy a program EGYFÉLEKÉPPEN mondja
    a méretet mindenhol (MK5). Két külön szókincs ugyanarra a fogalomra
    ugyanolyan hiba, mint két külön hibaüzenet ugyanarra a hibára."""
    return lemezhely.emberi_meret(n)


def human_time(seconds: float) -> str:
    """Hátralévő idő A FÜLNEK.

    MK5: a `retrypolicy.emberi_ido()`-ra épül, hogy a program NE mondjon
    kétféleképpen időt. Eddig két külön szókincs élt egymás mellett: az
    újrapróba „negyed órát" mondott, az összefoglaló „körülbelül 15 percet".
    Ugyanaz a fogalom, két hangzás – a felhasználó pedig azt hiszi, két
    különböző dologról van szó."""
    if seconds < 60:
        return "kevesebb mint egy perc"
    return "körülbelül " + retrypolicy.emberi_ido(int(seconds))


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
            # MK5: KIMONDOTT méret- és időszókincs (5,3 megabájt, negyed óra)
            extra += (f", együttes sebesség {mondott_meret(speed)} "
                      "másodpercenként")
            remaining = total - downloaded
            if remaining > 0:
                extra += f", hátralévő idő {human_time(remaining / speed)}"
        sentence += extra + "."

    # MK5: a LEGLASSABB elem külön mondatot érdemel. Az együttes hátralévő idő
    # félrevezet: ha négyből három egy perc múlva végez, a negyedik meg egy óra
    # múlva, az „átlag" alapján a felhasználó rosszul tervez. Vakon ő nem tudja
    # végigfutni szemmel a listát, hogy ezt észrevegye.
    lassu = leglassabb(jobs)
    if lassu:
        nev, hatra = lassu
        sentence += f" A leglassabb {nev}, {human_time(hatra)} múlva végez."

    if n["kész"]:
        sentence += f" Eddig {n['kész']} letöltés készült el."
    if n["hiba"]:
        sentence += f" {n['hiba']} hibára futott."
    return sentence


def leglassabb(jobs) -> tuple[str, float] | None:
    """A legkésőbb végző futó letöltés: (név, hátralévő másodperc).

    Csak akkor ad vissza valamit, ha **legalább kettő** fut és mindkettőnek
    van becsülhető ideje – egyetlen letöltésnél a „leglassabb" mondat üresen
    járna, és a bőbeszédűség vakon fárasztó."""
    jeloltek = []
    for j in jobs:
        p = j.progress
        if p.status != "letöltés" or not p.total or p.speed <= 0:
            continue
        hatra = (p.total - p.downloaded) / p.speed
        if hatra > 0:
            jeloltek.append((p.filename or j.url, hatra))
    if len(jeloltek) < 2:
        return None
    return max(jeloltek, key=lambda t: t[1])


def seed_mondat(nev: str, feltoltve: float, arany: float, peerek: int,
                fel_sebesseg: float = 0.0) -> str:
    """A seedelés állapota EMBERI mondatban (MK8).

    A lista oszlopaiban ez ma így néz ki: `1.2 MB/s (0.87)` — szemmel ez
    tömör és jó. **Kimondva viszont értelmezhetetlen:** a felolvasó a
    zárójeles számot külön mondja, a „0.87"-ből „nulla pont nyolcvanhét" lesz,
    és a felhasználónak fejben kell kitalálnia, mihez képest.

    Ez a mondat megmondja, amit tudni akar: mennyit adott vissza a
    közösségnek, és hányan töltik tőle épp most."""
    nev = (nev or "a torrent").strip()
    reszek = [f"{nev}: eddig {mondott_meret(feltoltve)} feltöltve"]
    if arany > 0:
        # a megosztási arány szorzóként érthető, nem tizedes számként
        reszek.append(f"a letöltött mennyiség {arany:.1f}-szerese"
                      .replace(".", ","))
    if peerek > 0:
        reszek.append(f"{peerek} társ tölti tőled most")
    elif fel_sebesseg <= 0:
        # ezt ki KELL mondani: a néma seedelés úgy néz ki, mintha elakadt volna
        reszek.append("jelenleg senki nem tölti tőled – ez nem hiba, "
                      "a torrent készen áll és vár")
    if fel_sebesseg > 0:
        reszek.append(f"{mondott_meret(fel_sebesseg)} másodpercenként")
    return ", ".join(reszek) + "."


def befejezes_mondat(nev: str, meret: float = 0) -> str:
    """A „kész" bemondás. MK5: a MÉRET is elhangzik.

    A név önmagában nem elég: vakon a méret az egyetlen visszajelzés arról,
    hogy tényleg a várt fájl jött-e le, és nem egy 4 kilobájtos hibaoldal."""
    nev = (nev or "a fájl").strip()
    if meret and meret > 0:
        return f"Elkészült: {nev}, {mondott_meret(meret)}."
    return f"Elkészült: {nev}."
