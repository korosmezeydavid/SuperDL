package com.superdl.launcher.weather

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.Locale

data class WeatherInfo(
    val location: String,
    val condition: String,
    val temperatureC: Int,
    val humidity: Int,
    val windKmh: Int
) {
    fun speakSummary(): String {
        val loc = if (location.isNotBlank()) "$location. " else ""
        return "${loc}${condition}. Hőmérséklet: $temperatureC fok. Páratartalom: $humidity százalék. Szél: $windKmh kilométer per óra."
    }
}

object WeatherHelper {

    fun fetch(
        city: String? = null,
        onResult: (WeatherInfo) -> Unit,
        onError: (String) -> Unit
    ) {
        Thread {
            try {
                val info = if (city.isNullOrBlank()) fetchAuto() else fetchCity(city)
                android.os.Handler(android.os.Looper.getMainLooper()).post {
                    onResult(info)
                }
            } catch (_: Exception) {
                android.os.Handler(android.os.Looper.getMainLooper()).post {
                    onError("Időjárás lekérése sikertelen. Ellenőrizd az internetkapcsolatot.")
                }
            }
        }.start()
    }

    private fun fetchAuto(): WeatherInfo = parseWttrJson(httpGet("https://wttr.in/?format=j1&lang=hu"))

    private fun fetchCity(city: String): WeatherInfo {
        val encoded = URLEncoder.encode(city, "UTF-8")
        return parseWttrJson(httpGet("https://wttr.in/$encoded?format=j1&lang=hu"))
    }

    private fun parseWttrJson(body: String): WeatherInfo {
        val root = JSONObject(body)
        val current = root.getJSONArray("current_condition").getJSONObject(0)
        val area = root.optJSONArray("nearest_area")?.optJSONObject(0)
        val location = area?.optJSONArray("areaName")?.optJSONObject(0)?.optString("value").orEmpty()
        val condition = current.optJSONArray("lang_hu")?.optJSONObject(0)?.optString("value")
            ?: current.optJSONArray("weatherDesc")?.optJSONObject(0)?.optString("value")
            ?: "Ismeretlen"
        return WeatherInfo(
            location = location,
            condition = condition.trim(),
            temperatureC = current.optString("temp_C", "0").toIntOrNull() ?: 0,
            humidity = current.optString("humidity", "0").toIntOrNull() ?: 0,
            windKmh = current.optString("windspeedKmph", "0").toIntOrNull() ?: 0
        )
    }

    private fun httpGet(url: String): String {
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 12_000
            readTimeout = 12_000
            setRequestProperty("User-Agent", "SuperDL/1.8")
            setRequestProperty("Accept-Language", "hu-HU,hu;q=0.9")
        }
        if (connection.responseCode !in 200..299) {
            throw IllegalStateException("HTTP ${connection.responseCode}")
        }
        return connection.inputStream.bufferedReader().readText()
    }
}