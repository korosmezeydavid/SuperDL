package com.superdl.launcher.backup

import android.content.Context
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject

/**
 * A SuperDL beállításainak mentése és visszaállítása.
 *
 * MIÉRT KELL: 44 Store, mind SharedPreferences. Ha elveszik vagy elromlik a
 * telefon, MINDEN elveszik: a névjegyekhez rendelt csengőhangok, a gyógyszer-
 * emlékeztetők, a kedvencek, a mentett GPS útvonalak, a könyvjelzők, a hang-
 * beállítások. Ezt újra felépíteni vakon napok munkája.
 *
 * Ez teszi a SuperDL-t HORDOZHATÓVÁ: új telefon, egy fájl, és minden ott van.
 *
 * MIÉRT MŰKÖDIK ÁLTALÁNOSAN: minden Store ugyanazt a mintát követi
 * (JsonPrefsHelper: prefs-fájl + JSON string + séma-verzió), ezért nem kell a
 * 44 Store-t egyenként ismerni — elég a prefs-fájlokat kiolvasni. Így egy új
 * Store magától bekerül a mentésbe, külön munka nélkül.
 */
object BackupManager {

    private const val TAG = "SuperDL.Backup"

    const val FORMAT_VERSION = 1

    /**
     * Ezeket a prefs-fájlokat mentjük.
     *
     * SZÁNDÉKOSAN NEM automatikus a felderítés: a shared_prefs mappában idegen
     * fájlok is vannak (WebViewChromiumPrefs, mlkit, AwOriginVisitLogger), amik
     * nem a mieink — átvinni őket másik telefonra káros lenne.
     */
    private val INCLUDED_PREFS = listOf(
        "superdl",                    // a gyűjtő: ébresztők, gyógyszerek, jegyzetek, kedvencek...
        "contact_ringtones",          // névjegyenkénti csengőhang
        "bluetooth_assistant",
        "elena_wake_prefs",           // saját felébresztő mondatok
        "superdl_hearing_aid",
        "keyguard_pin_assist",
        "com.superdl.launcher_preferences",
        "com.superdl.launcher.debug_preferences"
    )

    /**
     * Ezek a kulcsok SOHA nem kerülnek a mentésbe.
     *
     * MIÉRT:
     *  - pin_hash / pin_salt: a zárolás jelszava. Másik telefonra átvinni
     *    biztonsági hiba lenne.
     *  - hotspot_last_known, battery_full_announced, day_greeting_last_date,
     *    phone_ringer_fixup: pillanatnyi vagy eszközfüggő állapot, nem beállítás.
     *
     * Az e-mail jelszó eleve nincs itt: az EncryptedSharedPreferences-ben van, a
     * kulcsa a telefon HARDVERÉBEN (Keystore). Másik telefonon értelmezhetetlen,
     * ezért ott újra be kell írni — ezt a visszaállításnál ki is mondjuk.
     */
    private val EXCLUDED_KEYS = listOf(
        "pin_hash",
        "pin_salt",
        "pin_lock_enabled",
        "hotspot_last_known_updated_at",
        "phone_ringer_fixup_v1",
        "battery_full_announced",
        "day_greeting_last_date"
    )

    data class Summary(
        val fileCount: Int,
        val keyCount: Int,
        val createdAt: Long
    ) {
        fun speak(): String = "A mentés $keyCount beállítást tartalmaz."
    }

    /** Mit talált a visszaállítás — ezt mondjuk ki a felhasználónak. */
    data class RestoreResult(
        val ok: Boolean,
        val message: String,
        val restoredKeys: Int = 0
    )

    /**
     * Mentés készítése.
     *
     * A formátum szándékosan egyszerű és olvasható JSON: ha valaha baj van,
     * kézzel is megnézhető, mi van benne. A típusokat megőrizzük, mert a
     * SharedPreferences típusos — egy Int-et String-ként visszaírni hibát okozna.
     */
    fun export(context: Context): JSONObject {
        val root = JSONObject()
        root.put("format", FORMAT_VERSION)
        root.put("created_at", System.currentTimeMillis())
        root.put("app_version", appVersion(context))
        root.put("device", android.os.Build.MODEL.orEmpty())

        val files = JSONObject()
        var keyCount = 0

        for (name in INCLUDED_PREFS) {
            try {
                val all = context.getSharedPreferences(name, Context.MODE_PRIVATE).all
                if (all.isEmpty()) continue

                val entries = JSONObject()
                for ((key, value) in all) {
                    if (key in EXCLUDED_KEYS) continue
                    val encoded = encodeValue(value) ?: continue
                    entries.put(key, encoded)
                    keyCount++
                }
                if (entries.length() > 0) files.put(name, entries)
            } catch (e: Exception) {
                Log.w(TAG, "export failed for $name", e)
            }
        }

        root.put("files", files)
        root.put("key_count", keyCount)
        return root
    }

    fun exportSummary(context: Context): Summary {
        val json = export(context)
        val files = json.optJSONObject("files") ?: JSONObject()
        return Summary(
            fileCount = files.length(),
            keyCount = json.optInt("key_count"),
            createdAt = json.optLong("created_at")
        )
    }

    /**
     * Visszaállítás.
     *
     * MIÉRT ELLENŐRIZ ENNYIT: egy hibás vagy idegen fájl visszaírása tönkretenné
     * a működő beállításokat. Inkább utasítsuk el, mint hogy fél-állapotot
     * hagyjunk. A visszaállítás MINDENT felülír, amit a fájl tartalmaz — ezért
     * a hívónak meg KELL erősíttetnie a felhasználóval.
     */
    fun restore(context: Context, jsonText: String): RestoreResult {
        val root = try {
            JSONObject(jsonText)
        } catch (e: Exception) {
            return RestoreResult(false, "A fájl nem érvényes mentés: nem olvasható JSON.")
        }

        val format = root.optInt("format", -1)
        if (format < 1) {
            return RestoreResult(false, "A fájl nem SuperDL mentés, vagy sérült.")
        }
        if (format > FORMAT_VERSION) {
            return RestoreResult(
                false,
                "Ez a mentés újabb SuperDL verzióból való (formátum $format). " +
                    "Frissítsd az alkalmazást, mielőtt visszaállítod."
            )
        }

        val files = root.optJSONObject("files")
            ?: return RestoreResult(false, "A mentés üres: nincs benne beállítás.")

        var restored = 0
        var failedFiles = 0

        val names = files.keys()
        while (names.hasNext()) {
            val prefsName = names.next()
            // Csak a saját fájljainkba írunk vissza — egy manipulált fájl nem
            // tehet kárt más alkalmazás vagy a rendszer beállításaiban.
            if (prefsName !in INCLUDED_PREFS) {
                Log.w(TAG, "skipping unknown prefs file: $prefsName")
                continue
            }
            val entries = files.optJSONObject(prefsName) ?: continue
            try {
                val editor = context.getSharedPreferences(prefsName, Context.MODE_PRIVATE).edit()
                val keys = entries.keys()
                while (keys.hasNext()) {
                    val key = keys.next()
                    if (key in EXCLUDED_KEYS) continue
                    val obj = entries.optJSONObject(key) ?: continue
                    if (writeValue(editor, key, obj)) restored++
                }
                editor.apply()
            } catch (e: Exception) {
                Log.w(TAG, "restore failed for $prefsName", e)
                failedFiles++
            }
        }

        if (restored == 0) {
            return RestoreResult(false, "A mentésből egyetlen beállítást sem sikerült visszaállítani.")
        }

        val base = "$restored beállítás visszaállítva."
        val tail = " Az e-mail jelszót újra be kell írni: az biztonsági okból " +
            "a telefon hardveréhez kötve tárolódik, ezért nem hordozható. " +
            "Az engedélyeket is újra meg kell adni: Beállítások, Beállítás varázsló. " +
            "Indítsd újra a SuperDL-t, hogy minden beállítás életbe lépjen."
        val warn = if (failedFiles > 0) " Figyelem: $failedFiles részt nem sikerült visszaállítani." else ""

        return RestoreResult(true, base + warn + tail, restored)
    }

    // ==================== Típusok ====================
    //
    // MIÉRT KELL TÍPUST TÁROLNI: a SharedPreferences típusos. Ha egy Int-et
    // String-ként írnánk vissza, a getInt() ClassCastException-t dobna, és a
    // funkció összeomlana — vagy ami rosszabb, csendben az alapértékre esne
    // vissza. Ezért minden érték mellé megy a típusa is.

    private fun encodeValue(value: Any?): JSONObject? = when (value) {
        is String -> JSONObject().put("t", "s").put("v", value)
        is Int -> JSONObject().put("t", "i").put("v", value)
        is Long -> JSONObject().put("t", "l").put("v", value)
        is Float -> JSONObject().put("t", "f").put("v", value.toDouble())
        is Boolean -> JSONObject().put("t", "b").put("v", value)
        is Set<*> -> {
            // A String-halmazokat (pl. több kiválasztott elem) is meg kell őrizni.
            val arr = JSONArray()
            value.filterIsInstance<String>().forEach { arr.put(it) }
            JSONObject().put("t", "ss").put("v", arr)
        }
        else -> null
    }

    private fun writeValue(
        editor: android.content.SharedPreferences.Editor,
        key: String,
        obj: JSONObject
    ): Boolean = try {
        when (obj.optString("t")) {
            "s" -> { editor.putString(key, obj.optString("v")); true }
            "i" -> { editor.putInt(key, obj.optInt("v")); true }
            "l" -> { editor.putLong(key, obj.optLong("v")); true }
            "f" -> { editor.putFloat(key, obj.optDouble("v").toFloat()); true }
            "b" -> { editor.putBoolean(key, obj.optBoolean("v")); true }
            "ss" -> {
                val arr = obj.optJSONArray("v") ?: JSONArray()
                val set = mutableSetOf<String>()
                for (i in 0 until arr.length()) set.add(arr.optString(i))
                editor.putStringSet(key, set)
                true
            }
            else -> false
        }
    } catch (e: Exception) {
        Log.w(TAG, "restore value failed for $key", e)
        false
    }

    private fun appVersion(context: Context): String = try {
        context.packageManager.getPackageInfo(context.packageName, 0).versionName.orEmpty()
    } catch (_: Exception) {
        ""
    }
}
