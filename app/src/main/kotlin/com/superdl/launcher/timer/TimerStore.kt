package com.superdl.launcher.timer

import android.content.Context
import com.superdl.launcher.patrol.PatrolStore
import com.superdl.launcher.storage.JsonPrefsHelper
import org.json.JSONArray
import org.json.JSONObject

object TimerStore {

    private const val PREFS = "superdl"
    private const val KEY_TIMERS = "saved_timers"
    private const val KEY_TIMERS_SCHEMA = "saved_timers_schema"
    private const val SCHEMA_VERSION = 1
    private const val KEY_ACTIVE = "active_timer_session"
    const val MAX_TIMERS = 24
    const val MIN_DURATION_MINUTES = 1
    const val MAX_DURATION_MINUTES = 480

    val UNIT_OPTIONS = listOf(
        TimerUnitOption("Perc", multiplierMinutes = 1),
        TimerUnitOption("Óra", multiplierMinutes = 60)
    )

    fun getAll(context: Context): List<TimerEntry> {
        val list = mutableListOf<TimerEntry>()
        val array = JsonPrefsHelper.readJsonArray(
            context = context,
            prefsName = PREFS,
            dataKey = KEY_TIMERS,
            schemaVersionKey = KEY_TIMERS_SCHEMA,
            currentSchemaVersion = SCHEMA_VERSION
        )
        for (i in 0 until array.length()) {
            val obj = array.getJSONObject(i)
            list.add(
                TimerEntry(
                    id = obj.getInt("id"),
                    label = obj.optString("label", ""),
                    durationMinutes = obj.getInt("durationMinutes"),
                    announceIntervalMinutes = obj.getInt("announceIntervalMinutes")
                )
            )
        }
        return list.sortedBy { it.label.lowercase() }
    }

    fun getById(context: Context, id: Int): TimerEntry? =
        getAll(context).firstOrNull { it.id == id }

    fun add(
        context: Context,
        label: String,
        durationMinutes: Int,
        announceIntervalMinutes: Int
    ): TimerEntry? {
        val timers = getAll(context).toMutableList()
        if (timers.size >= MAX_TIMERS) return null
        val nextId = (timers.maxOfOrNull { it.id } ?: 0) + 1
        val entry = TimerEntry(nextId, label, durationMinutes, announceIntervalMinutes)
        timers.add(entry)
        saveAll(context, timers)
        return entry
    }

    fun update(
        context: Context,
        id: Int,
        label: String,
        durationMinutes: Int,
        announceIntervalMinutes: Int
    ): TimerEntry? {
        val timers = getAll(context).toMutableList()
        val index = timers.indexOfFirst { it.id == id }
        if (index < 0) return null
        val updated = TimerEntry(id, label, durationMinutes, announceIntervalMinutes)
        timers[index] = updated
        saveAll(context, timers)
        return updated
    }

    fun delete(context: Context, id: Int): TimerEntry? {
        val timers = getAll(context).toMutableList()
        val removed = timers.firstOrNull { it.id == id } ?: return null
        timers.removeAll { it.id == id }
        saveAll(context, timers)
        return removed
    }

    fun intervalOptionsFor(durationMinutes: Int): List<Int> {
        val short = listOf(1, 2, 3, 4, 5)
        val standard = PatrolStore.TIME_INTERVALS
        return (short + standard)
            .filter { it in 1..durationMinutes }
            .distinct()
            .sorted()
    }

    fun normalizeDuration(minutes: Int): Int =
        minutes.coerceIn(MIN_DURATION_MINUTES, MAX_DURATION_MINUTES)

    fun normalizeInterval(durationMinutes: Int, intervalMinutes: Int): Int {
        val options = intervalOptionsFor(durationMinutes)
        if (options.isEmpty()) return 1
        return options.minByOrNull { kotlin.math.abs(it - intervalMinutes) } ?: options.first()
    }

    fun getActiveSession(context: Context): ActiveTimerSession? {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_ACTIVE, null) ?: return null
        return try {
            val obj = JSONObject(raw)
            ActiveTimerSession(
                timerId = obj.getInt("timerId"),
                label = obj.optString("label", ""),
                durationMinutes = obj.getInt("durationMinutes"),
                announceIntervalMinutes = obj.getInt("announceIntervalMinutes"),
                startedAtMillis = obj.getLong("startedAtMillis"),
                lastAnnouncedElapsedMinutes = obj.optInt("lastAnnouncedElapsedMinutes", 0)
            )
        } catch (_: Exception) {
            null
        }
    }

    fun saveActiveSession(context: Context, session: ActiveTimerSession) {
        val obj = JSONObject().apply {
            put("timerId", session.timerId)
            put("label", session.label)
            put("durationMinutes", session.durationMinutes)
            put("announceIntervalMinutes", session.announceIntervalMinutes)
            put("startedAtMillis", session.startedAtMillis)
            put("lastAnnouncedElapsedMinutes", session.lastAnnouncedElapsedMinutes)
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_ACTIVE, obj.toString())
            .apply()
    }

    fun updateLastAnnounced(context: Context, elapsedMinutes: Int) {
        val session = getActiveSession(context) ?: return
        saveActiveSession(context, session.copy(lastAnnouncedElapsedMinutes = elapsedMinutes))
    }

    fun clearActiveSession(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .remove(KEY_ACTIVE)
            .apply()
    }

    private fun saveAll(context: Context, timers: List<TimerEntry>) {
        val array = JSONArray()
        timers.forEach { entry ->
            array.put(JSONObject().apply {
                put("id", entry.id)
                put("label", entry.label)
                put("durationMinutes", entry.durationMinutes)
                put("announceIntervalMinutes", entry.announceIntervalMinutes)
            })
        }
        JsonPrefsHelper.saveJsonArray(
            context,
            PREFS,
            KEY_TIMERS,
            KEY_TIMERS_SCHEMA,
            SCHEMA_VERSION,
            array
        )
    }
}

data class TimerUnitOption(
    val label: String,
    val multiplierMinutes: Int
)