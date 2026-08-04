package com.superdl.launcher.gps

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import kotlin.math.abs

object SavedPoiStore {

    private const val PREFS = "superdl"
    private const val KEY = "saved_pois"
    private const val COORD_EPSILON = 0.00005

    fun getAll(context: Context): List<SavedPoi> =
        loadRaw(context).sortedByDescending { it.savedAtMs }

    fun add(
        context: Context,
        name: String,
        latitude: Double,
        longitude: Double,
        category: String = "mentett"
    ): SavedPoi? {
        val trimmedName = name.trim()
        if (trimmedName.isBlank()) return null
        val current = loadRaw(context).toMutableList()
        if (current.any { near(it.latitude, it.longitude, latitude, longitude) }) return null
        val entry = SavedPoi(
            id = UUID.randomUUID().toString(),
            name = trimmedName,
            latitude = latitude,
            longitude = longitude,
            category = category
        )
        current.add(entry)
        save(context, current)
        return entry
    }

    fun remove(context: Context, id: String): Boolean {
        val current = loadRaw(context)
        val updated = current.filterNot { it.id == id }
        if (updated.size == current.size) return false
        save(context, updated)
        return true
    }

    /** Beállítja vagy törli (null) egy mentett ponthoz tartozó hangjegyzet útvonalát. */
    fun updateVoiceNote(context: Context, id: String, voiceNotePath: String?): SavedPoi? {
        val current = loadRaw(context).toMutableList()
        val index = current.indexOfFirst { it.id == id }
        if (index < 0) return null
        val updated = current[index].copy(voiceNotePath = voiceNotePath)
        current[index] = updated
        save(context, current)
        return updated
    }

    fun getById(context: Context, id: String): SavedPoi? =
        loadRaw(context).firstOrNull { it.id == id }

    fun containsCoords(context: Context, latitude: Double, longitude: Double): Boolean =
        loadRaw(context).any { near(it.latitude, it.longitude, latitude, longitude) }

    private fun near(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Boolean =
        abs(lat1 - lat2) < COORD_EPSILON && abs(lon1 - lon2) < COORD_EPSILON

    private fun loadRaw(context: Context): List<SavedPoi> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY, null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val item = array.getJSONObject(i)
                    val name = item.optString("name").trim()
                    val lat = item.optDouble("latitude")
                    val lon = item.optDouble("longitude")
                    if (name.isBlank()) continue
                    add(
                        SavedPoi(
                            id = item.optString("id", UUID.randomUUID().toString()),
                            name = name,
                            latitude = lat,
                            longitude = lon,
                            category = item.optString("category", "mentett"),
                            savedAtMs = item.optLong("savedAtMs", System.currentTimeMillis()),
                            voiceNotePath = item.optString("voiceNotePath", "").ifBlank { null }
                        )
                    )
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun save(context: Context, pois: List<SavedPoi>) {
        val array = JSONArray()
        pois.forEach { poi ->
            array.put(
                JSONObject()
                    .put("id", poi.id)
                    .put("name", poi.name)
                    .put("latitude", poi.latitude)
                    .put("longitude", poi.longitude)
                    .put("category", poi.category)
                    .put("savedAtMs", poi.savedAtMs)
                    .put("voiceNotePath", poi.voiceNotePath ?: "")
            )
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY, array.toString())
            .apply()
    }
}