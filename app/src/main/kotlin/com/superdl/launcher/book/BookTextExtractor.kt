package com.superdl.launcher.book

import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.text.PDFTextStripper
import org.xmlpull.v1.XmlPullParser
import org.xmlpull.v1.XmlPullParserFactory
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.nio.charset.Charset
import java.util.zip.Inflater
import java.util.zip.ZipFile

object BookTextExtractor {

    const val MAX_BOOK_FILE_BYTES = 26_214_400L
    const val MAX_BOOK_FILE_MB = 25

    val SUPPORTED_EXTENSIONS = setOf(
        "txt", "md", "rtf", "html", "htm",
        "epub", "fb2",
        "pdf",
        "doc", "docx", "odt",
        "mobi", "azw", "azw3", "prc"
    )

    fun isSupported(file: File): Boolean =
        file.isFile && file.extension.lowercase() in SUPPORTED_EXTENSIONS

    fun extract(context: android.content.Context, file: File): Result<ExtractedBook> = runCatching {
        if (!isSupported(file)) {
            error("Nem támogatott formátum: .${file.extension}")
        }
        if (file.length() > MAX_BOOK_FILE_BYTES) {
            error("A könyv túl nagy. Maximum $MAX_BOOK_FILE_MB megabájt tölthető be.")
        }
        when (file.extension.lowercase()) {
            "txt", "md" -> fromPlainText(file)
            "html", "htm" -> fromHtml(file)
            "rtf" -> fromRtf(file)
            "epub" -> fromEpub(file)
            "fb2" -> fromFb2(file)
            "pdf" -> fromPdf(context, file)
            "docx" -> fromDocx(file)
            "odt" -> fromOdt(file)
            "doc" -> fromLegacyDoc(file)
            "mobi", "azw", "azw3", "prc" -> fromMobi(file)
            else -> error("Nem támogatott formátum.")
        }
    }

    data class ExtractedBook(
        val title: String,
        val text: String
    )

    private fun fromPlainText(file: File): ExtractedBook {
        val raw = readTextAutoCharset(file)
        return ExtractedBook(file.nameWithoutExtension, clean(raw))
    }

    private fun fromHtml(file: File): ExtractedBook {
        val raw = readTextAutoCharset(file)
        return ExtractedBook(file.nameWithoutExtension, clean(stripHtml(raw)))
    }

    private fun fromRtf(file: File): ExtractedBook {
        val raw = readTextAutoCharset(file)
        val plain = raw
            .replace(Regex("\\\\par[d]?"), "\n")
            .replace(Regex("\\\\'[0-9a-fA-F]{2}"), " ")
            .replace(Regex("\\\\[a-z]+-?\\d* ?"), "")
            .replace(Regex("[{}]"), "")
        return ExtractedBook(file.nameWithoutExtension, clean(plain))
    }

    private fun fromEpub(file: File): ExtractedBook {
        ZipFile(file).use { zip ->
            val container = zip.getEntry("META-INF/container.xml")
                ?: error("Érvénytelen EPUB: hiányzik a container.xml.")
            val containerXml = zip.getInputStream(container).bufferedReader().readText()
            val opfPath = Regex("""full-path="([^"]+\.opf)"""", RegexOption.IGNORE_CASE)
                .find(containerXml)?.groupValues?.get(1)
                ?: error("Érvénytelen EPUB: nem található OPF fájl.")
            val opfEntry = zip.getEntry(opfPath) ?: error("Érvénytelen EPUB: OPF nem olvasható.")
            val opfXml = zip.getInputStream(opfEntry).bufferedReader().readText()
            val opfDir = opfPath.substringBeforeLast('/', "")

            val title = Regex("""<dc:title[^>]*>([^<]+)</dc:title>""", RegexOption.IGNORE_CASE)
                .find(opfXml)?.groupValues?.get(1)?.trim()
                ?: file.nameWithoutExtension

            val idToHref = mutableMapOf<String, String>()
            Regex("""<item[^>]+id="([^"]+)"[^>]+href="([^"]+)"""", RegexOption.IGNORE_CASE)
                .findAll(opfXml)
                .forEach { m ->
                    idToHref[m.groupValues[1]] = m.groupValues[2]
                }

            val spineIds = Regex("""<itemref[^>]+idref="([^"]+)"""", RegexOption.IGNORE_CASE)
                .findAll(opfXml)
                .map { it.groupValues[1] }
                .toList()

            val parts = mutableListOf<String>()
            for (id in spineIds) {
                val href = idToHref[id] ?: continue
                val entryPath = if (opfDir.isNotEmpty()) "$opfDir/$href" else href
                val entry = zip.getEntry(entryPath) ?: zip.getEntry(href) ?: continue
                val html = zip.getInputStream(entry).bufferedReader().readText()
                val text = clean(stripHtml(html))
                if (text.isNotBlank()) parts.add(text)
            }
            if (parts.isEmpty()) error("Az EPUB nem tartalmaz olvasható szöveget.")
            return ExtractedBook(title, parts.joinToString("\n\n"))
        }
    }

    private fun fromFb2(file: File): ExtractedBook {
        val xml = readTextAutoCharset(file)
        val title = Regex("""<book-title[^>]*>([^<]+)</book-title>""", RegexOption.IGNORE_CASE)
            .find(xml)?.groupValues?.get(1)?.trim()
            ?: file.nameWithoutExtension
        val body = Regex("""<body[^>]*>([\s\S]*?)</body>""", RegexOption.IGNORE_CASE)
            .find(xml)?.groupValues?.get(1)
            ?: xml
        return ExtractedBook(title, clean(stripHtml(body)))
    }

    private fun fromPdf(context: android.content.Context, file: File): ExtractedBook {
        PDFBoxResourceLoader.init(context.applicationContext)
        PDDocument.load(file).use { doc ->
            val stripper = PDFTextStripper()
            val text = stripper.getText(doc)
            val title = doc.documentInformation?.title?.trim().orEmpty()
                .ifBlank { file.nameWithoutExtension }
            if (text.isBlank()) error("A PDF nem tartalmaz kinyerhető szöveget.")
            return ExtractedBook(title, clean(text))
        }
    }

    private fun fromDocx(file: File): ExtractedBook {
        ZipFile(file).use { zip ->
            val entry = zip.getEntry("word/document.xml")
                ?: error("Érvénytelen DOCX fájl.")
            val xml = zip.getInputStream(entry).bufferedReader().readText()
            val title = extractDocxTitle(zip) ?: file.nameWithoutExtension
            return ExtractedBook(title, clean(extractDocxParagraphs(xml)))
        }
    }

    private fun extractDocxTitle(zip: ZipFile): String? {
        val core = zip.getEntry("docProps/core.xml") ?: return null
        val xml = zip.getInputStream(core).bufferedReader().readText()
        return Regex("""<dc:title[^>]*>([^<]+)</dc:title>""", RegexOption.IGNORE_CASE)
            .find(xml)?.groupValues?.get(1)?.trim()
    }

    private fun extractDocxParagraphs(xml: String): String {
        val factory = XmlPullParserFactory.newInstance()
        val parser = factory.newPullParser()
        parser.setInput(xml.reader())
        val buf = StringBuilder()
        var inText = false
        var event = parser.eventType
        while (event != XmlPullParser.END_DOCUMENT) {
            when (event) {
                XmlPullParser.START_TAG -> {
                    val name = parser.name
                    if (name == "t") inText = true
                    if (name == "tab") buf.append(' ')
                    if (name == "br" || name == "cr") buf.append('\n')
                }
                XmlPullParser.TEXT -> if (inText) buf.append(parser.text)
                XmlPullParser.END_TAG -> {
                    if (parser.name == "t") inText = false
                    if (parser.name == "p") buf.append('\n')
                }
            }
            event = parser.next()
        }
        return buf.toString()
    }

    private fun fromOdt(file: File): ExtractedBook {
        ZipFile(file).use { zip ->
            val entry = zip.getEntry("content.xml")
                ?: error("Érvénytelen ODT fájl.")
            val xml = zip.getInputStream(entry).bufferedReader().readText()
            val title = Regex("""<dc:title[^>]*>([^<]+)</dc:title>""", RegexOption.IGNORE_CASE)
                .find(xml)?.groupValues?.get(1)?.trim()
                ?: file.nameWithoutExtension
            return ExtractedBook(title, clean(stripXmlText(xml)))
        }
    }

    private fun fromLegacyDoc(file: File): ExtractedBook {
        val bytes = file.readBytes()
        val utf16 = extractUtf16Strings(bytes)
        val ascii = extractAsciiStrings(bytes)
        val merged = (utf16 + ascii).joinToString("\n").trim()
        if (merged.length < 80) {
            error("A régi DOC formátum nem támogatott megbízhatóan. Mentsd DOCX-be vagy PDF-be.")
        }
        return ExtractedBook(file.nameWithoutExtension, clean(merged))
    }

    private fun fromMobi(file: File): ExtractedBook {
        val bytes = file.readBytes()
        val text = MobiDecoder.decode(bytes)
        if (text.isBlank()) error("A MOBI fájl szövege nem olvasható.")
        return ExtractedBook(file.nameWithoutExtension, clean(text))
    }

    private fun readTextAutoCharset(file: File): String {
        val bytes = file.readBytes()
        val utf8 = bytes.toString(Charsets.UTF_8)
        if (!utf8.contains('\uFFFD')) return utf8
        return bytes.toString(Charset.forName("ISO-8859-2"))
    }

    private fun stripHtml(html: String): String {
        return html
            .replace(Regex("(?is)<(script|style)[^>]*>.*?</\\1>"), " ")
            .replace(Regex("(?is)<br\\s*/?>"), "\n")
            .replace(Regex("(?is)</p>"), "\n")
            .replace(Regex("(?is)<[^>]+>"), " ")
            .replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", "\"")
    }

    private fun stripXmlText(xml: String): String {
        return xml
            .replace(Regex("(?is)<text:line-break\\s*/>"), "\n")
            .replace(Regex("(?is)</text:p>"), "\n")
            .replace(Regex("(?is)<[^>]+>"), " ")
    }

    private fun extractUtf16Strings(bytes: ByteArray): List<String> {
        val out = mutableListOf<String>()
        val buf = StringBuilder()
        var i = 0
        while (i + 1 < bytes.size) {
            val lo = bytes[i].toInt() and 0xFF
            val hi = bytes[i + 1].toInt() and 0xFF
            val code = lo or (hi shl 8)
            if (code in 32..126 || code in 0x00C0..0x017E) {
                buf.append(code.toChar())
            } else {
                if (buf.length >= 20) out.add(buf.toString())
                buf.clear()
            }
            i += 2
        }
        if (buf.length >= 20) out.add(buf.toString())
        return out
    }

    private fun extractAsciiStrings(bytes: ByteArray): List<String> {
        val out = mutableListOf<String>()
        val buf = StringBuilder()
        for (b in bytes) {
            val c = b.toInt() and 0xFF
            if (c in 32..126) buf.append(c.toChar()) else {
                if (buf.length >= 30) out.add(buf.toString())
                buf.clear()
            }
        }
        if (buf.length >= 30) out.add(buf.toString())
        return out
    }

    fun clean(text: String): String {
        return text
            .replace("\r\n", "\n")
            .replace('\r', '\n')
            .replace(Regex("[ \t]+"), " ")
            .replace(Regex("\n{3,}"), "\n\n")
            .trim()
    }

    private object MobiDecoder {
        fun decode(data: ByteArray): String {
            if (data.size < 68) return ""
            val records = readUInt32(data, 8)
            if (records <= 0) return fallbackText(data)
            val record0Offset = readUInt32(data, 60)
            if (record0Offset <= 0 || record0Offset >= data.size) return fallbackText(data)

            val extraFlags = data.getOrNull(16)?.toInt()?.and(0xFF) ?: 0
            val mult = if (extraFlags and 0x40 != 0) 4 else 2
            val titleLen = readUInt16(data, 84)
            val titleStart = 84 + mult
            val title = if (titleLen > 0 && titleStart + titleLen <= data.size) {
                String(data, titleStart, titleLen, Charsets.UTF_8)
            } else ""

            val parts = mutableListOf<String>()
            for (i in 1 until records) {
                val start = readUInt32(data, 60 + i * 8)
                val end = if (i + 1 < records) readUInt32(data, 60 + (i + 1) * 8) else data.size
                if (start <= 0 || end <= start || start >= data.size) continue
                val chunk = data.copyOfRange(start, minOf(end, data.size))
                val text = decompressRecord(chunk)
                if (text.isNotBlank()) parts.add(text)
            }
            val body = parts.joinToString("\n")
            return if (title.isNotBlank() && body.isBlank()) title else body
        }

        private fun decompressRecord(record: ByteArray): String {
            if (record.isEmpty()) return ""
            val compression = record.getOrNull(0)?.toInt()?.and(0xFF) ?: 1
            val payload = if (record.size > 1) record.copyOfRange(1, record.size) else record
            return when (compression) {
                1 -> String(payload, Charsets.UTF_8)
                2 -> palmDocDecompress(payload)
                else -> String(payload, Charsets.UTF_8)
            }
        }

        private fun palmDocDecompress(input: ByteArray): String {
            val out = ByteArrayOutputStream()
            var i = 0
            while (i < input.size) {
                val c = input[i].toInt() and 0xFF
                i++
                when {
                    c in 1..8 -> {
                        val count = c
                        if (i + count > input.size) break
                        out.write(input, i, count)
                        i += count
                    }
                    c in 0x80..0xBF -> {
                        if (i + 1 >= input.size) break
                        val c2 = input[i].toInt() and 0xFF
                        i++
                        val distance = ((c shl 8) or c2) and 0x3FFF
                        val length = (distance and 0x07) + 3
                        val offset = (distance shr 3) + 1
                        repeat(length) {
                            val pos = out.size() - offset
                            if (pos >= 0) out.write(out.toByteArray()[pos].toInt())
                        }
                    }
                    c in 0xC0..0xFF -> {
                        if (i >= input.size) break
                        val c2 = input[i].toInt() and 0xFF
                        i++
                        out.write(c)
                        out.write(c2)
                    }
                    else -> out.write(c)
                }
            }
            return String(out.toByteArray(), Charsets.UTF_8)
        }

        private fun fallbackText(data: ByteArray): String {
            return String(data, Charsets.UTF_8)
                .replace(Regex("[^\\p{L}\\p{N}\\p{P}\\s]"), " ")
        }

        private fun readUInt32(data: ByteArray, offset: Int): Int {
            if (offset + 4 > data.size) return 0
            return (data[offset].toInt() and 0xFF) or
                ((data[offset + 1].toInt() and 0xFF) shl 8) or
                ((data[offset + 2].toInt() and 0xFF) shl 16) or
                ((data[offset + 3].toInt() and 0xFF) shl 24)
        }

        private fun readUInt16(data: ByteArray, offset: Int): Int {
            if (offset + 2 > data.size) return 0
            return (data[offset].toInt() and 0xFF) or
                ((data[offset + 1].toInt() and 0xFF) shl 8)
        }
    }
}