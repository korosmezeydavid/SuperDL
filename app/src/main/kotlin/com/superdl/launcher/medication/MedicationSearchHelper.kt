package com.superdl.launcher.medication

import android.util.Log
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Gyógyszer-információ kereső a magyar Wikipedia nyilvános API-jából.
 *
 * FONTOS: ez NEM gyógyszerészeti tanács, csak tájékoztató segítség. A hívó
 * mindig olvassa fel a figyelmeztetést (lásd DISCLAIMER) a találat előtt.
 *
 * Stratégia: előbb pontos cikkcím (a Wikipedia átirányít a hatóanyagra, pl.
 * Algopyrin -> Metamizol-nátrium), ha nincs, teljes szöveges keresés. A
 * kereszthatásokat szándékosan NEM listázzuk – ott a gyógyszerészhez irányítunk.
 */
object MedicationSearchHelper {

    private const val TAG = "SuperDL.MedSearch"
    private const val API = "https://hu.wikipedia.org/w/api.php"
    private const val USER_AGENT = "SuperDL/1.9 (accessibility launcher)"

    const val DISCLAIMER =
        "Figyelem: ez nem gyógyszerészeti tanács, csak tájékoztatás. " +
            "A pontos adagolást, kölcsönhatásokat és ellenjavallatokat mindig " +
            "kérdezd meg orvosodtól vagy gyógyszerészedtől."

    // A kereszthatás-szekció elé kerülő nyomatékos figyelmeztetés.
    private const val INTERACTION_WARNING =
        "Most a kölcsönhatásokról mondok tájékoztatást. " +
            "Ezek az adatok változhatnak és nem teljesek. " +
            "Mielőtt bármit együtt szednél, a biztosért kérdezd meg a gyógyszerészt."

    data class Result(
        val title: String,
        val summary: String,
        val sideEffects: String?,
        val interactions: String?
    ) {
        /** A teljes felolvasandó szöveg, a figyelmeztetéssel az elején. */
        fun speakText(): String = buildString {
            append(DISCLAIMER)
            append(" ")
            append("$title. ")
            append(summary)
            if (!sideEffects.isNullOrBlank()) {
                append(" Lehetséges mellékhatások: ")
                append(sideEffects)
            }
            if (!interactions.isNullOrBlank()) {
                append(" ")
                append(INTERACTION_WARNING)
                append(" A leírás szerint: ")
                append(interactions)
            } else {
                append(" A kölcsönhatásokról nem találtam megbízható adatot itt; ")
                append("ezekről feltétlenül kérdezd meg a gyógyszerészed.")
            }
        }
    }

    /**
     * Megkeresi a gyógyszert. Hálózati hívás – háttérszálon futtasd.
     * @return Result vagy null, ha nincs megbízható találat.
     */
    fun search(query: String): Result? {
        val trimmed = query.trim()
        if (trimmed.isBlank()) return null

        // 1) Pontos cikkcím (átirányítással)
        val direct = fetchExtract(trimmed)
        if (direct != null && direct.second.isNotBlank()) {
            return buildResult(direct.first, direct.second)
        }

        // 2) Teljes szöveges keresés – a legjobb találat (gyakran a hatóanyag)
        val bestTitle = searchBestTitle(trimmed) ?: return null
        val found = fetchExtract(bestTitle) ?: return null
        if (found.second.isBlank()) return null
        return buildResult(found.first, found.second)
    }

    private fun buildResult(title: String, fullText: String): Result {
        val intro = firstParagraphs(fullText, maxChars = 500)
        val side = extractSection(fullText, listOf("mellékhatás", "nemkívánatos"))
            ?.let { firstParagraphs(it, maxChars = 400) }
        // A kölcsönhatás/kereszthatás ritkán van külön szekcióban a magyar
        // Wikipédián; több kulcsszóval próbálkozunk, és ha nincs, null marad
        // (ilyenkor a gyógyszerészhez irányítunk).
        val interaction = extractSection(
            fullText,
            listOf("kölcsönhatás", "kolcsonhatas", "interakció", "együttadás", "kombináció")
        )?.let { firstParagraphs(it, maxChars = 350) }
        return Result(
            title = title,
            summary = intro,
            sideEffects = side,
            interactions = interaction
        )
    }

    /** A cikk eleje (bevezető), néhány mondatra vágva. */
    private fun firstParagraphs(text: String, maxChars: Int): String {
        val clean = text.replace(Regex("=+.*?=+"), " ") // szekciócímek kivágása
            .replace(Regex("\\s+"), " ")
            .trim()
        if (clean.length <= maxChars) return clean
        // Az utolsó teljes mondatig vágjuk.
        val cut = clean.substring(0, maxChars)
        val lastDot = cut.lastIndexOf('.')
        return if (lastDot > maxChars / 2) cut.substring(0, lastDot + 1) else "$cut…"
    }

    /**
     * Kikeresi a megadott kulcsszavakhoz tartozó szekciót a cikk szövegéből.
     * A Wikipedia sima szövegében a szekciócímek "== Cím ==" formában vannak.
     */
    private fun extractSection(fullText: String, keywords: List<String>): String? {
        val lines = fullText.lines()
        var capturing = false
        val sb = StringBuilder()
        for (line in lines) {
            val isHeader = line.trim().startsWith("==")
            if (isHeader) {
                if (capturing) break // a következő szekció kezdete -> vége
                val headerText = line.replace("=", "").trim().lowercase()
                if (keywords.any { headerText.contains(it) }) {
                    capturing = true
                    continue
                }
            } else if (capturing) {
                sb.appendLine(line)
            }
        }
        val result = sb.toString().trim()
        return result.ifBlank { null }
    }

    /** Egy cikk teljes szövegének lekérése (title, extract). */
    private fun fetchExtract(title: String): Pair<String, String>? {
        return try {
            val url = "$API?action=query&format=json&prop=extracts&explaintext=1" +
                "&redirects=1&titles=${URLEncoder.encode(title, "UTF-8")}"
            val json = httpGet(url) ?: return null
            val obj = JSONObject(json)
            val pages = obj.getJSONObject("query").getJSONObject("pages")
            val keys = pages.keys()
            if (!keys.hasNext()) return null
            val page = pages.getJSONObject(keys.next())
            if (page.has("missing")) return null
            val realTitle = page.optString("title", title)
            val extract = page.optString("extract", "")
            realTitle to extract
        } catch (e: Exception) {
            Log.w(TAG, "fetchExtract failed for $title", e)
            null
        }
    }

    /** Teljes szöveges keresés, a legjobb találat címét adja vissza. */
    private fun searchBestTitle(query: String): String? {
        return try {
            val url = "$API?action=query&format=json&list=search" +
                "&srlimit=3&srsearch=${URLEncoder.encode(query, "UTF-8")}"
            val json = httpGet(url) ?: return null
            val hits = JSONObject(json).getJSONObject("query").getJSONArray("search")
            if (hits.length() == 0) return null
            hits.getJSONObject(0).optString("title").ifBlank { null }
        } catch (e: Exception) {
            Log.w(TAG, "searchBestTitle failed for $query", e)
            null
        }
    }

    private fun httpGet(urlString: String): String? {
        var conn: HttpURLConnection? = null
        return try {
            val url = URL(urlString)
            conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 12_000
                readTimeout = 12_000
                setRequestProperty("User-Agent", USER_AGENT)
                setRequestProperty("Accept", "application/json")
            }
            if (conn.responseCode != 200) return null
            conn.inputStream.bufferedReader().use { it.readText() }
        } catch (e: Exception) {
            Log.w(TAG, "httpGet failed", e)
            null
        } finally {
            conn?.disconnect()
        }
    }
}
