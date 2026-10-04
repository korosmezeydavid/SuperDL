# Super Surf 0.1.0 – helyi akadálymentességi próba

Állapot: 2026-10-04, helyben telepített próbamodul. Nincs a GitHubra feltöltve,
és nincs éles kiadás.

## Használat

A Super Surf ablakban válassz forrást, írd be a keresőszót vagy URL-t,
majd Enter vagy „Lekérdezés”. Az eredmény fejezetei natív listában vannak,
a kijelölt fejezet szövege külön natív mezőben olvasható. A másolás,
mentés és forrás megnyitása külön gomb. A feldolgozott tartalomban a H2/H3
struktúra megmarad; a kezelőfelületen ezek fejezetlistaként jelennek meg.
Beágyazott böngésző már nincs az olvasóban.

Módok: magyar/angol Wikipédia-összefoglaló; nyilvános cikk-URL tisztítása;
aktuális időjárás település szerint; napi tájékoztató árfolyam (például
`EUR HUF`); angol szótár, opcionális etimológiával. A szótár még nem magyar
szótár. A dinamikusan betöltött, bejelentkezést vagy előfizetést kérő cikkek
nem feltétlenül nyerhetők ki.

## Akadálymentességi próba

1. NVDA/JAWS mellett keresés indítása: a betöltés és feldolgozás állapota
   egyszer hangozzon el; a fókusz a mezőben maradjon.
2. Eredmény után a fejezetlistára kerüljön a fókusz; fel/le nyílra a fejezet
   neve hangozzon el. Enterrel a szövegmezőbe, Escape-pel vissza a listára.
3. Másolás, mentés és a forrás megnyitása billentyűzettel is legyen elérhető.
4. Hibás URL, hiányzó találat és lassú hálózat esetén legyen érthető állapot.
5. Megszakítás után egy későn befutó válasz ne írja felül az új állapotot.

Képernyőolvasós élő próbát a felhasználó végzi; a programozott UI-próba nem
helyettesíti ezt. Az esetleges fókuszhibát a pontos képernyőolvasóval és
lépésekkel kell visszajelezni, mielőtt a modul éles kiadást kap.

## Ellenőrzés és források

A `tests/test_supersurf.py` az öt lekérdezési módot, a cikk struktúráját,
a HTML escape-et, a helyi URL tiltását és a megszakítást vizsgálja. Élő
Wikipédia-, Open-Meteo-, Frankfurter-, Free Dictionary API- és cikkoldal-próba
is sikerült 2026-10-04-én. Az API-k adatai és elérhetősége változhat.

Adatforrások: https://www.mediawiki.org/wiki/API:REST_API/Reference ;
https://open-meteo.com/en/docs ; https://frankfurter.dev/ ;
https://dictionaryapi.dev/ .
