# SuperDL – `mobil` ág

Ez az ág a **SuperDL MOBIL (Android)** verzióját tartalmazza – **külön** a
Windows-verziótól. A Windows-verzió a `main` ágon él (Python / wxPython); a
mobil app egy **különálló projekt** (Kotlin, Android, vak-first), ezért
szándékosan **orphan ág** ez: nincs közös történet a `main`-nel, hogy a két
kódbázis ne keveredjen.

## Mi kerül ide

- `app/` – az Android app forrása (Kotlin; gesztus + hang + TTS, vak-first
  launcher/app).
- `mobil-katalogus.json` – a mobil modul-/játék-**katalógus** (a Windows
  `modules.json` mobil megfelelője): innen tudja a mobil app, milyen modulok /
  játékok érhetők el és hol.

## Szabályok

- A `main` (Windows) ágat **nem** módosítjuk innen.
- **Titok/token/kredencál SOHA** nem kerül a repóba.
- Szigorúan **legális** használat; jogtiszta tartalom.

## Feltöltés (a mobil beszélgetésből)

```
git clone https://github.com/korosmezeydavid/SuperDL.git
cd SuperDL
git checkout mobil          # ez az ág már létezik
# ide másold be az app/ mappát és töltsd fel a mobil-katalogus.json-t
git add -A
git commit -m "SuperDL mobil: app + katalogus"
git push origin mobil
```
