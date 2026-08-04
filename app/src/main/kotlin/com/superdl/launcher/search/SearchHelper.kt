package com.superdl.launcher.search

import android.util.Log
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets

object SearchHelper {

    private const val TAG = "SearchHelper"
    private const val TIMEOUT_MS = 15_000
    private const val MAX_RESULTS = 8

    fun search(query: String): List<SearchResult> {
        val trimmed = query.trim()
        if (trimmed.isBlank()) return emptyList()
        return parseDuckDuckGoHtml(fetchDuckDuckGoHtml(trimmed))
    }

    private fun fetchDuckDuckGoHtml(query: String): String {
        val url = "https://html.duckduckgo.com/html/?q=${ArticleTextExtractor.encodeQuery(query)}"
        return try {
            val connection = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = TIMEOUT_MS
                readTimeout = TIMEOUT_MS
                requestMethod = "POST"
                doOutput = true
                setRequestProperty("User-Agent", "SuperDL/1.31 (Android; accessibility)")
                setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
            }
            val body = "q=${ArticleTextExtractor.encodeQuery(query)}&b="
            connection.outputStream.use { it.write(body.toByteArray(StandardCharsets.UTF_8)) }
            connection.inputStream.bufferedReader(StandardCharsets.UTF_8).use { it.readText() }
        } catch (e: Exception) {
            Log.w(TAG, "DuckDuckGo fetch failed: ${e.message}")
            ""
        }
    }

    private fun parseDuckDuckGoHtml(html: String): List<SearchResult> {
        if (html.isBlank()) return emptyList()
        val results = mutableListOf<SearchResult>()
        val linkPattern = Regex(
            """<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>""",
            RegexOption.IGNORE_CASE
        )
        val snippetPattern = Regex(
            """<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>([\s\S]*?)</a>""",
            RegexOption.IGNORE_CASE
        )
        val links = linkPattern.findAll(html).toList()
        val snippets = snippetPattern.findAll(html).map { cleanHtml(it.groupValues[1]) }.toList()
        links.forEachIndexed { index, match ->
            if (results.size >= MAX_RESULTS) return@forEachIndexed
            val rawUrl = decodeDuckDuckGoRedirect(match.groupValues[1])
            val title = cleanHtml(match.groupValues[2])
            if (title.isBlank() || rawUrl.isBlank()) return@forEachIndexed
            val snippet = snippets.getOrNull(index).orEmpty()
            results.add(SearchResult(title, snippet, rawUrl))
        }
        if (results.isNotEmpty()) return results

        // Fallback: generic result links
        val fallback = Regex(
            """<a[^>]*class="[^"]*result[^"]*"[^>]*href="(https?://[^"]+)"[^>]*>([\s\S]*?)</a>""",
            RegexOption.IGNORE_CASE
        )
        fallback.findAll(html).forEach { match ->
            if (results.size >= MAX_RESULTS) return@forEach
            val title = cleanHtml(match.groupValues[2])
            val url = match.groupValues[1]
            if (title.isNotBlank() && !url.contains("duckduckgo.com")) {
                results.add(SearchResult(title, "", url))
            }
        }
        return results
    }

    private fun decodeDuckDuckGoRedirect(href: String): String {
        val trimmed = href.trim()
        if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) return trimmed
        val uddg = Regex("uddg=([^&]+)").find(trimmed)?.groupValues?.getOrNull(1)
        if (uddg != null) {
            return try {
                java.net.URLDecoder.decode(uddg, StandardCharsets.UTF_8.name())
            } catch (_: Exception) {
                uddg
            }
        }
        return trimmed
    }

    private fun cleanHtml(raw: String): String =
        raw.replace(Regex("<[^>]+>"), " ")
            .replace("&nbsp;", " ")
            .replace("&amp;", " és ")
            .replace("&quot;", "\"")
            .replace("&#39;", "'")
            .replace(Regex("\\s+"), " ")
            .trim()
}