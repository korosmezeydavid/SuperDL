package com.superdl.launcher.favorites

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

object FavoritesStore {

    private const val PREFS = "superdl"
    private const val KEY = "favorite_contacts"

    fun getAll(context: Context): List<FavoriteEntry> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY, null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val item = array.getJSONObject(i)
                    val phone = normalizePhone(item.optString("phone"))
                    val name = item.optString("name").trim()
                    if (phone.isNotBlank()) add(FavoriteEntry(name, phone))
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun add(context: Context, name: String, phone: String): Boolean {
        val normalized = normalizePhone(phone)
        if (normalized.isBlank()) return false
        val current = getAll(context).toMutableList()
        if (current.any { normalizePhone(it.phone) == normalized }) return false
        current.add(FavoriteEntry(name.trim().ifBlank { normalized }, normalized))
        save(context, current)
        return true
    }

    fun remove(context: Context, phone: String): Boolean {
        val normalized = normalizePhone(phone)
        val current = getAll(context)
        val updated = current.filterNot { normalizePhone(it.phone) == normalized }
        if (updated.size == current.size) return false
        save(context, updated)
        return true
    }

    fun contains(context: Context, phone: String): Boolean {
        val normalized = normalizePhone(phone)
        return getAll(context).any { normalizePhone(it.phone) == normalized }
    }

    private fun save(context: Context, favorites: List<FavoriteEntry>) {
        val array = JSONArray()
        favorites.forEach { favorite ->
            array.put(
                JSONObject()
                    .put("name", favorite.name)
                    .put("phone", favorite.phone)
            )
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY, array.toString())
            .apply()
    }

    private fun normalizePhone(phone: String): String =
        phone.replace(" ", "").trim()
}