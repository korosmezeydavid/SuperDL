package com.superdl.launcher.train

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import kotlin.math.abs

object TrainStationStore {

    private const val PREFS = "superdl"
    private const val KEY = "favorite_train_stations"
    private const val COORD_EPSILON = 0.0002

    fun getAll(context: Context): List<FavoriteTrainStation> =
        loadRaw(context).sortedBy { it.name.lowercase() }

    fun add(
        context: Context,
        name: String,
        latitude: Double?,
        longitude: Double?,
        stationId: String? = null,
        address: String = ""
    ): FavoriteTrainStation? {
        val trimmedName = name.trim()
        if (trimmedName.isBlank()) return null
        val current = loadRaw(context).toMutableList()
        if (current.any { matches(it, trimmedName, latitude, longitude, stationId) }) return null
        val entry = FavoriteTrainStation(
            id = UUID.randomUUID().toString(),
            name = trimmedName,
            latitude = latitude,
            longitude = longitude,
            stationId = stationId,
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

    fun isFavorite(context: Context, name: String, stationId: String? = null): Boolean =
        loadRaw(context).any { favorite ->
            favorite.name.equals(name, ignoreCase = true) ||
                (!stationId.isNullOrBlank() && favorite.stationId == stationId)
        }

    private fun matches(
        favorite: FavoriteTrainStation,
        name: String,
        latitude: Double?,
        longitude: Double?,
        stationId: String?
    ): Boolean {
        if (!stationId.isNullOrBlank() && favorite.stationId == stationId) return true
        if (favorite.name.equals(name, ignoreCase = true)) return true
        if (latitude != null && longitude != null &&
            favorite.latitude != null && favorite.longitude != null
        ) {
            return abs(favorite.latitude - latitude) < COORD_EPSILON &&
                abs(favorite.longitude - longitude) < COORD_EPSILON
        }
        return false
    }

    private fun loadRaw(context: Context): List<FavoriteTrainStation> {
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
                        FavoriteTrainStation(
                            id = item.optString("id", UUID.randomUUID().toString()),
                            name = name,
                            latitude = item.optDouble("latitude").takeIf { !it.isNaN() },
                            longitude = item.optDouble("longitude").takeIf { !it.isNaN() },
                            stationId = item.optString("stationId").ifBlank { null },
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

    private fun save(context: Context, stations: List<FavoriteTrainStation>) {
        val array = JSONArray()
        stations.forEach { station ->
            array.put(
                JSONObject()
                    .put("id", station.id)
                    .put("name", station.name)
                    .put("latitude", station.latitude ?: JSONObject.NULL)
                    .put("longitude", station.longitude ?: JSONObject.NULL)
                    .put("stationId", station.stationId ?: "")
                    .put("address", station.address)
                    .put("savedAtMs", station.savedAtMs)
            )
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY, array.toString())
            .apply()
    }
}

data class FavoriteTrainStation(
    val id: String,
    val name: String,
    val latitude: Double?,
    val longitude: Double?,
    val stationId: String?,
    val address: String,
    val savedAtMs: Long = System.currentTimeMillis()
)