package com.superdl.launcher.email

import android.util.Base64
import com.superdl.launcher.search.ArticleTextExtractor
import java.nio.charset.Charset

/**
 * Nyers levéltörzsből OLVASHATÓ SZÖVEGET készít.
 *
 * Egy e-mail belül ritkán sima szöveg: általában több részből áll (MIME
 * multipart), a részek külön fejléccel, és a szöveg kódolva van —
 * quoted-printable ("=C3=A9") vagy base64. Ha ezt nyersen olvassuk fel, a
 * felhasználó a fejléceket, határolókat és a kódolt szemetet hallja.
 *
 * Ez az osztály:
 *   1. szétbontja a levelet részekre (boundary alapján),
 *   2. kiválasztja a legjobb részt (sima szöveg > HTML),
 *   3. dekódolja a kódolást (quoted-printable / base64) a megadott karakterkészlettel,
 *   4. HTML esetén kinyeri a szöveget,
 *   5. eltakarítja a maradék technikai sorokat.
 */
object EmailBodyExtractor {

    /**
     * A NYERS levél FEJLÉC-része: a legelejétől az első üres sorig.
     * (Itt található a From, Subject, Date.)
     */
    fun headerPartOf(raw: String): String {
        val idx = indexOfBlankLine(raw)
        return if (idx > 0) raw.substring(0, idx) else raw
    }

    /** A NYERS levél TÖRZS-része: az első üres sor után minden. */
    fun bodyPartOf(raw: String): String {
        val idx = indexOfBlankLine(raw)
        return if (idx > 0) raw.substring(idx).trim() else ""
    }

    /** A felolvasható szöveg előállítása a nyers levéltörzsből. */
    fun extract(raw: String): String {
        if (raw.isBlank()) return ""
        val best = pickBestPart(raw)
        val decoded = decodePart(best)
        val plain = if (looksLikeHtml(decoded)) {
            try {
                ArticleTextExtractor.extractPlainText(decoded)
            } catch (_: Exception) {
                stripHtmlTags(decoded)
            }
        } else {
            decoded
        }
        return tidy(plain)
    }

    /**
     * FEJLÉC-MEZŐK olvashatóvá tétele (tárgy, feladó neve).
     *
     * Az ékezetes fejléceket a levelezők kódolva küldik, például:
     *   =?UTF-8?B?SsOzIG5hcG90IQ==?=      (base64)
     *   =?ISO-8859-2?Q?Sz=E9p_nap?=       (quoted-printable)
     * Enélkül a felolvasás ezt a kódolt formát darálná.
     */
    fun decodeHeaderText(raw: String): String {
        if (raw.isBlank()) return raw
        val pattern = Regex("=\\?([^?]+)\\?([BbQq])\\?([^?]*)\\?=")
        var result = pattern.replace(raw) { m ->
            val charset = try {
                Charset.forName(m.groupValues[1].trim())
            } catch (_: Exception) {
                Charsets.UTF_8
            }
            val kind = m.groupValues[2].uppercase()
            val payload = m.groupValues[3]
            try {
                if (kind == "B") {
                    String(Base64.decode(payload, Base64.DEFAULT), charset)
                } else {
                    // A Q változatban az aláhúzás szóközt jelent.
                    decodeQuotedPrintable(payload.replace('_', ' '), charset)
                }
            } catch (_: Exception) {
                payload
            }
        }
        // A kódolt darabok közti tördelést a szabvány szerint el kell hagyni.
        result = result.replace(Regex("\\?=\\s+=\\?"), "")
        return result.replace(Regex("\\s+"), " ").trim()
    }

    // ── 1-2. Részekre bontás és a legjobb rész kiválasztása ─────────────────

    private data class MimePart(val headers: String, val content: String)

    /**
     * A sima szöveges részt részesítjük előnyben; ha nincs, a HTML-t. Ha a levél
     * nem többrészes, az egészet adjuk vissza.
     */
    private fun pickBestPart(raw: String): MimePart {
        val boundary = findBoundary(raw)
            ?: return MimePart(headerBlockOf(raw), bodyBlockOf(raw))

        val parts = raw.split("--$boundary")
            .map { it.trim() }
            .filter { it.isNotBlank() && it != "--" }
            .map { MimePart(headerBlockOf(it), bodyBlockOf(it)) }

        if (parts.isEmpty()) return MimePart(headerBlockOf(raw), bodyBlockOf(raw))

        // Beágyazott többrészes rész (pl. multipart/alternative a multipart/mixed-ben)
        parts.firstOrNull { it.headers.contains("multipart/", true) }?.let { nested ->
            val inner = pickBestPart(nested.content)
            if (inner.content.isNotBlank()) return inner
        }

        parts.firstOrNull {
            it.headers.contains("text/plain", true) && !isAttachment(it.headers)
        }?.let { return it }

        parts.firstOrNull {
            it.headers.contains("text/html", true) && !isAttachment(it.headers)
        }?.let { return it }

        return parts.first()
    }

    private fun isAttachment(headers: String): Boolean =
        headers.contains("Content-Disposition: attachment", true)

    private fun findBoundary(raw: String): String? =
        Regex("boundary\\s*=\\s*\"?([^\";\\r\\n]+)\"?", RegexOption.IGNORE_CASE)
            .find(raw)?.groupValues?.getOrNull(1)?.trim()

    /** A rész fejléc-blokkja: az első üres sorig tart. */
    private fun headerBlockOf(part: String): String {
        val idx = indexOfBlankLine(part)
        return if (idx > 0) part.substring(0, idx) else ""
    }

    /** A rész tartalma: az első üres sor után kezdődik. */
    private fun bodyBlockOf(part: String): String {
        val idx = indexOfBlankLine(part)
        return if (idx > 0) part.substring(idx).trim() else part
    }

    private fun indexOfBlankLine(text: String): Int {
        val i1 = text.indexOf("\r\n\r\n")
        if (i1 >= 0) return i1 + 4
        val i2 = text.indexOf("\n\n")
        if (i2 >= 0) return i2 + 2
        return -1
    }

    // ── 3. Kódolás feloldása ────────────────────────────────────────────────

    private fun decodePart(part: MimePart): String {
        val encoding = Regex("Content-Transfer-Encoding\\s*:\\s*([^\\r\\n;]+)", RegexOption.IGNORE_CASE)
            .find(part.headers)?.groupValues?.getOrNull(1)?.trim()?.lowercase().orEmpty()
        val charset = resolveCharset(part.headers)

        return when {
            encoding.contains("base64") -> decodeBase64(part.content, charset)
            encoding.contains("quoted-printable") -> decodeQuotedPrintable(part.content, charset)
            else -> part.content
        }
    }

    private fun resolveCharset(headers: String): Charset {
        val name = Regex("charset\\s*=\\s*\"?([^\";\\r\\n]+)\"?", RegexOption.IGNORE_CASE)
            .find(headers)?.groupValues?.getOrNull(1)?.trim()
        return try {
            if (name.isNullOrBlank()) Charsets.UTF_8 else Charset.forName(name)
        } catch (_: Exception) {
            Charsets.UTF_8
        }
    }

    private fun decodeBase64(content: String, charset: Charset): String = try {
        val cleaned = content.replace(Regex("\\s"), "")
        String(Base64.decode(cleaned, Base64.DEFAULT), charset)
    } catch (_: Exception) {
        content
    }

    /**
     * quoted-printable: a "=C3=A9" hármasok bájtok, a sorvégi "=" pedig csak
     * tördelés (soft line break), nem karakter.
     */
    private fun decodeQuotedPrintable(content: String, charset: Charset): String = try {
        val joined = content.replace(Regex("=\\r?\\n"), "")
        val out = java.io.ByteArrayOutputStream()
        var i = 0
        while (i < joined.length) {
            val c = joined[i]
            if (c == '=' && i + 2 < joined.length) {
                val hex = joined.substring(i + 1, i + 3)
                val value = hex.toIntOrNull(16)
                if (value != null) {
                    out.write(value)
                    i += 3
                    continue
                }
            }
            out.write(c.code)
            i++
        }
        String(out.toByteArray(), charset)
    } catch (_: Exception) {
        content
    }

    // ── 4-5. HTML és takarítás ──────────────────────────────────────────────

    private fun looksLikeHtml(text: String): Boolean {
        val head = text.take(1500).lowercase()
        return head.contains("<html") || head.contains("<body") ||
            head.contains("<div") || head.contains("<table") || head.contains("<br")
    }

    private fun stripHtmlTags(html: String): String =
        html.replace(Regex("(?is)<(script|style)[^>]*>.*?</\\1>"), " ")
            .replace(Regex("(?i)<br\\s*/?>"), "\n")
            .replace(Regex("(?i)</p>"), "\n")
            .replace(Regex("<[^>]+>"), " ")
            .let { unescapeHtmlEntities(it) }

    private fun unescapeHtmlEntities(text: String): String =
        text.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", "\"")
            .replace("&#39;", "'")
            .replace(Regex("&#(\\d+);")) { m ->
                m.groupValues[1].toIntOrNull()?.toChar()?.toString() ?: " "
            }

    /**
     * Az utolsó simítás: kiszedi a maradék technikai sorokat (fejléc-maradványok,
     * határolók, hosszú kódolt blokkok), és összevonja a fölös szóközöket.
     */
    private fun tidy(text: String): String {
        var out = text
        // Fejléc-maradványok és határolók sorai
        out = out.replace(
            Regex(
                "(?im)^(content-(type|transfer-encoding|disposition|id)|mime-version|" +
                    "x-[a-z-]+|boundary|charset)\\s*:.*$"
            ),
            " "
        )
        out = out.replace(Regex("(?m)^--[A-Za-z0-9'()+_,./:=?-]{8,}--?\\s*$"), " ")
        // Nagyon hosszú, szóköz nélküli blokkok (dekódolatlan melléklet-maradék)
        out = out.replace(Regex("\\S{200,}"), " ")
        // Idézőjelek elé kerülő idézett előzmény jelölése maradhat, de a
        // többszörös üres sorokat és szóközöket összevonjuk.
        out = out.replace(Regex("[ \\t]+"), " ")
            .replace(Regex("(\\r?\\n\\s*){3,}"), "\n\n")
        return out.trim()
    }
}
