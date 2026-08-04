package com.superdl.launcher.youtube

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLDecoder

object YoutubeStreamResolver {

    private const val USER_AGENT =
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    private const val ANDROID_USER_AGENT =
        "com.google.android.youtube/19.09.37 (Linux; U; Android 14) gzip"

    private val PIPED_INSTANCES = listOf(
        "https://api.piped.private.coffee",
        "https://pipedapi.kavin.rocks",
        "https://pipedapi.adminforge.de",
        "https://pipedapi.leptons.xyz",
        "https://pipedapi.in.projectsegfau.lt",
        "https://pipedapi.syncpundit.io"
    )

    private val INVIDIOUS_INSTANCES = listOf(
        "https://invidious.nerdvpn.de",
        "https://invidious.privacyredirect.com",
        "https://invidious.f5.si",
        "https://inv.nadeko.net",
        "https://invidious.protokolla.fi",
        "https://yt.artemislena.eu"
    )

    private data class InnerTubeClient(
        val clientName: String,
        val clientVersion: String,
        val clientId: String,
        val userAgent: String = USER_AGENT,
        val extraContext: JSONObject.() -> Unit = {}
    )

    private val INNERTUBE_CLIENTS = listOf(
        InnerTubeClient("ANDROID", "19.09.37", "3", ANDROID_USER_AGENT),
        InnerTubeClient("WEB", "2.20241120.01.00", "1"),
        InnerTubeClient("IOS", "19.09.3", "5", "com.google.ios.youtube/19.09.3 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)"),
        InnerTubeClient("TVHTML5_SIMPLY_EMBEDDED_PLAYER", "2.0", "85") {
            put("thirdParty", JSONObject().put("embedUrl", "https://www.youtube.com/"))
        },
        InnerTubeClient("MWEB", "2.20241120.01.00", "2", USER_AGENT) {
            put("platform", "MOBILE")
        }
    )

    /** Piped + Invidious only – gyors, nem nyit külső YouTube appot. */
    fun resolveInAppStreamUrls(videoId: String): List<String> {
        if (videoId.isBlank()) return emptyList()
        val urls = linkedSetOf<String>()
        resolveFromPipedInstances(videoId)?.let { urls += it }
        resolveFromInvidiousInstances(videoId)?.let { urls += it }
        return prioritizeVideoUrls(urls.toList())
    }

    fun resolveStreamUrls(videoId: String): List<String> {
        if (videoId.isBlank()) return emptyList()
        val urls = linkedSetOf<String>()
        resolveInAppStreamUrls(videoId).let { urls += it }
        for (client in INNERTUBE_CLIENTS) {
            resolveFromInnerTube(videoId, client)?.let { urls += it }
        }
        resolveFromWatchPage(videoId)?.let { urls += it }
        return prioritizeVideoUrls(urls.toList())
    }

    private fun prioritizeVideoUrls(urls: List<String>): List<String> {
        val video = urls.filter { looksLikeVideoUrl(it) }
        val audio = urls.filterNot { looksLikeVideoUrl(it) }
        return video + audio
    }

    fun looksLikeVideoUrlPublic(url: String): Boolean = looksLikeVideoUrl(url)

    private fun looksLikeVideoUrl(url: String): Boolean {
        val lower = url.lowercase()
        return lower.contains("mime=video") ||
            lower.contains("type=video") ||
            lower.contains(".mp4") ||
            (lower.contains("googlevideo.com") && !lower.contains("mime=audio"))
    }

    fun resolveAudioStreamUrl(videoId: String): String? =
        resolveStreamUrls(videoId).firstOrNull()

    private fun resolveFromPipedInstances(videoId: String): List<String>? {
        for (base in PIPED_INSTANCES) {
            try {
                val urls = resolveFromPiped("$base/streams/$videoId")
                if (urls.isNotEmpty()) return urls
            } catch (_: Exception) {
                continue
            }
        }
        return null
    }

    private fun resolveFromPiped(url: String): List<String> {
        val connection = openGet(url, mapOf("User-Agent" to "SuperDL/1.47"))
        return useConnection(connection) {
            if (it.responseCode !in 200..299) return@useConnection emptyList()
            val body = it.inputStream.bufferedReader().use { reader -> reader.readText() }
            val root = JSONObject(body)
            val urls = mutableListOf<String>()
            root.optJSONArray("audioStreams")?.let { pickBestAudioUrls(it) }?.let { urls += it }
            root.optJSONArray("videoStreams")?.let { pickBestProgressiveUrls(it) }?.let { urls += it }
            urls
        }
    }

    private fun resolveFromInvidiousInstances(videoId: String): List<String>? {
        for (base in INVIDIOUS_INSTANCES) {
            try {
                val urls = resolveFromInvidious("$base/api/v1/videos/$videoId")
                if (urls.isNotEmpty()) return urls
            } catch (_: Exception) {
                continue
            }
        }
        return null
    }

    private fun resolveFromInvidious(url: String): List<String> {
        val connection = openGet(url, mapOf("User-Agent" to USER_AGENT))
        return useConnection(connection) {
            if (it.responseCode !in 200..299) return@useConnection emptyList()
            val body = it.inputStream.bufferedReader().use { reader -> reader.readText() }
            val root = JSONObject(body)
            val merged = JSONArray()
            root.optJSONArray("adaptiveFormats")?.let { adaptive ->
                for (i in 0 until adaptive.length()) merged.put(adaptive.optJSONObject(i))
            }
            root.optJSONArray("formatStreams")?.let { formats ->
                for (i in 0 until formats.length()) merged.put(formats.optJSONObject(i))
            }
            val urls = mutableListOf<String>()
            pickInvidiousProgressiveUrls(merged).let { urls += it }
            pickInvidiousAudioUrls(merged).let { urls += it }
            urls
        }
    }

    private fun resolveFromInnerTube(videoId: String, client: InnerTubeClient): List<String>? {
        val payload = JSONObject().apply {
            put("context", JSONObject().apply {
                put("client", JSONObject().apply {
                    put("clientName", client.clientName)
                    put("clientVersion", client.clientVersion)
                    put("hl", "hu")
                    put("gl", "HU")
                    client.extraContext(this)
                })
            })
            put("videoId", videoId)
        }
        val connection = (URL("https://www.youtube.com/youtubei/v1/player?prettyPrint=false").openConnection()
            as HttpURLConnection).apply {
            requestMethod = "POST"
            doOutput = true
            connectTimeout = 8_000
            readTimeout = 8_000
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("User-Agent", client.userAgent)
            setRequestProperty("X-YouTube-Client-Name", client.clientId)
            setRequestProperty("X-YouTube-Client-Version", client.clientVersion)
            setRequestProperty("Origin", "https://www.youtube.com")
            setRequestProperty("Referer", "https://www.youtube.com/")
        }
        return useConnection(connection) {
            it.outputStream.use { stream -> stream.write(payload.toString().toByteArray(Charsets.UTF_8)) }
            if (it.responseCode !in 200..299) return@useConnection null
            val body = it.inputStream.bufferedReader().use { reader -> reader.readText() }
            val streaming = JSONObject(body).optJSONObject("streamingData") ?: return@useConnection null
            val urls = mutableListOf<String>()
            streaming.optJSONArray("formats")?.let { pickInnerTubeProgressiveUrls(it) }?.let { urls += it }
            streaming.optJSONArray("adaptiveFormats")?.let { pickInnerTubeAdaptiveUrls(it) }?.let { urls += it }
            urls.takeIf { urls -> urls.isNotEmpty() }
        }
    }

    private fun resolveFromWatchPage(videoId: String): List<String>? {
        val html = try {
            val connection = openGet(
                "https://www.youtube.com/watch?v=$videoId&has_verified=1",
                mapOf(
                    "User-Agent" to USER_AGENT,
                    "Accept-Language" to "hu-HU,hu;q=0.9,en;q=0.8",
                    "Cookie" to "CONSENT=YES+cb.20210328-17-p0.en+FX+667"
                )
            )
            useConnection(connection) {
                if (it.responseCode !in 200..299) return@useConnection null
                it.inputStream.bufferedReader().use { reader -> reader.readText() }
            }
        } catch (_: Exception) {
            return null
        } ?: return null
        val playerJson = extractEmbeddedJson(html, "ytInitialPlayerResponse")
            ?: extractEmbeddedJson(html, "ytInitialData")
            ?: return null
        val streaming = JSONObject(playerJson).optJSONObject("streamingData") ?: return null
        val urls = mutableListOf<String>()
        streaming.optJSONArray("formats")?.let { pickInnerTubeProgressiveUrls(it) }?.let { urls += it }
        streaming.optJSONArray("adaptiveFormats")?.let { pickInnerTubeAdaptiveUrls(it) }?.let { urls += it }
        return urls.takeIf { it.isNotEmpty() }
    }

    private fun extractEmbeddedJson(html: String, marker: String): String? {
        val token = "var $marker = "
        val start = html.indexOf(token)
        if (start < 0) return null
        return extractJsonObject(html, start + token.length)
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

    private fun pickBestProgressiveUrls(streams: JSONArray): List<String> {
        val candidates = mutableListOf<Pair<String, Int>>()
        for (i in 0 until streams.length()) {
            val stream = streams.optJSONObject(i) ?: continue
            val streamUrl = stream.optString("url")
            if (streamUrl.isBlank()) continue
            val mime = stream.optString("mimeType", stream.optString("type", ""))
            if (!mime.contains("video/") && !mime.contains("audio/")) continue
            val bitrate = stream.optInt("bitrate", 0)
            candidates += streamUrl to bitrate
        }
        return candidates.sortedByDescending { it.second }.map { it.first }
    }

    private fun pickBestAudioUrls(audioStreams: JSONArray): List<String> {
        val candidates = mutableListOf<Pair<String, Int>>()
        for (i in 0 until audioStreams.length()) {
            val stream = audioStreams.optJSONObject(i) ?: continue
            val streamUrl = stream.optString("url")
            if (streamUrl.isBlank()) continue
            val bitrate = stream.optInt("bitrate", 0)
            candidates += streamUrl to bitrate
        }
        return candidates.sortedByDescending { it.second }.map { it.first }
    }

    private fun pickInvidiousProgressiveUrls(formats: JSONArray): List<String> {
        val candidates = mutableListOf<Pair<String, Int>>()
        for (i in 0 until formats.length()) {
            val stream = formats.optJSONObject(i) ?: continue
            val type = stream.optString("type", "")
            if (!type.startsWith("video/")) continue
            val streamUrl = stream.optString("url")
            if (streamUrl.isBlank()) continue
            val bitrate = stream.optInt("bitrate", 0)
            candidates += streamUrl to bitrate
        }
        return candidates.sortedByDescending { it.second }.map { it.first }
    }

    private fun pickInvidiousAudioUrls(formats: JSONArray): List<String> {
        val candidates = mutableListOf<Pair<String, Int>>()
        for (i in 0 until formats.length()) {
            val stream = formats.optJSONObject(i) ?: continue
            val type = stream.optString("type", "")
            if (!type.startsWith("audio/")) continue
            val streamUrl = stream.optString("url")
            if (streamUrl.isBlank()) continue
            val bitrate = stream.optInt("bitrate", 0)
            candidates += streamUrl to bitrate
        }
        return candidates.sortedByDescending { it.second }.map { it.first }
    }

    private fun pickInnerTubeProgressiveUrls(formats: JSONArray): List<String> {
        val candidates = mutableListOf<Pair<String, Int>>()
        for (i in 0 until formats.length()) {
            val stream = formats.optJSONObject(i) ?: continue
            val mime = stream.optString("mimeType", "")
            if (!mime.startsWith("video/")) continue
            val streamUrl = extractStreamUrl(stream)
            if (streamUrl.isBlank()) continue
            val bitrate = stream.optInt("bitrate", 0)
            candidates += streamUrl to bitrate
        }
        return candidates.sortedByDescending { it.second }.map { it.first }
    }

    private fun pickInnerTubeAdaptiveUrls(formats: JSONArray): List<String> {
        val progressive = mutableListOf<Pair<String, Int>>()
        val audio = mutableListOf<Pair<String, Int>>()
        for (i in 0 until formats.length()) {
            val stream = formats.optJSONObject(i) ?: continue
            val mime = stream.optString("mimeType", "")
            val streamUrl = extractStreamUrl(stream)
            if (streamUrl.isBlank()) continue
            val bitrate = stream.optInt("bitrate", 0)
            when {
                mime.startsWith("video/") && mime.contains("mp4") -> progressive += streamUrl to bitrate
                mime.startsWith("audio/") -> audio += streamUrl to bitrate
            }
        }
        val result = mutableListOf<String>()
        result += progressive.sortedByDescending { it.second }.map { it.first }
        result += audio.sortedByDescending { it.second }.map { it.first }
        return result
    }

    private fun extractStreamUrl(stream: JSONObject): String {
        val direct = stream.optString("url")
        if (direct.isNotBlank()) return direct
        val cipher = stream.optString("signatureCipher").ifBlank { stream.optString("cipher") }
        if (cipher.isBlank()) return ""
        return parseCipherUrl(cipher)
    }

    private fun parseCipherUrl(cipher: String): String {
        val parts = cipher.split("&").associate {
            val idx = it.indexOf('=')
            if (idx < 0) it to "" else it.substring(0, idx) to it.substring(idx + 1)
        }
        val url = parts["url"]?.let { URLDecoder.decode(it, "UTF-8") }.orEmpty()
        val sig = parts["sig"] ?: parts["signature"] ?: parts["s"] ?: return url
        val sp = parts["sp"] ?: "signature"
        return if (url.isBlank()) "" else "$url&$sp=$sig"
    }

    private fun openGet(url: String, headers: Map<String, String>): HttpURLConnection =
        (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 8_000
            readTimeout = 8_000
            headers.forEach { (key, value) -> setRequestProperty(key, value) }
        }

    private fun <T> useConnection(connection: HttpURLConnection, block: (HttpURLConnection) -> T): T {
        try {
            return block(connection)
        } finally {
            runCatching { connection.inputStream?.close() }
            runCatching { connection.errorStream?.close() }
            runCatching { connection.disconnect() }
        }
    }
}