# -*- coding: utf-8 -*-
"""A játékok KATALÓGUSA – a felület ebből építi a két listát (Retró / Saját).

Minden RETRÓ játék a klasszikus magyar vakos DOS-játékok akadálymentes,
modern újraalkotása. A szerzőket a fejlesztő megkereste és ÍRÁSOS engedélyt
kapott; minden játék indulásakor elhangzik és megjelenik a SZERZŐ-MEGJELÖLÉS
(lásd `attribucio_szoveg`). Ahol a szerző ismeretlen, ott „várjuk a szerző
jelentkezését" felirat szerepel.

A tényleges játéklogika a `jatekok/` alcsomag generátor-korutinjaiban él; egy
játék akkor „indítható", ha a kulcsa szerepel a `jatekok.REGISZTER`-ben. Ha
még nincs megírva, a felület tisztességesen közli: „még készül" – nincs hamis
siker.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Jatek:
    kulcs: str
    nev: str
    leiras: str
    retro: bool = True            # retró hang + szerző-intro (False = saját)
    szerzo: str = ""              # eredeti szerző (üres = ismeretlen)
    ev: str = ""                  # az eredeti megjelenés éve
    jogtulaj: str = ""            # a szerzői jog jogosultja (üres = mint szerző)
    felnott: bool = False         # 18+ tartalom (figyelmeztetéssel indul)


# az ismétlődő szerzők, hogy ne gépeljük el őket
VAKODA = "Iván Várhelyi (VAKODA Software)"
PILLE = "a Pille software"
TURAI = "Turai László (Brailab Software)"


# =====================================================================
#  RETRÓ JÁTÉKOK
# =====================================================================
RETRO: tuple[Jatek, ...] = (
    # ---- kártya / kocka / szerencse ----
    Jatek("huszonegy", "Huszonegy (21)",
          "Ócsvári Áron magyar kártyás huszonegyese a gép ellen: legalább két "
          "lapot kérj, 15 pont alatt ne állj meg, és maradj 21-en vagy alatta "
          "– a gép 19-ig húz, aki 21 fölé megy, befuccsol.",
          szerzo="Ócsvári Áron", ev="2010"),
    Jatek("hazard", "Itt a piros, hol a piros?",
          "Három gyufásdoboz, egyben a piros golyó. Találd ki, melyikben!",
          szerzo=PILLE, ev="1994"),
    Jatek("snobli", "Snóbli",
          "A klasszikus kocsmai érme-kitalálós: hány érme van a kezekben?",
          szerzo=VAKODA, ev="1993"),
    Jatek("kocka3", "Kockadobás – három kocka",
          "Három kockával dobtok felváltva; egyformákra extra pont jár.",
          szerzo=PILLE, ev="1994"),
    Jatek("kocka1", "Kockajáték – összeg",
          "Egyszerű kockás pontverseny a gép ellen: a nagyobb összeg nyer.",
          szerzo="L. Bonta", ev="1994"),
    Jatek("kockadob", "Kockadobás – mezőverseny",
          "Egy kockával lépegettek a célig; aki a másikra lép, kiüti a startra.",
          szerzo=PILLE, ev="1994"),
    Jatek("rulett", "Rulett",
          "Kaszinó rulett: tégy számra, színre, párosra vagy tucatra.",
          szerzo=VAKODA, ev="1993"),
    Jatek("rulibuli", "Rulibuli",
          "Egyszerűsített rulett: a szám páros vagy páratlan lesz-e?",
          szerzo=TURAI, ev="1996"),
    Jatek("gyufa", "Gyufapöckölő játék",
          "Pöcköld a gyufásdobozt pontokért (2, 5 vagy a csoda 10) – tartsd meg "
          "vagy kockáztass tovább; 1–5 játékos és a Brailab gép ellen az "
          "elérendő pontszámig. A hivatalos Homelab-forrás hű átültetése."),

    # ---- logika / stratégia ----
    Jatek("mastermind", "Mastermind (kódtörő)",
          "Találd ki a gép négy színből álló, sorrendes kódját a "
          "fekete-fehér visszajelzések alapján.",
          szerzo=VAKODA, ev="1993"),
    Jatek("nim", "Négyzet kirakó (Nim)",
          "Húsz négyzet, körönként 1–3. Aki az utolsót rakja le, VESZT.",
          szerzo=PILLE, ev="1994"),
    Jatek("torpedo", "Torpedó",
          "Tízszer tízes rácson négy rejtett X-et kell megtalálnod.",
          szerzo=PILLE, ev="1994"),
    Jatek("horstep", "Lóugrás verseny",
          "Sakkló-lépésekkel érj a tábla túlsó sarkába a gép előtt.",
          szerzo=PILLE, ev="1994"),
    Jatek("labirint", "Labirintus",
          "Tapogatózz ki a labirintusból: iránnyal lépsz, a falat bemondja.",
          szerzo=PILLE, ev="1994"),
    Jatek("parbaj", "Párbaj",
          "Négy pozíció, rejtett ellenfél: találd el, hol áll, mielőtt ő téged.",
          szerzo="", ev=""),                      # ismeretlen szerző
    Jatek("teke", "Teve-parki tekeparti",
          "Kilenc bábu, középen a király (3 pont). Guríts a gép (Frédi) ellen!",
          szerzo=TURAI, ev="1996"),

    # ---- kvíz / oktató ----
    Jatek("allatism", "Állatismeret",
          "Biológiai kvíz állatokról: hol él, mivel táplálkozik, hová tartozik.",
          szerzo=VAKODA, ev="1993"),
    Jatek("fovaros", "Főváros",
          "Földrajzi kvíz: mondd meg az országok fővárosát.",
          szerzo=VAKODA, ev="1993"),
    Jatek("atomvad", "Atomvadász",
          "Kémiai betűvadászat: keresd a vegyjeleket a szavakban.",
          szerzo=VAKODA, ev="1993"),
    Jatek("braille", "Braille gyakorlat",
          "Betű és pontkombináció megfeleltetése – a Braille-írás gyakorlása.",
          szerzo="VAKODA Software", ev="1993"),
    Jatek("morse", "Morse ábécé",
          "Tanuld és gyakorold a Morse-kódot: betűből jel, jelből betű.",
          szerzo=TURAI, ev="1996"),
    Jatek("kitalal", "Szókitaláló",
          "A gép egy fogalomra gondol; tulajdonságok alapján találd ki.",
          szerzo=VAKODA, ev="1993"),
    Jatek("szamtan", "Számtan tanár",
          "Fejszámoló feladatok testre szabható művelettel és nagyságrenddel.",
          szerzo=VAKODA, ev="1993"),
    Jatek("memoria", "Memória – sorrend",
          "Jegyezd meg a növekvő sorozatot, és mondd vissza pontosan!",
          szerzo=VAKODA, ev="1993"),
    Jatek("memory", "Memory – párosító",
          "A klasszikus párkereső memóriajáték, hangalapú rácson.",
          szerzo=VAKODA, ev="1993"),
    Jatek("parver", "Billentyűzet verseny",
          "Reakciójáték: nyomd le minél gyorsabban a bemondott billentyűt.",
          szerzo="VAKODA Software", ev="1993"),

    # ---- kaland / egyéb ----
    Jatek("csata", "Csata – várvédés",
          "Védd meg a várat a törökök ostromától – lövésről lövésre.",
          szerzo=TURAI, ev="1996"),
    Jatek("harcos", "Országút harcosa",
          "Választásos kalandkönyv a járvány utáni világban, felfegyverzett "
          "Dodge Interceptorral.",
          szerzo="Varga Tamás (Sir-Soft) és Pál Zsolt (Pille software)",
          ev="1995–96"),
    Jatek("allah", "Allah szakálla",
          "Sugárzásmérővel keresd az időzített bombát a százemeletes "
          "szállodában, mielőtt lejár az idő.",
          szerzo="Csapó Endre (Marx György ötletéből)", ev="1993"),
    Jatek("zongora", "Zongora",
          "Zongorázz a számítógép billentyűzetén – egész és félhangok, oktávok.",
          szerzo="L. Turai", ev="1995"),
    Jatek("szindbad", "Szindbád (18+)",
          "Felnőtt hangvételű, humoros választásos kaland: mentsd meg a "
          "szultán hajóját, és válassz a jutalomból okosan.",
          szerzo=TURAI, ev="1996", felnott=True),

    # ---- a JATEK.EXE gyűjtemény mini-játékai (klasszikus/közkincs
    #      mechanikák; a szerző egyelőre ismeretlen – várjuk a jelentkezését) ----
    Jatek("domino", "Dominó",
          "A klasszikus dominó a gép ellen: illeszd a köveket a végekhez."),
    Jatek("tozsde", "Tőzsde",
          "Kis piac-szimuláció: vásárolj olcsón, adj el drágán."),
    Jatek("korong", "Korong",
          "Pozíciós táblás játék: fordítsd a magad színére a korongokat."),
    Jatek("nyulfarm", "Nyúlfarm",
          "Tenyészd és gazdálkodd fel a nyúlfarmodat évről évre."),
    Jatek("hamurabi", "Hamurabi",
          "Az ősi királyság-menedzsment: vess, arass, etesd a népet."),
    Jatek("mokita", "Mokita",
          "Kis logikai mini-játék a gyűjteményből."),

    # ---- HITELES portok a hivatalos Homelab/Brailab gyűjteményből
    #      (Documents\játékok) – a szabályokat, üzeneteket és állandókat a
    #      FORRÁS szerint követve, az EREDETI szerzők megjelölésével ----
    Jatek("blackjack", "Blackjack",
          "Kaszinó blackjack az osztó ellen: 21-hez közel túllépés nélkül, "
          "tét, lapkérés, megállás, duplázás és split.",
          szerzo="Halmágyi István", ev="1985"),
    Jatek("szamkit1", "Számkitaláló",
          "A gép egy számra gondol 1 és 100 között; tippelj, és a "
          "„nagyobbat / kisebbet” jelzésekkel találd ki minél kevesebből."),
    Jatek("amoba", "Amőba",
          "Öt egy sorban a gép ellen 17-szer 17-es táblán: a te jeled az X, "
          "a gépé az O. Védekező játékstílus is kérhető."),
    Jatek("nimjatek", "Nim játék",
          "Az nyer, aki utolsónak vesz: te adod a kezdő állást (2–5 kupac), "
          "a gép a nim-összeg szerint optimálisan lép."),
    Jatek("memteszt", "Memóriateszt",
          "A gép szám–szó párokat mond; jegyezd meg, és mondd vissza sorban – "
          "egyre több párral, egészen húszig."),
    Jatek("lotto", "Lottó szerencse",
          "Lottószám-tipp generátor: hagyományos ötös lottó (5/90) vagy hatos "
          "lottó (6/45), akár 255 szelvényre."),
    Jatek("foldrajz", "Földrajz – kitalálom az országod",
          "Gondolj egy európai országra, és igen–nem kérdésekkel kitalálom, "
          "melyikre gondoltál!"),
    Jatek("szamkit2", "Számkitaláló 2",
          "A gép egy számra gondol nulla és az általad megadott felső határ "
          "között; tippelj, és a nagyobbat–kisebbet jelzésekből fejtsd ki."),
    Jatek("dobokoc", "Dobókocka",
          "Pontgyűjtő kockajáték a gép ellen: a hatos új dobásokat ad, de 55, "
          "77 és 99 pontnál legurul a kocka – 99 fölött a több pont nyer."),
    Jatek("kocka", "Kockajáték – hat dobás",
          "HOMELAB 4 kockapárbaj: hatszor dobsz te, hatszor a gép, a nagyobb "
          "összeg nyer – az eredeti Brailab-párbeszéddel."),
    Jatek("fejtoro", "Fejtörő – matematika",
          "A HOMELAB 4 gép tíz szorzási feladatot ad; a jó válasz öt pont, a "
          "rossz mínusz tíz, a végén osztályzatot kapsz a tudásodra."),
    Jatek("kockaparti", "Kockaparti – tetszőleges menet",
          "Mint a kockajáték, de te szabod meg, hány menet legyen a forduló "
          "(1–100); döntetlennél visszavágót kérhetsz a gép ellen."),
    Jatek("celozz", "Célozz a hajóra!",
          "Tengeri tüzérjáték 20-szor 20-as mezőn: rejtett ellenséges hajó, "
          "10 lövedék, égtáj-visszajelzés – süllyeszd el, vagy jön a hadbíróság!",
          szerzo="Schuck Antal", ev="1987"),
    Jatek("tizfeles", "Tíz feles a tudományod",
          "Számkitaláló tíz tippel, csavaros, pálinkás humorral: minél hamarabb "
          "találod el a gondolt számot, annál több „feles” a jutalom."),
    Jatek("fogadas", "Fogadásos autóverseny",
          "Akár négy játékos fogad a nyolcvanas évek Forma-1-eseire (Lauda, "
          "Prost, McLaren, Alboreto): tégy tétet, és gyűjts 800 forintig!",
          szerzo="Balogh Tibor", ev="1984"),
    Jatek("szokita", "Szó kitalálós játék",
          "Szó-mastermind: a gép egy hárombetűs magyar szóra gondol, te "
          "hárombetűs szavakat tippelsz, és megmondja, hány betű egyezik a "
          "helyén – X-re elárulja a szót."),
    Jatek("szofajok", "Szófajok",
          "Nyelvtani gyorskvíz: a gép szót mond, te felismered a szófaját "
          "(névelő, számnév, főnév, ige, melléknév) – a végén osztályzattal."),
    Jatek("reszeg", "Részeg vagyok, rózsám (18+)",
          "Felnőtt, humoros számkitaláló 0 és 20 között konyakért: minden rossz "
          "tipp egy felesbe kerül, tíz tipp után te fizetsz – hat kör után záróra!",
          szerzo="Schuck Antal", ev="1987", felnott=True),
    Jatek("betpoker", "Betűpöker",
          "Szó-mastermind pontozással: a gép egy szóra gondol, megmondja a "
          "hosszát, te azonos hosszú szavakat tippelsz, és megtudod, hány betű "
          "van a helyén – 200 pontból gazdálkodsz a rossz tippekért."),
    Jatek("felkaru", "Félkarú bandita",
          "Pénznyerő automata: 10 forinttal indulsz, egy pénzbedobás 2 forint. "
          "Add meg, hányszor pörögjön a három tárcsa – két egyforma 5, három "
          "egyforma 25 forintot fizet. Addig játszol, míg el nem fogy a pénzed.",
          szerzo="Sédi Gábor", ev="1985"),
    Jatek("randi", "Telerandi",
          "Flörtös számkitaláló: a gép egy öt-hat jegyű telefonszámot választ, "
          "te számjegyenként tippelsz (négy próba, nagyobbat-kisebbet "
          "segítséggel). Fejtsd meg az egészet, és jöhet a randi – a Homelab "
          "klasszikus csattanójával a végén.",
          szerzo="Kisvarga Zsolt"),
    Jatek("loverseny", "Lóverseny",
          "Fogadós lóverseny Brailabbal, a versenybíróval: 1–10 játékos, "
          "fejenként 2000 forint. Fogadj egy rajtszámra és egy tétre – a "
          "győztesre 100, a másodikra 50, a harmadikra 25 százalék jár, "
          "egyébként a tét bánja. Aki elfogy, kiesik."),
    Jatek("nurmi", "Nurmi – futóverseny",
          "Fussál versenyt Murmival, a híres futóval! Felváltva sprinteltek, "
          "minden sprint öt-harminc méter; aki előbb eléri az ezer métert, "
          "győz. A vesztes vigaszdíjként visszavágót kérhet.",
          szerzo="Schuck Antalné"),
    Jatek("penzfel", "Pénzfeldobó",
          "Kétszemélyes érme-fogadás: mindketten fej vagy írás mellett tesztek "
          "(nem tippelhettek ugyanarra), és a feldobott pénz dönt – néha egy "
          "madár is beleszól. Fogadhattok konkrét tétbe, vagy csak a sorrendet "
          "döntitek el."),
    Jatek("kincs", "Elásott kincs",
          "Egy 15-ször 15-ös hálón a gép elás egy négy négyzet hosszú kincset; "
          "gödrökkel keresed, égtáj-segítséggel, tíz próbálkozásból. Találd meg, "
          "mielőtt elfogynak az ásásaid!",
          szerzo="Sűdi Gábor", ev="1985"),
    Jatek("apollo", "Apolló – holdraszállás",
          "Holdraszálló szimulátor: 20 kilométer magasból, 10 méter "
          "másodpercenként közeledsz. Alkalmanként megadod, hány fékezőrakétát "
          "indíts (összesen 700); a fizika dönt. Két méter per másodperc alatt "
          "kitűnő a leszállás, tizenkettő felett a személyzet odavész."),
    Jatek("simon15", "Szájmon 15",
          "Zenei memóriajáték: a gép ad egy dallamot (a négy hang 1–4), te "
          "visszajátszod. Hibátlan menet után a dallam két hanggal hosszabb; hét "
          "hibátlan menet a győzelem. Egy hiba, és kezdheted elölről!",
          szerzo="Csapó Endre", ev="1988"),
    Jatek("jvelem", "Játssz velem",
          "Kis fejtörő a géppel: két számot kér, kitalálod a szorzatukat (durva "
          "hibára megkapod a magadét!), majd az összegüket, végül gondol egy "
          "számot 1 és 100 között, amit ki kell találnod."),
    Jatek("atlantisz", "Atlantisz",
          "Tengeri navigáció egy 100-szor 100-as rácson: nyolc égtáj felé "
          "hajózol, radarral kutatod a rejtett szigetet, közben fogy az "
          "üzemanyag – négy olajkút menthet meg. Találd meg a szigetet, mielőtt "
          "kifogysz vagy ismeretlen vizekre tévedsz!",
          szerzo="Kisvarga Zsolt"),
    Jatek("szammem", "Számemória",
          "Szám-memóriajáték: a gép egy számsort ad, ami körönként eggyel "
          "hosszabb, és neked sorban vissza kell írnod. Minden hibás számjegy "
          "egy hibapont; tíznél több hiba a vég. Meddig jutsz a fejben?",
          szerzo="Kisvarga Zsolt"),
    Jatek("hajocsata", "Hajócsata",
          "Egy rejtett, mozgó ellenséges hajót kell elsüllyesztened a 15-ször "
          "10-es tengeren. Bombázz egy pontra, telepíts aknát, indíts torpedót, "
          "vagy derítsd fel radarral az irányt és távolságot. Öt találat, és a "
          "hajó a mélybe süllyed!"),
    Jatek("kastely", "Az elvarázsolt kastély",
          "Veszedelmekkel teli szöveges kaland: bolyongj a nyolc égtáj mentén a "
          "kastély 45 termében, gyűjts tárgyakat, és győzd le a hét szörnyet – "
          "mindegyikhez más eszköz kell! A cél megtalálni a kék madarat, "
          "kalitkába zárni, és a bázisra vinni, mielőtt letelik a 12 óra.",
          szerzo="Csapó Endre"),
)


# =====================================================================
#  SUPERDL SAJÁT JÁTÉKOK  (nem retró: normál hang, nincs szerző-intro)
# =====================================================================
SAJAT: tuple[Jatek, ...] = (
    Jatek("milliomos", "Milliomos kvíz",
          "A népszerű „Legyen Ön is Milliomos” kvízműsor által INSPIRÁLT, "
          "akadálymentes kvízjáték: 15 lépcsős pénzlétra 40 millió forintig, "
          "garantált pontokkal, három segítséggel (felezés, telefonos segítség, "
          "közönségszavazás) és több mint ezer kérdéssel. Saját, jogtiszta "
          "változat – a műsor zenéje és hangja nélkül.",
          retro=False),
    Jatek("uno", "UNO",
          "A klasszikus UNO három ellenféllel: rakj színben vagy értékben "
          "egyezőt, és fogyj ki elsőként a lapjaidból!",
          retro=False),
    Jatek("enektanito", "Gépi ének",
          "Taníts a gépnek egy dalt, és a saját formáns-hangján elénekli! "
          "Soronként adsz meg egy hangot: SZÓTAG HANGNÉV HOSSZ (pl. „bo g4 0.4”). "
          "A hangnév egy betű (c, d, e, f, g, a, h) és egy oktávszám (a 4 a "
          "középső), a hossz másodpercben vagy szóval (fél, negyed). Parancsok: "
          "énekeld, súgó, példa skála, példa boci, töröl, kész. A hangot 100 "
          "százalékban a mi saját szintetizátorunk adja – nincs benne idegen "
          "hangminta.",
          retro=False),
    Jatek("slot", "Félkarú rabló",
          "Pörgesd a tárcsákat, és gyűjts minél több érmét a nyerőtáblázat "
          "szerint.",
          retro=False),
    # Mille Bornes: EGYELŐRE KIVÉVE a listáról, mert még nincs megírva (a
    # katalógusban lógott, de „nem indult el" – listás visszajelzés). Ha kész a
    # jatek_millebornes és bekerül a REGISZTER-be, ezt visszatesszük.
)


def mind() -> tuple[Jatek, ...]:
    return RETRO + SAJAT


def keres(kulcs: str):
    for j in mind():
        if j.kulcs == kulcs:
            return j
    return None


# ---- szerző-megjelölés (a fejlesztő KIFEJEZETT kérése) ------------------

def attribucio_szoveg(j: Jatek) -> str:
    """A minden retró játék elején elhangzó és megjelenő szerző-megjelölés."""
    if j.szerzo:
        elso = f"Ezt a játékot készítette: {j.szerzo}"
        if j.ev:
            elso += f", {j.ev}-ban"
        elso += "."
    else:
        elso = ("Ennek a játéknak a szerzője egyelőre ismeretlen – "
                "várjuk a szerző jelentkezését.")
    kozep = (" Modernizálta Kőrösmezey Dávid, köszönettel azokért az órákért, "
             "amit együtt tölthettünk el ezen játékok játszásakor.")
    jog = j.jogtulaj or j.szerzo
    veg = f" A szerzői jogok {jog} illetik." if jog else ""
    return elso + kozep + veg
