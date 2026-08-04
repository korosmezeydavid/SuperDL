package com.superdl.launcher.transit

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import kotlin.math.abs

object TransitStopStore {

    private const val PREFS = "superdl"
    private const val KEY = "favorite_transit_stops"
    private const val COORD_EPSILON = 0.0002

    fun getAll(context: Context): List<FavoriteStop> =
        loadRaw(context).sortedBy { it.name.lowercase() }

    fun add(
        context: Context,
        name: String,
        latitude: Double?,
        longitude: Double?,
        stopId: String? = null,
        address: String = ""
    ): FavoriteStop? {
        val trimmedName = name.trim()
        if (trimmedName.isBlank()) return null
        val current = loadRaw(context).toMutableList()
        if (current.any { matches(it, trimmedName, latitude, longitude, stopId) }) return null
        val entry = FavoriteStop(
            id = UUID.randomUUID().toString(),
            name = trimmedName,
            latitude = latitude,
            longitude = longitude,
            stopId = stopId,
            address = address.ifBlank { trimmedName }
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

    fun isFavorite(context: Context, name: String, stopId: String? = null): Boolean =
        loadRaw(context).any { favorite ->
            favorite.name.equals(name, ignoreCase = true) ||
                (!stopId.isNullOrBlank() && favorite.stopId == stopId)
        }

    private fun matches(
        favorite: FavoriteStop,
        name: String,
        latitude: Double?,
        longitude: Double?,
        stopId: String?
    ): Boolean {
        if (!stopId.isNullOrBlank() && favorite.stopId == stopId) return true
        if (favorite.name.equals(name, ignoreCase = true)) return true
        if (latitude != null && longitude != null &&
            favorite.latitude != null && favorite.longitude != null
        ) {
            return abs(favorite.latitude - latitude) < COORD_EPSILON &&
                abs(favorite.longitude - longitude) < COORD_EPSILON
        }
        return false
    }

    private fun loadRaw(context: Context): List<FavoriteStop> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY, null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val item = array.optJSONObject(i) ?: continue
                    val name = item.optString("name").trim()
                    if (name.isBlank()) continue
                    add(
                        FavoriteStop(
                            id = item.optString("id", UUID.randomUUID().toString()),
                            name = name,
                            latitude = item.optDouble("latitude").takeIf { !it.isNaN() },
                            longitude = item.optDouble("longitude").takeIf { !it.isNaN() },
                            stopId = item.optString("stopId").ifBlank { null },
                            address = item.optString("address", name),
                            savedAtMs = item.optLong("savedAtMs", System.currentTimeMillis())
                        )
                    )
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun save(context: Context, stops: List<FavoriteStop>) {
        val array = JSONArray()
        stops.forEach { stop ->
            array.put(
                JSONObject()
                    .put("id", stop.id)
                    .put("name", stop.name)
                    .put("latitude", stop.latitude ?: JSONObject.NULL)
                    .put("longitude", stop.longitude ?: JSONObject.NULL)
                    .put("stopId", stop.stopId ?: "")
                    .put("address", stop.address)
                    .put("savedAtMs", stop.savedAtMs)
            )
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY, array.toString())
            .apply()
    }
}

data class FavoriteStop(
    val id: String,
    val name: String,
    val latitude: Double?,
    val longitude: Double?,
    val stopId: String?,
    val address: String,
    val savedAtMs: Long = System.currentTimeMillis()
)