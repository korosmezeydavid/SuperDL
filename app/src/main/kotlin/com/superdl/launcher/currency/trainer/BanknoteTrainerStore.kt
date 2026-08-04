package com.superdl.launcher.currency.trainer

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

/**
 * A betanított bankjegy-profilok tára (SharedPrefs + JSON, a LocationProfileStore
 * mintájára). Címletenként egy profil, ami több fotó ujjlenyomatát gyűjti.
 * Bővíthető: minden tanító-menetben új fotók adhatók ugyanahhoz a címlethez.
 */
object BanknoteTrainerStore {

    private const val PREFS = "superdl"
    private const val KEY = "banknote_trained_profiles"
    const val MAX_SAMPLES_PER_DENOMINATION = 40

    /** A támogatott címletek (gépi kulcs → kimondott címke). */
    val DENOMINATIONS: List<Pair<String, String>> = listOf(
        "500" to "500 forint",
        "1000" to "1000 forint",
        "2000" to "2000 forint",
        "5000" to "5000 forint",
        "10000" to "10000 forint",
        "20000" to "20000 forint",
    )

    fun labelFor(denomination: String): String =
        DENOMINATIONS.firstOrNull { it.first == denomination }?.second
            ?: "$denomination forint"

    fun getAll(context: Context): List<BanknoteTrainedProfile> =
        loadRaw(context).sortedBy { it.denomination.toIntOrNull() ?: 0 }

    fun getByDenomination(context: Context, denomination: String): BanknoteTrainedProfile? =
        loadRaw(context).firstOrNull { it.denomination == denomination }

    /** Hány címlethez van már legalább egy tanító-fotó. */
    fun trainedDenominationCount(context: Context): Int =
        loadRaw(context).count { it.sampleCount > 0 }

    /**
     * Fotók hozzáadása egy címlethez. Ha még nincs profil rá, létrehozza;
     * ha van, bővíti. Ez a "munkamenetenként bővíthető" lényege.
     */
    fun appendCaptures(
        context: Context,
        denomination: String,
        captures: List<BanknoteCaptureDraft>
    ): BanknoteTrainedProfile? {
        if (captures.isEmpty()) return getByDenomination(context, denomination)
        val current = loadRaw(context).toMutableList()
        val existing = current.firstOrNull { it.denomination == denomination }

        val newHistograms = captures.map { it.colorHistogram }
        val newHashes = captures.map { it.visualHash }.filter { it.isNotBlank() }
        val newPaths = captures.mapNotNull { it.thumbnailPath }

        val merged = if (existing != null) {
            existing.copy(
                colorHistograms = (existing.colorHistograms + newHistograms)
                    .takeLast(MAX_SAMPLES_PER_DENOMINATION),
                visualHashes = (existing.visualHashes + newHashes)
                    .takeLast(MAX_SAMPLES_PER_DENOMINATION),
                referenceImagePaths = (existing.referenceImagePaths + newPaths)
                    .takeLast(MAX_SAMPLES_PER_DENOMINATION)
            )
        } else {
            BanknoteTrainedProfile(
                id = UUID.randomUUID().toString(),
                denomination = denomination,
                label = labelFor(denomination),
                createdAt = System.currentTimeMillis(),
                colorHistograms = newHistograms,
                visualHashes = newHashes,
                referenceImagePaths = newPaths
            )
        }

        val index = current.indexOfFirst { it.denomination == denomination }
        if (index >= 0) current[index] = merged else current.add(merged)
        save(context, current)
        return merged
    }

    /** Egy címlet teljes profiljának törlése (a fotókkal együtt). */
    fun removeDenomination(context: Context, denomination: String): Boolean {
        val current = loadRaw(context)
        val removed = current.firstOrNull { it.denomination == denomination } ?: return false
        removed.referenceImagePaths.forEach { deleteFile(it) }
        save(context, current.filterNot { it.denomination == denomination })
        return true
    }

    private fun deleteFile(path: String?) {
        if (path.isNullOrBlank()) return
        try {
            val f = File(path)
            if (f.exists()) f.delete()
        } catch (_: Exception) {
        }
    }

    private fun loadRaw(context: Context): List<BanknoteTrainedProfile> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY, null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val o = array.getJSONObject(i)
                    val denom = o.optString("denomination").trim()
                    if (denom.isBlank()) continue
                    val histograms = parseHistograms(o.optJSONArray("colorHistograms"))
                    val hashes = parseStringArray(o.optJSONArray("visualHashes"))
                    if (histograms.isEmpty() && hashes.isEmpty()) continue
                    add(
                        BanknoteTrainedProfile(
                            id = o.optString("id", UUID.randomUUID().toString()),
                            denomination = denom,
                            label = o.optString("label", labelFor(denom)),
                            createdAt = o.optLong("createdAt", System.currentTimeMillis()),
                            colorHistograms = histograms,
                            visualHashes = hashes,
                            referenceImagePaths = parseStringArray(o.optJSONArray("referenceImagePaths"))
                        )
                    )
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun parseHistograms(array: JSONArray?): List<FloatArray> {
        if (array == null) return emptyList()
        return buildList {
            for (i in 0 until array.length()) {
                val encoded = array.optString(i)
                if (encoded.isNotBlank()) add(BanknoteColorFingerprint.decode(encoded))
            }
        }
    }

    private fun parseStringArray(array: JSONArray?): List<String> {
        if (array == null) return emptyList()
        return buildList {
            for (i in 0 until array.length()) {
                val v = array.optString(i).trim()
                if (v.isNotBlank()) add(v)
            }
        }
    }

    private fun save(context: Context, profiles: List<BanknoteTrainedProfile>) {
        val array = JSONArray()
        profiles.forEach { p ->
            val histArray = JSONArray()
            p.colorHistograms.forEach { histArray.put(BanknoteColorFingerprint.encode(it)) }
            val hashArray = JSONArray()
            p.visualHashes.forEach { hashArray.put(it) }
            val pathArray = JSONArray()
            p.referenceImagePaths.forEach { pathArray.put(it) }
            array.put(
                JSONObject()
                    .put("id", p.id)
                    .put("denomination", p.denomination)
                    .put("label", p.label)
                    .put("createdAt", p.createdAt)
                    .put("colorHistograms", histArray)
                    .put("visualHashes", hashArray)
                    .put("referenceImagePaths", pathArray)
            )
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY, array.toString()).apply()
    }
}
