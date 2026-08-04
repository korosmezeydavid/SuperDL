package com.superdl.launcher.radio

import android.util.Log
import java.net.HttpURLConnection
import java.net.URL

/**
 * Feloldja a rádió-URL-t a TÉNYLEGES hangfolyam címére.
 *
 * Sok állomás nem közvetlen stream-URL-t ad, hanem egy LEJÁTSZÁSI LISTÁT
 * (.pls / .m3u / .m3u8), ami a valódi stream címére mutat. A MediaPlayer ezeket
 * a listákat nem tudja lejátszani -> "nem elérhető" hiba. Ez az osztály letölti
 * a listát, és kibányássza belőle az első használható stream-URL-t.
 *
 * Ha az URL már közvetlen stream (nem lista), változatlanul visszaadja.
 * Mindig háttérszálról hívandó (hálózati művelet).
 */
object RadioPlaylistResolver {

    private const val TAG = "SDL_RADIO"
    private const val TIMEOUT_MS = 10_000
    private const val USER_AGENT = "SuperDL/1.0 (accessibility launcher)"

    /**
     * @return a lejátszható stream-URL, vagy null ha nem sikerült feloldani.
     */
    fun resolve(url: String): String? {
        if (url.isBlank()) return null
        val lower = url.substringBefore("?").lowercase()

        return when {
            lower.endsWith(".pls") -> extractFromPls(fetch(url))
            lower.endsWith(".m3u") || lower.endsWith(".m3u8") -> extractFromM3u(fetch(url))
            else -> {
                // Nem playlist-kiterjesztés. Lehet közvetlen stream — de az is
                // előfordul, hogy kiterjesztés nélkül ad playlistet. Megnézzük a
                // tartalom-típust; ha az playlist, feloldjuk, különben marad.
                resolveByContentType(url)
            }
        }
    }

    /** Az URL tartalom-típusa alapján dönt: playlist vagy közvetlen stream. */
    private fun resolveByContentType(url: String): String {
        var conn: HttpURLConnection? = null
        try {
            conn = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = TIMEOUT_MS
                readTimeout = TIMEOUT_MS
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", USER_AGENT)
            }
            val type = conn.contentType?.lowercase() ?: ""
            val isPls = type.contains("scpls") || type.contains("pls")
            val isM3u = type.contains("mpegurl") || type.contains("m3u")
            if (isPls || isM3u) {
                val body = conn.inputStream.bufferedReader().use { it.readText() }
                val resolved = if (isPls) extractFromPls(body) else extractFromM3u(body)
                if (resolved != null) return resolved
            }
        } catch (e: Exception) {
            Log.w(TAG, "resolveByContentType hiba: ${e.message}")
        } finally {
            conn?.disconnect()
        }
        // Nem playlist (vagy nem sikerült feloldani) → marad az eredeti URL.
        return url
    }

    /** .pls formátum: "File1=http://..." sorok. Az első stream-sort adjuk vissza. */
    private fun extractFromPls(body: String?): String? {
        if (body.isNullOrBlank()) return null
        return body.lineSequence()
            .map { it.trim() }
            .filter { it.startsWith("File", ignoreCase = true) && it.contains("=") }
            .map { it.substringAfter("=").trim() }
            .firstOrNull { it.startsWith("http", ignoreCase = true) }
    }

    /** .m3u formátum: a nem-komment (#-tal nem kezdődő) első http-sor. */
    private fun extractFromM3u(body: String?): String? {
        if (body.isNullOrBlank()) return null
        return body.lineSequence()
            .map { it.trim() }
            .filter { it.isNotBlank() && !it.startsWith("#") }
            .firstOrNull { it.startsWith("http", ignoreCase = true) }
    }

    private fun fetch(url: String): String? {
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = TIMEOUT_MS
                readTimeout = TIMEOUT_MS
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", USER_AGENT)
            }
            if (conn.responseCode !in 200..299) return null
            conn.inputStream.bufferedReader().use { it.readText() }
        } catch (e: Exception) {
            Log.w(TAG, "fetch hiba ($url): ${e.message}")
            null
        } finally {
            conn?.disconnect()
        }
    }
}
