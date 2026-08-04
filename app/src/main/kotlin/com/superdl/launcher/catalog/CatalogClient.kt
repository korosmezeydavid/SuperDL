package com.superdl.launcher.catalog

import android.content.Context
import android.util.Log
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * A KATALÓGUS letöltése és a modulok kezelése.
 *
 * MŰKÖDÉS:
 *  1. Letöltjük a katalógus-fájlt (mi érhető el).
 *  2. A felhasználó kiválaszt egy modult.
 *  3. Letöltjük a modul adatfájlját a telefonra.
 *  4. A SuperDL saját motorja onnantól helyben olvassa — internet NEM kell hozzá.
 *
 * BIZTONSÁG: kizárólag JSON adatot töltünk le, SOHA nem futtatható kódot.
 */
object CatalogClient {

    private const val TAG = "SDL_CATALOG"

    /**
     * A katalógus címe. GitHub-on a "raw" cím a fájl nyers tartalmát adja.
     * A felhasználó saját tárolójára cserélhető.
     */
    var baseUrl: String = "https://raw.githubusercontent.com/lufisdavid/superdl-catalog/main/"

    private const val CATALOG_FILE = "katalogus.json"
    private const val TIMEOUT_MS = 20_000

    /** A letöltött modulok helye a telefonon. */
    fun modulesDir(context: Context): File =
        File(context.filesDir, "katalogus").apply { mkdirs() }

    fun moduleFile(context: Context, moduleId: String): File =
        File(modulesDir(context), "$moduleId.json")

    // ── A KATALÓGUS LETÖLTÉSE ───────────────────────────────────────────────

    data class CatalogResult(
        val modules: List<CatalogModule>,
        val error: String?
    )

    /** HÁTTÉRSZÁLRÓL hívandó. */
    fun fetchCatalog(): CatalogResult {
        return try {
            val text = download(baseUrl + CATALOG_FILE)
                ?: return CatalogResult(emptyList(), "A katalógus nem érhető el. Van internet?")
            val root = JSONObject(text)
            val array = root.optJSONArray("modulok")
                ?: return CatalogResult(emptyList(), "A katalógus üres vagy hibás.")

            val out = mutableListOf<CatalogModule>()
            for (i in 0 until array.length()) {
                val o = array.getJSONObject(i)
                out.add(
                    CatalogModule(
                        id = o.optString("id"),
                        name = o.optString("nev", "Névtelen modul"),
                        type = ModuleType.fromKey(o.optString("tipus")),
                        version = o.optInt("verzio", 1),
                        description = o.optString("leiras", ""),
                        sizeBytes = o.optLong("meret", 0L),
                        filePath = o.optString("fajl"),
                        minAppVersion = o.optString("minAlkalmazasVerzio", "1.0.0")
                    )
                )
            }
            Log.i(TAG, "katalogus betoltve: ${out.size} modul")
            CatalogResult(out, null)
        } catch (e: Exception) {
            Log.w(TAG, "katalogus hiba: ${e.message}")
            CatalogResult(emptyList(), "A katalógus letöltése nem sikerült.")
        }
    }

    /**
     * Egy modul letöltése a telefonra.
     * @return null ha sikerült, különben a hiba emberi nyelven
     */
    fun downloadModule(context: Context, module: CatalogModule): String? {
        return try {
            val text = download(baseUrl + module.filePath)
                ?: return "A modul nem tölthető le."
            // Ellenőrzés: tényleg értelmes JSON-t kaptunk?
            JSONObject(text)
            moduleFile(context, module.id).writeText(text, Charsets.UTF_8)
            CatalogStore.markInstalled(context, module.id, module.version, module.type)
            Log.i(TAG, "modul letoltve: ${module.id} v${module.version}")
            null
        } catch (e: Exception) {
            Log.w(TAG, "modul letoltes hiba (${module.id}): ${e.message}")
            "A letöltés nem sikerült."
        }
    }

    private fun download(url: String): String? {
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = TIMEOUT_MS
                readTimeout = TIMEOUT_MS
                requestMethod = "GET"
                setRequestProperty("User-Agent", "SuperDL")
            }
            if (conn.responseCode != 200) {
                Log.w(TAG, "letoltes valasz: ${conn.responseCode} ($url)")
                return null
            }
            conn.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } catch (e: Exception) {
            Log.w(TAG, "letoltes hiba: ${e.message}")
            null
        } finally {
            try {
                conn?.disconnect()
            } catch (_: Exception) {
            }
        }
    }
}
