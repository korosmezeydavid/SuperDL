package com.superdl.launcher.youtube

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Keyless YouTube search via public proxies (Piped/Invidious), unofficial innerTube,
 * and raw HTML ytInitialData parsing — no Google Cloud API key required.
 */
internal object YoutubeExtractor {

    const val PAGE_SIZE = 20
    private const val MAX_RESULTS = PAGE_SIZE
    private const val USER_AGENT =
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    private val PIPED_INSTANCES = listOf(
        "https://api.piped.private.coffee",
        "https://pipedapi.kavin.rocks",
        "https://pipedapi.adminforge.de"
    )

    private val INVIDIOUS_INSTANCES = listOf(
        "https://invidious.nerdvpn.de",
        "https://invidious.privacyredirect.com",
        "https://invidious.f5.si"
    )

    fun search(query: String, page: Int = 0): YoutubeSearchPage {
        val trimmed = query.trim()
        if (trimmed.isBlank()) return YoutubeSearchPage(emptyList(), page, false)

        searchWithPiped(trimmed, page)?.let { return it }
        if (page == 0) {
            searchWithInvidious(trimmed)?.takeIf { it.videos.isNotEmpty() }?.let { return it }
            searchWithInnerTube(trimmed)?.takeIf { it.videos.isNotEmpty() }?.let { return it }
            val html = searchWithHtmlScrape(trimmed)
            return YoutubeSearchPage(html, 0, html.size >= PAGE_SIZE)
        }
        return YoutubeSearchPage(emptyList(), page, false)
    }

    private fun searchWithPiped(query: String, page: Int): YoutubeSearchPage? {
        val encoded = URLEncoder.encode(query, "UTF-8")
        for (base in PIPED_INSTANCES) {
            try {
                val result = fetchPipedPage("$base/search?q=$encoded&filter=videos", page)
                if (result.videos.isNotEmpty()) return result
            } catch (_: Exception) {
                continue
            }
        }
        return null
    }

    private fun fetchPipedPage(baseUrl: String, page: Int): YoutubeSearchPage {
        var url = baseUrl
        var currentPage = 0
        var hasMore = false
        var videos = emptyList<YoutubeVideo>()
        while (currentPage <= page) {
            val body = httpGet(url, mapOf("User-Agent" to "SuperDL/1.46"))
            val root = JSONObject(body)
            val items = root.optJSONArray("items") ?: JSONArray()
            hasMore = root.optString("nextpage").isNotBlank()
            if (currentPage == page) {
                videos = parsePipedItems(items)
                break
            }
            val next = root.optString("nextpage")
            if (next.isBlank()) {
                hasMore = false
                break
            }
            url = if (next.startsWith("http")) next else {
                val base = baseUrl.substringBefore("/search")
                "$base$next"
            }
            currentPage++
        }
        return YoutubeSearchPage(videos, page, hasMore)
    }

    private fun parsePipedItems(items: JSONArray): List<YoutubeVideo> {
        val videos = mutableListOf<YoutubeVideo>()
        for (i in 0 until items.length()) {
            val item = items.optJSONObject(i) ?: continue
            if (item.optString("type") != "stream") continue
            val videoId = extractVideoId(item.optString("url", "")) ?: continue
            val title = item.optString("title", "").trim()
            if (title.isBlank()) continue
            videos.add(
                YoutubeVideo(
                    videoId = videoId,
                    title = title,
                    channel = item.optString("uploaderName", "").trim(),
                    durationSeconds = item.optInt("duration", 0)
                )
            )
            if (videos.size >= MAX_RESULTS) break
        }
        return videos
    }

    private fun searchWithInvidious(query: String): YoutubeSearchPage? {
        val encoded = URLEncoder.encode(query, "UTF-8")
        for (base in INVIDIOUS_INSTANCES) {
            try {
                val body = httpGet("$base/api/v1/search?q=$encoded&type=video", mapOf("User-Agent" to USER_AGENT))
                val items = JSONArray(body)
                val videos = parseInvidiousItems(items)
                if (videos.isNotEmpty()) return YoutubeSearchPage(videos, 0, videos.size >= PAGE_SIZE)
            } catch (_: Exception) {
                continue
            }
        }
        return null
    }

    private fun parseInvidiousItems(items: JSONArray): List<YoutubeVideo> {
        val videos = mutableListOf<YoutubeVideo>()
        for (i in 0 until items.length()) {
            val item = items.optJSONObject(i) ?: continue
            if (item.optString("type") != "video") continue
            val videoId = item.optString("videoId")
            if (videoId.isBlank()) continue
            val title = item.optString("title", "").trim()
            if (title.isBlank()) continue
            videos.add(
                YoutubeVideo(
                    videoId = videoId,
                    title = title,
                    channel = item.optString("author", "").trim(),
                    durationSeconds = item.optInt("lengthSeconds", 0)
                )
            )
            if (videos.size >= MAX_RESULTS) break
        }
        return videos
    }

    private fun searchWithInnerTube(query: String): YoutubeSearchPage? {
        val payload = JSONObject().apply {
            put("context", innerTubeContext())
            put("query", query)
        }
        val body = httpPost(
            "https://www.youtube.com/youtubei/v1/search?prettyPrint=false",
            payload.toString(),
            mapOf(
                "User-Agent" to USER_AGENT,
                "Content-Type" to "application/json",
                "X-YouTube-Client-Name" to "1",
                "X-YouTube-Client-Version" to "2.20241120.01.00",
                "Origin" to "https://www.youtube.com",
                "Referer" to "https://www.youtube.com/"
            )
        )
        val videos = extractVideosFromJson(JSONObject(body))
        return YoutubeSearchPage(videos, 0, videos.size >= PAGE_SIZE)
    }

    private fun innerTubeContext(): JSONObject = JSONObject().apply {
        put("client", JSONObject().apply {
            put("clientName", "WEB")
            put("clientVersion", "2.20241120.01.00")
            put("hl", "hu")
            put("gl", "HU")
            put("originalUrl", "https://www.youtube.com")
            put("platform", "DESKTOP")
        })
    }

    private fun searchWithHtmlScrape(query: String): List<YoutubeVideo> {
        val encoded = URLEncoder.encode(query, "UTF-8")
        val html = httpGet(
            "https://www.youtube.com/results?search_query=$encoded",
            mapOf(
                "User-Agent" to USER_AGENT,
                "Accept-Language" to "hu-HU,hu;q=0.9,en;q=0.8",
                "Cookie" to "CONSENT=YES+cb.20210328-17-p0.en+FX+${(100..999).random()}"
            )
        )
        val jsonText = extractYtInitialData(html) ?: return emptyList()
        return extractVideosFromJson(JSONObject(jsonText))
    }

    private fun extractYtInitialData(html: String): String? {
        val marker = "var ytInitialData = "
        val start = html.indexOf(marker)
        if (start < 0) return null
        return extractJsonObject(html, start + marker.length)
    }

    private fun extractJsonObject(text: String, startIndex: Int): String? {
        var depth = 0
        var inString = false
        var escaped = false
        val start = text.indexOf('{', startIndex)
        if (start < 0) return null
        for (i in start until text.length) {
            val ch = text[i]
            if (inString) {
                if (escaped) escaped = false
                else if (ch == '\\') escaped = true
                else if (ch == '"') inString = false
                continue
            }
            when (ch) {
                '"' -> inString = true
                '{' -> depth++
                '}' -> {
                    depth--
                    if (depth == 0) return text.substring(start, i + 1)
                }
            }
        }
        return null
    }

    private fun extractVideosFromJson(root: JSONObject): List<YoutubeVideo> {
        val videos = mutableListOf<YoutubeVideo>()
        val seen = mutableSetOf<String>()
        collectVideoRenderers(root, videos, seen)
        return videos.take(MAX_RESULTS)
    }

    private fun collectVideoRenderers(node: Any?, videos: MutableList<YoutubeVideo>, seen: MutableSet<String>) {
        when (node) {
            is JSONObject -> {
                if (node.has("videoId") && node.has("title")) {
                    parseVideoRenderer(node)?.let { video ->
                        if (seen.add(video.videoId)) videos.add(video)
                    }
                }
                if (videos.size >= MAX_RESULTS) return
                for (key in node.keys()) {
                    collectVideoRenderers(node.get(key), videos, seen)
                    if (videos.size >= MAX_RESULTS) return
                }
            }
            is JSONArray -> {
                for (i in 0 until node.length()) {
                    collectVideoRenderers(node.get(i), videos, seen)
                    if (videos.size >= MAX_RESULTS) return
                }
            }
        }
    }

    private fun parseVideoRenderer(obj: JSONObject): YoutubeVideo? {
        val videoId = obj.optString("videoId").ifBlank { return null }
        val title = extractText(obj.optJSONObject("title")) ?: return null
        val channel = extractText(obj.optJSONObject("ownerText"))
            ?: extractText(obj.optJSONObject("longBylineText"))
            ?: extractText(obj.optJSONObject("shortBylineText"))
            ?: ""
        val durationText = extractText(obj.optJSONObject("lengthText")).orEmpty()
        val duration = parseDurationText(durationText)
            .takeIf { it > 0 }
            ?: parseAccessibilityDuration(obj.optJSONObject("lengthText"))
        return YoutubeVideo(videoId, title, channel, duration)
    }

    private fun extractText(obj: JSONObject?): String? {
        if (obj == null) return null
        val simple = obj.optString("simpleText").trim()
        if (simple.isNotBlank()) return simple
        val runs = obj.optJSONArray("runs") ?: return null
        return buildString {
            for (i in 0 until runs.length()) {
                append(runs.optJSONObject(i)?.optString("text").orEmpty())
            }
        }.trim().ifBlank { null }
    }

    private fun parseAccessibilityDuration(obj: JSONObject?): Int {
        val label = obj?.optJSONObject("accessibility")
            ?.optJSONObject("accessibilityData")
            ?.optString("label")
            .orEmpty()
        if (label.isBlank()) return 0
        var seconds = 0
        Regex("(\\d+)\\s*óra").find(label)?.groupValues?.get(1)?.toIntOrNull()?.let { seconds += it * 3600 }
        Regex("(\\d+)\\s*perc").find(label)?.groupValues?.get(1)?.toIntOrNull()?.let { seconds += it * 60 }
        Regex("(\\d+)\\s*másodperc").find(label)?.groupValues?.get(1)?.toIntOrNull()?.let { seconds += it }
        Regex("(\\d+)\\s*hour").find(label)?.groupValues?.get(1)?.toIntOrNull()?.let { seconds += it * 3600 }
        Regex("(\\d+)\\s*minute").find(label)?.groupValues?.get(1)?.toIntOrNull()?.let { seconds += it * 60 }
        Regex("(\\d+)\\s*second").find(label)?.groupValues?.get(1)?.toIntOrNull()?.let { seconds += it }
        return seconds
    }

    fun parseDurationText(text: String): Int {
        val cleaned = text.trim()
        if (cleaned.isBlank()) return 0
        val parts = cleaned.split(":").mapNotNull { it.trim().toIntOrNull() }
        return when (parts.size) {
            3 -> parts[0] * 3600 + parts[1] * 60 + parts[2]
            2 -> parts[0] * 60 + parts[1]
            1 -> parts[0]
            else -> 0
        }
    }

    private fun extractVideoId(url: String): String? {
        if (url.contains("/watch?v=")) {
            return url.substringAfter("/watch?v=").takeWhile { it != '&' && it != '?' }.ifBlank { null }
        }
        val marker = "v="
        val index = url.indexOf(marker)
        if (index < 0) return null
        return url.substring(index + marker.length).takeWhile { it != '&' && it != '?' }.ifBlank { null }
    }

    private fun httpGet(url: String, headers: Map<String, String> = emptyMap()): String {
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 12_000
            readTimeout = 12_000
            headers.forEach { (key, value) -> setRequestProperty(key, value) }
        }
        return readHttpBody(connection)
    }

    private fun httpPost(url: String, body: String, headers: Map<String, String>): String {
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            doOutput = true
            connectTimeout = 12_000
            readTimeout = 12_000
            headers.forEach { (key, value) -> setRequestProperty(key, value) }
        }
        connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
        return readHttpBody(connection)
    }

    private fun readHttpBody(connection: HttpURLConnection): String {
        try {
            val code = connection.responseCode
            if (code !in 200..299) throw IllegalStateException("HTTP $code")
            return connection.inputStream.bufferedReader().use { it.readText() }
        } finally {
            runCatching { connection.inputStream?.close() }
            runCatching { connection.errorStream?.close() }
            runCatching { connection.disconnect() }
        }
    }
}