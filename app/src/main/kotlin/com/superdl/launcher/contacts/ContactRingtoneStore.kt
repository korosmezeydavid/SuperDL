package com.superdl.launcher.contacts

import android.content.Context
import android.util.Log
import org.json.JSONObject

/**
 * Névjegyenkénti egyéni csengőhang.
 *
 * MIÉRT: vakon a hívó azonosítása a hangból a leggyorsabb – meg sem kell
 * érinteni a telefont ahhoz, hogy tudd, ki keres. Ez a funkció a látó
 * felhasználóknak kényelem, neked információ.
 *
 * A hangot a telefonszámhoz kötjük (nem a névjegy azonosítójához), mert a
 * szám akkor is megvan, ha a névjegy még nincs elmentve, és a bejövő
 * híváskor is ez az, amit biztosan tudunk.
 */
object ContactRingtoneStore {

    private const val TAG = "ContactRingtone"
    private const val PREFS = "contact_ringtones"
    private const val KEY_MAP = "ringtone_map"

    /** Egy névjegyhez rendelt hang. */
    data class Entry(val phone: String, val uri: String, val title: String)

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /**
     * A telefonszám normalizált alakja: csak a számjegyek, és csak az utolsó
     * 9 (a körzet/ország előhívó nélkül). Így a +36301234567 és a 06301234567
     * ugyanaz a szám marad.
     */
    private fun normalize(phone: String): String {
        val digits = phone.filter { it.isDigit() }
        return if (digits.length > 9) digits.takeLast(9) else digits
    }

    /** A névjegyhez rendelt hang, vagy null ha nincs egyéni. */
    fun getForPhone(context: Context, phone: String): Entry? {
        val key = normalize(phone)
        if (key.isBlank()) return null
        return try {
            val raw = prefs(context).getString(KEY_MAP, null) ?: return null
            val obj = JSONObject(raw)
            val item = obj.optJSONObject(key) ?: return null
            Entry(
                phone = phone,
                uri = item.optString("uri").ifBlank { return null },
                title = item.optString("title", "Egyéni hang")
            )
        } catch (e: Exception) {
            Log.w(TAG, "getForPhone failed", e)
            null
        }
    }

    /** Van-e egyéni hang ehhez a számhoz. */
    fun hasCustom(context: Context, phone: String): Boolean =
        getForPhone(context, phone) != null

    /** Egyéni hang beállítása. */
    fun set(context: Context, phone: String, uri: String, title: String): Boolean {
        val key = normalize(phone)
        if (key.isBlank()) return false
        return try {
            val raw = prefs(context).getString(KEY_MAP, null)
            val obj = if (raw != null) JSONObject(raw) else JSONObject()
            obj.put(
                key,
                JSONObject().apply {
                    put("uri", uri)
                    put("title", title)
                }
            )
            prefs(context).edit().putString(KEY_MAP, obj.toString()).apply()
            true
        } catch (e: Exception) {
            Log.w(TAG, "set failed", e)
            false
        }
    }

    /** Egyéni hang törlése (visszaáll az alapértelmezett csengőhangra). */
    fun clear(context: Context, phone: String): Boolean {
        val key = normalize(phone)
        if (key.isBlank()) return false
        return try {
            val raw = prefs(context).getString(KEY_MAP, null) ?: return false
            val obj = JSONObject(raw)
            if (!obj.has(key)) return false
            obj.remove(key)
            prefs(context).edit().putString(KEY_MAP, obj.toString()).apply()
            true
        } catch (e: Exception) {
            Log.w(TAG, "clear failed", e)
            false
        }
    }

    /** Az összes egyéni hang (a portál listájához). */
    fun getAll(context: Context): List<Entry> = try {
        val raw = prefs(context).getString(KEY_MAP, null)
        if (raw == null) {
            emptyList()
        } else {
            val obj = JSONObject(raw)
            obj.keys().asSequence().mapNotNull { key ->
                val item = obj.optJSONObject(key) ?: return@mapNotNull null
                Entry(
                    phone = key,
                    uri = item.optString("uri").ifBlank { return@mapNotNull null },
                    title = item.optString("title", "Egyéni hang")
                )
            }.toList()
        }
    } catch (e: Exception) {
        Log.w(TAG, "getAll failed", e)
        emptyList()
    }
}
