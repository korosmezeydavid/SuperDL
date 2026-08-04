package com.superdl.launcher.book

import android.content.Context
import com.superdl.launcher.storage.JsonPrefsHelper
import org.json.JSONArray
import org.json.JSONObject

object BookStore {

    private const val PREFS = "superdl"
    private const val KEY_POSITIONS = "book_positions"
    private const val KEY_RECENT = "book_recent"
    private const val KEY_BOOKMARKS = "book_bookmarks"
    private const val KEY_CUSTOM_FOLDERS = "book_custom_folders"
    private const val KEY_POSITIONS_SCHEMA = "book_positions_schema"
    private const val KEY_RECENT_SCHEMA = "book_recent_schema"
    private const val KEY_BOOKMARKS_SCHEMA = "book_bookmarks_schema"
    private const val KEY_CUSTOM_FOLDERS_SCHEMA = "book_custom_folders_schema"
    private const val SCHEMA_VERSION = 1
    private const val MAX_RECENT = 20
    private const val MAX_BOOKMARKS = 100
    private const val MAX_CUSTOM_FOLDERS = 5

    fun getPosition(context: Context, bookPath: String): Int {
        val obj = readPositions(context)
        return obj.optInt(bookPath, 0)
    }

    fun savePosition(context: Context, bookPath: String, charOffset: Int) {
        val obj = readPositions(context)
        obj.put(bookPath, charOffset.coerceAtLeast(0))
        JsonPrefsHelper.saveJsonObject(
            context, PREFS, KEY_POSITIONS, KEY_POSITIONS_SCHEMA, SCHEMA_VERSION, obj
        )
        touchRecent(context, bookPath)
    }

    fun getRecentPaths(context: Context): List<String> {
        val list = mutableListOf<String>()
        val array = JsonPrefsHelper.readJsonArray(
            context, PREFS, KEY_RECENT, KEY_RECENT_SCHEMA, SCHEMA_VERSION
        )
        for (i in 0 until array.length()) {
            val path = array.optString(i, "")
            if (path.isNotBlank()) list.add(path)
        }
        return list
    }

    fun touchRecent(context: Context, bookPath: String) {
        val current = getRecentPaths(context).toMutableList()
        current.removeAll { it == bookPath }
        current.add(0, bookPath)
        while (current.size > MAX_RECENT) current.removeLast()
        val array = JSONArray()
        current.forEach { array.put(it) }
        JsonPrefsHelper.saveJsonArray(
            context, PREFS, KEY_RECENT, KEY_RECENT_SCHEMA, SCHEMA_VERSION, array
        )
    }

    fun getBookmarks(context: Context, bookPath: String? = null): List<BookBookmark> {
        val list = mutableListOf<BookBookmark>()
        val array = JsonPrefsHelper.readJsonArray(
            context, PREFS, KEY_BOOKMARKS, KEY_BOOKMARKS_SCHEMA, SCHEMA_VERSION
        )
        for (i in 0 until array.length()) {
            val obj = array.getJSONObject(i)
            val path = obj.getString("bookPath")
            if (bookPath != null && path != bookPath) continue
            list.add(
                BookBookmark(
                    id = obj.getInt("id"),
                    bookPath = path,
                    bookTitle = obj.optString("bookTitle", ""),
                    charOffset = obj.getInt("charOffset"),
                    preview = obj.optString("preview", ""),
                    createdAt = obj.optLong("createdAt", 0L)
                )
            )
        }
        return list.sortedByDescending { it.createdAt }
    }

    fun addBookmark(
        context: Context,
        bookPath: String,
        bookTitle: String,
        charOffset: Int,
        preview: String
    ): BookBookmark? {
        val bookmarks = getBookmarks(context).toMutableList()
        if (bookmarks.size >= MAX_BOOKMARKS) return null
        val nextId = (bookmarks.maxOfOrNull { it.id } ?: 0) + 1
        val entry = BookBookmark(
            id = nextId,
            bookPath = bookPath,
            bookTitle = bookTitle,
            charOffset = charOffset.coerceAtLeast(0),
            preview = preview.trim(),
            createdAt = System.currentTimeMillis()
        )
        bookmarks.add(entry)
        saveBookmarks(context, bookmarks)
        return entry
    }

    fun deleteBookmark(context: Context, id: Int): BookBookmark? {
        val bookmarks = getBookmarks(context).toMutableList()
        val removed = bookmarks.firstOrNull { it.id == id } ?: return null
        bookmarks.removeAll { it.id == id }
        saveBookmarks(context, bookmarks)
        return removed
    }

    fun getCustomFolders(context: Context): List<String> {
        val list = mutableListOf<String>()
        val array = JsonPrefsHelper.readJsonArray(
            context, PREFS, KEY_CUSTOM_FOLDERS, KEY_CUSTOM_FOLDERS_SCHEMA, SCHEMA_VERSION
        )
        for (i in 0 until array.length()) {
            val path = array.optString(i, "")
            if (path.isNotBlank()) list.add(path)
        }
        return list
    }

    fun addCustomFolder(context: Context, path: String): Boolean {
        val folders = getCustomFolders(context).toMutableList()
        if (path in folders) return true
        if (folders.size >= MAX_CUSTOM_FOLDERS) return false
        folders.add(path)
        saveCustomFolders(context, folders)
        return true
    }

    fun clearCustomFolders(context: Context) {
        saveCustomFolders(context, emptyList())
    }

    private fun readPositions(context: Context): JSONObject =
        JsonPrefsHelper.readJsonObject(
            context, PREFS, KEY_POSITIONS, KEY_POSITIONS_SCHEMA, SCHEMA_VERSION
        )

    private fun saveCustomFolders(context: Context, folders: List<String>) {
        val array = JSONArray()
        folders.forEach { array.put(it) }
        JsonPrefsHelper.saveJsonArray(
            context, PREFS, KEY_CUSTOM_FOLDERS, KEY_CUSTOM_FOLDERS_SCHEMA, SCHEMA_VERSION, array
        )
    }

    private fun saveBookmarks(context: Context, bookmarks: List<BookBookmark>) {
        val array = JSONArray()
        bookmarks.forEach { b ->
            array.put(JSONObject().apply {
                put("id", b.id)
                put("bookPath", b.bookPath)
                put("bookTitle", b.bookTitle)
                put("charOffset", b.charOffset)
                put("preview", b.preview)
                put("createdAt", b.createdAt)
            })
        }
        JsonPrefsHelper.saveJsonArray(
            context, PREFS, KEY_BOOKMARKS, KEY_BOOKMARKS_SCHEMA, SCHEMA_VERSION, array
        )
    }
}