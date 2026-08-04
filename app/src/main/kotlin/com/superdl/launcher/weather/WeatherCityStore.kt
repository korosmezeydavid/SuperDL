package com.superdl.launcher.weather

import android.content.Context

object WeatherCityStore {

    private const val PREFS = "weather_city_store"
    private const val KEY_CITY = "last_city"

    fun get(context: Context): String? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_CITY, null)
            ?.trim()
            ?.takeIf { it.isNotBlank() }

    fun save(context: Context, city: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_CITY, city.trim())
            .apply()
    }
}