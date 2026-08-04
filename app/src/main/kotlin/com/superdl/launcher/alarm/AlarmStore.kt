package com.superdl.launcher.alarm

import android.content.Context
import com.superdl.launcher.storage.JsonPrefsHelper
import org.json.JSONArray
import org.json.JSONObject

object AlarmStore {

    private const val PREFS = "superdl"
    private const val KEY_ALARMS = "alarms"
    private const val KEY_ALARMS_SCHEMA = "alarms_schema"
    private const val SCHEMA_VERSION = 2
    private const val MAX_ALARMS = 12

    fun getAll(context: Context): List<AlarmEntry> {
        val list = mutableListOf<AlarmEntry>()
        val array = JsonPrefsHelper.readJsonArray(
            context = context,
            prefsName = PREFS,
            dataKey = KEY_ALARMS,
            schemaVersionKey = KEY_ALARMS_SCHEMA,
            currentSchemaVersion = SCHEMA_VERSION
        )
        for (i in 0 until array.length()) {
            val obj = array.getJSONObject(i)
            val repeatType = try {
                AlarmRepeatType.valueOf(obj.optString("repeatType", AlarmRepeatType.ONCE.name))
            } catch (_: Exception) {
                AlarmRepeatType.ONCE
            }
            val days = mutableSetOf<Int>()
            obj.optJSONArray("weekDays")?.let { arr ->
                for (j in 0 until arr.length()) days.add(arr.getInt(j))
            }
            list.add(
                AlarmEntry(
                    id = obj.getInt("id"),
                    hour = obj.getInt("hour"),
                    minute = obj.getInt("minute"),
                    label = obj.optString("label", ""),
                    enabled = obj.optBoolean("enabled", true),
                    repeatType = repeatType,
                    weekDays = days,
                    toneUri = obj.optString("toneUri", "").ifBlank { null },
                    toneTitle = obj.optString("toneTitle", "").ifBlank { null },
                    snoozeEnabled = obj.optBoolean("snoozeEnabled", true),
                    skipRemaining = obj.optInt("skipRemaining", 0)
                )
            )
        }
        return list.sortedWith(compareBy({ it.hour }, { it.minute }))
    }

    fun getEnabled(context: Context): List<AlarmEntry> =
        getAll(context).filter { it.enabled }

    /**
     * Kihagyás beállítása több ébresztőre egyszerre.
     * @param ids a kiválasztott ébresztők azonosítói
     * @param count hány következő ébresztést hagyjon ki mindegyik (0 = kihagyás vége)
     */
    fun setSkip(context: Context, ids: Set<Int>, count: Int): List<AlarmEntry> {
        val updated = getAll(context).map { entry ->
            if (entry.id in ids) entry.copy(skipRemaining = count.coerceAtLeast(0)) else entry
        }
        save(context, updated)
        return updated.filter { it.id in ids }
    }

    /**
     * Egy kihagyás "elhasználása": a megadott ébresztő számlálóját eggyel
     * csökkenti. Az ébresztő megszólalásakor hívjuk, ha épp kihagyás van
     * érvényben.
     *
     * @return a hátralévő kihagyások száma a csökkentés UTÁN
     */
    fun consumeSkip(context: Context, id: Int): Int {
        var left = 0
        val updated = getAll(context).map { entry ->
            if (entry.id == id && entry.skipRemaining > 0) {
                left = entry.skipRemaining - 1
                entry.copy(skipRemaining = left)
            } else entry
        }
        save(context, updated)
        return left
    }

    /** Minden kihagyás törlése (azonnal visszakapcsol mindent). */
    fun clearAllSkips(context: Context): Int {
        val all = getAll(context)
        val affected = all.count { it.skipRemaining > 0 }
        if (affected > 0) save(context, all.map { it.copy(skipRemaining = 0) })
        return affected
    }

    fun add(
        context: Context,
        hour: Int,
        minute: Int,
        label: String,
        repeatType: AlarmRepeatType = AlarmRepeatType.ONCE,
        weekDays: Set<Int> = emptySet(),
        toneUri: String? = null,
        toneTitle: String? = null,
        snoozeEnabled: Boolean = true
    ): AlarmEntry? {
        val alarms = getAll(context).toMutableList()
        if (alarms.size >= MAX_ALARMS) return null
        val nextId = (alarms.maxOfOrNull { it.id } ?: 0) + 1
        val entry = AlarmEntry(
            id = nextId,
            hour = hour,
            minute = minute,
            label = label,
            enabled = true,
            repeatType = repeatType,
            weekDays = weekDays,
            toneUri = toneUri,
            toneTitle = toneTitle,
            snoozeEnabled = snoozeEnabled
        )
        alarms.add(entry)
        save(context, alarms)
        return entry
    }

    fun setEnabled(context: Context, id: Int, enabled: Boolean): AlarmEntry? {
        val alarms = getAll(context).toMutableList()
        val index = alarms.indexOfFirst { it.id == id }
        if (index < 0) return null
        val updated = alarms[index].copy(enabled = enabled)
        alarms[index] = updated
        save(context, alarms)
        return updated
    }

    /** Egy ébresztő hangjának módosítása (a listából). */
    fun updateTone(context: Context, id: Int, toneUri: String?, toneTitle: String?): AlarmEntry? {
        val alarms = getAll(context).toMutableList()
        val index = alarms.indexOfFirst { it.id == id }
        if (index < 0) return null
        val updated = alarms[index].copy(toneUri = toneUri, toneTitle = toneTitle)
        alarms[index] = updated
        save(context, alarms)
        return updated
    }

    fun delete(context: Context, id: Int): AlarmEntry? {
        val alarms = getAll(context).toMutableList()
        val removed = alarms.firstOrNull { it.id == id } ?: return null
        alarms.removeAll { it.id == id }
        save(context, alarms)
        return removed
    }

    fun getNextAlarm(context: Context): AlarmEntry? {
        val nowMinutes = java.util.Calendar.getInstance().let { it.get(java.util.Calendar.HOUR_OF_DAY) * 60 + it.get(java.util.Calendar.MINUTE) }
        val enabled = getEnabled(context)
        val todayUpcoming = enabled.filter { it.hour * 60 + it.minute > nowMinutes }
        if (todayUpcoming.isNotEmpty()) return todayUpcoming.minBy { it.hour * 60 + it.minute }
        return enabled.minByOrNull { it.hour * 60 + it.minute }
    }

    private fun save(context: Context, alarms: List<AlarmEntry>) {
        val array = JSONArray()
        alarms.forEach { entry ->
            array.put(JSONObject().apply {
                put("id", entry.id)
                put("hour", entry.hour)
                put("minute", entry.minute)
                put("label", entry.label)
                put("enabled", entry.enabled)
                put("repeatType", entry.repeatType.name)
                put("weekDays", JSONArray(entry.weekDays.toList()))
                entry.toneUri?.let { put("toneUri", it) }
                entry.toneTitle?.let { put("toneTitle", it) }
                put("snoozeEnabled", entry.snoozeEnabled)
                put("skipRemaining", entry.skipRemaining)
            })
        }
        JsonPrefsHelper.saveJsonArray(
            context,
            PREFS,
            KEY_ALARMS,
            KEY_ALARMS_SCHEMA,
            SCHEMA_VERSION,
            array
        )
    }
}