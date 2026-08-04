package com.superdl.launcher.transit

import android.location.Location
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

internal object OsmHelper {

    private const val USER_AGENT = "SuperDL/1.9 (vak-barat launcher; korosmezey.david.richard@gmail.com)"

    fun reverseGeocode(lat: Double, lon: Double): String? {
        val url =
            "https://nominatim.openstreetmap.org/reverse?lat=$lat&lon=$lon&format=json&accept-language=hu"
        val json = JSONObject(fetchText(url))
        val display = json.optString("display_name").ifBlank { json.optString("name") }
        return display.ifBlank { null }
    }

    fun geocode(query: String): List<GeoPlace> {
        val encoded = URLEncoder.encode("$query, Magyarország", "UTF-8")
        val url = "https://nominatim.openstreetmap.org/search?q=$encoded&format=json&limit=6&accept-language=hu"
        val array = JSONArray(fetchText(url))
        val places = mutableListOf<GeoPlace>()
        for (i in 0 until array.length()) {
            val item = array.optJSONObject(i) ?: continue
            val name = item.optString("display_name").ifBlank { item.optString("name") }
            val lat = item.optString("lat").toDoubleOrNull() ?: continue
            val lon = item.optString("lon").toDoubleOrNull() ?: continue
            places.add(GeoPlace(item.optString("name").ifBlank { name }, name, lat, lon))
        }
        return places
    }

    fun nearbyStops(lat: Double, lon: Double, radiusMeters: Int = 500, limit: Int = 8): List<TransitPlace> {
        val query = """
            [out:json][timeout:12];
            (
              node(around:$radiusMeters,$lat,$lon)[highway=bus_stop];
              node(around:$radiusMeters,$lat,$lon)[public_transport=platform];
            );
            out body $limit;
        """.trimIndent().replace("\n", "")
        val url = "https://overpass-api.de/api/interpreter"
        val body = fetchPost(url, "data=$query")
        val elements = JSONObject(body).optJSONArray("elements") ?: JSONArray()
        val origin = Location("").apply {
            latitude = lat
            longitude = lon
        }
        val places = mutableListOf<TransitPlace>()
        for (i in 0 until elements.length()) {
            val item = elements.optJSONObject(i) ?: continue
            val tags = item.optJSONObject("tags") ?: continue
            val name = tags.optString("name")
            if (name.isBlank()) continue
            val stopLat = item.optDouble("lat")
            val stopLon = item.optDouble("lon")
            val distance = distanceMeters(origin, stopLat, stopLon)
            places.add(
                TransitPlace(
                    name = name,
                    address = tags.optString("operator").ifBlank { "OpenStreetMap" },
                    distanceMeters = distance
                )
            )
        }
        return places.distinctBy { it.name }.sortedBy { it.distanceMeters ?: Int.MAX_VALUE }
    }

    fun walkingRoute(
        fromLat: Double,
        fromLon: Double,
        toLat: Double,
        toLon: Double
    ): TransitRoute? {
        val url =
            "https://router.project-osrm.org/route/v1/foot/" +
                "$fromLon,$fromLat;$toLon,$toLat?overview=false&steps=true"
        val json = JSONObject(fetchText(url))
        if (json.optString("code") != "Ok") return null
        val route = json.optJSONArray("routes")?.optJSONObject(0) ?: return null
        val durationSec = route.optDouble("duration", 0.0).toInt()
        val duration = formatDuration(durationSec)
        val legs = route.optJSONArray("legs")?.optJSONObject(0) ?: return null
        val stepsArray = legs.optJSONArray("steps") ?: JSONArray()
        val steps = mutableListOf<TransitRouteStep>()
        for (i in 0 until stepsArray.length()) {
            val step = stepsArray.optJSONObject(i) ?: continue
            val instruction = buildStepInstruction(step)
            if (instruction.isNotBlank()) steps.add(TransitRouteStep(instruction))
        }
        if (steps.isEmpty()) return null
        return TransitRoute("Gyalogos útvonal", duration, steps)
    }

    private fun buildStepInstruction(step: JSONObject): String {
        val name = step.optString("name").ifBlank { "út" }
        val distance = step.optDouble("distance", 0.0).toInt()
        val distText = TransitPlace.formatDistance(distance)
        val modifier = translateModifier(step.optString("modifier"))
        val direction = translateDirection(step.optString("direction"))
        return when (step.optString("maneuver")) {
            "depart" -> "Indulás a $name felé, $distText."
            "arrive" -> "Érkezés, $distText."
            "turn", "new name" -> {
                val turn = listOf(modifier, direction).filter { it.isNotBlank() }.joinToString(" ")
                if (turn.isBlank()) "Haladj tovább a $name mentén, $distText."
                else "$turn a $name irányába, $distText."
            }
            else -> "Haladj a $name mentén, $distText."
        }
    }

    private fun translateModifier(value: String): String = when (value) {
        "left" -> "Fordulj balra"
        "right" -> "Fordulj jobbra"
        "slight left" -> "Kissé balra"
        "slight right" -> "Kissé jobbra"
        "straight" -> "Egyenesen"
        "uturn" -> "Fordulj vissza"
        else -> ""
    }

    private fun translateDirection(value: String): String = when (value) {
        "north" -> "észak felé"
        "south" -> "dél felé"
        "east" -> "kelet felé"
        "west" -> "nyugat felé"
        else -> ""
    }

    private fun formatDuration(seconds: Int): String {
        val minutes = (seconds + 59) / 60
        return if (minutes < 60) "$minutes perc" else "${minutes / 60} óra ${minutes % 60} perc"
    }

    private fun distanceMeters(origin: Location, lat: Double, lon: Double): Int {
        val result = FloatArray(1)
        Location.distanceBetween(origin.latitude, origin.longitude, lat, lon, result)
        return result[0].toInt()
    }

    private fun fetchText(url: String): String {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.connectTimeout = 12000
        connection.readTimeout = 12000
        connection.setRequestProperty("User-Agent", USER_AGENT)
        if (connection.responseCode !in 200..299) {
            throw TransitApiException("OpenStreetMap lekérdezés sikertelen.")
        }
        return connection.inputStream.bufferedReader().readText()
    }

    private fun fetchPost(url: String, formBody: String): String {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.connectTimeout = 15000
        connection.readTimeout = 15000
        connection.doOutput = true
        connection.setRequestProperty("User-Agent", USER_AGENT)
        connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
        connection.outputStream.use { it.write(formBody.toByteArray(Charsets.UTF_8)) }
        if (connection.responseCode !in 200..299) {
            throw TransitApiException("OpenStreetMap lekérdezés sikertelen.")
        }
        return connection.inputStream.bufferedReader().readText()
    }
}

internal data class GeoPlace(
    val shortName: String,
    val fullName: String,
    val lat: Double,
    val lon: Double
)

internal class TransitApiException(message: String) : Exception(message)