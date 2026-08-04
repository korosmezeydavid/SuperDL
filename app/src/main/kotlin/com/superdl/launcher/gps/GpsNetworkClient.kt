package com.superdl.launcher.gps

import android.util.Log
import java.net.HttpURLConnection
import java.net.URL

/**
 * Közös, STABILIZÁLT hálózati réteg a GPS-alapú lekérdezésekhez (utcanevek,
 * kereszteződések, POI-k). Ezt a réteget azért vezettük be, mert a korábbi
 * "egy próbálkozás, egy szerver" megközelítés ingadozó volt: az ingyenes
 * közösségi szerverek (Overpass, Nominatim) gyakran túlterheltek, és egyetlen
 * 429/503/504 vagy időtúllépés azonnal "sikertelen" üzenetet adott.
 *
 * A stabilizálás három pillére:
 *   1. TÖBB TÜKÖR: ha az elsődleges szerver bukik, jön a következő tükör.
 *   2. ÚJRAPRÓBÁLKOZÁS: ideiglenes hibáknál (429/5xx/timeout) rövid,
 *      növekvő várakozás után újra.
 *   3. EGYSÉGES időkorlátok és fejlécek.
 */
object GpsNetworkClient {

    private const val TAG = "SDL_GPS_NET"
    private const val USER_AGENT =
        "SuperDL/1.54 (vak-barat launcher; korosmezey.david.richard@gmail.com)"
    private const val CONNECT_TIMEOUT_MS = 12_000
    private const val READ_TIMEOUT_MS = 15_000
    private const val MAX_ATTEMPTS_PER_SERVER = 2

    /** Overpass API tükrök — sorrendben próbáljuk, amíg valamelyik válaszol. */
    val OVERPASS_MIRRORS = listOf(
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    )

    /** Nominatim tükrök (reverse geocoding). */
    val NOMINATIM_MIRRORS = listOf(
        "https://nominatim.openstreetmap.org",
        "https://nominatim.geocoding.ai",
    )

    /**
     * GET kérés több tükörrel és újrapróbálkozással.
     * @param buildUrl a tükör-alapcímből felépíti a teljes URL-t.
     * @return a válasz szövege, vagy null ha MINDEN tükör és próbálkozás bukott.
     */
    fun getWithFailover(mirrors: List<String>, buildUrl: (String) -> String): String? {
        for (mirror in mirrors) {
            val url = buildUrl(mirror)
            val result = attemptWithRetry { doGet(url) }
            if (result != null) return result
        }
        Log.w(TAG, "Minden tükör bukott (GET).")
        return null
    }

    /**
     * POST kérés (Overpass) több tükörrel és újrapróbálkozással.
     */
    fun postWithFailover(mirrors: List<String>, formBody: String): String? {
        for (mirror in mirrors) {
            val result = attemptWithRetry { doPost(mirror, formBody) }
            if (result != null) return result
        }
        Log.w(TAG, "Minden tükör bukott (POST).")
        return null
    }

    /** Egy szerverre több próbálkozás, növekvő várakozással. */
    private fun attemptWithRetry(block: () -> String?): String? {
        var wait = 600L
        repeat(MAX_ATTEMPTS_PER_SERVER) { attempt ->
            // Ha a szálat közben megszakították (pl. a felhasználó kilépett),
            // azonnal abbahagyjuk — ne blokkoljunk és ne adjunk kései eredményt.
            if (Thread.currentThread().isInterrupted) return null
            try {
                val result = block()
                if (result != null) return result
            } catch (e: Exception) {
                Log.w(TAG, "Próbálkozás ${attempt + 1} hiba: ${e.message}")
            }
            // Utolsó próbálkozás után nem várunk feleslegesen.
            if (attempt < MAX_ATTEMPTS_PER_SERVER - 1) {
                // Rövid darabokban alszunk, hogy a megszakítás gyorsan hasson.
                var remaining = wait
                while (remaining > 0) {
                    if (Thread.currentThread().isInterrupted) return null
                    val step = minOf(remaining, 150L)
                    try {
                        Thread.sleep(step)
                    } catch (_: InterruptedException) {
                        Thread.currentThread().interrupt()
                        return null
                    }
                    remaining -= step
                }
                wait *= 2
            }
        }
        return null
    }

    private fun doGet(url: String): String? {
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", USER_AGENT)
                setRequestProperty("Accept-Language", "hu")
            }
            readIfOk(conn)
        } catch (e: Exception) {
            Log.w(TAG, "doGet hiba ($url): ${e.message}")
            null
        } finally {
            conn?.disconnect()
        }
    }

    private fun doPost(url: String, formBody: String): String? {
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                doOutput = true
                setRequestProperty("User-Agent", USER_AGENT)
                setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
            }
            conn.outputStream.use { it.write(formBody.toByteArray(Charsets.UTF_8)) }
            readIfOk(conn)
        } catch (e: Exception) {
            Log.w(TAG, "doPost hiba ($url): ${e.message}")
            null
        } finally {
            conn?.disconnect()
        }
    }

    /**
     * Ha a válasz 2xx, visszaadja a szöveget. Ideiglenes hibáknál (429, 5xx)
     * null-t ad (hogy a retry/tükör működjön). Végleges hibáknál (4xx, kivéve
     * 429) is null, de azt már nem érdemes újrapróbálni ugyanott — a tükör-váltás
     * viszont segíthet.
     */
    private fun readIfOk(conn: HttpURLConnection): String? {
        val code = conn.responseCode
        if (code in 200..299) {
            return conn.inputStream.bufferedReader().use { it.readText() }
        }
        Log.w(TAG, "HTTP $code — ${conn.url.host}")
        return null
    }
}
