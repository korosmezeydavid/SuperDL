package com.superdl.launcher.medication

import android.content.Context
import android.util.Log
import com.superdl.launcher.storage.JsonPrefsHelper
import org.json.JSONArray
import org.json.JSONObject

object MedicationStore {

    private const val TAG = "SuperDL.MedicationStore"
    private const val PREFS = "superdl"
    private const val KEY_REMINDERS = "medication_reminders"
    private const val KEY_HISTORY = "medication_ingestion_history"
    private const val KEY_REMINDERS_SCHEMA = "medication_reminders_schema"
    private const val KEY_HISTORY_SCHEMA = "medication_history_schema"
    private const val SCHEMA_VERSION = 1
    const val MAX_REMINDERS = 48
    private const val MAX_HISTORY = 500

    fun getAll(context: Context): List<MedicationReminder> {
        val array = JsonPrefsHelper.readJsonArray(
            context = context,
            prefsName = PREFS,
            dataKey = KEY_REMINDERS,
            schemaVersionKey = KEY_REMINDERS_SCHEMA,
            currentSchemaVersion = SCHEMA_VERSION,
            migrate = ::migrateReminders
        )
        val list = mutableListOf<MedicationReminder>()
        for (i in 0 until array.length()) {
            parseReminder(array.optJSONObject(i))?.let { list.add(it) }
        }
        return list.sortedWith(compareBy({ it.hour }, { it.minute }, { it.name.lowercase() }))
    }

    fun getEnabled(context: Context): List<MedicationReminder> =
        getAll(context).filter { it.enabled }

    fun getById(context: Context, id: Int): MedicationReminder? =
        getAll(context).firstOrNull { it.id == id }

    fun getDueAt(context: Context, hour: Int, minute: Int): List<MedicationReminder> {
        val dayOfWeek = java.util.Calendar.getInstance().get(java.util.Calendar.DAY_OF_WEEK)
        return getEnabled(context).filter {
            it.hour == hour && it.minute == minute && it.shouldFireOn(dayOfWeek)
        }
    }

    fun add(
        context: Context,
        name: String,
        hour: Int,
        minute: Int,
        cycleType: MedicationCycleType,
        weekDays: Set<Int>,
        courseEndMillis: Long? = null
    ): MedicationReminder? {
        val reminders = getAll(context).toMutableList()
        if (reminders.size >= MAX_REMINDERS) return null
        val normalizedDays = normalizeWeekDays(cycleType, weekDays)
        if (cycleType != MedicationCycleType.DAILY && normalizedDays.isEmpty()) return null
        val nextId = (reminders.maxOfOrNull { it.id } ?: 0) + 1
        val entry = MedicationReminder(
            id = nextId,
            name = name.trim(),
            hour = hour,
            minute = minute,
            cycleType = cycleType,
            weekDays = normalizedDays,
            enabled = true,
            courseEndMillis = courseEndMillis
        )
        reminders.add(entry)
        saveAll(context, reminders)
        return entry
    }

    /**
     * Több napszakot vesz fel egyszerre ugyanahhoz a gyógyszerhez (pl. reggel,
     * dél, este). Minden napszakból külön emlékeztető lesz, azonos névvel és
     * kúra-véggel. A sikeresen felvett emlékeztetőket adja vissza.
     */
    fun addMultipleTimes(
        context: Context,
        name: String,
        times: List<Pair<Int, Int>>,
        cycleType: MedicationCycleType,
        weekDays: Set<Int>,
        courseEndMillis: Long? = null
    ): List<MedicationReminder> {
        val added = mutableListOf<MedicationReminder>()
        for ((h, m) in times) {
            val entry = add(context, name, h, m, cycleType, weekDays, courseEndMillis)
            if (entry != null) added.add(entry)
        }
        return added
    }

    fun delete(context: Context, id: Int): MedicationReminder? {
        val reminders = getAll(context).toMutableList()
        val removed = reminders.firstOrNull { it.id == id } ?: return null
        reminders.removeAll { it.id == id }
        saveAll(context, reminders)
        return removed
    }

    /** Egy emlékeztető be- vagy kikapcsolása (pl. lejárt kúránál automatikusan). */
    fun setEnabled(context: Context, id: Int, enabled: Boolean): MedicationReminder? {
        val reminders = getAll(context).toMutableList()
        val index = reminders.indexOfFirst { it.id == id }
        if (index < 0) return null
        val updated = reminders[index].copy(enabled = enabled)
        reminders[index] = updated
        saveAll(context, reminders)
        return updated
    }

    fun logIngestion(context: Context, reminders: List<MedicationReminder>) {
        if (reminders.isEmpty()) return
        val takenAt = System.currentTimeMillis()
        val history = getIngestionHistory(context).toMutableList()
        reminders.forEach { reminder ->
            history.add(
                MedicationIngestionLog(
                    reminderId = reminder.id,
                    medicationName = reminder.name,
                    takenAtMillis = takenAt
                )
            )
        }
        val trimmed = history.takeLast(MAX_HISTORY)
        saveHistory(context, trimmed)
    }

    fun getIngestionHistory(context: Context): List<MedicationIngestionLog> {
        val array = JsonPrefsHelper.readJsonArray(
            context = context,
            prefsName = PREFS,
            dataKey = KEY_HISTORY,
            schemaVersionKey = KEY_HISTORY_SCHEMA,
            currentSchemaVersion = SCHEMA_VERSION
        )
        val list = mutableListOf<MedicationIngestionLog>()
        for (i in 0 until array.length()) {
            try {
                val obj = array.getJSONObject(i)
                list.add(
                    MedicationIngestionLog(
                        reminderId = obj.getInt("reminderId"),
                        medicationName = obj.optString("medicationName", ""),
                        takenAtMillis = obj.getLong("takenAtMillis")
                    )
                )
            } catch (e: Exception) {
                Log.w(TAG, "Skipping corrupted history entry at index $i", e)
            }
        }
        return list
    }

    private fun migrateReminders(legacy: JSONArray): JSONArray {
        val migrated = JSONArray()
        for (i in 0 until legacy.length()) {
            val obj = legacy.optJSONObject(i) ?: continue
            migrated.put(obj)
        }
        Log.i(TAG, "Migrated ${migrated.length()} medication reminders to schema $SCHEMA_VERSION")
        return migrated
    }

    private fun parseReminder(obj: JSONObject?): MedicationReminder? {
        if (obj == null) return null
        return try {
            val weekDays = mutableSetOf<Int>()
            val daysArray = obj.optJSONArray("weekDays")
            if (daysArray != null) {
                for (j in 0 until daysArray.length()) {
                    weekDays.add(daysArray.getInt(j))
                }
            }
            val cycleType = parseCycleType(obj.optString("cycleType", MedicationCycleType.DAILY.name))
            val courseEnd = if (obj.has("courseEndMillis")) obj.optLong("courseEndMillis") else null
            MedicationReminder(
                id = obj.getInt("id"),
                name = obj.optString("name", ""),
                hour = obj.getInt("hour"),
                minute = obj.getInt("minute"),
                cycleType = cycleType,
                weekDays = weekDays,
                enabled = obj.optBoolean("enabled", true),
                courseEndMillis = courseEnd
            )
        } catch (e: Exception) {
            Log.w(TAG, "Skipping corrupted medication reminder entry", e)
            null
        }
    }

    private fun parseCycleType(raw: String): MedicationCycleType =
        MedicationCycleType.entries.firstOrNull { it.name == raw } ?: MedicationCycleType.DAILY

    private fun normalizeWeekDays(cycleType: MedicationCycleType, weekDays: Set<Int>): Set<Int> =
        when (cycleType) {
            MedicationCycleType.DAILY -> emptySet()
            MedicationCycleType.WEEKLY -> weekDays.take(1).toSet()
            MedicationCycleType.CUSTOM -> weekDays
        }

    private fun saveAll(context: Context, reminders: List<MedicationReminder>) {
        val array = JSONArray()
        reminders.forEach { entry ->
            array.put(JSONObject().apply {
                put("id", entry.id)
                put("name", entry.name)
                put("hour", entry.hour)
                put("minute", entry.minute)
                put("cycleType", entry.cycleType.name)
                put("weekDays", JSONArray(entry.weekDays.toList()))
                put("enabled", entry.enabled)
                entry.courseEndMillis?.let { put("courseEndMillis", it) }
            })
        }
        JsonPrefsHelper.saveJsonArray(
            context,
            PREFS,
            KEY_REMINDERS,
            KEY_REMINDERS_SCHEMA,
            SCHEMA_VERSION,
            array
        )
    }

    private fun saveHistory(context: Context, history: List<MedicationIngestionLog>) {
        val array = JSONArray()
        history.forEach { entry ->
            array.put(JSONObject().apply {
                put("reminderId", entry.reminderId)
                put("medicationName", entry.medicationName)
                put("takenAtMillis", entry.takenAtMillis)
            })
        }
        JsonPrefsHelper.saveJsonArray(
            context,
            PREFS,
            KEY_HISTORY,
            KEY_HISTORY_SCHEMA,
            SCHEMA_VERSION,
            array
        )
    }
}