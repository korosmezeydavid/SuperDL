package com.superdl.launcher.voice

/**
 * Diktált szabad szöveg központozása és szépítése.
 *
 * A beszédfelismerő írásjelek nélküli szóáradatot ad vissza. Ez a modul:
 *  1) a KIMONDOTT írásjeleket ("vessző", "pont", "kérdőjel") behelyettesíti,
 *  2) rendbe teszi a szóközöket az írásjelek körül,
 *  3) nagy kezdőbetűt tesz a mondatok elejére.
 *
 * FONTOS: ez csak SZABAD SZÖVEGRE való (e-mail, SMS, jegyzet, naptár-leírás).
 * A parancsértelmezéshez a SpeechCorrections való – az mást csinál (ékezet
 * nélkülire normalizál), a kettőt soha ne cseréljük fel.
 *
 * Aki nem mond ki írásjeleket, annak sem romlik el semmi: akkor csak a
 * nagy kezdőbetűt és a szóköz-rendezést kapja.
 */
object SpeechPunctuation {

    /**
     * Kimondott írásjelek és a beszúrandó karakter.
     * A ragozott alakok is szerepelnek, mert a felismerő gyakran úgy hallja
     * ("vesszőt", "pontot"). A hosszabb kifejezések előre kerülnek, hogy a
     * "felkiáltójel" ne bomoljon "fel" + "kiáltójel"-re.
     */
    private val punctuationMap: List<Pair<String, String>> = listOf(
        // Bekezdés / sortörés
        "új bekezdés" to "\n\n",
        "uj bekezdes" to "\n\n",
        "új sor" to "\n",
        "uj sor" to "\n",
        "sortörés" to "\n",
        "sortores" to "\n",
        "enter" to "\n",

        // Három pont
        "három pont" to "…",
        "harom pont" to "…",
        "pont pont pont" to "…",

        // Kérdő- és felkiáltójel
        "kérdőjel" to "?",
        "kerdojel" to "?",
        "kérdőjelet" to "?",
        "kerdojelet" to "?",
        "felkiáltójel" to "!",
        "felkialtojel" to "!",
        "felkiáltójelet" to "!",
        "felkialtojelet" to "!",

        // Kettőspont, pontosvessző
        "kettőspont" to ":",
        "kettospont" to ":",
        "kettőspontot" to ":",
        "kettospontot" to ":",
        "pontosvessző" to ";",
        "pontosvesszo" to ";",
        "pontosvesszőt" to ";",
        "pontosvesszot" to ";",

        // Zárójel
        "zárójel be" to "(",
        "zarojel be" to "(",
        "nyitó zárójel" to "(",
        "nyito zarojel" to "(",
        "zárójel ki" to ")",
        "zarojel ki" to ")",
        "záró zárójel" to ")",
        "zaro zarojel" to ")",
        "csukó zárójel" to ")",
        "csuko zarojel" to ")",

        // Idézőjel
        "idézőjel" to "\"",
        "idezojel" to "\"",
        "idézőjelet" to "\"",
        "idezojelet" to "\"",

        // Gondolatjel / kötőjel
        "gondolatjel" to " – ",
        "kötőjel" to "-",
        "kotojel" to "-",

        // ── BŐVÍTÉS: gyakori jelek és szimbólumok ──────────────────────────
        //
        // FIGYELEM: csak olyan kifejezéseket veszünk fel, amiket a hétköznapi
        // beszédben NEM használunk másra. A "csillag", a "százalék" és a
        // "kereszt" önmagában rendes magyar szó — ezeket CSAK "jel" utótaggal
        // alakítjuk át, különben a diktált mondatokat csonkítanánk.
        "kukac" to "@",
        "hashtag" to "#",
        "kettőskereszt jel" to "#",
        "kettoskereszt jel" to "#",
        "csillag jel" to "*",
        "csillagjel" to "*",
        "perjel" to "/",
        "per jel" to "/",
        "visszaper" to "\\",
        "aláhúzásjel" to "_",
        "alahuzasjel" to "_",
        "aláhúzás jel" to "_",
        "alahuzas jel" to "_",
        "százalékjel" to "%",
        "szazalekjel" to "%",
        "százalék jel" to "%",
        "szazalek jel" to "%",
        "pluszjel" to "+",
        "plusz jel" to "+",
        "egyenlőségjel" to "=",
        "egyenlosegjel" to "=",
        "és jel" to "&",
        "es jel" to "&",
        "fokjel" to "°",
        "aposztróf" to "'",
        "aposztrof" to "'",
        "szögletes zárójel be" to "[",
        "szogletes zarojel be" to "[",
        "szögletes zárójel ki" to "]",
        "szogletes zarojel ki" to "]",

        // Vessző és pont (ezek a leggyakoribbak, de rövidek – utolsóként!)
        "vesszőt" to ",",
        "vesszot" to ",",
        "vessző" to ",",
        "vesszo" to ",",
        "pontot" to ".",
        "pont" to "."
    )

    /**
     * A teljes feldolgozás: kimondott írásjelek + szóközök + nagy kezdőbetű.
     * @param raw a beszédfelismerő nyers szövege
     */
    fun apply(raw: String): String {
        if (raw.isBlank()) return raw
        var text = replaceSpokenPunctuation(raw)
        text = fixSpacing(text)
        text = capitalizeSentences(text)
        return text.trim()
    }

    /** A kimondott írásjel-szavakat lecseréli a tényleges karakterre. */
    private fun replaceSpokenPunctuation(input: String): String {
        var text = input
        for ((spoken, symbol) in punctuationMap) {
            // Csak önálló szóként cseréljük, hogy a "pontos" szó ne törjön el,
            // és a "Béla pontban ötkor" se váljon "Béla .ban ötkor"-rá.
            val pattern = Regex("(?i)(?<![\\p{L}])${Regex.escape(spoken)}(?![\\p{L}])")
            text = pattern.replace(text, symbol)
        }
        return text
    }

    /** Szóközök rendbetétele az írásjelek körül. */
    private fun fixSpacing(input: String): String {
        var text = input
        // Írásjel előtti szóköz törlése: "szia , hogy" -> "szia, hogy"
        text = text.replace(Regex("\\s+([,.;:!?…])"), "$1")
        // Írásjel után legyen szóköz, ha betű követi: "szia,hogy" -> "szia, hogy"
        text = text.replace(Regex("([,;:])(?=[\\p{L}])"), "$1 ")
        text = text.replace(Regex("([.!?…])(?=[\\p{L}])"), "$1 ")
        // Nyitó zárójel után / záró elé ne legyen szóköz
        text = text.replace(Regex("\\(\\s+"), "(")
        text = text.replace(Regex("\\s+\\)"), ")")
        // Több szóköz egybe, de a sortöréseket megtartjuk
        text = text.replace(Regex("[ \\t]{2,}"), " ")
        // Sortörés körüli felesleges szóközök
        text = text.replace(Regex(" *\\n *"), "\n")
        // Ismétlődő írásjelek egyszerűsítése ("..", ",,")
        text = text.replace(Regex("([,.;:!?])\\1+"), "$1")
        return text
    }

    /**
     * Nagy kezdőbetű a szöveg elején, minden mondatzáró után és új sor után.
     */
    private fun capitalizeSentences(input: String): String {
        if (input.isBlank()) return input
        val sb = StringBuilder(input)
        var capitalizeNext = true
        for (i in sb.indices) {
            val c = sb[i]
            when {
                capitalizeNext && c.isLetter() -> {
                    sb[i] = c.uppercaseChar()
                    capitalizeNext = false
                }
                c == '.' || c == '!' || c == '?' || c == '\n' -> capitalizeNext = true
                // A "…" után is új mondat jön
                c == '…' -> capitalizeNext = true
            }
        }
        return sb.toString()
    }

    /**
     * A felhasználónak felolvasható súgó: mit lehet kimondani.
     */
    fun helpText(): String =
        "Diktálás közben kimondhatod az írásjeleket: vessző, pont, kérdőjel, " +
            "felkiáltójel, kettőspont, pontosvessző, idézőjel, gondolatjel, " +
            "zárójel be, zárójel ki, új sor, új bekezdés. " +
            "A mondatok elejére magamtól teszek nagybetűt."
}
