package com.superdl.launcher.podcast

import android.content.Context
import android.util.Log
import java.io.File
import java.io.InputStream

/**
 * OPML import/export – a podcast-világ szabványos feliratkozás-formátuma.
 * Ezzel áthozhatod a gyűjteményedet másik appból (Pocket Casts, AntennaPod,
 * Overcast stb.), vagy kimentheted a sajátodat.
 *
 * Az OPML egy egyszerű XML: minden podcast egy <outline> sor, benne a
 * nevével (text/title) és az RSS-feed címével (xmlUrl).
 */
object PodcastOpml {

    private const val TAG = "SuperDL.Opml"

    /** Az OPML tartalmából kiolvassa a podcastokat (feed URL + név). */
    fun parse(xml: String): List<Podcast> {
        val outlines = Regex("""<outline\b[^>]*>""", RegexOption.IGNORE_CASE)
            .findAll(xml)
            .map { it.value }
            .toList()

        val list = mutableListOf<Podcast>()
        for (o in outlines) {
            val feed = attr(o, "xmlUrl") ?: continue
            val title = attr(o, "text") ?: attr(o, "title") ?: feed
            list.add(
                Podcast(
                    id = feed.hashCode().toString(),
                    title = unescape(title),
                    author = "",
                    feedUrl = unescape(feed)
                )
            )
        }
        return list.distinctBy { it.feedUrl }
    }

    /** Beolvasás fájlból (a felhasználó által választott OPML). */
    fun parseStream(input: InputStream): List<Podcast> = try {
        input.bufferedReader().use { parse(it.readText()) }
    } catch (e: Exception) {
        Log.w(TAG, "parseStream failed", e)
        emptyList()
    }

    /** A feliratkozásokból OPML-szöveget készít (exporthoz). */
    fun build(podcasts: List<Podcast>): String = buildString {
        appendLine("""<?xml version="1.0" encoding="UTF-8"?>""")
        appendLine("""<opml version="2.0">""")
        appendLine("  <head>")
        appendLine("    <title>SuperDL podcast feliratkozások</title>")
        appendLine("  </head>")
        appendLine("  <body>")
        podcasts.forEach { p ->
            val title = escape(p.title)
            val feed = escape(p.feedUrl)
            appendLine("""    <outline type="rss" text="$title" title="$title" xmlUrl="$feed" />""")
        }
        appendLine("  </body>")
        appendLine("</opml>")
    }

    /** Exportálás fájlba; visszaadja a fájlt vagy null-t. */
    fun export(context: Context, podcasts: List<Podcast>): File? = try {
        val dir = File(context.getExternalFilesDir(null), "podcast")
        if (!dir.exists()) dir.mkdirs()
        val file = File(dir, "superdl_feliratkozasok.opml")
        file.writeText(build(podcasts))
        file
    } catch (e: Exception) {
        Log.w(TAG, "export failed", e)
        null
    }

    private fun attr(tag: String, name: String): String? =
        Regex("""$name\s*=\s*"([^"]*)"""", RegexOption.IGNORE_CASE)
            .find(tag)?.groupValues?.get(1)?.trim()?.ifBlank { null }

    private fun escape(s: String): String = s
        .replace("&", "&amp;")
        .replace("\"", "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")

    private fun unescape(s: String): String = s
        .replace("&amp;", "&")
        .replace("&quot;", "\"")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&apos;", "'")
}
