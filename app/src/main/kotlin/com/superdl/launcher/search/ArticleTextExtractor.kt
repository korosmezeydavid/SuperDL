package com.superdl.launcher.search

import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.nio.charset.StandardCharsets

object ArticleTextExtractor {

    private const val MAX_CHARS = 12_000
    private const val TIMEOUT_MS = 15_000

    fun fetchText(url: String): String? {
        val normalized = url.trim()
        if (normalized.isBlank()) return null
        return try {
            val connection = (URL(normalized).openConnection() as HttpURLConnection).apply {
                connectTimeout = TIMEOUT_MS
                readTimeout = TIMEOUT_MS
                setRequestProperty("User-Agent", "SuperDL/1.31 (Android; accessibility)")
                instanceFollowRedirects = true
            }
            connection.inputStream.bufferedReader(StandardCharsets.UTF_8).use { reader ->
                val html = reader.readText()
                extractPlainText(html)
            }
        } catch (_: Exception) {
            null
        }
    }

    fun extractPlainText(html: String): String {
        var text = html
            .replace(Regex("(?is)<script[^>]*>.*?</script>"), " ")
            .replace(Regex("(?is)<style[^>]*>.*?</style>"), " ")
            .replace(Regex("(?is)<noscript[^>]*>.*?</noscript>"), " ")
            .replace(Regex("(?is)<header[^>]*>.*?</header>"), " ")
            .replace(Regex("(?is)<footer[^>]*>.*?</footer>"), " ")
            .replace(Regex("(?is)<nav[^>]*>.*?</nav>"), " ")
            .replace(Regex("<[^>]+>"), " ")
            .replace("&nbsp;", " ")
            .replace("&amp;", " és ")
            .replace("&quot;", "\"")
            .replace("&#39;", "'")
            .replace(Regex("\\s+"), " ")
            .trim()
        if (text.length > MAX_CHARS) {
            text = text.take(MAX_CHARS) + "…"
        }
        return text
    }

    fun encodeQuery(query: String): String =
        URLEncoder.encode(query.trim(), StandardCharsets.UTF_8.name())
}