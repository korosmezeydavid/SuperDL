package com.superdl.launcher.transit

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import android.os.Handler
import android.os.Looper
import androidx.core.content.ContextCompat
import com.superdl.launcher.gps.GpsRadarMath
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

object TransitHelper {

    private val ioExecutor: ExecutorService = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "SuperDL-TransitIO")
    }

    private const val BKK_BASE = "https://futar.bkk.hu/api/query/v1/ws/otp/api/where"
    private const val BKK_KEY = "bkk-web"
    private const val BKK_RADIUS_NEAR = 450
    private const val BKK_RADIUS_EXTENDED = 2500
    private const val OSM_RADIUS_NEAR = 500
    private const val OSM_RADIUS_EXTENDED = 2000

    enum class StopRadiusMode(val label: String, val bkkRadius: Int, val osmRadius: Int) {
        NEAR("Legközelebbi megállók", BKK_RADIUS_NEAR, OSM_RADIUS_NEAR),
        EXTENDED("Távolabbi megállók is", BKK_RADIUS_EXTENDED, OSM_RADIUS_EXTENDED)
    }
    private const val BUDAPEST_MIN_LAT = 47.30
    private const val BUDAPEST_MAX_LAT = 47.62
    private const val BUDAPEST_MIN_LON = 18.90
    private const val BUDAPEST_MAX_LON = 19.40

    fun fetchNearbyStops(
        context: Context,
        onResult: (List<TransitPlace>) -> Unit,
        onError: (String) -> Unit,
        radiusMode: StopRadiusMode = StopRadiusMode.NEAR,
        headingDegrees: Float = 0f
    ) {
        val location = getLastLocation(context)
            ?: run {
                onError("Helymeghatározás nem elérhető. Kapcsold be a G P S-t.")
                return
            }
        runAsync(onError, {
            val raw = if (isInBudapest(location)) {
                fetchBkkNearby(location, radiusMode.bkkRadius)
                    .ifEmpty { OsmHelper.nearbyStops(location.latitude, location.longitude, radiusMode.osmRadius, 12) }
            } else {
                OsmHelper.nearbyStops(location.latitude, location.longitude, radiusMode.osmRadius, 12)
            }
            enrichPlaces(context, raw, location, headingDegrees)
        }) { places ->
            if (places.isEmpty()) onError("Nem találtam megállót a ${radiusMode.label.lowercase()} körzetben.")
            else onResult(places)
        }
    }

    fun fetchFavoriteStops(
        context: Context,
        onResult: (List<TransitPlace>) -> Unit,
        onError: (String) -> Unit,
        headingDegrees: Float = 0f
    ) {
        val favorites = TransitStopStore.getAll(context)
        if (favorites.isEmpty()) {
            onError("Nincs mentett kedvenc megálló. A megálló listában jobbra műveletek, majd mentés.")
            return
        }
        val location = getLastLocation(context)
        runAsync(onError, {
            val places = favorites.map { favorite ->
                val distance = if (location != null && favorite.latitude != null && favorite.longitude != null) {
                    dist(location, favorite.latitude, favorite.longitude)
                } else null
                TransitPlace(
                    name = favorite.name,
                    address = favorite.address,
                    distanceMeters = distance,
                    latitude = favorite.latitude,
                    longitude = favorite.longitude,
                    stopId = favorite.stopId,
                    isFavorite = true
                )
            }.sortedBy { it.distanceMeters ?: Int.MAX_VALUE }
            val enriched = enrichPlaces(context, places, location, headingDegrees)
            if (location != null && isInBudapest(location)) {
                enriched.map { place ->
                    if (place.nextDepartures.isNotEmpty()) place
                    else refreshDeparturesForStop(location, place) ?: place
                }
            } else {
                enriched
            }
        }) { result ->
            if (result.isEmpty()) onError("Nem sikerült betölteni a kedvenc megállókat.")
            else onResult(result)
        }
    }

    fun searchStop(
        context: Context,
        stopName: String,
        onResult: (List<TransitPlace>) -> Unit,
        onError: (String) -> Unit,
        headingDegrees: Float = 0f
    ) {
        val trimmed = stopName.trim()
        if (trimmed.isBlank()) {
            onError("Üres megállónév.")
            return
        }
        val location = getLastLocation(context)
        val normalizedQuery = normalizeStopQuery(trimmed)
        runAsync(onError, {
            val bkkMatches = if (location != null && isInBudapest(location)) {
                fetchBkkStopsForLocation(location, BKK_RADIUS_EXTENDED)
                    .filter { matchesStopQuery(it.name, normalizedQuery) }
            } else {
                emptyList()
            }
            if (bkkMatches.isNotEmpty()) {
                enrichPlaces(context, bkkMatches, location, headingDegrees)
            } else {
                val geocoded = OsmHelper.geocode("$trimmed megálló")
                    .ifEmpty { OsmHelper.geocode(trimmed) }
                val places = geocoded.map { geo ->
                    val distance = location?.let { dist(it, geo.lat, geo.lon) }
                    TransitPlace(
                        name = geo.shortName,
                        address = geo.fullName,
                        distanceMeters = distance,
                        latitude = geo.lat,
                        longitude = geo.lon
                    )
                }.distinctBy { it.name }
                enrichPlaces(context, places, location, headingDegrees)
            }
        }) { result ->
            if (result.isEmpty()) onError("Nem találtam megállót: $trimmed.")
            else onResult(result.sortedBy { it.distanceMeters ?: Int.MAX_VALUE })
        }
    }

    fun fetchTransitRoute(
        context: Context,
        destination: String,
        onResult: (TransitRoute) -> Unit,
        onError: (String) -> Unit
    ) {
        val trimmed = destination.trim()
        if (trimmed.isBlank()) {
            onError("Üres célállomás.")
            return
        }
        val location = getLastLocation(context)
            ?: run {
                onError("Helymeghatározás nem elérhető. Kapcsold be a G P S-t.")
                return
            }
        runAsync(onError, {
            val target = OsmHelper.geocode(trimmed).firstOrNull()
                ?: throw TransitApiException("Nem található célállomás: $trimmed.")

            if (isInBudapest(location) && isInBudapest(target.lat, target.lon)) {
                fetchBkkRoute(location, target)?.let { return@runAsync it }
            }
            OsmHelper.walkingRoute(
                location.latitude, location.longitude, target.lat, target.lon
            ) ?: throw TransitApiException("Nem sikerült útvonalat tervezni ide: ${target.shortName}.")
        }) { route ->
            onResult(route)
        }
    }

    private fun fetchBkkNearby(location: Location, radius: Int): List<TransitPlace> {
        val url = bkkUrl(
            "arrivals-and-departures-for-location",
            "lat=${location.latitude}",
            "lon=${location.longitude}",
            "radius=$radius",
            "limit=16",
            "minutesAfter=45",
            "includeReferences=true"
        )
        val json = JSONObject(fetchText(url))
        val data = json.optJSONObject("data") ?: return emptyList()
        val references = data.optJSONObject("references") ?: JSONObject()
        val stopsRef = references.optJSONObject("stops") ?: JSONObject()
        val routesRef = references.optJSONObject("routes") ?: JSONObject()
        val vehiclesRef = references.optJSONObject("vehicles") ?: JSONObject()
        val list = data.optJSONArray("list") ?: JSONArray()

        val stopDepartures = linkedMapOf<String, MutableList<String>>()
        val stopLines = linkedMapOf<String, LinkedHashSet<String>>()
        val stopVehicleApproach = linkedMapOf<String, String>()
        val stopIds = linkedSetOf<String>()

        for (i in 0 until list.length()) {
            val group = list.optJSONObject(i) ?: continue
            val routeId = group.optString("routeId")
            val route = routesRef.optJSONObject(routeId)
            val routeName = route?.optString("shortName").orEmpty()
            val vehicle = vehicleName(route?.optString("type"))
            val headsign = group.optString("headsign")
            val stopTimes = group.optJSONArray("stopTimes") ?: continue
            for (j in 0 until stopTimes.length()) {
                val stopTime = stopTimes.optJSONObject(j) ?: continue
                val stopId = stopTime.optString("stopId")
                if (stopId.isBlank()) continue
                stopIds.add(stopId)
                if (routeName.isNotBlank()) {
                    stopLines.getOrPut(stopId) { linkedSetOf() }.add(routeName)
                }
                val departure = stopTime.optLong("predictedDepartureTime")
                    .takeIf { it > 0 } ?: stopTime.optLong("departureTime")
                val depText = formatDeparture(departure)
                val line = buildString {
                    if (vehicle.isNotBlank()) append("$vehicle ")
                    if (routeName.isNotBlank()) append("$routeName ")
                    append(headsign)
                    append(", $depText")
                }.trim()
                stopDepartures.getOrPut(stopId) { mutableListOf() }.add(line)
                val vehicleId = stopTime.optString("vehicleId")
                if (vehicleId.isNotBlank() && stopId !in stopVehicleApproach) {
                    formatVehicleApproach(vehiclesRef.optJSONObject(vehicleId), vehicle, routeName)
                        ?.let { stopVehicleApproach[stopId] = it }
                }
            }
        }

        return stopIds.mapNotNull { stopId ->
            val stop = stopsRef.optJSONObject(stopId) ?: return@mapNotNull null
            val name = stop.optString("name").ifBlank { return@mapNotNull null }
            val lat = stop.optDouble("lat")
            val lon = stop.optDouble("lon")
            TransitPlace(
                name = name,
                address = stop.optString("localityName").ifBlank { "BKK" },
                distanceMeters = dist(location, lat, lon),
                nextDepartures = stopDepartures[stopId]?.distinct()?.take(4).orEmpty(),
                latitude = lat,
                longitude = lon,
                stopId = stopId,
                routeLines = stopLines[stopId]?.toList().orEmpty(),
                vehicleApproach = stopVehicleApproach[stopId],
                wheelchairAccessible = parseWheelchair(stop)
            )
        }.sortedBy { it.distanceMeters ?: Int.MAX_VALUE }
            .distinctBy { it.stopId ?: it.name }
            .take(12)
    }

    private fun fetchBkkStopsForLocation(location: Location, radius: Int): List<TransitPlace> {
        val url = bkkUrl(
            "stops-for-location",
            "lat=${location.latitude}",
            "lon=${location.longitude}",
            "radius=$radius",
            "includeReferences=false"
        )
        val json = JSONObject(fetchText(url))
        val list = json.optJSONObject("data")?.optJSONArray("list") ?: JSONArray()
        val places = mutableListOf<TransitPlace>()
        for (i in 0 until list.length()) {
            val stop = list.optJSONObject(i) ?: continue
            val name = stop.optString("name")
            if (name.isBlank()) continue
            val lat = stop.optDouble("lat")
            val lon = stop.optDouble("lon")
            places.add(
                TransitPlace(
                    name = name,
                    address = stop.optString("localityName").ifBlank { "BKK" },
                    distanceMeters = dist(location, lat, lon),
                    latitude = lat,
                    longitude = lon,
                    stopId = stop.optString("id").ifBlank { stop.optString("stopId") }.ifBlank { null },
                    wheelchairAccessible = parseWheelchair(stop)
                )
            )
        }
        return places.distinctBy { it.stopId ?: it.name }.sortedBy { it.distanceMeters ?: Int.MAX_VALUE }
    }

    private fun refreshDeparturesForStop(location: Location, place: TransitPlace): TransitPlace? {
        if (place.latitude == null || place.longitude == null) return null
        val nearby = fetchBkkNearby(
            Location("").apply {
                latitude = place.latitude
                longitude = place.longitude
            },
            radius = 80
        )
        return nearby.firstOrNull { it.stopId == place.stopId || it.name == place.name }
    }

    private fun enrichPlaces(
        context: Context,
        places: List<TransitPlace>,
        location: Location?,
        headingDegrees: Float
    ): List<TransitPlace> = places.map { place ->
        val distance = if (location != null && place.latitude != null && place.longitude != null) {
            dist(location, place.latitude, place.longitude)
        } else {
            place.distanceMeters
        }
        val clockDirection = if (location != null && place.latitude != null && place.longitude != null) {
            val bearing = GpsRadarMath.bearingDegrees(
                location.latitude, location.longitude, place.latitude, place.longitude
            )
            GpsRadarMath.clockDirection(GpsRadarMath.relativeBearing(bearing, headingDegrees))
        } else {
            place.clockDirection
        }
        place.copy(
            distanceMeters = distance,
            clockDirection = clockDirection,
            isFavorite = TransitStopStore.isFavorite(context, place.name, place.stopId)
        )
    }

    private fun formatVehicleApproach(vehicle: JSONObject?, vehicleType: String, line: String): String? {
        vehicle ?: return null
        val status = vehicle.optString("status")
        val statusText = when (status.uppercase(Locale.ROOT)) {
            "IN_TRANSIT_TO" -> "úton a megálló felé"
            "STOPPED_AT" -> "a megállóban"
            else -> "közeledik"
        }
        return buildString {
            if (vehicleType.isNotBlank()) append("$vehicleType ")
            if (line.isNotBlank()) append("$line ")
            append(statusText)
        }.trim().ifBlank { null }
    }

    private fun parseWheelchair(stop: JSONObject): Boolean? = when (stop.optString("wheelchairBoarding")) {
        "true", "1", "yes" -> true
        "false", "0", "no" -> false
        else -> null
    }

    private fun normalizeStopQuery(query: String): String =
        query.lowercase()
            .replace("utca", "")
            .replace("út", "")
            .replace("tér", "")
            .replace(Regex("\\s+"), " ")
            .trim()

    private fun matchesStopQuery(stopName: String, normalizedQuery: String): Boolean {
        val normalizedStop = normalizeStopQuery(stopName)
        return normalizedStop.contains(normalizedQuery) ||
            normalizedQuery.contains(normalizedStop) ||
            normalizedStop.split(" ").any { it.startsWith(normalizedQuery) || normalizedQuery.startsWith(it) }
    }

    private fun fetchBkkRoute(origin: Location, target: GeoPlace): TransitRoute? {
        val url = bkkUrl(
            "plan-trip",
            "fromPlace=${origin.latitude},${origin.longitude}",
            "toPlace=${target.lat},${target.lon}",
            "mode=TRANSIT,WALK",
            "time=now"
        )
        val json = JSONObject(fetchText(url, timeoutMs = 25000))
        val plan = json.optJSONObject("data")
            ?.optJSONObject("entry")
            ?.optJSONObject("plan")
            ?: return null
        val itinerary = plan.optJSONArray("itineraries")?.optJSONObject(0) ?: return null
        val durationSec = itinerary.optInt("duration", 0)
        val duration = formatDuration(durationSec)
        val legs = itinerary.optJSONArray("legs") ?: JSONArray()
        val steps = mutableListOf<TransitRouteStep>()
        for (i in 0 until legs.length()) {
            val leg = legs.optJSONObject(i) ?: continue
            val instruction = formatBkkLeg(leg)
            if (instruction.isNotBlank()) steps.add(TransitRouteStep(instruction))
        }
        if (steps.isEmpty()) return null
        val destinationName = target.shortName
        return TransitRoute("Útvonal ide: $destinationName", duration, steps)
    }

    private fun formatBkkLeg(leg: JSONObject): String {
        return when (leg.optString("mode")) {
            "WALK" -> {
                val from = leg.optJSONObject("from")?.optString("name").orEmpty()
                val to = leg.optJSONObject("to")?.optString("name").orEmpty()
                val durationMin = (leg.optLong("duration", 0L) / 60000L).toInt().coerceAtLeast(1)
                when {
                    to.isNotBlank() -> "Gyalog $durationMin perc a $to megállóig."
                    from.isNotBlank() -> "Gyalog $durationMin perc innen: $from."
                    else -> "Gyalog $durationMin perc."
                }
            }
            "BUS", "TRAM", "SUBWAY", "TROLLEYBUS", "RAIL", "FERRY" -> {
                val vehicle = vehicleName(leg.optString("mode"))
                val line = leg.optString("routeShortName")
                val from = leg.optJSONObject("from")?.optString("name").orEmpty()
                val to = leg.optJSONObject("to")?.optString("name").orEmpty()
                val headsign = leg.optString("headsign")
                buildString {
                    append(vehicle)
                    if (line.isNotBlank()) append(" $line")
                    append(" járat")
                    if (headsign.isNotBlank()) append(", $headsign irány")
                    if (from.isNotBlank()) append(". Felszállás: $from")
                    if (to.isNotBlank()) append(". Leszállás: $to")
                }.trim()
            }
            else -> ""
        }
    }

    private fun vehicleName(type: String?): String = when (type?.uppercase(Locale.ROOT)) {
        "TRAM" -> "Villamos"
        "BUS" -> "Busz"
        "SUBWAY" -> "Metró"
        "TROLLEYBUS" -> "Trolibusz"
        "RAIL" -> "Vonat"
        "FERRY" -> "Hajó"
        else -> "Járat"
    }

    private fun formatDeparture(epochSeconds: Long): String {
        if (epochSeconds <= 0L) return "hamarosan"
        val now = System.currentTimeMillis()
        val target = epochSeconds * 1000L
        val diffMin = ((target - now) / 60000L).toInt()
        return when {
            diffMin <= 0 -> "most"
            diffMin == 1 -> "1 perc múlva"
            diffMin < 60 -> "$diffMin perc múlva"
            else -> {
                val fmt = SimpleDateFormat("HH:mm", Locale("hu", "HU")).apply {
                    timeZone = TimeZone.getTimeZone("Europe/Budapest")
                }
                fmt.format(Date(target))
            }
        }
    }

    private fun formatDuration(seconds: Int): String {
        val minutes = ((seconds + 59) / 60).coerceAtLeast(1)
        return if (minutes < 60) "$minutes perc" else "${minutes / 60} óra ${minutes % 60} perc"
    }

    private fun isInBudapest(location: Location): Boolean =
        isInBudapest(location.latitude, location.longitude)

    private fun isInBudapest(lat: Double, lon: Double): Boolean =
        lat in BUDAPEST_MIN_LAT..BUDAPEST_MAX_LAT && lon in BUDAPEST_MIN_LON..BUDAPEST_MAX_LON

    private fun dist(origin: Location, lat: Double, lon: Double): Int {
        val result = FloatArray(1)
        Location.distanceBetween(origin.latitude, origin.longitude, lat, lon, result)
        return result[0].toInt()
    }

    private fun bkkUrl(endpoint: String, vararg params: String): String {
        val query = buildList {
            add("key=$BKK_KEY")
            add("version=2")
            add("appVersion=SuperDL/1.6")
            addAll(params)
        }.joinToString("&")
        return "$BKK_BASE/$endpoint?$query"
    }

    private fun fetchText(url: String, timeoutMs: Int = 12000): String {
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = timeoutMs
            readTimeout = timeoutMs
            setRequestProperty("User-Agent", "SuperDL/1.6")
        }
        try {
            if (connection.responseCode !in 200..299) {
                throw TransitApiException("Tömegközlekedés lekérdezés sikertelen.")
            }
            return connection.inputStream.bufferedReader().use { it.readText() }
        } finally {
            runCatching { connection.inputStream?.close() }
            runCatching { connection.errorStream?.close() }
            runCatching { connection.disconnect() }
        }
    }

    private fun <T> runAsync(
        onError: (String) -> Unit,
        block: () -> T,
        onResult: (T) -> Unit
    ) {
        val mainHandler = Handler(Looper.getMainLooper())
        ioExecutor.execute {
            try {
                val result = block()
                mainHandler.post { onResult(result) }
            } catch (e: TransitApiException) {
                mainHandler.post { onError(e.message ?: "Tömegközlekedés hiba.") }
            } catch (_: Exception) {
                mainHandler.post {
                    onError("Tömegközlekedés lekérdezés sikertelen. Ellenőrizd az internetkapcsolatot.")
                }
            }
        }
    }

    private fun getLastLocation(context: Context): Location? {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION)
            != PackageManager.PERMISSION_GRANTED
        ) {
            return null
        }
        val manager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        return listOf(
            LocationManager.GPS_PROVIDER,
            LocationManager.NETWORK_PROVIDER,
            LocationManager.PASSIVE_PROVIDER
        ).mapNotNull { provider ->
            try {
                manager.getLastKnownLocation(provider)
            } catch (_: SecurityException) {
                null
            }
        }.maxByOrNull { it.time }
    }
}