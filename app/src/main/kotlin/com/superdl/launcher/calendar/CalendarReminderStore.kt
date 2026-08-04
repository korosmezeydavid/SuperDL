package com.superdl.launcher.calendar

import android.content.Context
import org.json.JSONArray

object CalendarReminderStore {

    private const val PREFS = "superdl"
    private const val KEY_COMPLETED = "calendar_completed_instances"

    fun instanceKey(eventId: Long, beginMs: Long): String = "${eventId}_$beginMs"

    fun isCompleted(context: Context, eventId: Long, beginMs: Long): Boolean {
        val key = instanceKey(eventId, beginMs)
        return getCompletedKeys(context).contains(key)
    }

    fun markCompleted(context: Context, eventId: Long, beginMs: Long) {
        val keys = getCompletedKeys(context).toMutableSet()
        keys.add(instanceKey(eventId, beginMs))
        saveCompletedKeys(context, keys)
    }

    fun clearCompletedForEvent(context: Context, eventId: Long) {
        val prefix = "${eventId}_"
        val keys = getCompletedKeys(context).filterNot { it.startsWith(prefix) }.toSet()
        saveCompletedKeys(context, keys)
    }

    fun reminderRequestCode(eventId: Long, beginMs: Long): Int =
        (eventId xor beginMs).toInt()

    private fun getCompletedKeys(context: Context): Set<String> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_COMPLETED, null) ?: return emptySet()
        return try {
            val array = JSONArray(raw)
            buildSet {
                for (i in 0 until array.length()) {
                    val value = array.optString(i).trim()
                    if (value.isNotBlank()) add(value)
                }
            }
        } catch (_: Exception) {
            emptySet()
        }
    }

    private fun saveCompletedKeys(context: Context, keys: Set<String>) {
        val array = JSONArray()
        keys.sorted().forEach { array.put(it) }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_COMPLETED, array.toString())
            .apply()
    }
}