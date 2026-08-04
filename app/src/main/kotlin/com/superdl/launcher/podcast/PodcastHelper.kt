package com.superdl.launcher.podcast

import android.util.Log
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Podcast-katalógus az Apple nyilvános API-jaiból (kulcs nélkül, ingyenes):
 *  - toplista: rss.applemarketingtools.com (országonként)
 *  - keresés: itunes.apple.com/search
 *  - epizódok: a podcast saját RSS-feedjéből
 *
 * Minden hívás hálózatot használ – háttérszálon futtasd.
 */
object PodcastHelper {

    private const val TAG = "SuperDL.Podcast"
    private const val USER_AGENT = "SuperDL/1.9 (accessibility launcher)"
    private const val TIMEOUT_MS = 15_000

    /** Népszerű podcastok az adott országban (alapból Magyarország). */
    fun topPodcasts(country: String = "hu", limit: Int = 25): List<Podcast> {
        val url = "https://rss.applemarketingtools.com/api/v2/$country/podcasts/top/$limit/podcasts.json"
        val json = httpGet(url) ?: return emptyList()
        return try {
            val results = JSONObject(json).getJSONObject("feed").getJSONArray("results")
            val list = mutableListOf<Podcast>()
            for (i in 0 until results.length()) {
                val obj = results.getJSONObject(i)
                val id = obj.optString("id")
                val name = obj.optString("name")
                val artist = obj.optString("artistName")
                if (id.isBlank() || name.isBlank()) continue
                // A toplista nem ad feed URL-t, ezért az ID alapján lekérjük.
                list.add(Podcast(id = id, title = name, author = artist, feedUrl = ""))
            }
            list
        } catch (e: Exception) {
            Log.w(TAG, "topPodcasts parse failed", e)
            emptyList()
        }
    }

    /** Podcast keresése név vagy téma alapján. */
    fun search(query: String, country: String = "HU", limit: Int = 25): List<Podcast> {
        val encoded = URLEncoder.encode(query.trim(), "UTF-8")
        val url = "https://itunes.apple.com/search?term=$encoded&country=$country&media=podcast&limit=$limit"
        val json = httpGet(url) ?: return emptyList()
        return parseItunesResults(json)
    }

    /** Egy podcast adatainak (főleg a feed URL-jének) lekérése iTunes ID alapján. */
    fun lookup(collectionId: String, country: String = "HU"): Podcast? {
        val url = "https://itunes.apple.com/lookup?id=$collectionId&country=$country&media=podcast"
        val json = httpGet(url) ?: return null
        return parseItunesResults(json).firstOrNull()
    }

    private fun parseItunesResults(json: String): List<Podcast> = try {
        val results = JSONObject(json).getJSONArray("results")
        val list = mutableListOf<Podcast>()
        for (i in 0 until results.length()) {
            val obj = results.getJSONObject(i)
            val feed = obj.optString("feedUrl")
            val name = obj.optString("collectionName")
            if (feed.isBlank() || name.isBlank()) continue
            list.add(
                Podcast(
                    id = obj.optLong("collectionId").toString(),
                    title = name,
                    author = obj.optString("artistName"),
                    feedUrl = feed
                )
            )
        }
        list
    } catch (e: Exception) {
        Log.w(TAG, "parseItunesResults failed", e)
        emptyList()
    }

    /**
     * Egy podcast epizódjai az RSS-feedjéből (legfrissebb elöl).
     * A feedek nagyok lehetnek (több száz adás), ezért limitáljuk.
     */
    fun episodes(feedUrl: String, podcastTitle: String = "", limit: Int = 50): List<PodcastEpisode> {
        val body = httpGet(feedUrl) ?: return emptyList()
        return parseFeed(body, podcastTitle, limit)
    }

    private fun parseFeed(xml: String, podcastTitle: String, limit: Int): List<PodcastEpisode> {
        val items = Regex("<item>(.*?)</item>", RegexOption.DOT_MATCHES_ALL)
            .findAll(xml)
            .take(limit)
            .map { it.groupValues[1] }
            .toList()

        return items.mapNotNull { item ->
            val title = extractTag(item, "title") ?: return@mapNotNull null
            val audio = Regex("""<enclosure[^>]*url="([^"]+)"""")
                .find(item)?.groupValues?.get(1) ?: return@mapNotNull null
            val duration = extractTag(item, "itunes:duration")?.let { parseDuration(it) } ?: 0
            val published = extractTag(item, "pubDate")?.let { shortDate(it) } ?: ""
            val desc = extractTag(item, "description")?.let { stripHtml(it) } ?: ""
            PodcastEpisode(
                title = title,
                audioUrl = audio,
                durationSeconds = duration,
                publishedText = published,
                description = desc,
                podcastTitle = podcastTitle
            )
        }
    }

    private fun extractTag(block: String, tag: String): String? {
        val m = Regex("<$tag[^>]*>(?:<!\\[CDATA\\[)?(.*?)(?:\\]\\]>)?</$tag>", RegexOption.DOT_MATCHES_ALL)
            .find(block) ?: return null
        return m.groupValues[1].trim().ifBlank { null }
    }

    /** "4607" vagy "01:15:30" vagy "45:20" formátumot másodpercre. */
    private fun parseDuration(text: String): Int {
        val t = text.trim()
        if (!t.contains(":")) return t.toIntOrNull() ?: 0
        val parts = t.split(":").mapNotNull { it.trim().toIntOrNull() }
        return when (parts.size) {
            3 -> parts[0] * 3600 + parts[1] * 60 + parts[2]
            2 -> parts[0] * 60 + parts[1]
            else -> 0
        }
    }

    /** "Wed, 02 Jul 2026 10:00:00 +0000" -> "július 2." */
    private fun shortDate(pubDate: String): String = try {
        val parts = pubDate.split(" ")
        if (parts.size >= 4) {
            val day = parts[1].toIntOrNull() ?: 0
            val month = when (parts[2].lowercase()) {
                "jan" -> "január"; "feb" -> "február"; "mar" -> "március"
                "apr" -> "április"; "may" -> "május"; "jun" -> "június"
                "jul" -> "július"; "aug" -> "augusztus"; "sep" -> "szeptember"
                "oct" -> "október"; "nov" -> "november"; "dec" -> "december"
                else -> ""
            }
            if (month.isNotBlank() && day > 0) "$month $day." else ""
        } else ""
    } catch (_: Exception) {
        ""
    }

    private fun stripHtml(html: String): String =
        html.replace(Regex("<[^>]+>"), " ")
            .replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&quot;", "\"")
            .replace(Regex("\\s+"), " ")
            .trim()

    private fun httpGet(urlString: String): String? {
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(urlString).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = TIMEOUT_MS
                readTimeout = TIMEOUT_MS
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", USER_AGENT)
            }
            if (conn.responseCode !in 200..299) return null
            conn.inputStream.bufferedReader().use { it.readText() }
        } catch (e: Exception) {
            Log.w(TAG, "httpGet failed: $urlString", e)
            null
        } finally {
            conn?.disconnect()
        }
    }
}
