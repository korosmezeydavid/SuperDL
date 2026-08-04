package com.superdl.launcher.info

import com.superdl.launcher.weather.WeatherHelper

object DayInfoHelper {

    fun speakLocal(): String {
        val datePart = InfoHelper.speakDateTime()
        val namedayPart = NamedayHelper.speakToday()
        return if (namedayPart.isBlank()) datePart else "$datePart $namedayPart"
    }

    fun fetchGreeting(
        includeWeather: Boolean = true,
        onResult: (String) -> Unit
    ) {
        val local = speakLocal()
        if (!includeWeather) {
            onResult(local)
            return
        }
        WeatherHelper.fetch(
            city = null,
            onResult = { weather -> onResult("$local ${weather.speakSummary()}") },
            onError = { onResult(local) }
        )
    }
}