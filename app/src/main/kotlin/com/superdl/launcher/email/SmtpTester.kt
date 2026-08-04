package com.superdl.launcher.email

import android.util.Base64
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.charset.StandardCharsets
import javax.net.ssl.SSLSocket
import javax.net.ssl.SSLSocketFactory

/**
 * E-mail beállítás tesztelése: kapcsolódás + bejelentkezés, levélküldés NÉLKÜL.
 *
 * MIÉRT KELL KÜLÖN OSZTÁLY: a SmtpSender.send() elnyeli a kivételt és csak
 * annyit mond, hogy false. Beállításkor viszont pont az a kérdés, hogy MIÉRT
 * nem megy: rossz a jelszó? rossz a szerver neve? nincs internet? Enélkül a
 * felhasználó vakon próbálkozna. Ez az osztály beszédes, magyar hibaüzenetet
 * ad vissza.
 *
 * Nem küld levelet, csak a SMTP AUTH-ig megy el, illetve IMAP-nál a LOGIN-ig.
 */
object SmtpTester {

    private const val TIMEOUT_MS = 12_000

    data class Result(
        val ok: Boolean,
        val message: String
    )

    /** A küldő (SMTP) és a fogadó (IMAP) szerver együttes ellenőrzése. */
    fun testAll(config: SmtpConfig): Result {
        val smtp = testSmtp(config)
        if (!smtp.ok) return smtp
        val imap = testImap(config)
        return if (imap.ok) {
            Result(true, "A küldés és az olvasás is működik. ${smtp.message} ${imap.message}")
        } else {
            // A küldés megy, csak az olvasás nem: ez félsiker, nem teljes hiba.
            // Ki kell mondani mindkettőt, különben a felhasználó azt hinné,
            // semmi sem működik.
            Result(false, "A küldés működik, de a bejövő levelek olvasása nem: ${imap.message}")
        }
    }

    /** Csak a küldő szerver: kapcsolódás, TLS, bejelentkezés. */
    fun testSmtp(config: SmtpConfig): Result {
        if (!config.isValid()) {
            return Result(false, "Hiányos beállítás: a szerver, a felhasználónév, a jelszó és a feladó cím kötelező.")
        }
        return try {
            Socket().use { socket ->
                socket.connect(InetSocketAddress(config.host, config.port), TIMEOUT_MS)
                socket.soTimeout = TIMEOUT_MS
                var reader = BufferedReader(InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8))
                var writer = OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8)

                expect(reader, 220, "A szerver nem válaszolt rendesen a kapcsolódásra.")
                line(writer, "EHLO superdl.local")
                multiline(reader, 250, "A szerver nem fogadta el a köszönést.")

                if (config.useTls) {
                    line(writer, "STARTTLS")
                    expect(reader, 220, "A szerver nem támogatja a titkosított kapcsolatot ezen a porton. Próbáld ki a titkosítás nélküli beállítást, vagy másik portot.")
                    val factory = SSLSocketFactory.getDefault() as SSLSocketFactory
                    val tls = factory.createSocket(socket, config.host, config.port, true) as SSLSocket
                    tls.startHandshake()
                    reader = BufferedReader(InputStreamReader(tls.getInputStream(), StandardCharsets.UTF_8))
                    writer = OutputStreamWriter(tls.getOutputStream(), StandardCharsets.UTF_8)
                    line(writer, "EHLO superdl.local")
                    multiline(reader, 250, "A szerver a titkosítás után nem fogadta el a köszönést.")
                }

                line(writer, "AUTH LOGIN")
                expect(reader, 334, "A szerver nem kéri a bejelentkezést a megszokott módon.")
                line(writer, b64(config.username))
                expect(reader, 334, "A szerver nem fogadta el a felhasználónevet.")
                line(writer, b64(config.password))
                expect(reader, 235, "Hibás felhasználónév vagy jelszó. Gmail esetén alkalmazásjelszó kell, a rendes jelszó nem működik.")

                line(writer, "QUIT")
                Result(true, "Küldő szerver rendben: ${config.host}, port ${config.port}.")
            }
        } catch (e: SmtpTestException) {
            Result(false, e.message.orEmpty())
        } catch (e: java.net.UnknownHostException) {
            Result(false, "A szerver neve nem található: ${config.host}. Ellenőrizd, jól írtad-e be, és van-e internet.")
        } catch (e: java.net.SocketTimeoutException) {
            Result(false, "A szerver nem válaszol (időtúllépés): ${config.host}, port ${config.port}. Lehet, hogy rossz a port.")
        } catch (e: java.net.ConnectException) {
            Result(false, "Nem sikerült kapcsolódni: ${config.host}, port ${config.port}. Ellenőrizd a portot és az internetet.")
        } catch (e: Exception) {
            Result(false, "Nem sikerült a kapcsolat: ${e.message ?: "ismeretlen hiba"}.")
        }
    }

    /** Csak a fogadó szerver: SSL kapcsolódás és bejelentkezés. */
    fun testImap(config: SmtpConfig): Result {
        if (!config.isValid()) {
            return Result(false, "Hiányos beállítás.")
        }
        val host = config.resolvedImapHost()
        val port = config.resolvedImapPort()
        if (host.isBlank()) {
            return Result(false, "Nincs megadva a bejövő levelek szervere.")
        }
        return try {
            val factory = SSLSocketFactory.getDefault() as SSLSocketFactory
            val socket = factory.createSocket(host, port) as SSLSocket
            socket.soTimeout = TIMEOUT_MS
            socket.use {
                it.startHandshake()
                val reader = BufferedReader(InputStreamReader(it.inputStream, StandardCharsets.UTF_8))
                val writer = OutputStreamWriter(it.outputStream, StandardCharsets.UTF_8)

                val greeting = reader.readLine().orEmpty()
                if (!greeting.startsWith("* OK")) {
                    return Result(false, "A bejövő szerver nem válaszolt rendesen: $host.")
                }

                writer.write("a1 LOGIN ${quote(config.username)} ${quote(config.password)}\r\n")
                writer.flush()
                var response = reader.readLine().orEmpty()
                // A szerver küldhet több sort is; az "a1" címkéjűt keressük.
                var guard = 0
                while (!response.startsWith("a1 ") && guard < 50) {
                    response = reader.readLine().orEmpty()
                    guard++
                }
                if (!response.startsWith("a1 OK")) {
                    return Result(false, "A bejövő szerver elutasította a bejelentkezést. Ellenőrizd a felhasználónevet és a jelszót.")
                }

                writer.write("a2 LOGOUT\r\n")
                writer.flush()
                Result(true, "Bejövő szerver rendben: $host, port $port.")
            }
        } catch (e: java.net.UnknownHostException) {
            Result(false, "A bejövő szerver neve nem található: $host. Add meg kézzel a haladó beállításban.")
        } catch (e: java.net.SocketTimeoutException) {
            Result(false, "A bejövő szerver nem válaszol: $host, port $port.")
        } catch (e: Exception) {
            Result(false, "A bejövő szerver nem érhető el: ${e.message ?: "ismeretlen hiba"}.")
        }
    }

    private class SmtpTestException(message: String) : Exception(message)

    private fun b64(text: String): String =
        Base64.encodeToString(text.toByteArray(StandardCharsets.UTF_8), Base64.NO_WRAP)

    private fun quote(text: String): String =
        "\"" + text.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

    private fun line(writer: OutputStreamWriter, text: String) {
        writer.write(text + "\r\n")
        writer.flush()
    }

    private fun expect(reader: BufferedReader, code: Int, failMessage: String) {
        val line = reader.readLine() ?: throw SmtpTestException("A szerver megszakította a kapcsolatot.")
        val actual = line.take(3).toIntOrNull()
        if (actual != code) throw SmtpTestException(failMessage)
    }

    private fun multiline(reader: BufferedReader, code: Int, failMessage: String) {
        while (true) {
            val line = reader.readLine() ?: throw SmtpTestException("A szerver megszakította a kapcsolatot.")
            val actual = line.take(3).toIntOrNull()
            if (actual != code) throw SmtpTestException(failMessage)
            // "250-" folytatás, "250 " az utolsó sor.
            if (line.length < 4 || line[3] != '-') return
        }
    }
}
