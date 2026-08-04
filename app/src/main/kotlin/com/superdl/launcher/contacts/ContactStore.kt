package com.superdl.launcher.contacts

import android.content.Context
import com.superdl.launcher.storage.JsonPrefsHelper
import org.json.JSONArray
import org.json.JSONObject

object ContactStore {

    private const val PREFS = "superdl"
    private const val KEY_CONTACTS = "contact_book_cache"
    private const val KEY_SCHEMA = "contact_book_cache_schema"
    private const val KEY_LAST_SYNC = "contact_book_last_sync_ms"
    private const val SCHEMA_VERSION = 1
    private const val ONE_DAY_MS = 24 * 60 * 60 * 1000L

    fun getCached(context: Context): List<ContactMatch> {
        val array = JsonPrefsHelper.readJsonArray(
            context = context,
            prefsName = PREFS,
            dataKey = KEY_CONTACTS,
            schemaVersionKey = KEY_SCHEMA,
            currentSchemaVersion = SCHEMA_VERSION
        )
        val list = mutableListOf<ContactMatch>()
        for (i in 0 until array.length()) {
            parseContact(array.optJSONObject(i))?.let { list.add(it) }
        }
        return list
    }

    fun save(context: Context, contacts: List<ContactMatch>, syncedAtMs: Long = System.currentTimeMillis()) {
        val array = JSONArray()
        contacts.forEach { contact ->
            array.put(
                JSONObject()
                    .put("id", contact.id)
                    .put("name", contact.name)
                    .put("phone", contact.phone)
            )
        }
        JsonPrefsHelper.saveJsonArray(context, PREFS, KEY_CONTACTS, KEY_SCHEMA, SCHEMA_VERSION, array)
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putLong(KEY_LAST_SYNC, syncedAtMs)
            .apply()
    }

    fun getLastSyncMs(context: Context): Long =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getLong(KEY_LAST_SYNC, 0L)

    fun needsDailySync(context: Context, nowMs: Long = System.currentTimeMillis()): Boolean {
        val last = getLastSyncMs(context)
        return last == 0L || nowMs - last >= ONE_DAY_MS
    }

    fun speakLastSync(context: Context): String {
        val last = getLastSyncMs(context)
        if (last == 0L) return "Még nem volt szinkronizálás."
        val hours = ((System.currentTimeMillis() - last) / 3_600_000).toInt()
        return when {
            hours < 1 -> "Utolsó szinkron: kevesebb mint egy órája."
            hours < 24 -> "Utolsó szinkron: $hours órája."
            else -> "Utolsó szinkron: több mint egy napja."
        }
    }

    private fun parseContact(obj: JSONObject?): ContactMatch? {
        if (obj == null) return null
        val id = obj.optString("id", "").trim()
        val name = obj.optString("name", "").trim()
        val phone = obj.optString("phone", "").trim()
        if (id.isBlank() || name.isBlank() || phone.isBlank()) return null
        return ContactMatch(id, name, phone)
    }
}