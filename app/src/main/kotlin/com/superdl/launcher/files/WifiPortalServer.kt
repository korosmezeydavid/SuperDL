package com.superdl.launcher.files

import android.content.Context
import android.net.wifi.WifiManager
import android.text.format.Formatter
import android.util.Log
import java.io.BufferedOutputStream
import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.net.ServerSocket
import java.net.Socket
import java.net.URLDecoder
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * WiFi fájlportál: a telefon nyit egy pici webszervert, és a gépről
 * böngészőben (pl. http://192.168.1.42:8080) fel lehet tölteni fájlokat,
 * illetve letölteni a telefonról – kábel és USB-mód nélkül.
 *
 * Miért ez a jó megoldás vakon:
 *  - az USB-mód átkapcsolását az Android nem engedi appból,
 *  - viszont egy WiFi-portálhoz semmilyen rendszerjog nem kell,
 *  - a gépen a böngésző teljesen hozzáférhető felület.
 *
 * Biztonság: csak a helyi WiFi-n érhető el, a szerver csak akkor fut, amíg
 * a felhasználó bekapcsolva hagyja, és minden feltöltés egyetlen mappába
 * kerül (SuperDL/Portal). Nincs jelszó – ezért a felhasználót figyelmeztetjük,
 * hogy megbízható hálózaton használja, és utána kapcsolja ki.
 */
class WifiPortalServer(
    private val context: Context,
    private val port: Int = 8080
) {

    companion object {
        private const val TAG = "SuperDL.Portal"
        const val UPLOAD_FOLDER = "SuperDL/Portal"
        private const val MAX_UPLOAD_BYTES = 2L * 1024 * 1024 * 1024 // 2 GB

        // A feltöltés-feldolgozó visszatoló pufferének mérete. Legalább akkora
        // kell legyen, mint amennyit a writePartToFile egy körben beolvashat
        // (64 KB + határoló), mert a határoló utáni bájtokat ide toljuk vissza.
        private const val UPLOAD_PUSHBACK_BYTES = 128 * 1024
    }

    private var serverSocket: ServerSocket? = null
    private val running = AtomicBoolean(false)
    private val pool = Executors.newFixedThreadPool(4)

    /**
     * Értesítés feltöltéskor – a telefon bemondja, hogy megérkezett a fájl.
     * Vakon ez fontos: akkor is tudod, ha nem a gép előtt ülsz.
     */
    var onFilesUploaded: ((names: List<String>, destination: String) -> Unit)? = null

    val isRunning: Boolean get() = running.get()

    /** A feltöltési mappa (létrehozza, ha kell). */
    fun uploadDir(): File {
        val dir = File(android.os.Environment.getExternalStorageDirectory(), UPLOAD_FOLDER)
        if (!dir.exists()) dir.mkdirs()
        return dir
    }

    // ==================== PIN-védelem ====================

    /**
     * Négyjegyű PIN, amit a telefon bemond induláskor. Enélkül bárki, aki
     * ugyanazon a WiFi-n van, hozzáférne a fájlokhoz (akár a jelszó-fájlhoz).
     */
    val pin: String = (1000..9999).random().toString()

    /** Felolvasható PIN: "3 7 2 9" – számjegyenként, hogy le lehessen írni. */
    fun speakPin(): String = pin.toCharArray().joinToString(" ")

    private fun isAuthorized(headers: Map<String, String>, path: String): Boolean {
        val cookie = headers["cookie"].orEmpty()
        if (cookie.contains("superdl_pin=$pin")) return true
        // A query-ben is jöhet (az első belépéskor)
        return path.contains("pin=$pin")
    }

    /**
     * Az űrlapok POST-tartalmának beolvasása (Content-Length alapján).
     * Kis méretű, URL-kódolt adat – SMS, névjegy, jegyzet.
     */
    private fun readBody(input: InputStream, headers: Map<String, String>): String {
        val length = headers["content-length"]?.toIntOrNull() ?: return ""
        if (length <= 0 || length > 512 * 1024) return ""
        return try {
            val buffer = ByteArray(length)
            var read = 0
            while (read < length) {
                val r = input.read(buffer, read, length - read)
                if (r <= 0) break
                read += r
            }
            String(buffer, 0, read, Charsets.UTF_8)
        } catch (e: Exception) {
            Log.w(TAG, "readBody failed", e)
            ""
        }
    }

    private fun handleLogin(output: OutputStream, path: String) {
        val given = path.substringAfter("pin=", "").substringBefore("&").trim()
        if (given == pin) {
            val response = "HTTP/1.1 302 Found\r\n" +
                "Set-Cookie: superdl_pin=$pin; Path=/\r\n" +
                "Location: /\r\n" +
                "Content-Length: 0\r\n" +
                "Connection: close\r\n\r\n"
            output.write(response.toByteArray())
        } else {
            serveHtml(output, buildLoginPage(true))
        }
    }

    private fun buildLoginPage(error: Boolean): String = """
        <!DOCTYPE html><html lang="hu"><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>SuperDL fájlportál</title><style>${portalCss()}</style></head><body>
        <h1>SuperDL fájlportál</h1>
        ${if (error) "<p class='err'>Hibás PIN. Próbáld újra.</p>" else ""}
        <p>Írd be a telefon által bemondott négyjegyű PIN kódot.</p>
        <form action="/login" method="get">
          <input type="text" name="pin" inputmode="numeric" autofocus placeholder="PIN kód">
          <button type="submit">Belépés</button>
        </form></body></html>
    """.trimIndent()

    private fun portalCss(): String = """
        body{font-family:system-ui,Arial,sans-serif;max-width:760px;margin:0 auto;padding:24px;background:#101418;color:#e8eaed}
        h1{font-size:1.6rem;color:#8ab4f8}
        input,button{font-size:1rem;padding:12px;margin:6px 0;border-radius:6px;border:1px solid #3c4043;background:#1e2126;color:#e8eaed}
        button{background:#8ab4f8;color:#101418;font-weight:600;cursor:pointer;border:none}
        .err{color:#f28b82}
    """.trimIndent()

    /** A telefon IP-címe a WiFi-n. */
    fun localIpAddress(): String? = try {
        val wm = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        @Suppress("DEPRECATION")
        val ip = wm.connectionInfo.ipAddress
        if (ip == 0) null else Formatter.formatIpAddress(ip)
    } catch (e: Exception) {
        Log.w(TAG, "localIpAddress failed", e)
        null
    }

    /** A böngészőbe írandó cím. */
    fun portalUrl(): String? = localIpAddress()?.let { "http://$it:$port" }

    /** Felolvasható cím: "192 pont 168 pont 1 pont 42 kettőspont 8080". */
    fun speakUrl(): String? {
        val ip = localIpAddress() ?: return null
        val spokenIp = ip.replace(".", " pont ")
        return "$spokenIp kettőspont $port"
    }

    fun start(): Boolean {
        if (running.get()) return true
        return try {
            // A portál mappa létrehozása induláskor – így a főoldal listája
            // akkor is működik, ha a felhasználó máshova (pl. Zene) tölt fel.
            uploadDir()
            serverSocket = ServerSocket(port)
            running.set(true)
            pool.execute { acceptLoop() }
            Log.i(TAG, "Portal started on port $port")
            true
        } catch (e: Exception) {
            Log.w(TAG, "start failed", e)
            running.set(false)
            false
        }
    }

    fun stop() {
        running.set(false)
        try {
            serverSocket?.close()
        } catch (_: Exception) {
        }
        serverSocket = null
        Log.i(TAG, "Portal stopped")
    }

    private fun acceptLoop() {
        while (running.get()) {
            try {
                val client = serverSocket?.accept() ?: break
                pool.execute { handleClient(client) }
            } catch (e: Exception) {
                if (running.get()) Log.w(TAG, "accept failed", e)
                break
            }
        }
    }

    private fun handleClient(socket: Socket) {
        try {
            // Nagyvonalúbb időkorlát: egy több száz MB-os feltöltésnél a WiFi
            // időnként megbicsaklik (roaming, interferencia), és a régi 30 mp
            // már egy rövid szünettől is elvágta a kapcsolatot. 3 perc alatt a
            // pillanatnyi zavarok kiheverhetők, de a beragadt kapcsolat sem él
            // örökké.
            socket.soTimeout = 180_000
            // TELJESÍTMÉNY: pufferelt be- és kimenet + nagyobb TCP puffer.
            // Pufferelés nélkül minden bájt külön rendszerhívás volt.
            socket.receiveBufferSize = 256 * 1024
            socket.tcpNoDelay = true
            val input = java.io.BufferedInputStream(socket.getInputStream(), 64 * 1024)
            val output = BufferedOutputStream(socket.getOutputStream(), 64 * 1024)

            val requestLine = readLine(input) ?: return
            val parts = requestLine.split(" ")
            if (parts.size < 2) return
            val method = parts[0]
            val path = parts[1]
            // A query stringet (?pin=... stb.) le kell vágni a ROUTINGHOZ, mert a
            // legtöbb ág pontos egyezést vár (path == "/backup/download"). A GET-
            // formok viszont a query-be teszik a PIN-t, ezért a nyers path nem
            // egyezne, és minden ilyen kérés a 404-es főoldalra esne. Az auth
            // továbbra is a NYERS path-ból olvassa a pin= paramétert.
            val route = path.substringBefore("?")

            // Fejlécek beolvasása
            val headers = mutableMapOf<String, String>()
            while (true) {
                val line = readLine(input) ?: break
                if (line.isBlank()) break
                val idx = line.indexOf(':')
                if (idx > 0) {
                    headers[line.substring(0, idx).trim().lowercase()] =
                        line.substring(idx + 1).trim()
                }
            }

            when {
                // PIN-ellenőrzés: a portál csak a helyes kóddal használható.
                // (Fontos: ide kerülhet a jelszó-fájl is, ezért nem lehet nyitott.)
                path.startsWith("/login") -> handleLogin(output, path)
                !isAuthorized(headers, path) -> serveHtml(output, buildLoginPage(false))
                method == "GET" && route == "/" ->
                    serveHtml(output, buildIndexPage())
                method == "GET" && route.startsWith("/download/") ->
                    serveDownload(output, route.removePrefix("/download/"))
                method == "POST" && route == "/upload" ->
                    handleUpload(input, output, headers)

                // ===== Vezérlő-oldalak: SMS, névjegyek, jegyzetek, állapot =====
                method == "GET" && route == "/sms" ->
                    serveHtml(output, PortalControlPages.smsPage(context))
                method == "POST" && route == "/sms/send" ->
                    serveHtml(output, PortalControlPages.handleSmsSend(context, readBody(input, headers)))
                method == "POST" && route == "/sms/delete" ->
                    serveHtml(output, PortalControlPages.handleSmsDelete(context, readBody(input, headers)))
                method == "POST" && route == "/sms/reply" ->
                    serveHtml(output, PortalControlPages.handleSmsReply(context, readBody(input, headers)))
                method == "GET" && route == "/contacts" ->
                    serveHtml(output, PortalControlPages.contactsPage(context))
                method == "POST" && route == "/contacts/add" ->
                    serveHtml(output, PortalControlPages.handleContactAdd(context, readBody(input, headers)))
                method == "POST" && route == "/contacts/share" ->
                    serveHtml(output, PortalControlPages.handleContactShare(context, readBody(input, headers)))
                method == "POST" && route == "/contacts/delete-confirm" ->
                    serveHtml(output, PortalControlPages.handleContactDeleteConfirm(context, readBody(input, headers)))
                method == "POST" && route == "/contacts/delete" ->
                    serveHtml(output, PortalControlPages.handleContactDelete(context, readBody(input, headers)))
                method == "GET" && route == "/contacts/export" -> {
                    val stamp = java.text.SimpleDateFormat("yyyyMMdd-HHmm", java.util.Locale.US)
                        .format(java.util.Date())
                    serveTextDownload(
                        output,
                        PortalControlPages.contactsVCard(context),
                        "superdl-nevjegyek-$stamp.vcf",
                        "text/vcard"
                    )
                }
                method == "GET" && route == "/medication" ->
                    serveHtml(output, PortalControlPages.medicationPage(context))
                method == "POST" && route == "/medication/add" ->
                    serveHtml(output, PortalControlPages.handleMedicationAdd(context, readBody(input, headers)))
                method == "POST" && route == "/medication/toggle" ->
                    serveHtml(output, PortalControlPages.handleMedicationToggle(context, readBody(input, headers)))
                method == "POST" && route == "/medication/delete-confirm" ->
                    serveHtml(output, PortalControlPages.handleMedicationDeleteConfirm(context, readBody(input, headers)))
                method == "POST" && route == "/medication/delete" ->
                    serveHtml(output, PortalControlPages.handleMedicationDelete(context, readBody(input, headers)))

                // ===== E-mail beállítások =====
                // A haladó űrlapot a ?advanced=1 nyitja ki (GET-tel, hogy a
                // gomb sima linkként is működjön képernyőolvasóval).
                method == "GET" && (path == "/email" || path.startsWith("/email?")) ->
                    serveHtml(
                        output,
                        PortalControlPages.emailPage(
                            context,
                            showAdvanced = path.contains("advanced=1")
                        )
                    )
                method == "POST" && route == "/email/save-gmail" ->
                    serveHtml(output, PortalControlPages.handleEmailSaveGmail(context, readBody(input, headers)))
                method == "POST" && route == "/email/save-advanced" ->
                    serveHtml(output, PortalControlPages.handleEmailSaveAdvanced(context, readBody(input, headers)))
                method == "POST" && route == "/email/test" ->
                    serveHtml(output, PortalControlPages.handleEmailTest(context))
                method == "POST" && route == "/email/delete-confirm" ->
                    serveHtml(output, PortalControlPages.handleEmailDeleteConfirm(context))
                method == "POST" && route == "/email/delete" ->
                    serveHtml(output, PortalControlPages.handleEmailDelete(context))

                method == "GET" && route == "/notes" ->
                    serveHtml(output, PortalControlPages.notesPage(context))
                method == "POST" && route == "/notes/add" ->
                    serveHtml(output, PortalControlPages.handleNoteAdd(context, readBody(input, headers)))

                method == "GET" && route == "/alarms" ->
                    serveHtml(output, PortalControlPages.alarmsPage(context))
                method == "POST" && route == "/alarms/add" ->
                    serveHtml(output, PortalControlPages.handleAlarmAdd(context, readBody(input, headers)))
                method == "POST" && route == "/alarms/delete" ->
                    serveHtml(output, PortalControlPages.handleAlarmDelete(context, readBody(input, headers)))

                method == "GET" && route == "/places" ->
                    serveHtml(output, PortalControlPages.placesPage(context))
                method == "POST" && route == "/places/delete" ->
                    serveHtml(output, PortalControlPages.handlePlaceDelete(context, readBody(input, headers)))

                method == "GET" && route == "/podcast" ->
                    serveHtml(output, PortalControlPages.podcastPage(context))
                method == "POST" && route == "/podcast/add" ->
                    serveHtml(output, PortalControlPages.handlePodcastAdd(context, readBody(input, headers)))

                method == "GET" && route == "/media" ->
                    serveHtml(output, PortalControlPages.mediaPage(context))
                method == "GET" && route == "/media/download" -> {
                    val token = path.substringAfter("token=", "").substringBefore("&").trim()
                    serveMediaDownload(output, token)
                }

                // Bevásárlólista: gyors bevitel a gépről.
                method == "GET" && route == "/shopping" ->
                    serveHtml(output, PortalControlPages.shoppingPage(context))
                method == "POST" && route == "/shopping/select" ->
                    serveHtml(output, PortalControlPages.handleShoppingSelect(context, readBody(input, headers)))
                method == "POST" && route == "/shopping/newlist" ->
                    serveHtml(output, PortalControlPages.handleShoppingNewList(context, readBody(input, headers)))
                method == "POST" && route == "/shopping/dellist" -> {
                    readBody(input, headers)
                    serveHtml(output, PortalControlPages.handleShoppingDeleteList(context))
                }
                method == "POST" && route == "/shopping/add" ->
                    serveHtml(output, PortalControlPages.handleShoppingAdd(context, readBody(input, headers)))
                method == "POST" && route == "/shopping/toggle" ->
                    serveHtml(output, PortalControlPages.handleShoppingToggle(context, readBody(input, headers)))
                method == "POST" && route == "/shopping/delete" ->
                    serveHtml(output, PortalControlPages.handleShoppingDelete(context, readBody(input, headers)))

                // Naptár: programok felvétele, szerkesztése, törlése a gépről.
                method == "GET" && route == "/calendar" -> {
                    val editId = path.substringAfter("edit=", "").substringBefore("&").trim().toLongOrNull()
                    serveHtml(output, PortalControlPages.calendarPage(context, editId = editId))
                }
                method == "POST" && route == "/calendar/add" ->
                    serveHtml(output, PortalControlPages.handleCalendarAdd(context, readBody(input, headers)))
                method == "POST" && route == "/calendar/update" ->
                    serveHtml(output, PortalControlPages.handleCalendarUpdate(context, readBody(input, headers)))
                method == "POST" && route == "/calendar/delete" ->
                    serveHtml(output, PortalControlPages.handleCalendarDelete(context, readBody(input, headers)))

                // Saját rádióállomások (m3u/pls/direkt stream URL).
                method == "GET" && route == "/radio" ->
                    serveHtml(output, PortalControlPages.radioPage(context))
                method == "POST" && route == "/radio/add" ->
                    serveHtml(output, PortalControlPages.handleRadioAdd(context, readBody(input, headers)))
                method == "POST" && route == "/radio/delete" ->
                    serveHtml(output, PortalControlPages.handleRadioDelete(context, readBody(input, headers)))

                // "Hol a telóm?" — hangos csörgetés a portálról.
                method == "POST" && route == "/find-phone/start" -> {
                    com.superdl.launcher.files.FindPhoneHelper.start(context)
                    serveHtml(output, PortalControlPages.statusPage(context, findPhoneMsg = "A telefon csörög! Kövesd a hangot. 30 másodperc múlva magától elhallgat."))
                }
                method == "POST" && route == "/find-phone/stop" -> {
                    com.superdl.launcher.files.FindPhoneHelper.stop(context)
                    serveHtml(output, PortalControlPages.statusPage(context, findPhoneMsg = "A csörgetés leállítva."))
                }

                method == "GET" && route == "/status" ->
                    serveHtml(output, PortalControlPages.statusPage(context))

                method == "GET" && route == "/setup" ->
                    serveHtml(output, PortalControlPages.setupPage(context))

                method == "GET" && route == "/diagnostics" ->
                    serveHtml(output, PortalControlPages.diagnosticsPage(context))

                // ===== Mentés és visszaállítás =====
                method == "GET" && route == "/backup" ->
                    serveHtml(output, PortalControlPages.backupPage(context))
                method == "GET" && route == "/backup/download" -> {
                    val stamp = java.text.SimpleDateFormat("yyyyMMdd-HHmm", java.util.Locale.US)
                        .format(java.util.Date())
                    serveTextDownload(
                        output,
                        PortalControlPages.backupJson(context),
                        "superdl-mentes-$stamp.json",
                        "application/json"
                    )
                }
                method == "POST" && route == "/backup/restore-confirm" ->
                    serveHtml(
                        output,
                        PortalControlPages.backupRestoreConfirm(
                            context,
                            readSmallTextUpload(input, headers)
                        )
                    )
                method == "POST" && route == "/backup/restore" ->
                    serveHtml(output, PortalControlPages.handleBackupRestore(context, readBody(input, headers)))

                else ->
                    serveHtml(output, buildIndexPage(), status = "404 Not Found")
            }
            output.flush()
        } catch (e: Exception) {
            Log.w(TAG, "handleClient failed", e)
        } finally {
            try {
                socket.close()
            } catch (_: Exception) {
            }
        }
    }

    // ==================== Feltöltés ====================

    /**
     * Kis méretű szövegfájl beolvasása multipart-ból, MEMÓRIÁBA.
     *
     * MIÉRT KÜLÖN a handleUpload-tól: az lemezre streamel (nagy fájlokra
     * tervezve). A mentés-fájl viszont kicsi, és NEM akarjuk a telefonra írni,
     * mielőtt kiderülne, egyáltalán érvényes-e. Ha mégis óriási, elutasítjuk.
     */
    private fun readSmallTextUpload(
        input: InputStream,
        headers: Map<String, String>,
        maxBytes: Int = 4 * 1024 * 1024
    ): String {
        val contentType = headers["content-type"] ?: return ""
        val boundary = Regex("boundary=(.+)").find(contentType)
            ?.groupValues?.get(1)?.trim('"') ?: return ""
        val contentLength = headers["content-length"]?.toIntOrNull() ?: return ""
        if (contentLength > maxBytes) return ""

        val raw = ByteArray(contentLength)
        var read = 0
        while (read < contentLength) {
            val n = input.read(raw, read, contentLength - read)
            if (n <= 0) break
            read += n
        }
        val body = String(raw, 0, read, Charsets.UTF_8)

        // A rész fejlécei után üres sor jön, utána a tartalom, a végén a határoló.
        val delimiter = "--$boundary"
        val start = body.indexOf("\r\n\r\n")
        if (start < 0) return ""
        val afterHeaders = body.substring(start + 4)
        val end = afterHeaders.indexOf(delimiter)
        return if (end >= 0) {
            afterHeaders.substring(0, end).trim()
        } else {
            afterHeaders.trim()
        }
    }


    /**
     * multipart/form-data feltöltés feldolgozása.
     * Egyszerű, streamelő megvalósítás: a fájlt közvetlenül lemezre írjuk,
     * hogy a nagy fájlok se egyék meg a memóriát.
     */
    private fun handleUpload(rawInput: InputStream, output: OutputStream, headers: Map<String, String>) {
        val contentType = headers["content-type"] ?: ""
        val boundary = Regex("boundary=(.+)").find(contentType)?.groupValues?.get(1)?.trim('"')
        if (boundary == null) {
            serveHtml(output, resultPage("Hiba: hiányzó fájlhatár.", false))
            return
        }
        val contentLength = headers["content-length"]?.toLongOrNull() ?: 0L
        Log.i(TAG, "UPLOAD KERES: varhato meret=${contentLength / 1024 / 1024} MB")
        if (contentLength > MAX_UPLOAD_BYTES) {
            serveHtml(output, resultPage("A fájl túl nagy (max 2 GB).", false))
            return
        }

        // FONTOS (feltöltés-megakadás + duplikáció javítása):
        // A writePartToFile nagy blokkokban olvas, ezért a fájl végét jelző
        // határoló UTÁNI bájtok is a pufferbe kerülnek. Korábban ezeket eldobtuk,
        // amitől a feldolgozó elvesztette a szinkront: utána olyan adatra várt,
        // amit már elfogyasztott -> a feltöltés beállt (a böngésző a válaszra
        // várt, a szerver meg további adatra), majd az újrapróbálkozások miatt
        // sokszorozódtak a fájlok. A PushbackInputStream lehetővé teszi, hogy a
        // fölöslegesen beolvasott bájtokat VISSZATOLJUK az adatfolyamba.
        val input = java.io.PushbackInputStream(rawInput, UPLOAD_PUSHBACK_BYTES)

        val delimiter = "--$boundary"
        var savedNames = mutableListOf<String>()
        // A teljes útvonalak a MediaStore-bejelentéshez (enélkül nem látja a zenelejátszó).
        val savedPaths = mutableListOf<String>()
        // A felhasználó által választott célmappa (a form "dest" mezője).
        var destination = "portal"

        try {
            var line = readLine(input)
            while (line != null) {
                if (line.startsWith(delimiter)) {
                    // Fejlécek a részhez
                    var filename: String? = null
                    var fieldName: String? = null
                    while (true) {
                        val h = readLine(input) ?: break
                        if (h.isBlank()) break
                        if (h.lowercase().startsWith("content-disposition")) {
                            filename = Regex("filename=\"([^\"]*)\"").find(h)?.groupValues?.get(1)
                            fieldName = Regex("name=\"([^\"]*)\"").find(h)?.groupValues?.get(1)
                        }
                    }
                    when {
                        // A célmappa-választó értéke (nem fájl, hanem sima mező)
                        filename == null && fieldName == "dest" -> {
                            val value = readLine(input)?.trim()
                            if (!value.isNullOrBlank()) destination = value
                        }
                        !filename.isNullOrBlank() -> {
                            val dir = destinationDir(destination)
                            // A Windows/mac rendszerfájljait kihagyjuk: az Android
                            // egy részüket amúgy is tiltja (EPERM), és semmi
                            // keresnivalójuk a zenék közt.
                            val isJunk = isJunkFile(filename)
                            val target = uniqueFile(dir, sanitize(filename))
                            val written = writePartToFile(input, target, delimiter, skip = isJunk)
                            if (written) {
                                savedNames.add(target.name)
                                savedPaths.add(target.absolutePath)
                            }
                        }
                    }
                }
                line = readLine(input)
                if (line != null && line.startsWith("$delimiter--")) break
            }
        } catch (e: Exception) {
            Log.w(TAG, "upload failed", e)
        }

        val msg = if (savedNames.isEmpty()) {
            "Nem érkezett fájl."
        } else {
            // FONTOS: a fájlt be kell jelenteni a MediaStore-nak, különben a
            // zenelejátszók (a SuperDL sajátja is) NEM LÁTJÁK – ott van a lemezen,
            // de az Android média-adatbázisa nem tud róla.
            scanIntoMediaStore(savedPaths, destination)
            // A telefon bemondja, hogy megérkezett – akkor is, ha nem a gépnél ül.
            onFilesUploaded?.invoke(savedNames, destinationName(destination))
            "Feltöltve ide: ${destinationName(destination)} – ${savedNames.joinToString(", ")}"
        }
        serveHtml(output, resultPage(msg, savedNames.isNotEmpty()))
    }

    /**
     * A frissen feltöltött fájlok bejelentése az Android média-adatbázisába.
     * Enélkül a zenelejátszó, a galéria stb. nem látja őket.
     *
     * A hang-mappáknál (csengőhang, értesítés, ébresztő) külön meg is jelöljük
     * a fájlt a megfelelő típussal – így a hangválasztókban azonnal megjelenik.
     */
    private fun scanIntoMediaStore(paths: List<String>, destination: String = "portal") {
        if (paths.isEmpty()) return
        try {
            android.media.MediaScannerConnection.scanFile(
                context,
                paths.toTypedArray(),
                null
            ) { path, uri ->
                Log.i(TAG, "MediaStore scanned: $path -> $uri")
                // A hangokat megjelöljük típus szerint, hogy a rendszer
                // csengőhang-választója felismerje őket.
                if (uri != null) markAudioKind(uri, destination)
            }
        } catch (e: Exception) {
            Log.w(TAG, "MediaStore scan failed", e)
        }
    }

    /**
     * A feltöltött hang megjelölése csengőhangként / értesítésként / ébresztőként.
     * Enélkül a fájl csak "zene" marad, és a hangválasztókban nem jelenik meg.
     */
    private fun markAudioKind(uri: android.net.Uri, destination: String) {
        val values = android.content.ContentValues()
        when (destination) {
            "ringtones" -> {
                values.put(android.provider.MediaStore.Audio.Media.IS_RINGTONE, true)
                values.put(android.provider.MediaStore.Audio.Media.IS_NOTIFICATION, false)
                values.put(android.provider.MediaStore.Audio.Media.IS_ALARM, false)
                values.put(android.provider.MediaStore.Audio.Media.IS_MUSIC, false)
            }
            "notifications" -> {
                values.put(android.provider.MediaStore.Audio.Media.IS_RINGTONE, false)
                values.put(android.provider.MediaStore.Audio.Media.IS_NOTIFICATION, true)
                values.put(android.provider.MediaStore.Audio.Media.IS_ALARM, false)
                values.put(android.provider.MediaStore.Audio.Media.IS_MUSIC, false)
            }
            "alarms" -> {
                values.put(android.provider.MediaStore.Audio.Media.IS_RINGTONE, false)
                values.put(android.provider.MediaStore.Audio.Media.IS_NOTIFICATION, false)
                values.put(android.provider.MediaStore.Audio.Media.IS_ALARM, true)
                values.put(android.provider.MediaStore.Audio.Media.IS_MUSIC, false)
            }
            else -> return  // a zene és a többi marad, ami
        }
        try {
            val updated = context.contentResolver.update(uri, values, null, null)
            Log.i(TAG, "markAudioKind($destination) updated=$updated for $uri")
        } catch (e: Exception) {
            // Android 10+ alatt előfordulhat, hogy nem engedi – nem végzetes,
            // a fájl akkor is ott van, csak a választóban nem jelenik meg.
            Log.w(TAG, "markAudioKind failed", e)
        }
    }

    /** A választott célmappa tényleges elérési útja. */
    private fun destinationDir(dest: String): File {
        val ext = android.os.Environment.getExternalStorageDirectory()
        val dir = when (dest) {
            "music" -> File(ext, android.os.Environment.DIRECTORY_MUSIC)
            "documents" -> File(ext, android.os.Environment.DIRECTORY_DOCUMENTS)
            "download" -> File(ext, android.os.Environment.DIRECTORY_DOWNLOADS)
            // Saját hangok: ezekbe töltve a rendszer hangválasztói is látják őket
            // (a MediaStore-bejelentés után).
            "ringtones" -> File(ext, android.os.Environment.DIRECTORY_RINGTONES)
            "notifications" -> File(ext, android.os.Environment.DIRECTORY_NOTIFICATIONS)
            "alarms" -> File(ext, android.os.Environment.DIRECTORY_ALARMS)
            else -> uploadDir()
        }
        if (!dir.exists()) dir.mkdirs()
        return dir
    }

    /** A célmappa magyar neve (a visszajelzéshez és a bemondáshoz). */
    private fun destinationName(dest: String): String = when (dest) {
        "music" -> "Zene mappa"
        "documents" -> "Dokumentumok"
        "download" -> "Letöltések"
        "ringtones" -> "Csengőhangok"
        "notifications" -> "Értesítési hangok"
        "alarms" -> "Ébresztő hangok"
        else -> "Portál mappa"
    }

    /**
     * Egy multipart rész kiírása fájlba, amíg el nem érjük a határolót.
     *
     * TELJESÍTMÉNY: nagy pufferrel olvasunk (64 KB), és a határolót a
     * pufferen belül keressük. A korábbi bájtonkénti olvasás egy 5 MB-os
     * fájlnál 5 millió rendszerhívást jelentett – ez volt a lassúság oka.
     */
    private fun writePartToFile(
        input: java.io.PushbackInputStream,
        target: File,
        delimiter: String,
        skip: Boolean = false
    ): Boolean {
        val delimBytes = "\r\n$delimiter".toByteArray()
        val bufferSize = 64 * 1024
        // Ha a fájl nem hozható létre (pl. az Android tiltja: desktop.ini,
        // Thumbs.db -> EPERM), vagy szándékosan kihagyjuk, NEM szakítjuk meg az
        // egész feltöltést! Korábban egyetlen ilyen fájl kilőtte a teljes
        // ciklust, a kapcsolat megszakadt, és a böngésző "nem sikerült a
        // kapcsolat" hibát mutatott a többi fájl közepén. Most a rész adatát
        // elnyeljük (hogy a feldolgozás ne csússzon el), és csak EZT az egy
        // fájlt hagyjuk ki.
        val out: java.io.BufferedOutputStream? = if (skip) {
            Log.i(TAG, "KIHAGYVA (rendszerfajl): ${target.name}")
            null
        } else try {
            java.io.BufferedOutputStream(target.outputStream(), bufferSize)
        } catch (e: Exception) {
            Log.w(TAG, "KIHAGYVA (nem hozhato letre): ${target.name} - ${e.message}")
            null
        }
        // A puffer végén meg kell tartanunk annyi bájtot, amennyi a határoló,
        // mert a határoló átnyúlhat két olvasás határán.
        val buffer = ByteArray(bufferSize + delimBytes.size)
        var pending = 0  // az előző körből átvitt bájtok száma
        // Csak akkor teljes a fájl, ha megtaláltuk a lezáró határolót. Ha a
        // kapcsolat idő előtt megszakad (nagy fájlnál gyakori), a rész CSONKA —
        // ilyenkor nem szabad sikeresnek jelenteni, és a féloldalas fájlt is
        // törölni kell, nehogy használhatatlan zeneként ott maradjon.
        var complete = false

        // NAPLÓZÁS: nagy feltöltéseknél elengedhetetlen, hogy utólag lássuk,
        // hány bájtnál és milyen hibával szakadt meg az átvitel.
        var totalWritten = 0L
        var nextLogAt = 16L * 1024 * 1024   // 16 MB-onként naplózunk
        val startMs = System.currentTimeMillis()
        Log.i(TAG, "FELTOLTES INDUL: ${target.name}")

        return try {
            while (true) {
                val read = input.read(buffer, pending, bufferSize)
                if (read <= 0) {
                    // A bemenet váratlanul véget ért: a rész csonka maradt.
                    if (pending > 0) {
                        out?.write(buffer, 0, pending)
                        totalWritten += pending
                    }
                    Log.w(
                        TAG,
                        "FELTOLTES VEGE IDO ELOTT (read=$read) ${target.name} " +
                            "irt=${totalWritten / 1024 / 1024} MB"
                    )
                    break
                }
                val available = pending + read
                val idx = indexOf(buffer, available, delimBytes)
                if (idx >= 0) {
                    // Megtaláltuk a határolót: eddig tart a fájl tartalma.
                    out?.write(buffer, 0, idx)
                    // A határoló ELŐTTI "\r\n"-t átugorjuk (idx + 2), és a
                    // maradékot VISSZATOLJUK az adatfolyamba, hogy a hívó a
                    // "--boundary" sornál folytathassa. Enélkül ezek a bájtok
                    // elvesznének, a feldolgozó elvesztené a szinkront, és a
                    // feltöltés beállna (majd újrapróbálkozáskor duplikálódna).
                    val leftoverFrom = idx + 2
                    val leftoverLen = available - leftoverFrom
                    if (leftoverLen > 0) {
                        input.unread(buffer, leftoverFrom, leftoverLen)
                    }
                    complete = true
                    totalWritten += idx
                    val sec = (System.currentTimeMillis() - startMs) / 1000.0
                    Log.i(
                        TAG,
                        "FELTOLTES KESZ: ${target.name} " +
                            "meret=${totalWritten / 1024 / 1024} MB ido=${"%.1f".format(sec)}s"
                    )
                    break
                }
                // Nincs határoló: kiírjuk, de a végéből megtartunk annyit,
                // amennyi a határoló lehetne (átnyúlás elleni védelem)
                val keep = (delimBytes.size - 1).coerceAtMost(available)
                val writeLen = available - keep
                if (writeLen > 0) {
                    out?.write(buffer, 0, writeLen)
                    totalWritten += writeLen
                    if (totalWritten >= nextLogAt) {
                        val sec = (System.currentTimeMillis() - startMs) / 1000.0
                        val mbps = if (sec > 0) (totalWritten / 1024.0 / 1024.0) / sec else 0.0
                        Log.i(
                            TAG,
                            "feltoltes halad: ${totalWritten / 1024 / 1024} MB " +
                                "(${"%.1f".format(mbps)} MB/s)"
                        )
                        nextLogAt += 16L * 1024 * 1024
                    }
                }
                System.arraycopy(buffer, writeLen, buffer, 0, keep)
                pending = keep
            }
            out?.flush()
            out?.close()
            if (out == null) {
                // Ez a fájl ki lett hagyva (nem hozható létre), de az adatát
                // elnyeltük, így a többi fájl feltöltése zavartalanul folytatódik.
                return false
            }
            if (!complete) {
                // Csonka rész: a féloldalas fájl törlése, és NEM sikeres.
                Log.w(TAG, "Csonka feltöltés, a részfájl törölve: ${target.name}")
                try {
                    target.delete()
                } catch (_: Exception) {
                }
            }
            complete
        } catch (e: Exception) {
            // A PONTOS hiba és a bájtszám — ebből derül ki, mi szakítja meg
            // a nagy feltöltéseket (időtúllépés, kapcsolat-bontás, tárhely stb.).
            val sec = (System.currentTimeMillis() - startMs) / 1000.0
            Log.w(
                TAG,
                "FELTOLTES MEGSZAKADT: ${target.name} " +
                    "irt=${totalWritten / 1024 / 1024} MB ido=${"%.1f".format(sec)}s " +
                    "hiba=${e.javaClass.simpleName}: ${e.message}",
                e
            )
            try {
                out?.close()
            } catch (_: Exception) {
            }
            // Megszakadt átvitel: a féloldalas fájl ne maradjon ott.
            try {
                target.delete()
            } catch (_: Exception) {
            }
            false
        }
    }

    /**
     * Windows/mac rendszer- és szemétfájlok, amik gyakran belekerülnek egy
     * mappa-kijelölésbe. Az Android egy részüket amúgy is tiltja (desktop.ini
     * -> EPERM), és korábban EGYETLEN ilyen fájl megszakította a teljes
     * feltöltést. Ezeket csendben kihagyjuk.
     */
    private fun isJunkFile(name: String): Boolean {
        val n = name.substringAfterLast('/').substringAfterLast('\\').lowercase()
        return n == "desktop.ini" ||
            n == "thumbs.db" ||
            n == ".ds_store" ||
            n == "folder.ini" ||
            n.endsWith(".lnk") ||
            n.startsWith("._")
    }

    /** A minta első előfordulása a pufferben (vagy -1). */
    private fun indexOf(buffer: ByteArray, length: Int, pattern: ByteArray): Int {
        if (pattern.isEmpty() || length < pattern.size) return -1
        outer@ for (i in 0..(length - pattern.size)) {
            for (j in pattern.indices) {
                if (buffer[i + j] != pattern[j]) continue@outer
            }
            return i
        }
        return -1
    }

    // ==================== Letöltés ====================

    /**
     * Média-fájl (fotó vagy hangfelvétel) kiszolgálása token alapján. A tokent a
     * PortalMediaHelper oldja fel biztonságosan (csak engedélyezett fájlok).
     */
    private fun serveMediaDownload(output: OutputStream, token: String) {
        val resolved = try {
            PortalMediaHelper.resolveToken(context, token)
        } catch (_: Exception) {
            null
        }
        if (resolved == null) {
            serveHtml(output, resultPage("A fájl nem található vagy nem tölthető le.", false), status = "404 Not Found")
            return
        }
        val (bytes, name, mime) = resolved
        val header = buildString {
            append("HTTP/1.1 200 OK\r\n")
            append("Content-Type: $mime\r\n")
            append("Content-Length: ${bytes.size}\r\n")
            append("Content-Disposition: attachment; filename=\"$name\"\r\n")
            append("Connection: close\r\n\r\n")
        }
        output.write(header.toByteArray())
        output.write(bytes)
        output.flush()
    }

    private fun serveDownload(output: OutputStream, encodedName: String) {
        val name = try {
            URLDecoder.decode(encodedName, "UTF-8")
        } catch (_: Exception) {
            encodedName
        }
        // A fájlt bármelyik célmappában keressük (a lista is mindet mutatja).
        val safeName = sanitize(name)
        val file = listOf(
            uploadDir(),
            destinationDir("music"),
            destinationDir("ringtones"),
            destinationDir("notifications"),
            destinationDir("alarms"),
            destinationDir("documents"),
            destinationDir("download")
        ).map { File(it, safeName) }
            .firstOrNull { it.exists() && it.isFile }

        if (file == null) {
            serveHtml(output, resultPage("A fájl nem található.", false), status = "404 Not Found")
            return
        }
        val header = buildString {
            append("HTTP/1.1 200 OK\r\n")
            append("Content-Type: application/octet-stream\r\n")
            append("Content-Length: ${file.length()}\r\n")
            append("Content-Disposition: attachment; filename=\"${file.name}\"\r\n")
            append("Connection: close\r\n\r\n")
        }
        output.write(header.toByteArray())
        // 64 KB-os puffer: nagy fájloknál számottevően gyorsabb.
        file.inputStream().buffered(64 * 1024).use { it.copyTo(output, 64 * 1024) }
    }

    // ==================== HTML ====================

    /**
     * Szöveg letöltése fájlként (mentés, vCard...).
     *
     * A Content-Disposition attachment miatt a böngésző letölti, nem megjeleníti.
     * A content-type paraméterezhető: JSON a beállítás-mentéshez, vCard a
     * névjegyekhez.
     */
    private fun serveTextDownload(
        output: java.io.OutputStream,
        text: String,
        filename: String,
        contentType: String = "application/octet-stream"
    ) {
        val bytes = text.toByteArray(Charsets.UTF_8)
        val header = buildString {
            append("HTTP/1.1 200 OK\r\n")
            append("Content-Type: $contentType; charset=UTF-8\r\n")
            append("Content-Disposition: attachment; filename=\"$filename\"\r\n")
            append("Content-Length: ${bytes.size}\r\n")
            append("Connection: close\r\n\r\n")
        }
        output.write(header.toByteArray())
        output.write(bytes)
    }


    private fun serveHtml(output: OutputStream, html: String, status: String = "200 OK") {
        val bytes = html.toByteArray(Charsets.UTF_8)
        val header = buildString {
            append("HTTP/1.1 $status\r\n")
            append("Content-Type: text/html; charset=UTF-8\r\n")
            append("Content-Length: ${bytes.size}\r\n")
            append("Connection: close\r\n\r\n")
        }
        output.write(header.toByteArray())
        output.write(bytes)
    }

    private fun buildIndexPage(): String {
        // Minden célmappa tartalmát mutatjuk, nem csak a Portálét – így látod
        // a Zene mappába töltött számokat is, és nem tűnik úgy, hogy semmi nem ment át.
        val allFiles = listOf(
            "Portál mappa" to uploadDir(),
            "Zene mappa" to destinationDir("music"),
            "Csengőhangok" to destinationDir("ringtones"),
            "Értesítési hangok" to destinationDir("notifications"),
            "Ébresztő hangok" to destinationDir("alarms"),
            "Dokumentumok" to destinationDir("documents"),
            "Letöltések" to destinationDir("download")
        ).mapNotNull { (label, dir) ->
            val files = try {
                dir.listFiles()
                    ?.filter { it.isFile }
                    ?.sortedByDescending { it.lastModified() }
                    ?.take(15)
                    ?: emptyList()
            } catch (_: Exception) {
                emptyList()
            }
            if (files.isEmpty()) null else label to files
        }

        val fileRows = if (allFiles.isEmpty()) {
            "<p class='empty'>Még nincs feltöltött fájl.</p>"
        } else {
            allFiles.joinToString("\n") { (label, files) ->
                val rows = files.joinToString("\n") { f ->
                    val size = Formatter.formatShortFileSize(context, f.length())
                    val enc = java.net.URLEncoder.encode(f.name, "UTF-8")
                    "<li><a href='/download/$enc'>${escapeHtml(f.name)}</a> <span>$size</span></li>"
                }
                "<h3>$label (${files.size})</h3><ul class='files'>$rows</ul>"
            }
        }

        return """
<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SuperDL fájlportál</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
         max-width: 720px; margin: 0 auto; padding: 24px;
         background: #0f1115; color: #e8eaed; line-height: 1.6; }
  h1 { font-size: 1.6rem; margin: 0 0 4px; }
  .sub { color: #9aa0a6; margin: 0 0 28px; font-size: 0.95rem; }
  .card { background: #1a1d23; border: 1px solid #2a2e37; border-radius: 12px;
          padding: 20px; margin-bottom: 20px; }
  h2 { font-size: 1.1rem; margin: 0 0 14px; color: #8ab4f8; }
  h3 { font-size: 0.95rem; margin: 18px 0 6px; color: #e8eaed; }
  h3:first-of-type { margin-top: 0; }
  input[type=file] { width: 100%; padding: 14px; background: #0f1115;
                     border: 2px dashed #3c4043; border-radius: 8px; color: #e8eaed;
                     margin-bottom: 14px; font-size: 1rem; }
  .lbl { display: block; margin-bottom: 6px; color: #9aa0a6; font-size: 0.9rem; }
  select { width: 100%; padding: 12px; background: #0f1115; border: 1px solid #3c4043;
           border-radius: 8px; color: #e8eaed; margin-bottom: 14px; font-size: 1rem; }
  button { background: #8ab4f8; color: #0f1115; border: 0; border-radius: 8px;
           padding: 13px 26px; font-size: 1rem; font-weight: 600; cursor: pointer; }
  button:hover { background: #a8c7fa; }
  ul.files { list-style: none; padding: 0; margin: 0; }
  ul.files li { display: flex; justify-content: space-between; align-items: center;
                padding: 11px 0; border-bottom: 1px solid #2a2e37; }
  ul.files li:last-child { border-bottom: 0; }
  ul.files a { color: #8ab4f8; text-decoration: none; word-break: break-all; }
  ul.files a:hover { text-decoration: underline; }
  ul.files span { color: #9aa0a6; font-size: 0.85rem; margin-left: 14px; white-space: nowrap; }
  .empty { color: #9aa0a6; margin: 0; }
  .hint { font-size: 0.85rem; color: #9aa0a6; margin-top: 10px; }
  .status { margin-top: 14px; padding: 14px; border-radius: 8px; font-size: 1rem;
            background: #0f1115; border: 1px solid #2a2e37; color: #8ab4f8;
            min-height: 24px; }
  .status:empty { display: none; }
  .mainnav { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }
  .tab { padding: 10px 16px; background: #1a1d23; border: 1px solid #3c4043;
         border-radius: 8px; color: #e8eaed; text-decoration: none; }
  .tab.active { background: #8ab4f8; color: #0f1115; font-weight: 600; }
  .tab:focus { outline: 3px solid #8ab4f8; outline-offset: 2px; }
</style>
</head>
<body>
  <h1>SuperDL fájlportál</h1>
  <p class="sub">A telefonod és a géped ugyanazon a WiFi-n. Ide feltöltött fájlok a telefon <strong>$UPLOAD_FOLDER</strong> mappájába kerülnek.</p>

  <nav aria-label="Fő navigáció" class="mainnav">
    <a href="/" aria-current="page" class="tab active">Fájlok</a>
    <a href="/sms" class="tab">SMS</a>
    <a href="/email" class="tab">E-mail</a>
    <a href="/contacts" class="tab">Névjegyek</a>
    <a href="/notes" class="tab">Jegyzetek</a>
    <a href="/alarms" class="tab">Ébresztők</a>
    <a href="/medication" class="tab">Patika Őrangyal</a>
    <a href="/calendar" class="tab">Naptár</a>
    <a href="/shopping" class="tab">Bevásárlólista</a>
    <a href="/places" class="tab">Emlékhelyek</a>
    <a href="/podcast" class="tab">Podcast</a>
    <a href="/media" class="tab">Fotók és hangok</a>
    <a href="/radio" class="tab">Rádió</a>
    <a href="/status" class="tab">Állapot</a>
    <a href="/setup" class="tab">Beállítás</a>
    <a href="/diagnostics" class="tab">Diagnosztika</a>
    <a href="/backup" class="tab">Mentés</a>
  </nav>

  <div class="card">
    <h2>Feltöltés a telefonra</h2>
    <form id="upform" method="POST" action="/upload" enctype="multipart/form-data">
      <label class="lbl" for="dest">Hova kerüljön?</label>
      <select name="dest" id="dest">
        <option value="portal">Portál mappa (alapértelmezett)</option>
        <option value="music">Zene mappa</option>
        <option value="documents">Dokumentumok</option>
        <option value="download">Letöltések</option>
        <option value="ringtones">Csengőhangok</option>
        <option value="notifications">Értesítési hangok</option>
        <option value="alarms">Ébresztő hangok</option>
      </select>
      <input type="file" name="file" id="fileinput" multiple required>
      <button type="submit" id="upbtn">Feltöltés</button>
    </form>
    <!-- Élő állapot: a képernyőolvasó minden változást felolvas.
         Vakon ez a legfontosabb rész – enélkül nem tudni, halad-e egyáltalán. -->
    <div id="status" role="status" aria-live="assertive" class="status"></div>
    <p class="hint">Több fájlt is kijelölhetsz egyszerre. A zenét a Zene mappába töltsd, hogy a SuperDL zenelejátszó azonnal megtalálja. A Csengőhangok, Értesítési hangok és Ébresztő hangok mappákba töltött fájlok megjelennek a telefon hangválasztóiban is.</p>
  </div>

  <script>
    (function () {
      var form = document.getElementById('upform');
      var status = document.getElementById('status');
      var btn = document.getElementById('upbtn');
      var fileInput = document.getElementById('fileinput');

      // A kiválasztott fájlokat azonnal visszamondjuk.
      fileInput.addEventListener('change', function () {
        var n = fileInput.files.length;
        if (n === 0) { status.textContent = ''; return; }
        var total = 0;
        for (var i = 0; i < n; i++) total += fileInput.files[i].size;
        status.textContent = n + ' fájl kiválasztva, összesen ' + human(total) +
          '. Nyomd meg a Feltöltés gombot.';
      });

      form.addEventListener('submit', function (e) {
        e.preventDefault();
        if (fileInput.files.length === 0) {
          status.textContent = 'Előbb válassz fájlt.';
          return;
        }
        var data = new FormData(form);
        var xhr = new XMLHttpRequest();
        var lastSpoken = -1;

        xhr.upload.addEventListener('progress', function (ev) {
          if (!ev.lengthComputable) return;
          var pct = Math.round((ev.loaded / ev.total) * 100);
          // Csak 10 százalékonként szólalunk meg, hogy ne darálja a felolvasó.
          var step = Math.floor(pct / 10);
          if (step !== lastSpoken) {
            lastSpoken = step;
            status.textContent = 'Feltöltés folyamatban: ' + pct + ' százalék. ' +
              human(ev.loaded) + ' a ' + human(ev.total) + '-ból.';
          }
        });

        xhr.addEventListener('load', function () {
          if (xhr.status >= 200 && xhr.status < 300) {
            status.textContent = 'Feltöltés kész. A telefon is bemondja. ' +
              'Az oldal frissül, hogy lásd a fájlokat.';
            setTimeout(function () { window.location.href = '/'; }, 2500);
          } else {
            status.textContent = 'Hiba a feltöltés során. Próbáld újra.';
            btn.disabled = false;
          }
        });

        xhr.addEventListener('error', function () {
          status.textContent = 'Nem sikerült a kapcsolat. Ellenőrizd, hogy a telefon ' +
            'ugyanazon a WiFi-n van-e, és fut-e még a portál.';
          btn.disabled = false;
        });

        xhr.addEventListener('abort', function () {
          status.textContent = 'A feltöltés megszakadt.';
          btn.disabled = false;
        });

        btn.disabled = true;
        status.textContent = 'Feltöltés indul. Egy pillanat.';
        xhr.open('POST', '/upload');
        xhr.send(data);
      });

      function human(bytes) {
        if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + ' gigabájt';
        if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' megabájt';
        if (bytes >= 1024) return Math.round(bytes / 1024) + ' kilobájt';
        return bytes + ' bájt';
      }
    })();
  </script>

  <div class="card">
    <h2>Fájlok a telefonon</h2>
    $fileRows
    <p class="hint">Kattints a névre a letöltéshez.</p>
  </div>
</body>
</html>
        """.trimIndent()
    }

    private fun resultPage(message: String, success: Boolean): String = """
<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SuperDL fájlportál</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 720px; margin: 0 auto;
         padding: 40px 24px; background: #0f1115; color: #e8eaed; text-align: center; }
  .msg { font-size: 1.2rem; padding: 24px; border-radius: 12px;
         background: ${if (success) "#1e3a29" else "#3a1e1e"};
         border: 1px solid ${if (success) "#34a853" else "#ea4335"}; }
  a { color: #8ab4f8; display: inline-block; margin-top: 20px;
      padding: 12px 24px; background: #1a1d23; border: 1px solid #3c4043;
      border-radius: 8px; text-decoration: none; font-weight: 600; }
</style>
</head>
<body>
  <!-- role=status: a képernyőolvasó magától felolvassa, amint megjelenik.
       Nincs automatikus visszaugrás – vakon az elszaladó oldalt nem lehet elolvasni. -->
  <h1>${if (success) "Kész" else "Hiba"}</h1>
  <div class="msg" role="status" aria-live="assertive">${escapeHtml(message)}</div>
  <p><a href="/">Vissza a portálra</a></p>
</body>
</html>
    """.trimIndent()

    // ==================== Segédek ====================

    private fun readLine(input: InputStream): String? {
        val sb = StringBuilder()
        while (true) {
            val b = input.read()
            if (b < 0) return if (sb.isEmpty()) null else sb.toString()
            if (b == '\n'.code) break
            if (b != '\r'.code) sb.append(b.toChar())
        }
        return sb.toString()
    }

    private fun sanitize(name: String): String =
        File(name).name.replace(Regex("[/\\\\:*?\"<>|]"), "_").take(150)

    private fun uniqueFile(dir: File, name: String): File {
        var f = File(dir, name)
        if (!f.exists()) return f
        val base = name.substringBeforeLast('.', name)
        val ext = name.substringAfterLast('.', "")
        var i = 2
        while (f.exists() && i < 1000) {
            f = File(dir, if (ext.isBlank()) "$base ($i)" else "$base ($i).$ext")
            i++
        }
        return f
    }

    private fun escapeHtml(s: String): String = s
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
}
