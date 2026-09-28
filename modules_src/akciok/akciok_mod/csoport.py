# -*- coding: utf-8 -*-
"""Közös termékcsoportok minden bolthoz (Petrus József kérése, 2026-09-26).

A PDF-újságos boltoknál (Lidl, Tesco, Spar, Auchan) nincs termékcsoport – a
„kategória" ott az újság neve. Ezért egy KÖZÖS szűrő kell, ami a
„Tejtermék"-et minden boltban ugyanúgy érti.

A besorolás KULCSSZAVAS (nem AI, nem hálózat): a termék nevéből, ha abból
nem derül ki, a bolt saját kategóriájából, végül a bolt jellegéből. A
szabályok SORRENDJE számít – az első találat nyer: „Tejszelet" az
édességekhez kerül, mielőtt a „tej" a tejtermékekhez vinné; „Almás pite" a
pékáruhoz, mielőtt az „alma" a gyümölcshöz. Ami bizonytalan, az „Egyéb" –
inkább oda, mint rossz helyre.

A kulcsszavak ékezet nélkül, a szó ELEJÉRE illesztve (a magyar összetett
szavak miatt: „csirkemellfilé" → „csirke…"). Az `=` előtag teljes szót
jelent (pl. „=bor", hogy a „borsó" ne ital legyen), a `~` a szó belsejét is
(„lecsókolbász" → „~kolbasz").
"""
import re

from .termek import ekezet_nelkul

EGYEB = "Egyéb"

# (csoport, kulcsszavak) – a sorrend a szabály!
_SZABALYOK = [
    ("Baba", "~pelenka babakozmetik bebietel bebiital babaetel babafurdet "
             "popsi cumi cumisuveg babatorl babahinto babaolaj =baby kubu hipp gerber "
             "babydream babylove pampers huggies bebivita tejpep babaapol"),
    ("Állateledel", "macska kutya allateledel eledel alom =whiskas "
                    "pedigree prevital felix =perfect friskies kitekat "
                    "jutalomfalat ragocsont"),
    # a parfüm KÜLÖN csoport (2026-09-27: az Illatorium saját kínálata és a
    # drogériák parfümjei egy helyen). Csak teljes szóra: a „parfümös
    # tusfürdő" maradjon drogéria.
    ("Parfüm és illat", "=parfum =parfumje =eau =edp =edt =edc =kolni "
                        "parfumviz illatpermet =testpermet"),
    ("Drogéria és szépségápolás",
     "sampon hajbalzsam =balzsam hajpakolas hajmaszk hajfest hajlakk hajhab "
     "hajzsele hajolaj tusfurd tusolo habfurd dezodor deo =izzadsag "
     "fogkrem fogkefe fogselyem fogkoz mosdato szajviz szajvi arckrem kezkrem labkrem "
     "testapol testvaj testolaj arcszerum szerum arctisztit arclemos "
     "sminklemos micellas napozo naptej fenyvedo parfum kolni rúzs "
     "ruzs ajak szempilla szemhej szemceruza szemfest alapozo puder "
     "pirosito korom =smink highlighter borotv borotva intim tampon "
     "egeszsegugyi =betet tisztasagi vatta fultiszt szappan kezmos "
     "~szappan ~sampon kontaktlencse =vitamin etrend magnezium "
     "hajcsat hajgumi hajpant hajdisz ~hajszinez hajspray fejbor ovszer"),
    ("Háztartás és tisztítószer",
     "mososzer moso =mosopor mosogel mosokapszula mosogat oblito "
     "tisztito tisztitoszer fertotlenit =wc wc-  toalettpapir toalett "
     "papirtorlo konyhai papir zsebkendo szemeteszsak szemetes folia "
     "alufolia szivacs ~mososzer ~oblito ~tisztito illatgyongy penesz ~kendo ~torlokendo felmoso legfrissit illatgyertya gyertya =elem "
     "elemek izzo villanykorte vizkoold vizkooldo zsiroldo "
     "ablaktisztit padlotisztit finish domestos ariel persil lenor "
     "=jar sanytol calgon vanish perwoll silan bref cillit "
     "mosogepi mosogatogep tabletta"),
    ("Fagyasztott", "gyorsfagyaszt fagyaszt mirelit jegkrem fagylalt "
                    "=jegkocka hasab halrud"),
    ("Ital", "asvanyviz =viz =vize szensavas udito =cola =kola "
             "limonade gyumolcsle =le =leve nektar szorp =sor =sore "
             "=sorok =bor =bora vorosbor feherbor roze pezsgo palinka "
             "whisky vodka likor rum =gin konyak brandy energiaital "
             "=ital itala jegestea =tea teafilter =kave kaveszemes "
             "kavekapszula kavespecial =cappuccino "
             "latte shot fuzetea sorpack ~buzasor =pils ~bier weissbier =jagermeister prosecco ~likor sportital ~aperitif ~szorp ~kave gyumolcsital ~italpor kaveital ~szirup gyogyviz =icetea nestea =smoothie =kombucha =nektar"),
    ("Édesség és snack", "tejszelet =rudi csoki csokolade "
                         "=cukorka cukorka kemenycukor nyaloka bonbon desszert keksz "
                         "puszedli fondant ~csokolad "
                         "ostya napolyi piskota gumicukor zselecukor "
                         "=szelet muzliszelet proteinszelet chips =ropi "
                         "perec popcorn =mogyoro pattogatott "
                         "=nasi rago rágó marcipan halva praline "
                         "=torta ~torta ~sutemeny ~snack ~mogyoro ~kraker ~kreker tortak "
                         "=pite =suti sutemeny linzer"),
    ("Tejtermék és tojás", "=tej =tejes tejfol ~joghurt kefir =turo "
                           "turos =sajt sajtos sajtkrem =vaj =vajas "
                           "tejszin habtejszin mascarpone mozzarella "
                           "habalap =trapista =gouda =edami =cheddar =feta "
                           "=parmezan =camembert =brie =tojas =tojast "
                           "=puding tejbegriz tejberizs =ayran =skyr "
                           "~pudding tejital tejdesszert zabital sojaital "
                           "=margarin =rama"),
    ("Hús, hal, felvágott", "=hus husos csirke diszno toka ~kolbasz ~szalami ~sonka ~virsli ~szalonna ~felvagott ~pastetom =csirkemell pulyka "
                            "sertes marha =borju =barany =kacsa =liba "
                            "karaj =comb combfile =mell mellfile "
                            "=daralt kolbasz szalami sonka virsli "
                            "felvagott szalonna tepertő toperto "
                            "pastetom mahony parizsi =fasirt =hamburger "
                            "=hal =halfile lazac tonhal harcsa ponty "
                            "pisztrang tokehal hekk garnela =rak "
                            "rakpalca szardinia makrela hering "
                            "csulok oldalas tarja =nyul nyulfel krinolin szafalade =maj =lecso"),
    ("Pékáru", "kenyer zsemle kifli =bucka =buci bagett kalacs "
               "pogacsa =fank retes =csiga muffin =toast toastkenyer "
               "tortilla croissant ~kenyer ~kifli ~zsemle =pita =lepeny pekaru =briós brios kornspitz ciabatta =vekni "
               "=kalacs =bejgli =pogi"),
    ("Alapvető élelmiszer", "=liszt =cukor =kristalycukor porcukor =so "
                            "=olaj napraforgo olivaolaj =ecet =rizs "
                            "teszta spagetti makaroni =penne fusilli "
                            "=orso szarvacska =metelt galuska konzerv "
                            "befott lekvar =mez szosz =ketchup majonez "
                            "mustar fuszer =bors =orolt =leves "
                            "levespor =muzli zabpehely gabonapehely "
                            "corn flakes =kakao =bab =lencse csicseri "
                            "=kukorica =zab tarkabab feherbab vorosbab mogyorovaj puree pure =ivolé "
                            "savanyusag csemege ecetes ~teszta "
                            "=chilis =pesto =humusz =tahini dzsem "
                            "kakaopor pudingpor sutopor eleszto ~morzsa =maggi "
                            "zselatin =tészta taco"),
    ("Zöldség és gyümölcs", "=alma =almat banan =korte szolo narancs "
                            "citrom mandarin =lime dinnye gorogdinnye "
                            "sargadinnye =eper malna afonya szeder "
                            "szilva =barack oszibarack kajszi =kiwi "
                            "ananasz mango avokado grapefruit =dio "
                            "=mandula paradicsom =paprika ~uborka "
                            "burgonya =krumpli hagyma lilahagyma "
                            "fokhagyma =repa sargarepa cekla =retek "
                            "kaposzta =kel karfiol brokkoli cukkini "
                            "sutotok =padlizsan salata "
                            "jegsalata rukkola spenot =gomba "
                            "csiperke =zoldseg zoldsegek =gyumolcs "
                            "=petrezselyem =zeller =kapor karalabe =sosk =cekla"),
]

# NEM ÉLELMISZER (0.6.0: Pepco, Müller-játékok, Libri). A lista VÉGÉN állnak,
# hogy az élelmiszer- és drogériaszabályok előbb döntsenek; a vegyes áru
# boltjainál (_CSAK_NEM_ELELMISZER) viszont CSAK ezek jöhetnek szóba – egy
# „macskamintás ruha" ott ne legyen állateledel.
_SZABALYOK += [
    ("Ruházat és cipő", "=polo polot =ruha =ruhat szoknya leggings pizsama "
                        "zokni harisnya pulover pulcsi kardigan kabat dzseki "
                        "nadrag farmer =ing =inget bluz =cipo cipot csizma "
                        "papucs sapka kesztyu sal =sal melltarto bugyi "
                        "alsonadrag boxer overal jelmez tunika "
                        "melegito =mez fehernemu"),
    ("Otthon és dekoráció", "parna parnahuzat takaro pled agynemu lepedo "
                            "torolkozo furdolepedo fuggony szonyeg labtorlo "
                            "dekor dekoracio bogre tanyer =pohar poharak "
                            "evoeszkoz =tal =talka kosar =doboz tarolo lampa "
                            "koszoru =vaza gyertyatarto kepkeret =ora faliora "
                            "=serpenyo =labas edeny"),
    ("Játék", "jatek jatekfigura pluss plussfigura =lego kirako puzzle "
              "tarsasjatek =baba babak jatekauto =auto kisauto labda "
              "szinezo gyurma =kocka"),
    ("Könyv", "=konyv konyvek regeny"),
    # műszaki és barkács (Euronics, Praktiker – 2026-09-28)
    ("Műszaki cikk", "=tv televizio okostelefon telefon mobiltelefon laptop "
                     "notebook =tablet monitor nyomtato fulhallgato "
                     "hangszoro soundbar kavefozo kavegep mosogep "
                     "mosogatogep szaritogep hutoszekreny =huto "
                     "hutogep fagyaszto =suto mikrohullamu "
                     "porszivo robotporszivo =vasalo turmix botmixer "
                     "konyhagep robotgep =fozolap fozolap =tuzhely "
                     "legkondicionalo klima hajszarito borotva "
                     "=konzol jatekkonzol okosora =kamera "
                     "=smart =led =qned =oled"),
    ("Barkács és kert", "=kert kerti =tarolo =furo furogep csavar "
                        "csavarhuzo szerszam szerszamkeszlet =kalapacs "
                        "=festek falfestek =csempe burkolat laminalt parketta "
                        "zuhanykabin =mosdo =csaptelep =wc =ajto =ablak "
                        "=letra fuvago funyiro gereblye lapat =ontozo "
                        "tomlo =grill pavilon sorpad napernyo "
                        "=fenyforras izzo =lampa hosszabbito kabel "
                        "=polc =szekreny =tuzifa =cserep =viragfold"),
]

_NEM_ELELMISZER = ("Ruházat és cipő", "Otthon és dekoráció", "Játék",
                   "Könyv", "Parfüm és illat", "Drogéria és szépségápolás",
                   "Háztartás és tisztítószer", "Műszaki cikk",
                   "Barkács és kert")
_CSAK_NEM_ELELMISZER = {"Pepco", "Euronics", "Praktiker"}
# a nem-élelmiszer boltok alapcsoportja, ha a névből semmi nem derül ki
_NEM_ELELMISZER_ALAP = {"Euronics": "Műszaki cikk",
                        "Praktiker": "Barkács és kert"}

# a bolt SAJÁT kategóriájának szavai (Rossmann, dm, Penny) – ha a névből
# nem derül ki
_KATEGORIA_JEL = [
    ("Játék", "jatek jatekok"),
    ("Könyv", "=konyv konyvek"),
    ("Baba", "=baba pelenka"),
    ("Állateledel", "=allat allateledel =kisallat"),
    ("Háztartás és tisztítószer", "haztartas tisztit mosas"),
    ("Drogéria és szépségápolás", "dekorkozmetika arcapolas =haj "
                                  "szepsegapolas szajapolas parfum "
                                  "egeszseg kozmetik testapolas "
                                  "hajapolas napozo"),
    ("Fagyasztott", "fagyaszt mirelit"),
    ("Ital", "=ital =italok =bor =sor"),
    ("Édesség és snack", "edesseg snack nasi"),
    ("Tejtermék és tojás", "tejtermek tojas"),
    ("Hús, hal, felvágott", "=hus husok =hal felvagott"),
    ("Pékáru", "pekaru =kenyer"),
    ("Zöldség és gyümölcs", "zoldseg gyumolcs"),
    ("Alapvető élelmiszer", "=elelmiszer alapveto konzerv"),
]

# ha semmi nem illik: a bolt jellege
_BOLT_ALAP = {"Rossmann": "Drogéria és szépségápolás",
              "dm": "Drogéria és szépségápolás"}
# vegyes kínálatú drogéria (édességet, kávét, italt is árul): a NÉV dönt, és
# csak ha semmi nem illik, akkor drogéria
_ALAP_HA_SEMMI = {"Müller": "Drogéria és szépségápolás"}

CSOPORTOK = [c for c, _k in _SZABALYOK] + [EGYEB]


def _minta(szavak: str):
    reszek = []
    for s in szavak.split():
        s = ekezet_nelkul(s)
        if s.startswith("="):
            reszek.append(r"\b%s\b" % re.escape(s[1:]))
        elif s.startswith("~"):             # a szó BELSEJÉBEN is (összetett szó)
            reszek.append(re.escape(s[1:]))
        else:
            reszek.append(r"\b%s" % re.escape(s))
    return re.compile("|".join(reszek))


_NEV_MINTAK = [(c, _minta(k)) for c, k in _SZABALYOK]
_KAT_MINTAK = [(c, _minta(k)) for c, k in _KATEGORIA_JEL]


def _elso(mintak, szoveg: str):
    sz = ekezet_nelkul(szoveg or "")
    for csop, m in mintak:
        if m.search(sz):
            return csop
    return None


def csoportja(t) -> str:
    """A termék csoportja, egyszer kiszámolva és a termékben megjegyezve."""
    if not t.csoport:
        t.csoport = besorol(t.nev, t.kategoria, t.bolt)
    return t.csoport


def besorol(nev: str, kategoria: str = "", bolt: str = "") -> str:
    """A termék közös csoportja: név → bolti kategória → bolt jellege →
    „Egyéb"."""
    if bolt in _CSAK_NEM_ELELMISZER:
        # a bolt SAJÁT profilja elől: a Praktiker „kerti tárolója" barkács
        # és kert, ne otthon és dekoráció
        alap = _NEM_ELELMISZER_ALAP.get(bolt)
        for c, m in _NEV_MINTAK:
            if c == alap and m.search(ekezet_nelkul(nev or "")):
                return c
        for c, m in _NEV_MINTAK:
            if c in _NEM_ELELMISZER and m.search(ekezet_nelkul(nev or "")):
                return c
        return _NEM_ELELMISZER_ALAP.get(bolt, EGYEB)
    if bolt in _BOLT_ALAP:
        # drogérialánc: a SAJÁT kategóriája megbízhatóbb, mint a név (egy
        # „citromos tusfürdő" ne legyen gyümölcs); élelmiszernél a név dönt
        k = _elso(_KAT_MINTAK, kategoria)
        if k and k != "Alapvető élelmiszer":
            return k
        if k:
            return _elso(_NEV_MINTAK, nev) or k
        nevbol = _elso(_NEV_MINTAK, nev)
        drog = ("Parfüm és illat", "Drogéria és szépségápolás",
                "Háztartás és tisztítószer",
                "Baba", "Állateledel")
        return nevbol if nevbol in drog else _BOLT_ALAP[bolt]
    return (_elso(_NEV_MINTAK, nev) or _elso(_KAT_MINTAK, kategoria)
            or _ALAP_HA_SEMMI.get(bolt) or EGYEB)
