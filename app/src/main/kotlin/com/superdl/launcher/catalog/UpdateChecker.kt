package com.superdl.launcher.catalog

import android.content.Context
import android.util.Log
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * FRISSÍTÉS-FIGYELŐ.
 *
 * MIÉRT KELL: ha a SuperDL nem a Google Play-ről érkezik, akkor NINCS
 * automatikus frissítés — a felhasználó észre sem venné, hogy új verzió van.
 * Ezért az alkalmazás maga nézi meg naponta egyszer-kétszer, van-e újabb, és
 * SZÓL, ha igen.
 *
 * MŰKÖDÉS: egy kis JSON fájlt tölt le a tárolóból, ami megmondja, mi a legújabb
 * verzió, hol tölthető le, és mi változott. Semmilyen kódot nem tölt le és nem
 * futtat — a telepítést a felhasználó indítja, tudatosan.
 */
object UpdateChecker {

    private const val TAG = "SDL_UPDATE"
    private const val PREFS = "superdl_update"
    private const val KEY_LAST_CHECK = "last_check"
    private const val KEY_LAST_SEEN_VERSION = "last_seen_version"

    /** Ennyi időnként nézünk rá (12 óra = napi kétszer). */
    private const val CHECK_INTERVAL_MS = 12 * 60 * 60 * 1000L

    private const val TIMEOUT_MS = 15_000

    /** A verzió-fájl címe. A katalógus tárolójában van. */
    private val versionUrl: String
        get() = CatalogClient.baseUrl + "verzio.json"

    data class UpdateInfo(
        val version: String,
        val downloadUrl: String,
        val notes: String
    ) {
        fun speak(): String =
            "Új verzió érhető el: $version. $notes"
    }

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** Esedékes-e a következő ellenőrzés? */
    fun isDue(context: Context): Boolean {
        val last = prefs(context).getLong(KEY_LAST_CHECK, 0L)
        return System.currentTimeMillis() - last > CHECK_INTERVAL_MS
    }

    /**
     * Ellenőrzés. HÁTTÉRSZÁLRÓL hívandó.
     * @param force igaz esetén akkor is néz, ha még nem esedékes
     * @return az új verzió adatai, vagy null ha nincs újabb (vagy nem sikerült)
     */
    fun check(context: Context, force: Boolean = false): UpdateInfo? {
        if (!force && !isDue(context)) return null
        prefs(context).edit().putLong(KEY_LAST_CHECK, System.currentTimeMillis()).apply()

        val text = download(versionUrl) ?: return null
        return try {
            val o = JSONObject(text)
            val latest = o.optString("verzio")
            if (latest.isBlank()) return null
            val current = currentVersion(context)
            if (!isNewer(latest, current)) {
                Log.i(TAG, "nincs ujabb verzio (jelenlegi=$current, tavoli=$latest)")
                return null
            }
            Log.i(TAG, "UJ VERZIO: $latest (jelenlegi: $current)")
            UpdateInfo(
                version = latest,
                downloadUrl = o.optString("letoltes"),
                notes = o.optString("ujdonsagok", "")
            )
        } catch (e: Exception) {
            Log.w(TAG, "verzio-ellenorzes hiba: ${e.message}")
            null
        }
    }

    /** Már szóltunk erről a verzióról? (Hogy ne nyaggassuk a felhasználót.) */
    fun alreadyAnnounced(context: Context, version: String): Boolean =
        prefs(context).getString(KEY_LAST_SEEN_VERSION, null) == version

    fun markAnnounced(context: Context, version: String) {
        prefs(context).edit().putString(KEY_LAST_SEEN_VERSION, version).apply()
    }

    fun currentVersion(context: Context): String = try {
        context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: "0.0.0"
    } catch (_: Exception) {
        "0.0.0"
    }

    /** Verzió-összehasonlítás pontokkal tagolt számokra (1.55.0 < 1.56.0). */
    fun isNewer(remote: String, current: String): Boolean {
        val r = remote.trim().split(".").mapNotNull { it.filter(Char::isDigit).toIntOrNull() }
        val c = current.trim().split(".").mapNotNull { it.filter(Char::isDigit).toIntOrNull() }
        for (i in 0 until maxOf(r.size, c.size)) {
            val a = r.getOrElse(i) { 0 }
            val b = c.getOrElse(i) { 0 }
            if (a != b) return a > b
        }
        return false
    }

    private fun download(url: String): String? {
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = TIMEOUT_MS
                readTimeout = TIMEOUT_MS
                setRequestProperty("User-Agent", "SuperDL")
            }
            if (conn.responseCode != 200) return null
            conn.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } catch (_: Exception) {
            null
        } finally {
            try {
                conn?.disconnect()
            } catch (_: Exception) {
            }
        }
    }
}
