package com.superdl.launcher.apps

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

object FavoriteAppsStore {

    private const val PREFS = "superdl"
    private const val KEY = "favorite_apps"

    fun getAll(context: Context): List<FavoriteAppEntry> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY, null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val item = array.getJSONObject(i)
                    val type = runCatching {
                        FavoriteAppType.valueOf(item.optString("type"))
                    }.getOrNull() ?: continue
                    val id = item.optString("id").trim()
                    val label = item.optString("label").trim()
                    if (id.isBlank() || label.isBlank()) continue
                    add(FavoriteAppEntry(type, id, label))
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun add(context: Context, entry: FavoriteAppEntry): Boolean {
        val current = getAll(context).toMutableList()
        if (current.any { it.type == entry.type && it.id == entry.id }) return false
        current.add(entry)
        save(context, current)
        return true
    }

    fun remove(context: Context, entry: FavoriteAppEntry): Boolean {
        val current = getAll(context)
        val updated = current.filterNot { it.type == entry.type && it.id == entry.id }
        if (updated.size == current.size) return false
        save(context, updated)
        return true
    }

    fun contains(context: Context, type: FavoriteAppType, id: String): Boolean {
        return getAll(context).any { it.type == type && it.id == id }
    }

    private fun save(context: Context, favorites: List<FavoriteAppEntry>) {
        val array = JSONArray()
        favorites.forEach { favorite ->
            array.put(
                JSONObject()
                    .put("type", favorite.type.name)
                    .put("id", favorite.id)
                    .put("label", favorite.label)
            )
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY, array.toString())
            .apply()
    }
}