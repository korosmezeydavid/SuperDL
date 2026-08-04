package com.superdl.launcher.train

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

internal object TrainStationCache {

    private const val PREFS = "superdl"
    private const val KEY_STATIONS = "mav_station_catalog"
    private const val KEY_FETCHED_AT = "mav_station_catalog_fetched_at"
    private const val TTL_MS = 24 * 60 * 60 * 1000L

    data class CachedStation(
        val id: String,
        val name: String,
        val latitude: Double?,
        val longitude: Double?
    )

    fun getAll(context: Context): List<CachedStation>? {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val fetchedAt = prefs.getLong(KEY_FETCHED_AT, 0L)
        if (fetchedAt <= 0L || System.currentTimeMillis() - fetchedAt > TTL_MS) return null
        val raw = prefs.getString(KEY_STATIONS, null) ?: return null
        return try {
            val array = JSONArray(raw)
            val stations = mutableListOf<CachedStation>()
            for (i in 0 until array.length()) {
                val item = array.optJSONObject(i) ?: continue
                val id = item.optString("id")
                val name = item.optString("name")
                if (id.isBlank() || name.isBlank()) continue
                stations.add(
                    CachedStation(
                        id = id,
                        name = name,
                        latitude = item.optDouble("latitude").takeIf { !it.isNaN() },
                        longitude = item.optDouble("longitude").takeIf { !it.isNaN() }
                    )
                )
            }
            stations.ifEmpty { null }
        } catch (_: Exception) {
            null
        }
    }

    fun save(context: Context, stations: List<CachedStation>) {
        val array = JSONArray()
        stations.forEach { station ->
            array.put(
                JSONObject()
                    .put("id", station.id)
                    .put("name", station.name)
                    .put("latitude", station.latitude ?: JSONObject.NULL)
                    .put("longitude", station.longitude ?: JSONObject.NULL)
            )
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_STATIONS, array.toString())
            .putLong(KEY_FETCHED_AT, System.currentTimeMillis())
            .apply()
    }
}