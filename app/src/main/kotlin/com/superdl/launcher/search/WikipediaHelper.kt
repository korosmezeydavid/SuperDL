package com.superdl.launcher.search

import android.util.Log
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.nio.charset.StandardCharsets

object WikipediaHelper {

    private const val TAG = "WikipediaHelper"
    private const val API = "https://hu.wikipedia.org/w/api.php"
    private const val TIMEOUT_MS = 15_000
    private const val MIN_EXTRACT_CHARS = 80

    data class Article(val title: String, val extract: String)

    fun prefersWikipedia(query: String): Boolean {
        val text = query.trim().lowercase()
        if (text.length < 4) return false
        val markers = listOf(
            "mi az", "mi a ", "kicsoda", "ki az", "ki a ", "mit jelent",
            "definíció", "definicio", "mire jó", "mire jo", "miért", "miert"
        )
        return markers.any { text.contains(it) }
    }

    fun tryFetch(query: String): Article? {
        val trimmed = query.trim()
        if (trimmed.isBlank()) return null
        return try {
            val title = searchTitle(trimmed) ?: return null
            val extract = fetchExtract(title) ?: return null
            if (extract.length < MIN_EXTRACT_CHARS) return null
            Article(title, extract)
        } catch (e: Exception) {
            Log.w(TAG, "Wikipedia fetch failed: ${e.message}")
            null
        }
    }

    private fun searchTitle(query: String): String? {
        val url = "$API?action=query&list=search&srsearch=${encode(query)}&srlimit=1&format=json"
        val json = JSONObject(httpGet(url))
        val items = json.optJSONObject("query")?.optJSONArray("search") ?: return null
        if (items.length() == 0) return null
        return items.getJSONObject(0).optString("title").takeIf { it.isNotBlank() }
    }

    private fun fetchExtract(title: String): String? {
        val url = "$API?action=query&prop=extracts&exintro=&explaintext=1&titles=${encode(title)}&format=json"
        val json = JSONObject(httpGet(url))
        val pages = json.optJSONObject("query")?.optJSONObject("pages") ?: return null
        val key = pages.keys().asSequence().firstOrNull() ?: return null
        val page = pages.optJSONObject(key) ?: return null
        if (page.has("missing")) return null
        return page.optString("extract").trim().takeIf { it.isNotBlank() }
    }

    private fun httpGet(urlString: String): String {
        val connection = (URL(urlString).openConnection() as HttpURLConnection).apply {
            connectTimeout = TIMEOUT_MS
            readTimeout = TIMEOUT_MS
            requestMethod = "GET"
            setRequestProperty("User-Agent", "SuperDL/1.32 (Android; accessibility)")
        }
        return connection.inputStream.bufferedReader(StandardCharsets.UTF_8).use { it.readText() }
    }

    private fun encode(value: String): String =
        URLEncoder.encode(value, StandardCharsets.UTF_8.name())
}