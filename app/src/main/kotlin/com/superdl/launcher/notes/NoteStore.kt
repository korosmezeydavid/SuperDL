package com.superdl.launcher.notes

import android.content.Context
import com.superdl.launcher.storage.JsonPrefsHelper
import org.json.JSONArray
import org.json.JSONObject

object NoteStore {

    private const val PREFS = "superdl"
    private const val KEY_NOTES = "user_notes"
    private const val KEY_NOTES_SCHEMA = "user_notes_schema"
    private const val SCHEMA_VERSION = 1
    const val MAX_NOTES = 200
    const val MAX_BODY_CHARS = 500_000

    fun getAll(context: Context): List<NoteEntry> {
        val array = JsonPrefsHelper.readJsonArray(
            context = context,
            prefsName = PREFS,
            dataKey = KEY_NOTES,
            schemaVersionKey = KEY_NOTES_SCHEMA,
            currentSchemaVersion = SCHEMA_VERSION
        )
        val list = mutableListOf<NoteEntry>()
        for (i in 0 until array.length()) {
            parseNote(array.optJSONObject(i))?.let { list.add(it) }
        }
        return list.sortedByDescending { it.createdAt }
    }

    fun getById(context: Context, id: Int): NoteEntry? =
        getAll(context).firstOrNull { it.id == id }

    fun add(
        context: Context,
        title: String,
        body: String,
        sourceUrl: String? = null
    ): NoteEntry? {
        val trimmedTitle = title.trim().ifBlank { "Névtelen jegyzet" }
        val trimmedBody = body.trim()
        if (trimmedBody.isBlank()) return null
        val notes = getAll(context).toMutableList()
        if (notes.size >= MAX_NOTES) return null
        val nextId = (notes.maxOfOrNull { it.id } ?: 0) + 1
        val entry = NoteEntry(
            id = nextId,
            title = trimmedTitle,
            body = trimmedBody.take(MAX_BODY_CHARS),
            sourceUrl = sourceUrl?.trim()?.takeIf { it.isNotBlank() },
            createdAt = System.currentTimeMillis()
        )
        notes.add(0, entry)
        saveAll(context, notes)
        return entry
    }

    fun delete(context: Context, id: Int): NoteEntry? {
        val notes = getAll(context).toMutableList()
        val removed = notes.firstOrNull { it.id == id } ?: return null
        notes.removeAll { it.id == id }
        saveAll(context, notes)
        return removed
    }

    private fun parseNote(obj: JSONObject?): NoteEntry? {
        if (obj == null) return null
        val title = obj.optString("title", "").trim()
        val body = obj.optString("body", "").trim()
        if (body.isBlank()) return null
        return NoteEntry(
            id = obj.optInt("id", 0),
            title = title.ifBlank { "Névtelen jegyzet" },
            body = body,
            sourceUrl = obj.optString("sourceUrl", "").trim().ifBlank { null },
            createdAt = obj.optLong("createdAt", 0L)
        )
    }

    private fun saveAll(context: Context, notes: List<NoteEntry>) {
        val array = JSONArray()
        notes.forEach { note ->
            array.put(
                JSONObject()
                    .put("id", note.id)
                    .put("title", note.title)
                    .put("body", note.body)
                    .put("sourceUrl", note.sourceUrl.orEmpty())
                    .put("createdAt", note.createdAt)
            )
        }
        JsonPrefsHelper.saveJsonArray(
            context,
            PREFS,
            KEY_NOTES,
            KEY_NOTES_SCHEMA,
            SCHEMA_VERSION,
            array
        )
    }
}