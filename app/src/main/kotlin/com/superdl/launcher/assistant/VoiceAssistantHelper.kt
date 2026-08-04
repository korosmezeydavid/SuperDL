package com.superdl.launcher.assistant

import android.content.Context
import com.superdl.launcher.menu.MenuAction
import com.superdl.launcher.menu.MenuItem
import com.superdl.launcher.menu.MenuTree
import com.superdl.launcher.voice.SpeechCorrections
import com.superdl.launcher.voice.SpeechRecognitionResult
import java.text.Normalizer
import java.util.Locale

sealed class VoiceAssistantIntent {
    data class Speak(val message: String) : VoiceAssistantIntent()
    data class RunAction(val action: MenuAction) : VoiceAssistantIntent()
    data class CallContact(val query: String) : VoiceAssistantIntent()
    data class TransitRoute(val destination: String) : VoiceAssistantIntent()
    data class NavWalkRoute(val destination: String) : VoiceAssistantIntent()
    data class YoutubeSearch(val query: String) : VoiceAssistantIntent()
    data class BookSearch(val query: String) : VoiceAssistantIntent()
    data class OpenExternalApp(val query: String) : VoiceAssistantIntent()
    data class WebSearch(val query: String) : VoiceAssistantIntent()
}

object VoiceAssistantHelper {

    private val LOCKED_ALLOWED_ACTIONS = setOf(
        MenuAction.TIME_NOW,
        MenuAction.SMS_WRITE,
        MenuAction.SOS,
        MenuAction.BATTERY,
        MenuAction.DAY_GREETING,
        MenuAction.FAVORITES_CALL,
        MenuAction.CONTACTS,
        MenuAction.DIAL
    )

    fun isAllowedWhenLocked(intent: VoiceAssistantIntent): Boolean = when (intent) {
        is VoiceAssistantIntent.Speak -> true
        is VoiceAssistantIntent.CallContact -> true
        is VoiceAssistantIntent.RunAction -> intent.action in LOCKED_ALLOWED_ACTIONS
        else -> false
    }

    data class InterpretedCommand(
        val intent: VoiceAssistantIntent,
        val heard: String
    )

    fun interpret(raw: String, context: Context? = null): VoiceAssistantIntent =
        interpretCommand(raw, context).intent

    fun interpretCommand(raw: String, context: Context? = null): InterpretedCommand {
        val text = SpeechCorrections.apply(raw)
        val intent = interpretNormalized(text, context)
        return InterpretedCommand(intent, text)
    }

    fun interpretBest(result: SpeechRecognitionResult, context: Context? = null): InterpretedCommand {
        val candidates = buildCandidateList(result)
        var best = InterpretedCommand(
            VoiceAssistantIntent.Speak(unknownText()),
            candidates.firstOrNull().orEmpty()
        )
        var bestScore = -1
        for ((index, candidate) in candidates.withIndex()) {
            val interpreted = interpretCommand(candidate, context)
            val confidenceBoost = confidenceBoost(result.confidences, index)
            val score = scoreIntent(interpreted.intent, interpreted.heard) + confidenceBoost
            if (score > bestScore) {
                bestScore = score
                best = interpreted
            }
        }
        return best
    }

    private fun buildCandidateList(result: SpeechRecognitionResult): List<String> {
        val merged = linkedSetOf<String>()
        result.hypotheses.forEach { hypothesis ->
            merged.add(hypothesis)
            merged.add(SpeechCorrections.apply(hypothesis))
        }
        return merged.filter { it.isNotBlank() }
    }

    private fun confidenceBoost(confidences: FloatArray?, index: Int): Int {
        val confidence = confidences?.getOrNull(index) ?: return 0
        return when {
            confidence >= 0.85f -> 3
            confidence >= 0.65f -> 2
            confidence >= 0.45f -> 1
            else -> 0
        }
    }

    private fun scoreIntent(intent: VoiceAssistantIntent, text: String): Int = when (intent) {
        is VoiceAssistantIntent.Speak -> when {
            text.isBlank() -> 0
            intent.message.startsWith("Nem értettem") -> 0
            intent.message.startsWith("Nem hallottam") -> 1
            else -> 8
        }
        is VoiceAssistantIntent.WebSearch -> 11 + text.length.coerceAtMost(20) / 10
        is VoiceAssistantIntent.RunAction -> 12
        is VoiceAssistantIntent.OpenExternalApp -> 13
        is VoiceAssistantIntent.YoutubeSearch,
        is VoiceAssistantIntent.BookSearch -> 13
        is VoiceAssistantIntent.TransitRoute,
        is VoiceAssistantIntent.NavWalkRoute -> 14
        is VoiceAssistantIntent.CallContact -> 15
    }

    private fun interpretNormalized(text: String, context: Context? = null): VoiceAssistantIntent {
        if (text.isBlank()) {
            return VoiceAssistantIntent.Speak("Nem hallottam semmit. Mondd újra lassan.")
        }

        if (context != null) {
            if (ElenaWakeHelper.isWakeOnly(text, context)) {
                return VoiceAssistantIntent.Speak(ElenaWakeHelper.wakeGreeting())
            }
            ElenaWakeHelper.stripWakePrefix(text, context)?.let { command ->
                if (command.isBlank()) {
                    return VoiceAssistantIntent.Speak(ElenaWakeHelper.wakeGreeting())
                }
                return interpretNormalized(command, context)
            }
        }

        if (isHelpRequest(text)) {
            if (containsAny(text, "tudasbazis", "tudásbázis", "mit tudsz a programrol", "mit tudsz a programról")) {
                return VoiceAssistantIntent.Speak(ElenaKnowledgeBase.topicListSummary(context))
            }
            return VoiceAssistantIntent.Speak(helpText())
        }

        extractCallTarget(text)?.let { target ->
            return VoiceAssistantIntent.CallContact(target)
        }

        extractAfter(text, listOf("gyalogos utvonal", "gyalog menj", "setalj"))?.let { destination ->
            if (destination.length >= 3) return VoiceAssistantIntent.NavWalkRoute(destination)
        }

        extractAfter(text, listOf("utvonal", "kozlekedes", "busszal", "metróval", "metrovall", "juss el", "hogyan menjek"))?.let { destination ->
            if (destination.length >= 3) return VoiceAssistantIntent.TransitRoute(destination)
        }

        extractAfter(text, listOf("youtube", "jutub", "jutyub", "jutjub"))?.let { query ->
            if (query.length >= 2) return VoiceAssistantIntent.YoutubeSearch(query)
        }

        extractAfter(text, listOf("konyv keres", "keresd a konyvet", "keresd a konyvot", "konyvet keres"))?.let { query ->
            if (query.length >= 2) return VoiceAssistantIntent.BookSearch(query)
        }

        extractOpenAppTarget(text)?.let { appName ->
            if (appName.length >= 2) return VoiceAssistantIntent.OpenExternalApp(appName)
        }

        extractAfter(text, listOf("keresd meg", "keress ra", "internet kereses", "internet keresés", "google kereses"))?.let { query ->
            if (query.length >= 3) return VoiceAssistantIntent.WebSearch(query)
        }

        matchMenuAction(text)?.let { action ->
            return VoiceAssistantIntent.RunAction(action)
        }

        matchKeywordAction(text)?.let { action ->
            return VoiceAssistantIntent.RunAction(action)
        }

        ElenaKnowledgeBase.findAnswer(text, context)?.let { answer ->
            return VoiceAssistantIntent.Speak(answer)
        }

        if (looksLikeWebSearch(text)) {
            return VoiceAssistantIntent.WebSearch(text)
        }

        return VoiceAssistantIntent.Speak(unknownText())
    }

    fun unknownFeedback(heard: String): String {
        val preview = heard.trim().take(80)
        return if (preview.isBlank()) {
            unknownText()
        } else {
            "Ezt hallottam: $preview. ${unknownText()}"
        }
    }

    fun helpText(): String =
        "${ElenaWakeHelper.ASSISTANT_NAME}, a Super DL hangos asszisztense. Amit tudok: pontos idő, napi üdvözlés, időjárás, hírek, akkumulátor, " +
            "ébresztő beállítása és listázása, időzítő, gyógyszer emlékeztető, " +
            "üzenet küldés és olvasás, e-mail küldés és beállítás, hívás név szerint, hívásnapló, szám tárcsázás, " +
            "új névjegy, kedvenc hívás és törlés, " +
            "naptár mai és holnapi program, új program, saját jegyzetek, új jegyzet, " +
            "hol vagyok, hely keresése, gyalogos útvonal, közlekedési útvonal, közeli megállók, " +
            "zene, YouTube keresés, könyvtár, könyvjelzők, könyvmappa, könyv keresése, " +
            "napi összefoglaló, bevásárlólista, e-mailek olvasása, " +
            "zseblámpa, számológép, Q R olvasó, pénzfelismerő, gyógyszerdoboz olvasó, címke olvasó, szöveg olvasó, folyamatos szövegolvasó, diktafon és diktafon beállítás, tanuló mód, G P S kitekintő, környezeti kitekintő, egyéni helyek, helyszín felismerő, arc kamera, G P S útvonal rögzítés, internet kereső, " +
            "értesítések, WiFi, Bluetooth, hangerő, csengőhang hangerő, néma mód, őrség beállítások, P I N zárolás, rejtett számok tiltása, " +
            "S O S és S O S számok, T T S motor, külső alkalmazások, névjegy és jogi információk, " +
            "Elena figyelő, Elena tanítás, saját felébresztő mondat, hotspot, helyi tudásbázis. " +
            "Kérdezhetsz tőlem: mi az a Super DL, hogyan működnek a gesztusok, S O S, PIN, navigáció. " +
            "Példák: Szia ${ElenaWakeHelper.ASSISTANT_NAME}, hány óra van, hívd fel Anyát, útvonal a Deák térre, " +
            "ébresztő hét óra, üzenet küldés, pin zárolás, e-mail küldő beállítás, zene, könyvtár, " +
            "Messenger megnyitása, hogyan készül a loncsos káposzta."

    private fun unknownText(): String =
        "Nem értettem. Próbáld így: Szia ${ElenaWakeHelper.ASSISTANT_NAME}, idő, hívd fel és a név, " +
            "útvonal a célállomásra, ébresztő, üzenet, zene, vagy mondd: segítség."

    private fun isHelpRequest(text: String): Boolean =
        containsAny(
            text,
            "segitseg",
            "segits",
            "mit tudsz",
            "mit tudsz csinalni",
            "mire vagy kepes",
            "parancsok",
            "sugo",
            "help",
            "mit csinalsz",
            "tudasbazis",
            "tudásbázis",
            "mit tudsz a programrol",
            "mit tudsz a programról",
            "mire jo ez az app",
            "mire jó ez az app"
        )

    private val CALL_TARGET_BLOCKLIST = listOf(
        "hivasnaplo",
        "hivas ertesites",
        "hivas figyelmeztetes",
        "hivas engedely",
        "hivas szuro",
        "kedvenc hivas",
        "nevjegybol hivas",
        "nev szerint hivas"
    )

    private fun extractCallTarget(text: String): String? {
        if (CALL_TARGET_BLOCKLIST.any { text.contains(it) }) return null

        val prefixes = listOf(
            "hivd fel",
            "hivj fel",
            "hivd meg",
            "hivj meg",
            "felhivom",
            "felhivjuk",
            "felhivod",
            "felhivja",
            "hivom fel",
            "hivom meg",
            "hivom",
            "hivjuk",
            "hivod",
            "hivja",
            "telefonalok",
            "telefonaljuk",
            "telefonalj",
            "telefonalj neki",
            "telefonald meg",
            "telefonald",
            "keresd fel",
            "keresd telefonon",
            "csorgass",
            "csorogj",
            "hivas",
            "hivd",
            "hivj"
        )
        extractAfter(text, prefixes)?.let { target ->
            val cleaned = cleanCallTarget(target)
            if (cleaned.length >= 2) return cleaned
        }

        extractCallTargetFromSuffix(text)?.let { return it }

        return null
    }

    private fun extractCallTargetFromSuffix(text: String): String? {
        val patterns = listOf(
            Regex("""(.+?)\s+hiv(?:as|asa|ast|ja|juk|od)"""),
            Regex("""(.+?)\s+telefonal(?:as|asa|ast|ok|juk|od)""")
        )
        for (pattern in patterns) {
            val match = pattern.find(text) ?: continue
            val cleaned = cleanCallTarget(match.groupValues[1])
            if (cleaned.length >= 2 && !isCallMetaWord(cleaned)) return cleaned
        }
        return null
    }

    private fun isCallMetaWord(value: String): Boolean =
        value in setOf(
            "hivas",
            "telefon",
            "telefonalas",
            "nevjegy",
            "kedvenc",
            "szam",
            "szamot"
        )

    private fun cleanCallTarget(raw: String): String =
        raw.removePrefix("a ")
            .removePrefix("az ")
            .removePrefix("egy ")
            .removeSuffix("t")
            .removeSuffix("t fel")
            .removeSuffix("nak")
            .removeSuffix("nek")
            .removeSuffix("hoz")
            .removeSuffix("hez")
            .removeSuffix("hivas")
            .removeSuffix("hivast")
            .trim()

    private fun matchMenuAction(text: String): MenuAction? {
        var bestAction: MenuAction? = null
        var bestScore = 0
        for (item in MenuTree.allItems()) {
            if (item.action == MenuAction.SUBMENU || item.id.endsWith("_back")) continue
            val label = normalize(item.label)
            val score = labelMatchScore(text, label)
            if (score > bestScore) {
                bestScore = score
                bestAction = item.action
            }
        }
        return if (bestScore >= 2) bestAction else null
    }

    private fun labelMatchScore(text: String, label: String): Int {
        if (label.isBlank()) return 0
        if (text == label) return label.length + 4
        if (text.contains(label)) return label.length + 2
        val words = label.split(" ").filter { it.isNotBlank() }
        if (words.size == 1) {
            val word = words.first()
            if (text == word) return word.length + 5
            if (text.contains(word) && word.length >= 3) return word.length + 3
        }
        val longWords = words.filter { it.length >= 4 }
        val hits = longWords.count { text.contains(it) }
        return if (hits >= 2) hits * 3 else longWords.count { text.contains(it) }
    }

    private fun matchKeywordAction(text: String): MenuAction? = when {
        containsAny(text, "sos szam 1", "s o s szam 1", "sos egy", "sos elso") ->
            MenuAction.SOS_SET_1

        containsAny(text, "sos szam 2", "s o s szam 2", "sos ketto", "sos masodik") ->
            MenuAction.SOS_SET_2

        containsAny(text, "sos szam 3", "s o s szam 3", "sos harom", "sos harmadik") ->
            MenuAction.SOS_SET_3

        containsAny(text, "sos szam 4", "s o s szam 4", "sos negy", "sos negyedik") ->
            MenuAction.SOS_SET_4

        containsAny(text, "sos szamok", "s o s szamok", "sos szam felolvas", "sos beallitasok") ->
            MenuAction.SOS_READ_ALL

        containsAny(text, "s o s", "sos", "vesz", "veszhelyzet", "vészhelyzet") ->
            MenuAction.SOS

        containsAny(text, "pontos ido", "hany ora", "mennyi az ido", "mennyi az ora", "mennyi ido") &&
            !containsAny(text, "ebreszto", "idozito", "program", "belepes", "bekapcsolo") ->
            MenuAction.TIME_NOW

        containsAny(text, "ido", "ora") &&
            !containsAny(text, "ebreszto", "idozito", "program", "belepes", "bekapcsolo", "idojaras", "naptar") &&
            text.split(" ").size <= 3 ->
            MenuAction.TIME_NOW

        containsAny(text, "napi udvozles", "udvozles", "nevnap", "reggel") ->
            MenuAction.DAY_GREETING

        containsAny(text, "akkumulator orseg", "orseg", "teljes orseg") ->
            MenuAction.BATTERY_PATROL_TOGGLE

        containsAny(text, "akkumulator figyeles", "akkumulator figyelés") ->
            MenuAction.PATROL_BATTERY_TOGGLE

        containsAny(text, "hivas ertesites", "hivas figyelmeztetes") ->
            MenuAction.PATROL_CALL_ALERT_TOGGLE

        containsAny(text, "uzenet ertesites", "sms ertesites") ->
            MenuAction.PATROL_SMS_ALERT_TOGGLE

        containsAny(text, "egyeb ertesites", "mas ertesites") ->
            MenuAction.PATROL_NOTIFICATION_ALERT_TOGGLE

        containsAny(text, "ido bemondas gyakorisag", "ido gyakorisag", "ido bemondas idokoz") ->
            MenuAction.PATROL_TIME_INTERVAL_CYCLE

        containsAny(text, "ido bemondas", "idobe mond", "mondd az idot") ->
            MenuAction.PATROL_TIME_ANNOUNCE_TOGGLE

        containsAny(text, "ejszakai csend kezdet", "csend kezdete", "ejszaka kezdete") ->
            MenuAction.PATROL_NIGHT_START_SET

        containsAny(text, "ejszakai csend vege", "csend vege", "ejszaka vege") ->
            MenuAction.PATROL_NIGHT_END_SET

        containsAny(text, "ejszakai csend", "ejszaka csend") ->
            MenuAction.PATROL_NIGHT_MODE_TOGGLE

        containsAny(text, "bekapcsolo gomb ido", "bekapcsolas ido", "power gomb ido") ->
            MenuAction.PATROL_POWER_BUTTON_TIME_TOGGLE

        containsAny(text, "akkumulator", "toltottseg", "toltottség", "battery", "toltes") ->
            MenuAction.BATTERY

        containsAny(text, "hirek", "hir ", "rss") ->
            MenuAction.NEWS_READ

        containsAny(text, "idojaras varos", "idojaras budapesten", "idojaras debrecenben") ->
            MenuAction.WEATHER_CITY

        containsAny(text, "idojaras", "esik", "meleg van", "hideg van") ->
            MenuAction.WEATHER

        containsAny(text, "kovetkezo ebreszto", "kovetkezo ebresztes") ->
            MenuAction.ALARM_READ_NEXT

        containsAny(text, "ebreszto torles", "ebresztok torlese", "torold az ebresztot") ->
            MenuAction.ALARM_DELETE

        containsAny(text, "ebresztok", "ebreszto lista", "ebresztesek") ->
            MenuAction.ALARM_LIST

        containsAny(text, "ebreszto", "ebresztes", "ebredj") ->
            MenuAction.ALARM_SET

        containsAny(text, "uzenet kuldes", "uzenet kul", "sms kul", "irj uzenet", "sms iras", "sms kuldes", "kuldj uzenet", "kuldj sms") ->
            MenuAction.SMS_WRITE

        containsAny(text, "uzenet olvas", "sms olvas", "olvasd az uzenet", "uzenetek", "olvasd az sms") ->
            MenuAction.SMS_READ

        containsAny(text, "kimenő uzenet", "kimeno uzenet", "kuldott uzenet", "küldött üzenet", "elkuldott uzenet", "elküldött üzenet") ->
            MenuAction.SMS_SENT_READ

        containsAny(text, "email import", "email cimek import", "email cim import") ->
            MenuAction.EMAIL_IMPORT

        containsAny(text, "email hozzaad", "email cim hozzaad", "uj email cim") ->
            MenuAction.EMAIL_ADD

        containsAny(text, "email cimek", "mentett email", "email lista") ->
            MenuAction.EMAIL_LIST

        containsAny(text, "email kuldo beallit", "smtp beallit", "email kuldo allit") ->
            MenuAction.EMAIL_SMTP_SETUP

        containsAny(text, "email kuldo felolvas", "smtp felolvas", "email kuldo olvas") ->
            MenuAction.EMAIL_SMTP_READ

        containsAny(text, "email kuldo torles", "smtp torles", "email kuldo torol") ->
            MenuAction.EMAIL_SMTP_CLEAR

        containsAny(text, "email olvas", "e-mailek olvas", "olvasd az email", "van uj email", "bejovo email") ->
            MenuAction.EMAIL_IMAP_READ

        containsAny(text, "e-mail", "email", "level", "irj email", "email kuldes") ->
            MenuAction.EMAIL_WRITE

        containsAny(text, "napi osszefoglalo", "reggeli osszefoglalo", "mi var ram ma", "mi var rad ma") ->
            MenuAction.DAY_SUMMARY

        containsAny(text, "helyzetjelentes", "helyzet jelentes", "mi a helyzet", "mi ujsag", "hol allok", "gyors jelentes", "roviden mi van") ->
            MenuAction.STATUS_REPORT

        containsAny(text, "bevasarlolista", "bevasarlo lista", "mi van a listan", "vasarlolista") ->
            MenuAction.SHOPPING_LIST

        containsAny(text, "mennyire pontos a helyem", "gps pontossag", "hely pontossag") ->
            MenuAction.NAV_WHERE

        containsAny(text, "hivasnaplo", "hivasok", "utolso hivasok") ->
            MenuAction.CALL_LOG

        containsAny(text, "uj nevjegy", "nevjegy letrehoz", "nevjegy mentes", "kontakt letrehoz") ->
            MenuAction.CONTACT_CREATE

        containsAny(text, "kedvenc torles", "kedvenc torlese", "kedvencet torol") ->
            MenuAction.FAVORITES_DELETE

        containsAny(text, "kedvenc hozzaad", "kedvenc hozzaadasa", "uj kedvenc", "kedvenc mentes") ->
            MenuAction.FAVORITES_ADD

        containsAny(text, "kedvenc hivas", "kedvencek", "kedvencet hiv") ->
            MenuAction.FAVORITES_CALL

        containsAny(text, "tarcsaz", "szamot hiv", "szam beir", "billentyuzet") ->
            MenuAction.DIAL

        containsAny(text, "nevjegybol hivas", "nev szerint hivas", "nevjegy hivas") ->
            MenuAction.CONTACTS

        containsAny(text, "nevjegyzek", "nevjegy lista", "nevjegyek", "nevjegy szinkron") ->
            MenuAction.CONTACT_BOOK

        containsAny(text, "hol vagyok", "hol vagy", "tartozkodasi hely", "hol vagyok most") ->
            MenuAction.NAV_WHERE

        containsAny(text, "hely keres", "cim keres", "keresd a helyet", "keresd a cimet") ->
            MenuAction.NAV_SEARCH

        containsAny(text, "gps kitekinto", "gps radar", "kozeli helyek", "kitekinto") ->
            MenuAction.GPS_RADAR

        containsAny(
            text,
            "mi van elottem",
            "mi van előttem",
            "mit latsz",
            "mit látsz",
            "nezz korul",
            "nézz körül"
        ) -> MenuAction.ENV_SNAPSHOT

        containsAny(
            text,
            "kornyezeti kitekinto",
            "kornyezet felismeres",
            "objektum felismeres",
            "kamera kitekinto",
            "kornyezet kamera"
        ) -> MenuAction.ENV_SCANNER

        containsAny(text, "mentett helyek", "mentett helyeim", "mentett poi", "mentett celok") ->
            MenuAction.GPS_RADAR_SAVED_LIST

        containsAny(text, "sajat hely mentes", "mentsd a helyemet", "mentsem a helyem", "ide mentsek", "mentsd ide") ->
            MenuAction.GPS_RADAR_SAVE_OWN

        containsAny(text, "mentsd el a helyet", "poi mentes", "hely mentese", "mentsd el ezt a helyet", "mentsd a bolt") ->
            MenuAction.GPS_RADAR_SAVE_POI

        containsAny(text, "kozeli megallo", "megallok", "busz megallo", "megallo") ->
            MenuAction.TRANSIT

        containsAny(text, "megallo keres", "megallot keres") ->
            MenuAction.TRANSIT_STOP

        containsAny(text, "kedvenc megallo", "kedvenc megallok", "mentett megallo") ->
            MenuAction.TRANSIT_FAVORITES

        containsAny(text, "kozeli allomas", "kozeli vasutallomas", "vonat allomas", "mav allomas") ->
            MenuAction.TRAIN_NEARBY

        containsAny(text, "allomas keres", "allomast keres", "vasutallomas keres") ->
            MenuAction.TRAIN_STATION_SEARCH

        containsAny(text, "kedvenc allomas", "kedvenc allomasok", "mentett allomas", "kedvenc vonat allomas") ->
            MenuAction.TRAIN_FAVORITES

        containsAny(text, "vonat", "mav", "vasut", "vasutallomas") ->
            MenuAction.TRAIN_NEARBY

        containsAny(text, "kozlekedes", "tomegkozlekedes", "busszal menj") ->
            MenuAction.TRANSIT_ROUTE

        containsAny(text, "uj program", "naptar bejegyzes", "program beallit", "esemeny") ->
            MenuAction.CALENDAR_ADD

        containsAny(text, "jegyzet torles", "jegyzetek torlese", "torold a jegyzetet") ->
            MenuAction.NOTE_DELETE

        containsAny(text, "uj jegyzet", "jegyzet iras", "jegyzet rogzit", "jegyzet keszit") ->
            MenuAction.NOTE_CREATE

        containsAny(text, "sajat jegyzetek", "jegyzetek", "jegyzet lista", "jegyzeteim") ->
            MenuAction.NOTE_LIST

        containsAny(text, "holnapi program", "holnapi naptar") ->
            MenuAction.CALENDAR_TOMORROW

        containsAny(text, "heti program", "heti naptar") ->
            MenuAction.CALENDAR_WEEK

        containsAny(text, "naptar", "mai program", "programom", "ma mi van") ->
            MenuAction.CALENDAR_READ

        containsAny(text, "idozito torles", "idozitok torlese") ->
            MenuAction.TIMER_DELETE

        containsAny(text, "idozito modosit", "idozito szerkeszt", "idozito atallit") ->
            MenuAction.TIMER_EDIT

        containsAny(text, "idozitok", "idozito lista") ->
            MenuAction.TIMER_LIST

        containsAny(text, "idozito indit", "indits idozitot") ->
            MenuAction.TIMER_START

        containsAny(text, "idozito leallit", "allitsd le az idozitot") ->
            MenuAction.TIMER_STOP

        containsAny(text, "uj idozito", "idozito", "visszaszamlalo") ->
            MenuAction.TIMER_CREATE

        containsAny(text, "gyogyszer torles", "gyogyszer emlekezteto torles") ->
            MenuAction.MEDICATION_DELETE

        containsAny(text, "gyogyszer hozzaad", "uj gyogyszer", "patika orangyal") ->
            MenuAction.MEDICATION_ADD

        containsAny(text, "gyogyszer", "gyogyszerek", "emlekezteto") ->
            MenuAction.MEDICATION_READ

        containsAny(text, "zene", "zenek", "zeneszam", "zene a telefonon") ->
            MenuAction.MUSIC

        // SÖTÉT MÓD — sokféleképpen mondható, ezért bő a felsorolás.
        containsAny(
            text,
            "sotet mod",
            "sotetitsd",
            "sotet kepernyo",
            "kepernyo sotet",
            "fuggony",
            "fuggonyozd",
            "kapcsold le a kepernyot",
            "kapcsold ki a kepernyot",
            "ne latszodjon a kepernyo",
            "feketitsd"
        ) -> MenuAction.SCREEN_CURTAIN_TOGGLE

        containsAny(text, "zseblampa", "lampa be", "villogo", "villog") ->
            MenuAction.FLASHLIGHT

        containsAny(text, "szinfelismero", "szin felismer", "milyen szin", "szin meres") ->
            MenuAction.COLOR_DETECTOR

        containsAny(
            text,
            "penz felismero",
            "penzmeres",
            "penzmerő",
            "bankjegy",
            "bankjegy felismer",
            "forint felismer",
            "penzfelismero"
        ) -> MenuAction.CURRENCY_RECOGNIZER

        containsAny(text, "fenydetektor", "feny meres") ->
            MenuAction.LIGHT_DETECTOR

        containsAny(
            text,
            "gyogyszerdoboz",
            "gyogyszer doboz",
            "gyogyszer felirat",
            "gyogyszer olvas"
        ) -> MenuAction.MEDICATION_READER

        containsAny(
            text,
            "cimke olvas",
            "termek cimke",
            "etel cimke",
            "osszetetel olvas"
        ) -> MenuAction.LABEL_READER

        containsAny(
            text,
            "szoveg olvas",
            "dokumentum olvas",
            "papir olvas",
            "felirat olvas"
        ) -> MenuAction.TEXT_READER

        containsAny(
            text,
            "folyamatos ocr",
            "folyamatos szoveg",
            "folyamatos olvas",
            "folyamatos szovegolvas",
            "folyamatos szovegolvaso"
        ) -> MenuAction.CONTINUOUS_OCR

        containsAny(text, "diktafon beallit", "felvetel minoseg", "diktafon minoseg") ->
            MenuAction.DICTAPHONE_SETTINGS

        containsAny(text, "mentett felvetel", "felvetelek", "diktafon konyvtar") ->
            MenuAction.DICTAPHONE_LIBRARY

        containsAny(text, "szamologep", "szamolj", "szamolas") ->
            MenuAction.CALCULATOR

        containsAny(text, "diktafon", "felvetel", "hangfelvetel") ->
            MenuAction.DICTAPHONE_RECORD

        containsAny(text, "rejtett szam", "rejtett szamok", "magán szam", "maganszam") ->
            MenuAction.CALL_FILTER_BLOCK_PRIVATE_TOGGLE

        containsAny(text, "pin beallit", "pin kod beallit", "uj pin") ->
            MenuAction.LOCK_PIN_SET

        containsAny(text, "pin allapot", "pin statusz", "pin zarolas allapot") ->
            MenuAction.LOCK_PIN_STATUS

        containsAny(text, "pin zaro", "pin zarolas", "pin kod") ->
            MenuAction.LOCK_PIN_TOGGLE

        containsAny(text, "q r", "qr", "vonalkod", "kod olvas") ->
            MenuAction.QR_SCAN

        containsAny(text, "wifi", "vifi", "wífi") ->
            MenuAction.WIFI_TOGGLE

        containsAny(text, "hotspot", "hot spot", "megosztott internet", "internet megosztas", "wifi hotspot") ->
            MenuAction.HOTSPOT_TOGGLE

        containsAny(text, "bluetooth", "kek fuggony") ->
            MenuAction.BT_TOGGLE

        containsAny(text, "ertesites", "ertesitesek", "notification") ->
            MenuAction.NOTIFICATIONS_READ

        containsAny(text, "hangero fel", "hangero novel", "hangosabban", "hangosits") ->
            MenuAction.VOLUME_UP

        containsAny(text, "hangero le", "hangero csokkent", "halkabban", "halkits") ->
            MenuAction.VOLUME_DOWN

        containsAny(text, "beszed gyorsabb", "gyorsabban olvass", "gyorsits") ->
            MenuAction.TTS_SPEED_UP

        containsAny(text, "beszed lassabb", "lassabban olvass", "lassits") ->
            MenuAction.TTS_SPEED_DOWN

        containsAny(text, "t t s motor", "tts motor", "beszed motor", "felolvaso motor") ->
            MenuAction.TTS_ENGINE_SELECT

        containsAny(text, "konyvmappa torles", "konyvmappak torlese") ->
            MenuAction.BOOK_FOLDER_CLEAR

        containsAny(text, "konyvmappa beallit", "konyv mappa beallit", "uj konyvmappa") ->
            MenuAction.BOOK_FOLDER_SET

        containsAny(text, "konyvmappa felolvas", "konyvmappak", "konyv mappa") ->
            MenuAction.BOOK_FOLDER_READ

        containsAny(text, "konyvjelzo torles", "konyvjelzok torlese") ->
            MenuAction.BOOK_BOOKMARK_DELETE

        containsAny(text, "nem reg olvasott", "friss konyvek", "utobbi konyvek") ->
            MenuAction.BOOK_RECENT

        containsAny(text, "konyvtar", "konyvek", "konyveim") ->
            MenuAction.BOOK_LIBRARY

        containsAny(text, "konyvjelzo", "konyvjelzok") ->
            MenuAction.BOOK_BOOKMARKS

        containsAny(text, "olvasas folytat", "folytasd a konyvet", "konyv folytatas") ->
            MenuAction.BOOK_RESUME

        containsAny(text, "minden alkalmazas", "kulso alkalmazas", "alkalmazasok listaja", "appok") ->
            MenuAction.EXTERNAL_APPS

        containsAny(text, "internet kereso", "internet kereső", "web kereses", "kereso") ->
            MenuAction.WEB_SEARCH

        containsAny(text, "adatvedelem", "adatvedelmi", "privacy") ->
            MenuAction.PRIVACY_POLICY

        containsAny(text, "felhasznalasi feltetelek", "felhasznalasi feltetel", "terms") ->
            MenuAction.TERMS_OF_USE

        containsAny(text, "jogi nyilatkozat", "jogi informacio") ->
            MenuAction.LEGAL_NOTICE

        containsAny(text, "kapcsolat email", "fejlesztoi email", "fejleszto email") ->
            MenuAction.CONTACT_EMAIL

        containsAny(text, "fejleszto", "ki keszitette", "keszitette") ->
            MenuAction.ABOUT_DEVELOPER

        containsAny(text, "az alkalmazasrol", "alkalmazas verzio", "verzio") ->
            MenuAction.ABOUT_APP

        containsAny(text, "kilepes launcher", "launcher valtas", "masik launcher") ->
            MenuAction.EXIT_LAUNCHER

        containsAny(text, "elena figyelo be", "elena figyelo indit", "elena figyel", "elena hallgass") ->
            MenuAction.ELENA_WAKE_LISTEN_ON

        containsAny(text, "elena figyelo ki", "elena figyelo le", "elena figyelo stop", "elena ne figyelj") ->
            MenuAction.ELENA_WAKE_LISTEN_OFF

        containsAny(text, "elena figyelo", "elena figyelo allapot", "elena figyelo statusz") ->
            MenuAction.ELENA_WAKE_LISTEN_TOGGLE

        containsAny(text, "elena tanitas", "elena tanit", "sajat felebeszto", "sajat felebeszto mondat", "felebeszto tanitas") ->
            MenuAction.ELENA_WAKE_TRAIN

        containsAny(text, "sajat felebeszto mondatok", "elena mondatok", "mentett felebeszto") ->
            MenuAction.ELENA_WAKE_CUSTOM_LIST

        containsAny(text, "elena", "szia elena", "kerlek elena", "hello elena", "hallo elena") ->
            MenuAction.VOICE_ASSISTANT

        containsAny(text, "hangos asszisztens", "asszisztens indit", "asszisztens indits") ->
            MenuAction.VOICE_ASSISTANT

        containsAny(text, "alapertelmezett asszisztens", "asszisztens beallit", "asszisztens beallitas", "oldalso gomb") ->
            MenuAction.ASSISTANT_DEFAULT_SETUP

        containsAny(text, "asszisztens allapot", "asszisztens statusz", "ki az asszisztens", "ki az elena") ->
            MenuAction.ASSISTANT_DEFAULT_STATUS

        containsAny(text, "csengohang hangerő", "csengohang hangero", "emlekezteto hangerő", "emlekezteto hangero") ->
            MenuAction.ALERT_SOUND_VOLUME_CYCLE

        containsAny(text, "nema mod", "néma mód", "csendes mod", "csendes mód", "hangok nemitasa") ->
            MenuAction.ALERT_SILENT_MODE_TOGGLE

        containsAny(text, "hangok", "program hangjai", "hangok betanitasa") ->
            MenuAction.SOUND_TRAINING

        containsAny(text, "söprés hangtema", "söprés hangtéma", "hangtema", "hangtéma", "gesztus hang") ->
            MenuAction.SOUND_THEME_SELECT

        containsAny(text, "tanulo mod", "tanuló mód", "gesztus gyakorlas", "gesztusok gyakorlasa", "jatszoter", "játszótér", "betanulas", "betanulás") ->
            MenuAction.TRAINING_PLAYGROUND

        containsAny(text, "helyszin tanitas", "helyszin tanitasa", "helyszin profil", "uj helyszin") ->
            MenuAction.LOCATION_TRAIN

        containsAny(text, "helyszin figyelo leallit", "helyszin figyelo stop", "figyelo leallitasa") ->
            MenuAction.LOCATION_WATCH_STOP

        containsAny(text, "helyszin figyelo szoveg", "helyszin figyelo szoveggel", "figyelo szoveg") ->
            MenuAction.LOCATION_WATCH_TEXT

        containsAny(text, "mentett helyszinek", "helyszin profilok", "helyszin lista") ->
            MenuAction.LOCATION_PROFILE_LIST

        containsAny(text, "helyszin figyelo", "helyszin felismero", "figyelo inditas") ->
            MenuAction.LOCATION_WATCH_START

        containsAny(text, "szelfi kamera", "szelfi", "elso kamera") ->
            MenuAction.FACE_CAMERA_SELFIE

        containsAny(text, "kamera minoseg", "kamera beallitas", "foto minoseg") ->
            MenuAction.FACE_CAMERA_QUALITY

        containsAny(text, "arc kamera", "arc felismero kamera", "arcfelismero", "kamera es szelfi", "kamera") ->
            MenuAction.FACE_CAMERA

        containsAny(text, "gps utvonal torles", "utvonal torlese", "mentett utvonal torles") ->
            MenuAction.GPS_ROUTE_DELETE

        containsAny(text, "gps utvonal lista", "mentett utvonalak", "utvonal lista") ->
            MenuAction.GPS_ROUTE_LIST

        containsAny(text, "gps utvonal utmutatas", "utvonal utmutatas", "utvonal kovetes") ->
            MenuAction.GPS_ROUTE_GUIDE

        containsAny(text, "gps utvonal leallit", "utvonal rögzites leallit", "utvonal rekord stop") ->
            MenuAction.GPS_ROUTE_STOP

        containsAny(text, "gps utvonal rogzites", "gps rekord", "utvonal felvetel", "utvonal rogzites") ->
            MenuAction.GPS_ROUTE_RECORD

        containsAny(text, "milyen nap van", "milyen nap", "ma milyen nap", "het napja") ->
            MenuAction.TIME_NOW

        containsAny(text, "milyen datum", "mai datum", "ma hanyadika", "ma milyen datum") ->
            MenuAction.TIME_NOW

        containsAny(text, "nevjegy szinkron", "nevjegyek frissites", "nevjegy frissites") ->
            MenuAction.CONTACT_SYNC

        containsAny(text, "gyalog utvonal", "seta utvonal", "setalj ide") ->
            MenuAction.NAV_WALK

        containsAny(text, "youtube keres", "jutub keres", "videot keres") ->
            MenuAction.YOUTUBE

        containsAny(text, "program hang", "emlekezteto hang", "csengohang valasztas") ->
            MenuAction.ALERT_SOUND_CALENDAR

        containsAny(text, "sms beallitas", "uzenet app beallitas", "alapertelmezett uzenet") ->
            MenuAction.SMS_DEFAULT_SETUP

        containsAny(text, "sms app allapot", "uzenet app allapot") ->
            MenuAction.SMS_DEFAULT_STATUS

        containsAny(text, "telefon beallitas", "alapertelmezett telefon") ->
            MenuAction.DIALER_DEFAULT_SETUP

        containsAny(text, "t t s hang", "beszed hang", "hang valasztas") ->
            MenuAction.TTS_ENGINE_SELECT

        containsAny(text, "milyen hang", "milyen beszed hang") ->
            MenuAction.TTS_ENGINE_READ

        else -> null
    }

    private fun extractOpenAppTarget(text: String): String? {
        val prefixes = listOf(
            "nyisd meg a",
            "nyisd meg az",
            "nyisd meg",
            "inditsd el a",
            "inditsd el az",
            "inditsd el",
            "nyit meg a",
            "nyit meg az"
        )
        extractAfter(text, prefixes)?.let { target ->
            val cleaned = target
                .removeSuffix(" alkalmazast")
                .removeSuffix(" appot")
                .removeSuffix(" app")
                .removeSuffix(" megnyitasa")
                .removeSuffix(" megnyitasa")
                .removeSuffix(" inditasa")
                .trim()
            if (cleaned.length >= 2) return cleaned
        }
        val openSuffix = Regex("""(.+?)\s+megnyitasa$""")
        openSuffix.find(text)?.groupValues?.getOrNull(1)?.trim()?.let {
            if (it.length >= 2) return it
        }
        return null
    }

    fun looksLikeWebSearch(text: String): Boolean {
        if (text.length < 8) return false
        val markers = listOf(
            "hogyan", "mi az", "mi a", "miert", "mikor", "hol van", "hol talal",
            "recept", "elkeszites", "keszites", "keszul", "mit jelent",
            "mire jo", "melyik", "kinek", "milyen", "mennyi", "lehet e"
        )
        if (markers.any { text.contains(it) }) return true
        return text.contains("?") || text.endsWith(" e") || text.contains(" keres")
    }

    private fun extractAfter(text: String, prefixes: List<String>): String? {
        for (prefix in prefixes) {
            val normalizedPrefix = normalize(prefix)
            val idx = text.indexOf(normalizedPrefix)
            if (idx >= 0) {
                val rest = text.substring(idx + normalizedPrefix.length).trim()
                    .removePrefix("hogy")
                    .removePrefix("ide")
                    .removePrefix("oda")
                    .removePrefix("a ")
                    .removePrefix("az ")
                    .removePrefix(":")
                    .trim()
                if (rest.isNotBlank()) return rest
            }
        }
        return null
    }

    private fun containsAny(text: String, vararg terms: String): Boolean =
        terms.any { term ->
            val normalized = normalize(term)
            text.contains(normalized) || text.split(" ").any { word -> word == normalized }
        }

    fun normalize(raw: String): String {
        val lower = raw.trim().lowercase(Locale("hu", "HU"))
        val noAccent = Normalizer.normalize(lower, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
        return noAccent
            .replace(Regex("[^a-z0-9\\s]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
    }
}