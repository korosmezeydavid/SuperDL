package com.superdl.launcher.radio

import android.util.Log
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * A Radio Browser API kliense (https://api.radio-browser.info).
 *
 * Ingyenes, nyílt, közösségi rádió-adatbázis 45 000+ állomással. A lényeges
 * előnye: az "url_resolved" mező MÁR feloldott hangfolyam-URL-t ad (a .pls/.m3u
 * listákat helyettünk feloldja), így közvetlenül streamelhető.
 *
 * A hívások hálózatot használnak — mindig háttérszálról hívd őket.
 */
object RadioBrowserClient {

    private const val TAG = "SuperDL.Radio"
    private const val USER_AGENT = "SuperDL-Android/1.0"
    private const val TIMEOUT_MS = 15_000

    // A hivatalos ajánlás szerint több szerver van, bármelyik elérhető lehet.
    // A "de1" a legstabilabb nyilvános tükör; hiba esetén jön a tartalék.
    private val SERVERS = listOf(
        "https://de1.api.radio-browser.info",
        "https://nl1.api.radio-browser.info",
        "https://at1.api.radio-browser.info"
    )

    /** Magyar állomások, népszerűség szerint rendezve. */
    fun hungarianStations(limit: Int = 30): List<RadioStation> =
        query("/json/stations/bycountrycodeexact/HU?order=clickcount&reverse=true&hidebroken=true&limit=$limit")

    /** Keresés név szerint (bármely országból). */
    fun searchByName(name: String, limit: Int = 30): List<RadioStation> {
        val encoded = URLEncoder.encode(name, "UTF-8")
        return query("/json/stations/search?name=$encoded&order=clickcount&reverse=true&hidebroken=true&limit=$limit")
    }

    private fun query(path: String): List<RadioStation> {
        for (server in SERVERS) {
            val json = httpGet(server + path) ?: continue
            return parse(json)
        }
        return emptyList()
    }

    private fun parse(json: String): List<RadioStation> {
        val out = mutableListOf<RadioStation>()
        try {
            val arr = JSONArray(json)
            for (i in 0 until arr.length()) {
                val o = arr.optJSONObject(i) ?: continue
                // A feloldott URL a megbízható; ha üres, essünk vissza a nyersre.
                val stream = o.optString("url_resolved").ifBlank { o.optString("url") }
                val name = o.optString("name").trim()
                val uuid = o.optString("stationuuid")
                if (stream.isBlank() || name.isBlank()) continue
                out.add(RadioStation(id = uuid.ifBlank { stream }, name = name, streamUrl = stream))
            }
        } catch (e: Exception) {
            Log.w(TAG, "parse failed", e)
        }
        return out
    }

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
