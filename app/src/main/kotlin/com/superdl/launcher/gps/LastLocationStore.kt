package com.superdl.launcher.gps

import android.content.Context
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class StoredLocation(
    val latitude: Double,
    val longitude: Double,
    val address: String,
    val accuracyMeters: Int,
    val savedAtMillis: Long
) {
    fun speakSummary(): String {
        val fmt = SimpleDateFormat("yyyy. MMMM d., HH:mm", Locale("hu", "HU"))
        val whenStr = fmt.format(Date(savedAtMillis))
        return "Utolsó ismert hely, $whenStr: $address. Pontosság akkor: $accuracyMeters méter."
    }
}

object LastLocationStore {

    private const val PREFS = "last_location_store"

    fun save(context: Context, lat: Double, lon: Double, address: String, accuracyMeters: Int) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putFloat("lat", lat.toFloat())
            .putFloat("lon", lon.toFloat())
            .putString("address", address.trim())
            .putInt("accuracy", accuracyMeters)
            .putLong("saved_at", System.currentTimeMillis())
            .apply()
    }

    fun get(context: Context): StoredLocation? {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!prefs.contains("lat")) return null
        val address = prefs.getString("address", null)?.trim().orEmpty()
        if (address.isBlank()) return null
        return StoredLocation(
            latitude = prefs.getFloat("lat", 0f).toDouble(),
            longitude = prefs.getFloat("lon", 0f).toDouble(),
            address = address,
            accuracyMeters = prefs.getInt("accuracy", 0),
            savedAtMillis = prefs.getLong("saved_at", 0L)
        )
    }
}