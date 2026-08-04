package com.superdl.launcher.email

import android.util.Base64
import android.util.Log
import com.superdl.launcher.search.ArticleTextExtractor
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.nio.charset.StandardCharsets
import javax.net.ssl.SSLSocket
import javax.net.ssl.SSLSocketFactory

object ImapReader {

    private const val TAG = "SDL_IMAP"
    private const val MAX_MESSAGES = 20

    /**
     * A levéltörzsből legfeljebb ennyi bájtot töltünk le. A felolvasás úgyis csak
     * az első pár ezer karaktert mondja ki, viszont a teljes levél több megabájt
     * is lehet — az pedig időtúllépéshez vezetett.
     */
    private const val BODY_FETCH_BYTES = 65536

    /**
     * A listával EGYÜTT letöltött levélrészlet mérete. A felolvasás úgyis csak
     * az első pár ezer karaktert mondja ki, így 20 levélnél ez összesen ~80 KB —
     * gyorsan letöltődik, viszont a megnyitás azonnali lesz.
     */
    private const val BODY_PREVIEW_BYTES = 4096

    /**
     * A listával együtt letöltött NYERS levélrészlet mérete (fejléc + törzs eleje).
     *
     * A mai levelek fejléce MEGLEPŐEN NAGY: a mérések szerint jellemzően 4-6 KB
     * (hitelesítési adatok, továbbítási láncok), és előfordul 8 KB fölött is.
     * A korábbi 8 KB-os korlátnál ezeknél a leveleknél a fejléc VÉGE — és vele a
     * feladó/tárgy/dátum — bele sem fért, ezért maradt üres minden mező.
     * 20 KB már bőven elég a fejlécre ÉS a felolvasáshoz szükséges szövegre is.
     */
    private const val RAW_FETCH_BYTES = 20480

    /**
     * Az utolsó hiba emberi nyelven — a felhasználónak bemondható.
     * Null, ha az utolsó lekérés sikeres volt.
     */
    var lastError: String? = null
        private set

    fun fetchInbox(config: SmtpConfig): List<ImapMail> {
        lastError = null
        if (!config.isValid()) {
            lastError = "Az e-mail beállítás hiányos."
            Log.w(TAG, "config nem ervenyes")
            return emptyList()
        }
        Log.i(TAG, "IMAP kapcsolodas: ${config.resolvedImapHost()}:${config.resolvedImapPort()} felhasznalo=${config.username}")
        return try {
            val mails = fetchWithSsl(config)
            Log.i(TAG, "IMAP siker: ${mails.size} level")
            if (mails.isEmpty()) lastError = "A postafiók üres, vagy nem érkezett levél."
            mails
        } catch (e: Exception) {
            val msg = e.message.orEmpty()
            Log.w(TAG, "IMAP HIBA: ${e.javaClass.simpleName}: $msg", e)
            lastError = when {
                msg.contains("AUTHENTICATIONFAILED", true) || msg.contains("LOGIN failed", true) ->
                    "A bejelentkezés nem sikerült. Ellenőrizd a felhasználónevet és az alkalmazás jelszót."
                msg.contains("timed out", true) || msg.contains("timeout", true) ->
                    "A szerver nem válaszolt időben. Ellenőrizd az internetkapcsolatot."
                msg.contains("Unable to resolve host", true) ->
                    "A szerver nem található. Ellenőrizd az IMAP kiszolgáló nevét."
                msg.contains("SELECT", true) ->
                    "A postafiók nem nyitható meg. Lehet, hogy az IMAP nincs engedélyezve a fiókban."
                else -> "Nem sikerült betölteni a leveleket. Részletek a naplóban."
            }
            emptyList()
        }
    }

    fun countUnread(config: SmtpConfig): Int {
        if (!config.isValid()) return 0
        return try {
            withSession(config) { readUnreadCount(it) }
        } catch (_: Exception) {
            0
        }
    }

    private fun fetchWithSsl(config: SmtpConfig): List<ImapMail> =
        withSession(config) { session ->
            // NAGY POSTAFIÓKNÁL EZ A KULCS:
            // Korábban "UID SEARCH ALL" futott, ami MINDEN levél azonosítóját
            // visszaadta egyetlen sorban (15000+ levélnél ~100 KB), majd minden
            // levélhez KÜLÖN parancs ment, ami a TELJES levéltörzset is letöltötte.
            // Ezért futott időtúllépésbe: "várakozz", majd visszalépés.
            //
            // Most: a postafiók méretéből (SELECT válaszának EXISTS értéke)
            // számoljuk a legutolsó N levél sorszám-tartományát, és EGYETLEN
            // paranccsal, CSAK A FEJLÉCEKET kérjük le. A levéltörzs akkor
            // töltődik le, amikor a felhasználó megnyit egy levelet.
            val total = session.lastSelectExists
            if (total <= 0) {
                emptyList()
            } else {
                val from = maxOf(1, total - MAX_MESSAGES + 1)
                Log.i(TAG, "postafiok merete=$total, lekert tartomany=$from..$total (csak fejlecek)")
                // A legfrissebb levél elöl. Az abszolút érték szerint rendezünk,
                // mert az azonosító lehet valódi UID (pozitív) vagy sorszám
                // (negatív) — mindkettőnél a NAGYOBB érték jelenti az újabbat.
                fetchHeaderRange(session, from, total)
                    .sortedByDescending { kotlin.math.abs(it.uid) }
            }
        }

    /**
     * Egyetlen FETCH paranccsal lekéri a megadott sorszám-tartomány fejléceit.
     * A levéltörzset NEM tölti le (az a megnyitáskor jön).
     */
    private fun fetchHeaderRange(session: ImapSession, from: Int, to: Int): List<ImapMail> {
        // A FEJLÉCET ÉS A TÖRZS ELEJÉT EGYSZERRE kérjük le.
        // Korábban a törzs külön kapcsolaton, megnyitáskor jött — de az minden
        // alkalommal új bejelentkezéssel és a 15000+ leveles postafiók újbóli
        // megnyitásával járt, ami időtúllépésbe futott. Így egyetlen parancs van,
        // és a levél megnyitása AZONNALI (nincs hálózati művelet).
        // A LEVÉL ELEJÉT KÉRJÜK EGYBEN (fejléc + törzs eleje).
        //
        // MIÉRT ÍGY: korábban két külön szekciót kértünk
        // (BODY.PEEK[HEADER.FIELDS (...)] és BODY.PEEK[TEXT]), de a szerver a
        // FEJLÉC-SZEKCIÓT NEM KÜLDTE VISSZA — a naplóban minden válasz
        // "BODY[TEXT]" volt, a fejléc hossza 0. Ezért nem hangzott el a feladó,
        // a tárgy és a dátum.
        // A "BODY.PEEK[]<0.N>" a NYERS LEVÉL első N bájtja, amiben a fejléc
        // MINDIG ott van elöl, utána egy üres sor, majd a törzs. A szétválasztás
        // ezután már a mi dolgunk — és megbízható.
        val tag = session.send("FETCH", "$from:$to (UID BODY.PEEK[]<0.$RAW_FETCH_BYTES>)")
        val mails = mutableListOf<ImapMail>()
        var seqNum = -1
        var uid = -1L
        var rawText = ""

        fun flush() {
            if (rawText.isBlank()) return
            val id = if (uid > 0) uid else -seqNum.toLong()
            // Szétválasztás az első üres sornál: előtte fejléc, utána törzs.
            val headerText = EmailBodyExtractor.headerPartOf(rawText)
            val bodyText = EmailBodyExtractor.bodyPartOf(rawText)
            val parsedFrom = parseHeaderField(headerText, "From")
            val parsedSubject = parseHeaderField(headerText, "Subject")
            val parsedDate = parseHeaderField(headerText, "Date")
            Log.i(
                TAG,
                "PARSE uid=$id fejlec=${headerText.length} torzs=${bodyText.length} " +
                    "from=[${parsedFrom.take(30)}] subject=[${parsedSubject.take(30)}]"
            )
            mails.add(
                ImapMail(
                    uid = id,
                    from = parsedFrom,
                    subject = parsedSubject.ifBlank { "Nincs tárgy" },
                    date = parsedDate.ifBlank { "Ismeretlen dátum" },
                    body = if (bodyText.isNotBlank()) cleanBody(rawText) else ""
                )
            )
            rawText = ""
            uid = -1L
        }

        while (true) {
            val line = session.readLine()
            if (line.isEmpty()) continue
            if (line.startsWith(tag)) {
                if (!line.contains("OK")) Log.w(TAG, "FETCH nem OK: $line")
                break
            }
            Regex("^\\*\\s+(\\d+)\\s+FETCH", RegexOption.IGNORE_CASE).find(line)?.let { m ->
                flush()
                seqNum = m.groupValues[1].toIntOrNull() ?: -1
            }
            Regex("UID\\s+(\\d+)").find(line)?.let { m ->
                m.groupValues[1].toLongOrNull()?.let { uid = it }
            }
            if (line.contains("{") && line.contains("}")) {
                rawText = session.readLiteral(line)
            }
        }
        flush()
        Log.i(
            TAG,
            "betoltve: ${mails.size} level, torzzsel egyutt " +
                "(${mails.count { it.body.isNotBlank() }} db-nak van tartalma)"
        )
        return mails
    }

    /**
     * Egyetlen levél TÖRZSÉNEK letöltése — akkor hívjuk, amikor a felhasználó
     * megnyit egy levelet a listából. Így a lista gyorsan betölt, és csak a
     * ténylegesen elolvasott levél tartalma jön le a hálózaton.
     */
    fun fetchBody(config: SmtpConfig, uid: Long): String? {
        if (!config.isValid() || uid == 0L) return null
        return try {
            withSession(config) { session ->
                // CSAK AZ ELEJÉT KÉRJÜK LE!
                // A teljes levél több megabájt is lehet (beágyazott képek, HTML),
                // ami időtúllépésbe futott. A felolvasás úgyis csak az első pár
                // ezer karaktert mondja ki, ezért az IMAP részleges letöltését
                // használjuk: "<0.65536>" = az első 64 kilobájt.
                val section = "BODY.PEEK[TEXT]<0.$BODY_FETCH_BYTES>"
                val tag = if (uid > 0) {
                    session.send("UID FETCH", "$uid ($section)")
                } else {
                    session.send("FETCH", "${-uid} ($section)")
                }
                val chunks = session.collectFetchLines(tag)
                Log.i(TAG, "torzs letoltve: azonosito=$uid, blokkok=${chunks.size}, " +
                    "nyers hossz=${chunks.sumOf { it.length }}")
                cleanBody(chunks.maxByOrNull { it.length }.orEmpty()).ifBlank { null }
            }
        } catch (e: Exception) {
            Log.w(TAG, "fetchBody hiba (azonosito=$uid): ${e.javaClass.simpleName}: ${e.message}")
            null
        }
    }

    private fun <T> withSession(config: SmtpConfig, block: (ImapSession) -> T): T {
        val factory = SSLSocketFactory.getDefault() as SSLSocketFactory
        // A szerver a beállításból jön (korábban imap.gmail.com volt bedrótozva,
        // ezért nem-Gmail fióknál a küldés ment, az olvasás némán üres maradt).
        val imapHost = config.resolvedImapHost()
        val imapPort = config.resolvedImapPort()
        val socket = factory.createSocket(imapHost, imapPort) as SSLSocket
        // Türelmesebb időkorlát: nagy postafióknál a megnyitás és a levéltörzs
        // letöltése is eltarthat pár másodpercig, a 15 mp kevésnek bizonyult.
        socket.soTimeout = 45_000
        socket.startHandshake()
        val reader = BufferedReader(InputStreamReader(socket.inputStream, StandardCharsets.UTF_8))
        val writer = OutputStreamWriter(socket.outputStream, StandardCharsets.UTF_8)
        val session = ImapSession(reader, writer)
        try {
            expectTag(session.readLine(), "* OK")
            session.command("LOGIN", imapQuote(config.username) + " " + imapQuote(config.password))
            // A SELECT válaszából kiolvassuk a postafiók méretét (EXISTS) — ebből
            // számoljuk a legutolsó levelek tartományát, SEARCH nélkül.
            session.lastSelectExists = selectInbox(session)
            return block(session)
        } finally {
            try {
                session.command("LOGOUT")
            } catch (_: Exception) {
            }
            socket.close()
        }
    }

    /**
     * Megnyitja a beérkező postafiókot, és visszaadja a benne lévő levelek
     * számát (az "EXISTS" válaszból). Ebből számoljuk a legutolsó levelek
     * sorszám-tartományát — így nem kell az összes azonosítót lekérni.
     */
    private fun selectInbox(session: ImapSession): Int {
        val tag = session.send("SELECT", "INBOX")
        var exists = 0
        while (true) {
            val line = session.readLine()
            if (line.isEmpty()) continue
            if (line.startsWith(tag)) {
                if (!line.contains("OK")) throw IllegalStateException("IMAP SELECT failed: $line")
                break
            }
            if (line.contains("EXISTS")) {
                exists = line.trim().split(Regex("\\s+")).getOrNull(1)?.toIntOrNull() ?: exists
            }
        }
        return exists
    }

    private fun readUnreadCount(session: ImapSession): Int {
        session.command("SEARCH", "UNSEEN")
        val line = session.lastDataLine
        val parts = line.substringAfter("SEARCH", line).trim().split(Regex("\\s+"))
        return parts.count { part -> part.all(Char::isDigit) && part.isNotBlank() }
    }

    private fun searchAll(session: ImapSession): List<Long> {
        session.command("UID SEARCH", "ALL")
        val line = session.lastDataLine
        val tail = line.substringAfter("SEARCH", line).trim()
        return tail.split(Regex("\\s+"))
            .mapNotNull { part -> part.toLongOrNull() }
            .sortedDescending()
    }

    private fun fetchMessage(session: ImapSession, uid: Long): ImapMail? {
        // FONTOS: a FETCH választ NEM a command()-dal olvassuk!
        // A command() a záró tag-ig végigolvassa a választ, így utána a
        // collectFetchLines() már üres adatfolyamra várt volna -> időtúllépés
        // (15 mp), majd kivétel -> a fetchInbox üres listát adott vissza.
        // Ezért itt csak ELKÜLDJÜK a parancsot, és a válasz feldolgozását
        // teljes egészében a collectFetchLines(tag) végzi.
        val tag = session.send(
            "UID FETCH",
            "$uid (BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)] BODY.PEEK[TEXT])"
        )
        val chunks = session.collectFetchLines(tag)
        if (chunks.isEmpty()) return null
        val header = chunks.firstOrNull { it.contains("From:") || it.contains("FROM:") }.orEmpty()
        val body = chunks.lastOrNull().orEmpty()
        return ImapMail(
            uid = uid,
            from = parseHeaderField(header, "From"),
            subject = parseHeaderField(header, "Subject").ifBlank { "Nincs tárgy" },
            date = parseHeaderField(header, "Date").ifBlank { "Ismeretlen dátum" },
            body = cleanBody(body)
        )
    }

    private fun parseHeaderField(header: String, field: String): String {
        // A fejléc több sorba tördelve is jöhet: a folytatás-sorok szóközzel
        // vagy tabulátorral kezdődnek, azokat hozzá kell fűzni.
        val regex = Regex("(?im)^$field:\\s*(.+(?:\\r?\\n[ \\t].+)*)$")
        val raw = regex.find(header)?.groupValues?.getOrNull(1)
            ?.replace(Regex("\\r?\\n[ \\t]+"), " ")
            ?.trim()
            .orEmpty()
        // Az ékezetes tárgy/feladó kódolva érkezik ("=?UTF-8?B?...?="), ezt
        // olvashatóvá alakítjuk, különben a felolvasás a kódot darálná.
        return EmailBodyExtractor.decodeHeaderText(raw)
    }

    /**
     * A nyers levéltörzsből olvasható szöveget készít.
     *
     * A korábbi változat csak a HTML-t próbálta kezelni, ezért a felhasználó a
     * MIME-fejléceket, a határolókat és a kódolt szemetet ("=C3=A9", base64)
     * hallotta felolvasva. Most az EmailBodyExtractor végzi a munkát: szétbontja
     * a levelet részekre, kiválasztja a sima szöveges részt, feloldja a
     * kódolást a helyes karakterkészlettel, és eltakarítja a technikai sorokat.
     */
    private fun cleanBody(raw: String): String = EmailBodyExtractor.extract(raw)

    private fun imapQuote(value: String): String {
        val escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
        return "\"$escaped\""
    }

    private fun expectTag(line: String, prefix: String) {
        if (!line.startsWith(prefix)) throw IllegalStateException("IMAP greeting: $line")
    }

    private class ImapSession(
        private val reader: BufferedReader,
        private val writer: OutputStreamWriter
    ) {
        private var tagCounter = 0
        var lastDataLine: String = ""

        /** A legutóbbi postafiók-megnyitáskor jelentett levélszám (EXISTS). */
        var lastSelectExists: Int = 0

        /** Egy IMAP literál blokk beolvasása (a "{123}" jelölésű rész). */
        fun readLiteral(headerLine: String): String = readLiteralBlock(headerLine)

        fun readLine(): String = reader.readLine() ?: ""

        /** Csak elküldi a parancsot, a választ a hívó olvassa (a tag-et adja vissza). */
        fun send(cmd: String, args: String = ""): String {
            val tag = "A${++tagCounter}"
            if (args.isBlank()) write("$tag $cmd\r\n") else write("$tag $cmd $args\r\n")
            return tag
        }

        fun command(cmd: String, args: String = "") {
            val tag = send(cmd, args)
            var data = ""
            while (true) {
                val line = readLine()
                if (line.startsWith(tag)) {
                    if (!line.contains("OK")) throw IllegalStateException("IMAP $cmd failed: $line")
                    break
                }
                if (line.startsWith("*")) data = line
            }
            lastDataLine = data
        }

        /** A FETCH válasz feldolgozása a megadott tag záró soráig. */
        fun collectFetchLines(tag: String): List<String> {
            val lines = mutableListOf<String>()
            while (true) {
                val line = readLine()
                if (line.isEmpty()) continue
                if (line.startsWith(tag)) {
                    if (!line.contains("OK")) {
                        Log.w(TAG, "IMAP FETCH nem OK: $line")
                    }
                    break
                }
                if (line.contains("{") && line.contains("}")) {
                    val literal = readLiteralBlock(line)
                    if (literal.isNotBlank()) lines.add(literal)
                }
            }
            return lines
        }

        private fun readLiteralBlock(headerLine: String): String {
            val match = Regex("\\{(\\d+)\\}").find(headerLine) ?: return ""
            val size = match.groupValues[1].toIntOrNull() ?: return ""
            val buf = CharArray(size)
            var read = 0
            while (read < size) {
                val r = reader.read(buf, read, size - read)
                if (r < 0) break
                read += r
            }
            readLine()
            return String(buf, 0, read.coerceAtLeast(0))
        }

        private fun write(text: String) {
            writer.write(text)
            writer.flush()
        }
    }
}