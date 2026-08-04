package com.superdl.launcher.assistant

import android.content.Context

/**
 * Elena helyi tudásbázis – gyakori kérdésekre ad választ internet nélkül.
 * Forrás: beépített bejegyzések + assets/elena_tudas_superdl.txt (SUPERDL.TXT).
 */
object ElenaKnowledgeBase {

    data class Entry(
        val id: String,
        val triggers: List<String>,
        val answer: String,
        val priority: Int = 0
    )

    private val entries: List<Entry> = listOf(
        Entry(
            id = "superdl_what",
            triggers = listOf(
                "mi az a super dl", "mi a super dl", "mi ez az app", "mi ez a program",
                "mire jo a super dl", "mire valo a super dl", "mi a launcher"
            ),
            answer = "A Super DL egy magyar, vakbarát Android kezdőképernyő, amely a telefon launcherje. " +
                "Gesztusokkal és hanggal vezérelhető: hívás, üzenet, ébresztő, S O S, hírek, könyvolvasás, " +
                "navigáció, kamera eszközök és sok más. Minimális látás mellett is használható. " +
                "Én vagyok Elena, a hangos asszisztensed.",
            priority = 10
        ),
        Entry(
            id = "elena_who",
            triggers = listOf(
                "ki vagy", "ki vagy te", "te ki vagy", "mi a neved", "hogyan hivnak",
                "ki az elena", "mi az elena"
            ),
            answer = "Én Elena vagyok, a Super DL hangos asszisztense. Segítek parancsokkal: idő, hívás, üzenet, " +
                "naptár, zene, navigáció és még sok minden. Mondd: segítség, ha szeretnéd hallani, mit tudok.",
            priority = 12
        ),
        Entry(
            id = "elena_wake",
            triggers = listOf(
                "hogyan ebredsz fel", "hogyan inditlak", "hogyan hivlak",
                "szia elena mit jelent", "felébresztő", "felebeszto", "elena figyelo"
            ),
            answer = "Felébreszthetsz így: Szia Elena, vagy Kérlek Elena. " +
                "A Beállítások, Asszisztens menüben bekapcsolható az Elena figyelő háttérfigyelés. " +
                "Saját felébresztő mondatot az Elena felébresztő tanítása menüpontban menthetsz.",
            priority = 11
        ),
        Entry(
            id = "gestures",
            triggers = listOf(
                "gesztusok", "söprés", "huzas", "húzás", "hogyan navigalok", "hogyan navigálok",
                "fel le jobbra balra", "mit jelent a söprés"
            ),
            answer = "A fő képernyőn: fel söprés előző elem, le söprés következő, jobbra söprés megnyitás vagy megerősítés, " +
                "balra söprés vissza vagy kilépés. Folyamat közben ugyanígy: jobbra megerősít, balra mégse. " +
                "Tanuló módban kilépéshez két gyors balra söprés kell.",
            priority = 8
        ),
        Entry(
            id = "sos",
            triggers = listOf(
                "s o s", "sos", "veszhelyzet", "vészhelyzet", "sos szam", "sos hivas"
            ),
            answer = "Az S O S vészjelzés: öt másodperces visszaszámlálás, balra söprés megszakítja. " +
                "Utána sorban hívja a beállított számokat, maximum négyet. " +
                "Számok: Beállítások, S O S paraméterek. Mondd: S O S. Zárolt képernyőn is működik.",
            priority = 9
        ),
        Entry(
            id = "pin_lock",
            triggers = listOf(
                "pin zarolas", "pin zárás", "pin kod", "pin kód", "hogyan zarolom", "hogyan zárolom"
            ),
            answer = "A PIN zárolás a Beállítások, Biztonság menüben kapcsolható. Beállíthatod a PIN kódot, " +
                "és zárolt képernyőn is véd. Mondd: pin zárolás, pin beállítás, vagy pin állapot.",
            priority = 7
        ),
        Entry(
            id = "phone_sms",
            triggers = listOf(
                "hogyan hivjak", "hogyan hívjak", "hogyan kuldjek uzenetet", "hogyan küldjek üzenetet",
                "telefon hasznalat", "telefon használat", "sms kuldes", "sms küldés"
            ),
            answer = "Híváshoz mondd: hívd fel és a név, vagy válaszd a Telefon és Hívások menüt. " +
                "Üzenethez: üzenet küldés. A Super DL alapértelmezett telefon és üzenet appként is beállítható " +
                "a Beállítások menüben, így a hívó neve és az SMS is jobban működik.",
            priority = 7
        ),
        Entry(
            id = "alarm_calendar",
            triggers = listOf(
                "ebreszto", "ébresztő", "naptar", "naptár", "program", "idozito", "időzítő"
            ),
            answer = "Ébresztő: mondd ébresztő hét óra, vagy az Idő és Szervezés menüben. " +
                "Naptár: mai program, holnapi program, új program. Időzítő: új időzítő, indíts időzítőt. " +
                "A naptár dátumát és idejét hanggal is megadhatod.",
            priority = 6
        ),
        Entry(
            id = "notes",
            triggers = listOf(
                "jegyzet", "jegyzetek", "sajat jegyzet", "hogyan mentek jegyzetet"
            ),
            answer = "A saját jegyzetek az Idő és Szervezés menüben vannak. Új jegyzet diktálással: mondd új jegyzet. " +
                "Listázás: saját jegyzetek. Törlés: jegyzet törlése. Az internet kereső találatnál le söpréssel " +
                "is menthetsz jegyzetet.",
            priority = 6
        ),
        Entry(
            id = "navigation",
            triggers = listOf(
                "navigacio", "navigáció", "gps", "hol vagyok", "utvonal", "útvonal", "bkk", "kozlekedes", "közlekedés"
            ),
            answer = "Hol vagyok: mond hangosan, vagy a Közösség menüben. Útvonal: útvonal a célállomásra. " +
                "Gyalogos útvonal külön parancs. GPS kitekintő: közeli helyek radarja. " +
                "GPS útvonal rögzítés és útmutatás az Eszközök menüben.",
            priority = 6
        ),
        Entry(
            id = "camera_tools",
            triggers = listOf(
                "kamera", "ocr", "szoveg olvas", "szöveg olvas", "penz felismero", "pénz felismerő",
                "qr", "szin felismero", "szín felismerő", "fenymero", "fénymérő"
            ),
            answer = "Eszközök menü: szöveg olvasó, folyamatos szövegolvasó, pénzfelismerő, QR olvasó, " +
                "szín- és fénydetektor, gyógyszerdoboz és címke olvasó, kamera és szelfi, helyszín felismerő. " +
                "A pénzfelismerőn hangerő gomb: azonnali ellenőrzés.",
            priority = 5
        ),
        Entry(
            id = "media",
            triggers = listOf(
                "zene", "youtube", "konyv", "könyv", "konyvtar", "könyvtár", "diktafon"
            ),
            answer = "Zene: a telefonon lévő zenék. YouTube: hangos keresés és lejátszás. Könyvtár: TXT, EPUB, PDF, DOCX olvasás. " +
                "Diktafon: profi hangfelvétel FLAC-ban, mentett felvételek megosztása. " +
                "Mondd: zene, YouTube keresés, könyvtár, diktafon.",
            priority = 5
        ),
        Entry(
            id = "medication",
            triggers = listOf(
                "gyogyszer", "gyógyszer", "patika orangyal", "patika őrangyal", "emlekezteto", "emlékeztető"
            ),
            answer = "A Patika Őrangyal gyógyszer-emlékeztető. Új gyógyszer hozzáadása, listázás, törlés hanggal. " +
                "Riasztáskor söprés menü: halasztás egy órával vagy bevétel megerősítése. Zárolt képernyőn is jelez.",
            priority = 6
        ),
        Entry(
            id = "wifi_bt_hotspot",
            triggers = listOf(
                "wifi", "vifi", "bluetooth", "hotspot", "megosztott internet", "internet megosztas",
                "internet megosztás", "wifi hotspot"
            ),
            answer = "A Beállítások menüben: WiFi be- és kikapcsolás, Bluetooth be- és kikapcsolás, " +
                "és Hotspot be- és kikapcsolás. Mondd: WiFi, Bluetooth, hotspot. " +
                "A hotspot közvetlenül kapcsol, első használatkor a közeli WiFi eszközök engedély kellhet.",
            priority = 8
        ),
        Entry(
            id = "assistant_setup",
            triggers = listOf(
                "alapertelmezett asszisztens", "oldalso gomb", "oldalsó gomb", "digitalis asszisztens",
                "hogyan inditom az asszisztenst"
            ),
            answer = "Állítsd be a Super DL-t alapértelmezett digitális asszisztensként: Asszisztens menü, " +
                "Alapértelmezett asszisztens beállítása. Utána az oldalsó gomb hosszú nyomására Elena indul. " +
                "Bluetooth gomb asszisztens is bekapcsolható ugyanebben a menüben.",
            priority = 7
        ),
        Entry(
            id = "dictation_cancel",
            triggers = listOf(
                "diktalas megszakit", "diktálás megszakít", "mikrofon bezar", "mikrofon bezár",
                "nem akarok diktalni", "nem akarok diktálni"
            ),
            answer = "Bármely diktálás közben balra söprés megszakítja a felismerést és a felolvasást. " +
                "Ez minden funkcióra érvényes: asszisztens, üzenet, e-mail, név, keresés és többi.",
            priority = 5
        ),
        Entry(
            id = "tts_settings",
            triggers = listOf(
                "beszed hang", "tts", "felolvaso", "felolvasó", "hang gyors", "hang lassu", "hang lassú"
            ),
            answer = "Beállítások menü: T T S hang választása, beszéd gyorsítása vagy lassítása, " +
                "hangerő növelése vagy csökkentése. Mondd: T T S motor, beszéd gyorsabb, beszéd lassabb.",
            priority = 4
        ),
        Entry(
            id = "patrol",
            triggers = listOf(
                "orseg", "őrség", "akkumulator figyeles", "akkumulátor figyelés", "ido bemondas", "idő bemondás",
                "ejszakai csend", "éjszakai csend"
            ),
            answer = "Az őrség funkciók a Beállítások, Őrség beállítások menüben vannak: akkumulátor figyelés, " +
                "hívás és üzenet értesítés felolvasása, idő bemondás gyakorisága, éjszakai csend időszak.",
            priority = 4
        ),
        Entry(
            id = "developer",
            triggers = listOf(
                "fejleszto", "fejlesztő", "ki keszitette", "kapcsolat", "email", "e-mail", "verzio", "verzió"
            ),
            answer = "A Super DL fejlesztője Kőrösmezey Dávid. Kapcsolat: korosmezey.david.richard@gmail.com. " +
                "Az alkalmazás verziója a Névjegy és jogi információk menüben hallható.",
            priority = 3
        ),
        Entry(
            id = "troubleshoot_mic",
            triggers = listOf(
                "nem hall engem", "nem érti a hangom", "nem erti a hangom", "mikrofon nem jo",
                "mikrofon nem jó", "nem ert semmit", "nem ért semmit"
            ),
            answer = "Ha nem értem a parancsot: mondd rövidebben, tisztán, és várj a sípszó után. " +
                "Ellenőrizd a mikrofon engedélyt a Super DL alkalmazásnál. Próbáld: Szia Elena, idő, vagy segítség. " +
                "Ha továbbra is gond van, diktálj csendesebb helyen, közelebb a telefonhoz.",
            priority = 9
        ),
        Entry(
            id = "troubleshoot_internet",
            triggers = listOf(
                "nincs internet", "nem megy a net", "nincs halozat", "nincs hálózat", "offline"
            ),
            answer = "Kapcsold be a WiFi-t vagy a mobilnetet a Beállítások menüben. Hotspotot is bekapcsolhatsz, " +
                "ha más eszközzel osztod meg a netet. Időjárás, hírek és internet kereső stabil netet igényel.",
            priority = 7
        ),
        Entry(
            id = "phone_detail",
            triggers = listOf(
                "nevjegybol hivas", "névjegyből hívás", "hivas kozben", "hívás közben",
                "hivas bontas", "hívás bontás", "incall", "hivo kijelzo"
            ),
            answer = "Névjegyből hívás: diktáld a nevet, fel-le a találatok, jobbra a hívás. " +
                "Hívás közben saját képernyő: felolvassa az állapotot. Balra söprés: hívás bontása.",
            priority = 8
        ),
        Entry(
            id = "sms_flow",
            triggers = listOf(
                "sms folyamat", "uzenet kuldes hogyan", "üzenet küldés hogyan", "hogyan kuldjek sms",
                "sms lepes", "sms lépés"
            ),
            answer = "SMS küldés: címzett diktálása, megerősítés, üzenet diktálása, küldés megerősítése. " +
                "Balra söprés bármely lépésnél megszakít. Mondd: üzenet küldés.",
            priority = 7
        ),
        Entry(
            id = "email_smtp",
            triggers = listOf(
                "smtp", "email kuldo", "e-mail küldő", "gmail beallitas", "gmail beállítás",
                "hogyan kuldjek email", "hogyan küldjek email"
            ),
            answer = "E-mail SMTP-n keresztül megy, nem a Gmail appot nyitja. " +
                "Először állítsd be az e-mail küldőt: felhasználónév, jelszó, Gmail App Password ajánlott. " +
                "Utána: e-mail írás, címzett, tárgy, szöveg, megerősítés.",
            priority = 7
        ),
        Entry(
            id = "news_sources",
            triggers = listOf(
                "hirek forras", "hírek forrás", "milyen hirek", "milyen hírek", "rss", "telex", "index hir"
            ),
            answer = "Hírek: tizennyolc forrás, kategóriák: általános, politika, gazdaság, sport, tech, kultúra. " +
                "Pl. Telex, 444, Index, HVG, Portfolio, Nemzeti Sport. Forrás választás, majd jobbra: betöltés. Internet kell.",
            priority = 6
        ),
        Entry(
            id = "book_detail",
            triggers = listOf(
                "konyv formatum", "könyv formátum", "milyen konyv", "milyen könyv", "epub", "pdf konyv",
                "konyvjelzo hogyan", "könyvjelző hogyan"
            ),
            answer = "Könyvformátumok: TXT, EPUB, PDF, DOCX, MOBI és mások. Könyvtár menü vagy könyv keresés. " +
                "Olvasás közben: fel ismétlés, le következő rész, jobbra könyvjelző, balra kilépés.",
            priority = 6
        ),
        Entry(
            id = "sounds_training",
            triggers = listOf(
                "program hangjai", "hangok megismerese", "hangok megismerése", "milyen hang", "milyen sip"
            ),
            answer = "A Névjegy menüben: Program hangjainak megismerése. Nyolc hang kipróbálható magyarázattal: " +
                "indítás, söprés irányok, siker, hiba, menü kattanás. Segít megjegyezni a visszajelzéseket.",
            priority = 5
        ),
        Entry(
            id = "qr_reader",
            triggers = listOf(
                "qr olvas", "qr kód", "vonalkod", "vonalkód", "kod olvas"
            ),
            answer = "QR olvasó az Eszközök menüben. Beolvassa a kódot, majd ajánl műveletet: hívás, SMS, e-mail, " +
                "gyalogos útvonal a geo linkből. Fel-le választás, jobbra végrehajtás.",
            priority = 6
        ),
        Entry(
            id = "permissions",
            triggers = listOf(
                "engedely", "engedély", "milyen engedely", "milyen engedély", "mikrofon engedely",
                "ertesites engedely", "értesítés engedély", "notification listener"
            ),
            answer = "Induláskor kéri: telefon, SMS, hely, mikrofon, naptár, kamera, értesítések. " +
                "Az értesítések olvasásához külön kell engedélyezni a Super DL-t a rendszer értesítés-hozzáférésnél. " +
                "Diktáláshoz mikrofon engedély szükséges.",
            priority = 6
        ),
        Entry(
            id = "limitations",
            triggers = listOf(
                "korlat", "korlát", "mit nem tud", "mit nem tudsz", "ismert korlat", "nem ert mindent"
            ),
            answer = "Ismert korlátok: Elena helyi kulcsszó-felismerés, nem felhő AI. YouTube stream függőség. " +
                "BKK elsősorban Budapest. E-mail SMTP beállítás kell. PDF-ben képalapú oldal nem mindig olvasható. " +
                "Ha másik launcher az alapértelmezett, a Super DL csak appként érhető el.",
            priority = 8
        ),
        Entry(
            id = "main_menu",
            triggers = listOf(
                "fo menu", "főmenü", "milyen menu", "milyen menü", "menu struktura", "menü struktúra",
                "milyen funkciok", "milyen funkciók"
            ),
            answer = "Főmenü tizenkét csoport: Telefon és hívások, Üzenetek és e-mail, S O S, Idő és szervezés, " +
                "Zene és média, Könyvek, Információ, Közösség navigáció, Eszközök, Asszisztens Elena, Beállítások, Névjegy.",
            priority = 7
        ),
        Entry(
            id = "favorites_contacts",
            triggers = listOf(
                "kedvenc hivas", "kedvenc hívás", "uj nevjegy", "új névjegy", "nevjegy mentes"
            ),
            answer = "Kedvenc hívás a Telefon és Hívások menüben. Új névjegy: szám billentyűzet vagy diktálás, majd név. " +
                "Hívásnaplóból is menthetsz névjegyet. Mondd: új névjegy, kedvenc hívás.",
            priority = 6
        ),
        Entry(
            id = "battery_patrol",
            triggers = listOf(
                "akkumulator orseg", "akkumulátor őrség", "alacsony toltes", "alacsony töltés", "tele toltes"
            ),
            answer = "Akkumulátor őrség háttérben figyel: tizenöt százalék alatt és száz százaléknál sípol. " +
                "Beállítások menüben ki-be kapcsolható. Mondd: akkumulátor őrség.",
            priority = 5
        ),
        Entry(
            id = "weather_detail",
            triggers = listOf(
                "idojaras hogyan", "időjárás hogyan", "nevnap", "névnap", "napi udvozles reszletes"
            ),
            answer = "Napi üdvözlés: dátum, magyar névnap offline, időjárás netről. Időjárás most: hely, hőmérséklet, szél. " +
                "Város szerint is kérhető diktálással. Mondd: napi üdvözlés, időjárás.",
            priority = 6
        ),
        Entry(
            id = "assistant_commands",
            triggers = listOf(
                "milyen parancsok", "parancs lista", "osszes parancs", "összes parancs", "mit mondjak"
            ),
            answer = "Példák: idő, ébresztő, hívd fel és a név, üzenet küldés, hol vagyok, útvonal a célhoz, " +
                "zene, könyvtár, WiFi, hotspot, S O S, segítség. A teljes listához mondd: segítség.",
            priority = 7
        )
    )

    fun findAnswer(raw: String, context: Context? = null): String? {
        val text = VoiceAssistantHelper.normalize(raw)
        if (text.length < 4) return null

        var best: Entry? = null
        var bestScore = 0

        for (entry in entries) {
            val score = scoreEntry(text, entry)
            if (score > bestScore) {
                bestScore = score
                best = entry
            }
        }

        if (bestScore >= 4) return best?.answer

        return context?.let { ElenaKnowledgeLoader.findSectionAnswer(it, raw) }
    }

    fun topicListSummary(context: Context? = null): String {
        val builtIn = listOf(
            "Super DL és Elena",
            "gesztusok, diktálás, TTS",
            "telefon, SMS, e-mail SMTP",
            "S O S, ébresztő, naptár, jegyzetek",
            "zene, YouTube, könyvek",
            "hírek, időjárás, névnap",
            "navigáció, BKK, GPS",
            "kamera, OCR, QR, pénzfelismerő",
            "WiFi, Bluetooth, hotspot",
            "engedélyek és korlátok"
        )
        val assetSections = context?.let {
            ElenaKnowledgeLoader.ensureLoaded(it)
            ElenaKnowledgeLoader.sectionTitles(it).take(8)
        }.orEmpty()
        val extra = if (assetSections.isNotEmpty()) {
            " A SUPERDL.TXT alapján még: ${assetSections.joinToString(", ")}."
        } else {
            ""
        }
        return "Tudásbázis témák: ${builtIn.joinToString(", ")}.$extra " +
            "Kérdezz konkrétan, pl.: hogyan küldjek SMS-t, milyen hírek vannak, vagy mi az a könyvjelző."
    }

    private fun scoreEntry(text: String, entry: Entry): Int {
        var score = 0
        for (trigger in entry.triggers) {
            val normalizedTrigger = VoiceAssistantHelper.normalize(trigger)
            when {
                text == normalizedTrigger -> score += normalizedTrigger.length + 8 + entry.priority
                text.contains(normalizedTrigger) -> score += normalizedTrigger.length + 4 + entry.priority
                normalizedTrigger.length >= 6 && wordsOverlap(text, normalizedTrigger) >= 2 ->
                    score += wordsOverlap(text, normalizedTrigger) * 2 + entry.priority
            }
        }
        return score
    }

    private fun wordsOverlap(a: String, b: String): Int {
        val wordsA = a.split(" ").filter { it.length >= 3 }.toSet()
        val wordsB = b.split(" ").filter { it.length >= 3 }.toSet()
        return wordsA.count { it in wordsB }
    }
}