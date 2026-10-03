# SuperDL – átvételi felmérés

Dátum: 2026-10-03. Készítette: Codex. Kérés: a teljes SuperDL-koncepció és a Claude-tól történő átvétel megítélése.

## Döntés

A helyben elérhető Windows- és Android-projekt fejlesztése átvehető. Megvan a forrás, a verziótörténet, az átadási dokumentáció, Claude helyi memóriája és a szükséges eszközök jelentős része. A Windows környezetét célzott ellenőrzésekkel igazoltam. Androidon a forrást és a környezet útvonalait ellenőriztem; új buildet és készülékes próbát nem végeztem.

Ez koncepció- és átvételi felmérés, nem minden forrássorra kiterjedő audit, teljes regressziós teszt vagy kiadási jóváhagyás. Claude felhős projektjét, levelezését és a nyilvános kiadások aktuális állapotát ebben a körben nem ellenőriztem.

## A koncepció értelmezése

A SuperDL közös célja a vak felhasználó önállósága: egységes, magyarul használható környezet olyan feladatokhoz is, amelyek más programokban nehezen hozzáférhetők. A funkciók köre a letöltésen és médián túl kommunikációra, dokumentumokra, szervezésre, játékokra és mindennapi eszközökre terjed ki.

A minőség része a hallható és igaz állapot, a kiszámítható fókusz és navigáció, a megszakíthatóság, a megmaradó beállítás, valamint az érthető hiba. A képernyőolvasó elsőbbsége és az opcionális saját hang külön követelmény. A sikeres háttérművelet önmagában kevés, ha a felhasználó nem értesül róla.

Windows: Python/wxPython Core, közös szolgáltatások, CoreContext és külön telepíthető modulok. A modul saját verzióval frissülhet; új futtatókörnyezeti függőséghez Core-kiadás szükséges. A modulbetöltés és frissítés körül verziókapuk, SHA-ellenőrzés és visszaállítási mechanizmusok vannak.

Android: Kotlin-alapú launcher és széles funkciókészlet, saját képernyőolvasóval, gesztuskezeléssel, beszéddel és asszisztenssel. A megvalósítás erősen MainActivity-központú; a windowsos modularchitektúra nem vetíthető rá automatikusan. A két terméket többek között WiFi-portál, könyvjelző- és bevásárlólista-kapcsolatok kötik össze.

## Ellenőrzött helyi állapot

- Windows HEAD: `dacb535`; a forrás verziója `4.6.30`.
- `modules.json`: 21 modul. Mindegyik verziója egyezik a helyi manifesttel; mind a 21 megfelelő ZIP SHA-256 értéke egyezik a katalógussal. Ez helyi konzisztencia, nem a távoli letöltések ellenőrzése.
- Meglévő kimenet: GUI és CLI exe, valamint `SuperDL-Setup-4.6.30.exe`, 2026-10-02-i fájldátumokkal. Ezeket nem építettem újra és nem indítottam el.
- A `tools/build_ellenor.py --elotte` sikeres a `C:\Users\msn\AppData\Local\Programs\Python\Python314\python.exe` interpreterrel.
- A `tools/build_ellenor.py` sikeres a meglévő onedir kimeneten és a hozzá tartozó helyi PYZ-n. Ez függőség-ellenőrzés, nem a teljes alkalmazás működésének bizonyítéka.
- `python -B -m pytest tests/test_modkit.py -q -p no:cacheprovider`: 16 sikeres teszt, kilépési kód 0. A teljes tesztcsomagot nem futtattam.
- Android HEAD: `e1f273e`; `app/build.gradle`: `1.86.0`, versionCode `154`. A kiadási összefoglaló után további commitok vannak, ezért a verziószám önmagában nem azonosítja a kiadott tartalmat.
- Android Studio JBR és az SDK `platform-tools/adb.exe` létezik. Telefonkapcsolatot és telepített változatot nem ellenőriztem.
- Mindkét munkamappában vannak korábbi helyi munkafájlok. Androidon két követett eszközszkript is módosított. Ezeket megőriztem.

## Az átvétel lényeges kockázatai

1. **Elavult és ellentmondó állapotlapok.** A Windows HANDOFF szeptember 29-i állapotot közöl, a bevezetőben még 17 modult és 4.5.5-öt említ. A régi és az új build-interpreter útvonala ugyanabban a dokumentumban szerepel. A buildszkript és a mostani ellenőrzés a Programs/Python/Python314 útvonalat igazolja.
2. **Szétszórt projektmemória.** A helyi Claude-memória hozzáférhető, de több régi terv már megvalósult. A HANDOFF által hivatkozott `claude/` mappa itt hiányzik. A claude.ai „super dl windows and android” projekt anyagait külön kell összevetni, ha egy feladathoz csak ott van meg az indoklás vagy a friss döntés.
3. **Nagy központi felületek.** A Windows főablaka és különösen az Android MainActivity sok funkciót kapcsol össze. Módosításkor a teljes bekötést, állapotváltást, fókuszt és beszédutat kell követni; egy osztály létezése még nem működő funkció.
4. **A teszt és a kiadott csomag eltérhet.** A CI Python 3.12-t használ, a helyi build 3.14-et. A függőséglista, a PyInstaller-spec és a tényleges csomagtartalom együtt ellenőrzendő. A build-őr hasznos, de nem teljes funkcionális teszt.
5. **Élő hozzáférhetőségi próba szükséges.** NVDA/JAWS, valódi Android-gesztusok, Bluetooth-eszközváltás és kétgépes kommunikáció minőségét a mostani vizsgálat nem igazolja. Ezekhez célzott valós próbák és felhasználói visszajelzés kell.

## A folytatás munkarendje

A meglévő program fokozatos karbantartása és továbbfejlesztése indokolt. Első feladatnál a hozzá tartozó legfrissebb commitokat, tényleges bekötést, teszteket és felhasználói hibajelentést kell összekapcsolni. Régi backlog-tételt nem szabad ellenőrzés nélkül új feladatként kezelni.

A dokumentált windowsos munkarendet megtartjuk: „create maxima” indítja a kódolást/buildet, külön „publikálás” a kiadást. Kiadás előtt a teljes előírt tesztelés, kész programos önpróba és kulcsszken szükséges. A jelen felmérésben alkalmazáskód, build, telepítés, commit és publikálás nem történt.

Claude teljes felhős beszélgetéstörténete nem előfeltétele minden fejlesztésnek. A hiányzó, feladatspecifikus döntéseket azonban be kell emelni a közös dokumentációba. Ez a felmérés és a HANDOFF-bejegyzés biztosítja a mostani vizsgálat folytathatóságát.
