# Super Surf 0.1.0 – kutatás és cikkolvasás

Állapot: 2026-10-04, első nyilvános Windows-modulkiadás.
Telepítés a SuperDL 4.6.30 vagy újabb verziójának Modulkezelőjéből.
Kiadás: https://github.com/korosmezeydavid/SuperDL/releases/tag/mod-supersurf-0.1.0 .

## Használat

A Super Surf ablakban válassz forrást, írd be a keresőszót vagy URL-t,
majd Enter vagy „Lekérdezés”. Az eredmény fejezetei natív listában vannak,
a kijelölt fejezet szövege külön natív mezőben olvasható. A másolás,
mentés és forrás megnyitása külön gomb. A feldolgozott tartalomban a H2/H3
struktúra megmarad; a kezelőfelületen ezek fejezetlistaként jelennek meg.
Beágyazott böngésző már nincs az olvasóban.

Módok: magyar/angol Wikipédia-cikk teljes olvasható tartalma; nyilvános cikk-URL tisztítása;
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

A kiadás előtti képernyőolvasós próbát a fejlesztő végezte; a forrásválasztó
fókuszhibáját jelzése alapján javítottuk. További fókuszhibánál a pontos
képernyőolvasót és lépéseket kérjük visszajelzésként.

## Ellenőrzés és források

A `tests/test_supersurf.py` az öt lekérdezési módot, a cikk struktúráját,
a HTML escape-et, a helyi URL tiltását és a megszakítást vizsgálja. Élő
Wikipédia-, Open-Meteo-, Frankfurter-, Free Dictionary API- és cikkoldal-próba
is sikerült 2026-10-04-én. Az API-k adatai és elérhetősége változhat.

Fejlesztési állapot (2026-10-05, még nem kiadott): ha az első angol szótár
időtúllépést jelez, a modul a Datamuse API pontos címszóhoz tartozó
definícióit kéri le. A Wikipédia mód a MediaWiki Parse API teljes cikkét
dolgozza fel: fejezetek, bekezdések, listák, táblázatsorok, képaláírások
és hivatkozásjegyzék. A képek maguk továbbra sem jelennek meg a szöveges
olvasóban. A Datamuse adatforrás
elismerése: https://www.datamuse.com/api/ .

A webcímes cikkolvasó helyi változata rövid bekezdéseket, táblázatsorokat,
képaláírásokat, önálló képek leírását, fogalomlistákat és kódblokkokat is
megtart. A menük, hirdetések és rejtett elemek továbbra sem kerülnek az
olvasóba. A bejelentkezéshez kötött, kizárólag JavaScripttel betöltött vagy
az olvasási méretkorlátot túllépő oldalak tartalma nem mindig érhető el.

Adatforrások: https://www.mediawiki.org/wiki/API:Parsing_wikitext ;
https://open-meteo.com/en/docs ; https://frankfurter.dev/ ;
https://dictionaryapi.dev/ .
