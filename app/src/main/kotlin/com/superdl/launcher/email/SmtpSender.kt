package com.superdl.launcher.email

import android.util.Base64
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.charset.StandardCharsets
import javax.net.ssl.SSLSocketFactory

object SmtpSender {

    private const val MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024

    fun send(config: SmtpConfig, to: String, subject: String, body: String): Boolean =
        send(config, to, subject, body, attachment = null)

    fun send(
        config: SmtpConfig,
        to: String,
        subject: String,
        body: String,
        attachment: File?,
        attachmentMime: String = "application/octet-stream",
        attachmentName: String? = null
    ): Boolean {
        if (!config.isValid() || !EmailHelper.isValidEmail(to)) return false
        if (attachment != null && (!attachment.exists() || attachment.length() > MAX_ATTACHMENT_BYTES)) return false
        return try {
            if (config.useTls) sendWithStartTls(config, to, subject, body, attachment, attachmentMime, attachmentName)
            else sendPlain(config, to, subject, body, attachment, attachmentMime, attachmentName)
        } catch (_: Exception) {
            false
        }
    }

    private fun sendWithStartTls(
        config: SmtpConfig,
        to: String,
        subject: String,
        body: String,
        attachment: File?,
        attachmentMime: String,
        attachmentName: String?
    ): Boolean {
        Socket().use { socket ->
            socket.connect(InetSocketAddress(config.host, config.port), 12_000)
            val reader = BufferedReader(InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8))
            val writer = OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8)

            expect(reader, 220)
            writeLine(writer, "EHLO superdl.local")
            readMultiline(reader, 250)

            writeLine(writer, "STARTTLS")
            expect(reader, 220)

            val factory = SSLSocketFactory.getDefault() as SSLSocketFactory
            val tls = factory.createSocket(socket, config.host, config.port, true) as javax.net.ssl.SSLSocket
            tls.startHandshake()

            val tlsReader = BufferedReader(InputStreamReader(tls.getInputStream(), StandardCharsets.UTF_8))
            val tlsWriter = OutputStreamWriter(tls.getOutputStream(), StandardCharsets.UTF_8)

            writeLine(tlsWriter, "EHLO superdl.local")
            readMultiline(tlsReader, 250)
            authenticate(tlsReader, tlsWriter, config)
            transmit(tlsReader, tlsWriter, config, to, subject, body, attachment, attachmentMime, attachmentName)
            tls.close()
        }
        return true
    }

    private fun sendPlain(
        config: SmtpConfig,
        to: String,
        subject: String,
        body: String,
        attachment: File?,
        attachmentMime: String,
        attachmentName: String?
    ): Boolean {
        Socket().use { socket ->
            socket.connect(InetSocketAddress(config.host, config.port), 12_000)
            val reader = BufferedReader(InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8))
            val writer = OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8)
            expect(reader, 220)
            writeLine(writer, "EHLO superdl.local")
            readMultiline(reader, 250)
            authenticate(reader, writer, config)
            transmit(reader, writer, config, to, subject, body, attachment, attachmentMime, attachmentName)
        }
        return true
    }

    private fun authenticate(reader: BufferedReader, writer: OutputStreamWriter, config: SmtpConfig) {
        writeLine(writer, "AUTH LOGIN")
        expect(reader, 334)
        writeLine(writer, Base64.encodeToString(config.username.toByteArray(StandardCharsets.UTF_8), Base64.NO_WRAP))
        expect(reader, 334)
        writeLine(writer, Base64.encodeToString(config.password.toByteArray(StandardCharsets.UTF_8), Base64.NO_WRAP))
        expect(reader, 235)
    }

    private fun transmit(
        reader: BufferedReader,
        writer: OutputStreamWriter,
        config: SmtpConfig,
        to: String,
        subject: String,
        body: String,
        attachment: File?,
        attachmentMime: String,
        attachmentName: String?
    ) {
        val from = config.fromEmail
        writeLine(writer, "MAIL FROM:<$from>")
        expect(reader, 250)
        writeLine(writer, "RCPT TO:<$to>")
        expect(reader, 250)
        writeLine(writer, "DATA")
        expect(reader, 354)

        val fromHeader = if (config.fromName.isNotBlank()) {
            "${config.fromName} <$from>"
        } else {
            from
        }
        val message = if (attachment == null) {
            buildPlainMessage(fromHeader, to, subject, body)
        } else {
            buildMultipartMessage(fromHeader, to, subject, body, attachment, attachmentMime, attachmentName)
        }
        writer.write(message)
        writer.flush()
        expect(reader, 250)
        writeLine(writer, "QUIT")
        readCode(reader)
    }

    private fun buildPlainMessage(fromHeader: String, to: String, subject: String, body: String): String =
        buildString {
            append("From: $fromHeader\r\n")
            append("To: <$to>\r\n")
            append("Subject: ${encodeSubject(subject)}\r\n")
            append("MIME-Version: 1.0\r\n")
            append("Content-Type: text/plain; charset=UTF-8\r\n")
            append("Content-Transfer-Encoding: 8bit\r\n")
            append("\r\n")
            append(body)
            append("\r\n.\r\n")
        }

    private fun buildMultipartMessage(
        fromHeader: String,
        to: String,
        subject: String,
        body: String,
        attachment: File,
        attachmentMime: String,
        attachmentName: String?
    ): String {
        val boundary = "superdl_${System.currentTimeMillis()}"
        val fileName = attachmentName ?: attachment.name
        val encoded = Base64.encodeToString(attachment.readBytes(), Base64.NO_WRAP)
        val wrapped = encoded.chunked(76).joinToString("\r\n")
        return buildString {
            append("From: $fromHeader\r\n")
            append("To: <$to>\r\n")
            append("Subject: ${encodeSubject(subject)}\r\n")
            append("MIME-Version: 1.0\r\n")
            append("Content-Type: multipart/mixed; boundary=\"$boundary\"\r\n")
            append("\r\n")
            append("--$boundary\r\n")
            append("Content-Type: text/plain; charset=UTF-8\r\n")
            append("Content-Transfer-Encoding: 8bit\r\n")
            append("\r\n")
            append(body)
            append("\r\n")
            append("--$boundary\r\n")
            append("Content-Type: $attachmentMime; name=\"$fileName\"\r\n")
            append("Content-Transfer-Encoding: base64\r\n")
            append("Content-Disposition: attachment; filename=\"$fileName\"\r\n")
            append("\r\n")
            append(wrapped)
            append("\r\n")
            append("--$boundary--\r\n")
            append(".\r\n")
        }
    }

    private fun encodeSubject(subject: String): String {
        if (subject.all { it.code < 128 }) return subject
        val encoded = Base64.encodeToString(subject.toByteArray(StandardCharsets.UTF_8), Base64.NO_WRAP)
        return "=?UTF-8?B?$encoded?="
    }

    private fun writeLine(writer: OutputStreamWriter, line: String) {
        writer.write("$line\r\n")
        writer.flush()
    }

    private fun expect(reader: BufferedReader, code: Int) {
        val response = readCode(reader)
        if (response != code) throw IllegalStateException("SMTP expected $code got $response")
    }

    private fun readMultiline(reader: BufferedReader, code: Int) {
        var line = reader.readLine() ?: throw IllegalStateException("SMTP connection closed")
        while (line.length >= 4 && line[3] == '-') {
            line = reader.readLine() ?: throw IllegalStateException("SMTP connection closed")
        }
        val response = line.take(3).toIntOrNull() ?: -1
        if (response != code) throw IllegalStateException("SMTP expected $code got $response")
    }

    private fun readCode(reader: BufferedReader): Int =
        reader.readLine()?.take(3)?.toIntOrNull() ?: -1
}