package com.superdl.launcher.email

import android.content.Context
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.io.OutputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import javax.net.ssl.SSLSocket
import javax.net.ssl.SSLSocketFactory

/**
 * E-mail (IMAP) kapcsolat LÉPÉSENKÉNTI naplózása hibakereséshez.
 *
 * A rendes olvasás csak annyit mond, hogy "nem sikerült" — ez viszont
 * végigmegy a kapcsolódás összes lépésén, MÉRI az időt, és fájlba írja, hogy
 * pontosan hol akad el:
 *   1. beállítások ellenőrzése   2. névfeloldás (DNS)   3. TCP kapcsolat
 *   4. titkosított kézfogás      5. szerver köszönése   6. bejelentkezés
 *   7. postafiók megnyitása      8. levelek számlálása
 *
 * ADATVÉDELEM: a napló SOHA nem tartalmazza a jelszót, és a levelek tartalmát
 * sem — csak a lépések eredményét és a darabszámot.
 *
 * A fájl helye (ADB-vel olvasható):
 *   /sdcard/Android/data/<csomag>/files/email_diagnosztika.txt
 */
object EmailDiagnostics {

    private const val FILE_NAME = "email_diagnosztika.txt"
    private const val CONNECT_TIMEOUT_MS = 15_000
    private const val READ_TIMEOUT_MS = 20_000

    data class Result(
        val success: Boolean,
        /** Rövid, kimondható összefoglaló a felhasználónak. */
        val spokenSummary: String,
        val filePath: String
    )

    fun diagnosticsFile(context: Context): File =
        File(context.getExternalFilesDir(null), FILE_NAME)

    /**
     * Végigfut a kapcsolódás lépésein és fájlba írja az eredményt.
     * HÁTTÉRSZÁLRÓL hívandó (hálózati művelet).
     */
    fun run(context: Context): Result {
        val log = StringBuilder()
        val stamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale("hu")).format(Date())
        log.appendLine("SUPERDL — E-MAIL KAPCSOLAT DIAGNOSZTIKA")
        log.appendLine("Időpont: $stamp")
        log.appendLine("=".repeat(60))

        var socket: Socket? = null
        var spoken: String
        var ok = false

        try {
            // 1. BEÁLLÍTÁSOK
            val config = SmtpConfigStore.get(context)
            if (config == null || !config.isValid()) {
                log.appendLine("1. BEÁLLÍTÁS: HIÁNYZIK vagy hiányos.")
                log.appendLine("   -> Előbb állítsd be az e-mail fiókot.")
                spoken = "Nincs beállítva e-mail fiók, vagy hiányos a beállítás."
                return finish(context, log, spoken, false)
            }
            val host = config.resolvedImapHost()
            val port = config.resolvedImapPort()
            log.appendLine("1. BEÁLLÍTÁS: rendben.")
            log.appendLine("   IMAP kiszolgáló: $host")
            log.appendLine("   Port: $port")
            log.appendLine("   Felhasználónév hossza: ${config.username.length} karakter")
            log.appendLine("   Jelszó hossza: ${config.password.length} karakter (a jelszót NEM naplózzuk)")
            if (config.password.contains(" ")) {
                log.appendLine("   FIGYELEM: a jelszó SZÓKÖZT tartalmaz. A Gmail alkalmazás-jelszót")
                log.appendLine("   szóközök NÉLKÜL, egybeírva kell megadni!")
            }

            // 2. NÉVFELOLDÁS
            var t = System.currentTimeMillis()
            val address = try {
                InetAddress.getByName(host)
            } catch (e: Exception) {
                log.appendLine("2. NÉVFELOLDÁS: SIKERTELEN (${e.javaClass.simpleName}: ${e.message})")
                log.appendLine("   -> Nincs internet, vagy hibás a kiszolgáló neve.")
                spoken = "A kiszolgáló nem található. Ellenőrizd az internetkapcsolatot és a kiszolgáló nevét."
                return finish(context, log, spoken, false)
            }
            log.appendLine("2. NÉVFELOLDÁS: rendben (${System.currentTimeMillis() - t} ms) -> ${address.hostAddress}")

            // 3. TCP KAPCSOLAT
            t = System.currentTimeMillis()
            socket = try {
                Socket().apply {
                    soTimeout = READ_TIMEOUT_MS
                    connect(InetSocketAddress(address, port), CONNECT_TIMEOUT_MS)
                }
            } catch (e: Exception) {
                log.appendLine("3. KAPCSOLAT: SIKERTELEN (${e.javaClass.simpleName}: ${e.message})")
                log.appendLine("   -> A port zárva lehet, vagy a hálózat blokkolja.")
                spoken = "Nem sikerült kapcsolódni a kiszolgálóhoz. Lehet, hogy a hálózat blokkolja."
                return finish(context, log, spoken, false)
            }
            log.appendLine("3. KAPCSOLAT: rendben (${System.currentTimeMillis() - t} ms)")

            // 4. TITKOSÍTOTT KÉZFOGÁS
            t = System.currentTimeMillis()
            val ssl = try {
                (SSLSocketFactory.getDefault() as SSLSocketFactory)
                    .createSocket(socket, host, port, true) as SSLSocket
            } catch (e: Exception) {
                log.appendLine("4. TITKOSÍTÁS: SIKERTELEN (${e.javaClass.simpleName}: ${e.message})")
                spoken = "A titkosított kapcsolat nem jött létre."
                return finish(context, log, spoken, false)
            }
            try {
                ssl.startHandshake()
            } catch (e: Exception) {
                log.appendLine("4. TITKOSÍTÁS: kézfogás SIKERTELEN (${e.message})")
                spoken = "A titkosított kapcsolat nem jött létre."
                return finish(context, log, spoken, false)
            }
            log.appendLine("4. TITKOSÍTÁS: rendben (${System.currentTimeMillis() - t} ms)")
            socket = ssl

            val reader = BufferedReader(InputStreamReader(ssl.inputStream, Charsets.UTF_8))
            val writer: OutputStream = ssl.outputStream

            // 5. SZERVER KÖSZÖNÉSE
            t = System.currentTimeMillis()
            val greeting = try {
                reader.readLine()
            } catch (e: Exception) {
                log.appendLine("5. KÖSZÖNÉS: NEM ÉRKEZETT (${e.javaClass.simpleName}: ${e.message})")
                log.appendLine("   -> A szerver nem válaszol. EZ A TIPIKUS 'VÁRAKOZIK, MAJD VISSZALÉP' OK.")
                spoken = "A kiszolgáló nem válaszolt időben."
                return finish(context, log, spoken, false)
            }
            log.appendLine("5. KÖSZÖNÉS: ${greeting?.take(60)} (${System.currentTimeMillis() - t} ms)")

            // 6. BEJELENTKEZÉS
            t = System.currentTimeMillis()
            writer.write("A1 LOGIN \"${config.username}\" \"${config.password}\"\r\n".toByteArray())
            writer.flush()
            var loginOk = false
            var loginLine: String? = null
            while (true) {
                val line = try {
                    reader.readLine()
                } catch (e: Exception) {
                    log.appendLine("6. BEJELENTKEZÉS: időtúllépés (${e.message})")
                    break
                } ?: break
                if (line.startsWith("A1")) {
                    loginLine = line
                    loginOk = line.contains("OK")
                    break
                }
            }
            if (!loginOk) {
                log.appendLine("6. BEJELENTKEZÉS: SIKERTELEN (${System.currentTimeMillis() - t} ms)")
                log.appendLine("   Válasz: ${loginLine?.take(120)}")
                log.appendLine("   -> Hibás felhasználónév vagy alkalmazás-jelszó, VAGY az IMAP")
                log.appendLine("      nincs engedélyezve a fiókban.")
                spoken = "A bejelentkezés nem sikerült. Ellenőrizd a felhasználónevet és az alkalmazás jelszót."
                return finish(context, log, spoken, false)
            }
            log.appendLine("6. BEJELENTKEZÉS: rendben (${System.currentTimeMillis() - t} ms)")

            // 7. POSTAFIÓK MEGNYITÁSA
            t = System.currentTimeMillis()
            writer.write("A2 SELECT INBOX\r\n".toByteArray())
            writer.flush()
            var selectOk = false
            var messageCount = -1
            while (true) {
                val line = try {
                    reader.readLine()
                } catch (e: Exception) {
                    log.appendLine("7. POSTAFIÓK: időtúllépés (${e.message})")
                    break
                } ?: break
                if (line.contains("EXISTS")) {
                    messageCount = line.trim().split(" ").getOrNull(1)?.toIntOrNull() ?: -1
                }
                if (line.startsWith("A2")) {
                    selectOk = line.contains("OK")
                    break
                }
            }
            if (!selectOk) {
                log.appendLine("7. POSTAFIÓK: NEM NYITHATÓ MEG (${System.currentTimeMillis() - t} ms)")
                spoken = "A postafiók nem nyitható meg."
                return finish(context, log, spoken, false)
            }
            log.appendLine("7. POSTAFIÓK: rendben (${System.currentTimeMillis() - t} ms)")
            log.appendLine("   Levelek száma a beérkezőben: $messageCount")

            // 8. ÖSSZEGZÉS
            writer.write("A3 LOGOUT\r\n".toByteArray())
            writer.flush()
            log.appendLine("=".repeat(60))
            log.appendLine("EREDMÉNY: A KAPCSOLAT TELJESEN MŰKÖDIK.")
            log.appendLine("Ha a levelek mégsem listázódnak, a hiba a levél-letöltésben van,")
            log.appendLine("nem a kapcsolatban.")
            ok = true
            spoken = if (messageCount >= 0) {
                "A kapcsolat működik. $messageCount levél van a postafiókban."
            } else {
                "A kapcsolat működik."
            }
        } catch (e: Exception) {
            log.appendLine("VÁRATLAN HIBA: ${e.javaClass.simpleName}: ${e.message}")
            spoken = "Váratlan hiba történt a vizsgálat közben."
        } finally {
            try {
                socket?.close()
            } catch (_: Exception) {
            }
        }
        return finish(context, log, spoken, ok)
    }

    private fun finish(context: Context, log: StringBuilder, spoken: String, ok: Boolean): Result {
        val file = diagnosticsFile(context)
        try {
            file.parentFile?.mkdirs()
            file.writeText(log.toString(), Charsets.UTF_8)
        } catch (_: Exception) {
        }
        return Result(ok, spoken, file.absolutePath)
    }
}
