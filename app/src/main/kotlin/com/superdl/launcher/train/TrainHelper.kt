package com.superdl.launcher.train

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import android.os.Handler
import android.os.Looper
import androidx.core.content.ContextCompat
import com.superdl.launcher.gps.GpsRadarMath
import com.superdl.launcher.transit.TransitApiException
import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

object TrainHelper {

    private val ioExecutor: ExecutorService = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "SuperDL-TrainIO")
    }

    private const val MAV_UAID = "2Juija1mabqr24Blkx1qkXxJ105j"
    private val MAV_BASE_URLS = listOf(
        "https://vim.mav-start.hu/VIM/PR/20250529/MobileService.svc/rest/",
        "http://vim.mav-start.hu/VIM/PR/150225/MobileService.svc/rest/",
        "https://vim.mav-start.hu/VIM/QA/UAT/20250529/MobileService.svc/rest/"
    )

    private const val RADIUS_NEAR = 2500
    private const val RADIUS_EXTENDED = 15000
    private const val OSM_RADIUS_NEAR = 3000
    private const val OSM_RADIUS_EXTENDED = 12000
    private const val APPROACH_RADIUS_METERS = 8000
    private const val USER_AGENT = "SuperDL/1.9 (vak-barat launcher; korosmezey.david.richard@gmail.com)"

    enum class StationRadiusMode(val label: String, val mavRadius: Int, val osmRadius: Int) {
        NEAR("Legközelebbi állomások", RADIUS_NEAR, OSM_RADIUS_NEAR),
        EXTENDED("Távolabbi állomások is", RADIUS_EXTENDED, OSM_RADIUS_EXTENDED)
    }

    fun fetchNearbyStations(
        context: Context,
        onResult: (List<TrainStation>) -> Unit,
        onError: (String) -> Unit,
        radiusMode: StationRadiusMode = StationRadiusMode.NEAR,
        headingDegrees: Float = 0f
    ) {
        val location = getLastLocation(context)
            ?: run {
                onError("Helymeghatározás nem elérhető. Kapcsold be a G P S-t.")
                return
            }
        runAsync(onError, {
            val catalog = loadStationCatalog(context)
            val nearby = catalog
                .filter { it.latitude != null && it.longitude != null }
                .mapNotNull { station ->
                    val distance = dist(location, station.latitude!!, station.longitude!!)
                    if (distance > radiusMode.mavRadius) return@mapNotNull null
                    TrainStation(
                        name = station.name,
                        address = "MÁV",
                        distanceMeters = distance,
                        latitude = station.latitude,
                        longitude = station.longitude,
                        stationId = station.id
                    )
                }
                .sortedBy { it.distanceMeters ?: Int.MAX_VALUE }
                .take(12)
            val places = if (nearby.isNotEmpty()) {
                nearby
            } else {
                fetchOsmRailwayStations(location, radiusMode.osmRadius, 12, catalog)
            }
            enrichStations(context, places, location, headingDegrees)
        }) { stations ->
            if (stations.isEmpty()) {
                onError("Nem találtam vasútállomást a ${radiusMode.label.lowercase()} körzetben.")
            } else {
                onResult(stations)
            }
        }
    }

    fun fetchFavoriteStations(
        context: Context,
        onResult: (List<TrainStation>) -> Unit,
        onError: (String) -> Unit,
        headingDegrees: Float = 0f
    ) {
        val favorites = TrainStationStore.getAll(context)
        if (favorites.isEmpty()) {
            onError("Nincs mentett kedvenc állomás. Az állomás listában jobbra műveletek, majd mentés.")
            return
        }
        val location = getLastLocation(context)
        runAsync(onError, {
            val places = favorites.map { favorite ->
                val distance = if (location != null && favorite.latitude != null && favorite.longitude != null) {
                    dist(location, favorite.latitude, favorite.longitude)
                } else null
                TrainStation(
                    name = favorite.name,
                    address = favorite.address,
                    distanceMeters = distance,
                    latitude = favorite.latitude,
                    longitude = favorite.longitude,
                    stationId = favorite.stationId,
                    isFavorite = true
                )
            }.sortedBy { it.distanceMeters ?: Int.MAX_VALUE }
            enrichStations(context, places, location, headingDegrees, refreshDepartures = true)
        }) { result ->
            if (result.isEmpty()) onError("Nem sikerült betölteni a kedvenc állomásokat.")
            else onResult(result)
        }
    }

    fun searchStation(
        context: Context,
        stationName: String,
        onResult: (List<TrainStation>) -> Unit,
        onError: (String) -> Unit,
        headingDegrees: Float = 0f
    ) {
        val trimmed = stationName.trim()
        if (trimmed.isBlank()) {
            onError("Üres állomásnév.")
            return
        }
        val location = getLastLocation(context)
        val normalizedQuery = normalizeStationQuery(trimmed)
        runAsync(onError, {
            val catalog = loadStationCatalog(context)
            val matches = catalog
                .filter { matchesStationQuery(it.name, normalizedQuery) }
                .map { station ->
                    val distance = if (location != null && station.latitude != null && station.longitude != null) {
                        dist(location, station.latitude, station.longitude)
                    } else null
                    TrainStation(
                        name = station.name,
                        address = "MÁV",
                        distanceMeters = distance,
                        latitude = station.latitude,
                        longitude = station.longitude,
                        stationId = station.id
                    )
                }
            val places = if (matches.isNotEmpty()) {
                matches
            } else {
                fetchOsmRailwayStationsByName(trimmed, location, catalog)
            }
            enrichStations(context, places.sortedBy { it.distanceMeters ?: Int.MAX_VALUE }.take(12), location, headingDegrees)
        }) { result ->
            if (result.isEmpty()) onError("Nem találtam állomást: $trimmed.")
            else onResult(result)
        }
    }

    private fun enrichStations(
        context: Context,
        stations: List<TrainStation>,
        location: Location?,
        headingDegrees: Float,
        refreshDepartures: Boolean = true
    ): List<TrainStation> {
        val liveTrains = if (refreshDepartures) fetchLiveTrainsSafe() else emptyList()
        return stations.map { station ->
            val distance = if (location != null && station.latitude != null && station.longitude != null) {
                dist(location, station.latitude, station.longitude)
            } else {
                station.distanceMeters
            }
            val clockDirection = if (location != null && station.latitude != null && station.longitude != null) {
                val bearing = GpsRadarMath.bearingDegrees(
                    location.latitude, location.longitude, station.latitude, station.longitude
                )
                GpsRadarMath.clockDirection(GpsRadarMath.relativeBearing(bearing, headingDegrees))
            } else {
                station.clockDirection
            }
            val withDepartures = if (refreshDepartures && !station.stationId.isNullOrBlank()) {
                val departures = fetchStationDepartures(station.stationId, station, liveTrains, location)
                val delayWarning = buildDelayWarning(departures)
                station.copy(
                    nextDepartures = departures,
                    delayWarning = delayWarning
                )
            } else {
                station
            }
            withDepartures.copy(
                distanceMeters = distance,
                clockDirection = clockDirection,
                isFavorite = TrainStationStore.isFavorite(context, station.name, station.stationId)
            )
        }
    }

    private fun buildDelayWarning(departures: List<TrainDeparture>): String? {
        val delayed = departures.filter { (it.delayMinutes ?: 0) > 0 }
        if (delayed.isEmpty()) return null
        val worst = delayed.maxOf { it.delayMinutes ?: 0 }
        val count = delayed.size
        return if (count == 1) {
            "Figyelem: egy vonat $worst perces késéssel indul."
        } else {
            "Figyelem: $count vonat késik, legnagyobb késés $worst perc."
        }
    }

    private fun fetchStationDepartures(
        stationId: String,
        station: TrainStation,
        liveTrains: List<LiveTrain>,
        userLocation: Location?
    ): List<TrainDeparture> {
        val body = JSONObject()
            .put("AllomasID", stationId)
            .put("Datum", budapestDayStartEpochSec())
            .put("Nyelv", "HU")
            .put("UAID", MAV_UAID)
        val json = postMavJson("GetAllomasInfo", body) ?: return emptyList()
        val schedule = json.optJSONArray("Menetrend") ?: return emptyList()
        val nowSec = System.currentTimeMillis() / 1000L
        val departures = mutableListOf<TrainDeparture>()
        for (i in 0 until schedule.length()) {
            val entry = schedule.optJSONObject(i) ?: continue
            val train = entry.optJSONObject("Vonat") ?: continue
            val time = entry.optJSONObject("Ido") ?: continue
            val scheduledSec = time.optLong("IndMDatum").takeIf { it > 0L }
                ?: time.optLong("ErkMDatum").takeIf { it > 0L }
                ?: continue
            if (scheduledSec < nowSec - 120L) continue
            val actualSec = time.optLong("IndTenyDatum").takeIf { it > 0L }
                ?: time.optLong("ErkTenyDatum").takeIf { it > 0L }
            val delayMinutes = computeDelayMinutes(scheduledSec, actualSec)
            val trainNumber = train.optString("Szam").ifBlank { train.optString("ID") }
            // A MÁV API nem ad külön vonatnevet ezen a végponton; a vonal-jelzést használjuk.
            val lineLabel = train.optJSONObject("ViszonylatJeloles")?.optString("Jel")?.ifBlank { null }
            val trainName = lineLabel
            val trainType = train.optJSONArray("Tipus")?.optJSONObject(0)
                ?.optString("VonatnemRovid")
                ?.ifBlank { train.optJSONArray("Tipus")?.optJSONObject(0)?.optString("Vonatnem") }
                ?.ifBlank { null }
            // A Viszonylat objektum csak állomáskódokat tartalmaz, nem nevet;
            // a vonal-jelzés (pl. S60) a leghasznosabb irány-információ.
            val destination = lineLabel?.let { "$it vonal" } ?: "ismeretlen irány"
            val platform = train.optString("IndVagany")
                .ifBlank { train.optString("ErkVagany") }
                .ifBlank { null }
            val approachText = findApproachText(trainNumber, station, liveTrains, userLocation)
            departures.add(
                TrainDeparture(
                    trainNumber = trainNumber,
                    trainName = trainName,
                    trainType = trainType,
                    destination = destination,
                    platform = platform,
                    scheduledEpochSec = scheduledSec,
                    actualEpochSec = actualSec,
                    delayMinutes = delayMinutes,
                    approachText = approachText
                )
            )
        }
        return departures
            .sortedBy { it.actualEpochSec ?: it.scheduledEpochSec }
            .distinctBy { "${it.trainNumber}_${it.scheduledEpochSec}" }
            .take(6)
    }

    private fun findApproachText(
        trainNumber: String,
        station: TrainStation,
        liveTrains: List<LiveTrain>,
        userLocation: Location?
    ): String? {
        val live = liveTrains.firstOrNull {
            it.trainNumber.equals(trainNumber, ignoreCase = true) ||
                it.trainNumber.removePrefix("H") == trainNumber.removePrefix("H")
        } ?: return null
        val reference = when {
            station.latitude != null && station.longitude != null -> {
                Location("").apply {
                    latitude = station.latitude
                    longitude = station.longitude
                }
            }
            userLocation != null -> userLocation
            else -> return live.delayText()
        }
        if (live.latitude == null || live.longitude == null) return live.delayText()
        val trainLocation = Location("").apply {
            latitude = live.latitude
            longitude = live.longitude
        }
        val distance = reference.distanceTo(trainLocation).toInt()
        return when {
            distance <= 400 -> buildString {
                append("A vonat már nagyon közel van")
                live.delayText()?.let { append(", $it") }
            }
            distance <= APPROACH_RADIUS_METERS -> buildString {
                append("A vonat kb. ${TrainStation.formatDistance(distance)}-re van")
                live.delayText()?.let { append(", $it") }
            }
            else -> live.delayText()
        }
    }

    private fun loadStationCatalog(context: Context): List<TrainStationCache.CachedStation> {
        TrainStationCache.getAll(context)?.let { return it }
        val body = JSONObject()
            .put("AllomasIdoBelyeg", "1000")
            .put("ErtekelesIdoBelyeg", "1000")
            .put("KedvezmenyIdoBelyeg", "1000")
            .put("UAID", MAV_UAID)
        val json = postMavJson("GetAlapadatok", body) ?: return emptyList()
        val list = json.optJSONObject("Allomasok")?.optJSONArray("AllomasLista") ?: JSONArray()
        val stations = mutableListOf<TrainStationCache.CachedStation>()
        for (i in 0 until list.length()) {
            val item = list.optJSONObject(i) ?: continue
            val id = item.optString("ID")
            val name = item.optString("Nev")
            if (id.isBlank() || name.isBlank()) continue
            stations.add(
                TrainStationCache.CachedStation(
                    id = id,
                    name = name,
                    latitude = parseHungarianCoordinate(item.optString("GpsLat")),
                    longitude = parseHungarianCoordinate(item.optString("GpsLon"))
                )
            )
        }
        if (stations.isNotEmpty()) TrainStationCache.save(context, stations)
        return stations
    }

    private fun fetchLiveTrainsSafe(): List<LiveTrain> {
        return try {
            val body = JSONObject()
                .put("Nyelv", "HU")
                .put("UAID", MAV_UAID)
            val json = postMavJson("GetVonatok", body) ?: return emptyList()
            val list = json.optJSONArray("Vonatok") ?: return emptyList()
            val trains = mutableListOf<LiveTrain>()
            for (i in 0 until list.length()) {
                val item = list.optJSONObject(i) ?: continue
                val number = item.optString("Vonatszam")
                if (number.isBlank()) continue
                trains.add(
                    LiveTrain(
                        trainNumber = number,
                        latitude = item.optDouble("GpsLat").takeIf { !it.isNaN() && it != 0.0 },
                        longitude = item.optDouble("GpsLon").takeIf { !it.isNaN() && it != 0.0 },
                        delayMinutes = item.optInt("Keses").takeIf { it > 0 }
                    )
                )
            }
            trains
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun fetchOsmRailwayStations(
        location: Location,
        radiusMeters: Int,
        limit: Int,
        catalog: List<TrainStationCache.CachedStation>
    ): List<TrainStation> {
        val query = """
            [out:json][timeout:15];
            (
              node(around:$radiusMeters,${location.latitude},${location.longitude})[railway=station][uic_ref];
              node(around:$radiusMeters,${location.latitude},${location.longitude})[railway=station][train=yes];
              node(around:$radiusMeters,${location.latitude},${location.longitude})[railway=halt][uic_ref];
              node(around:$radiusMeters,${location.latitude},${location.longitude})[railway=halt][train=yes];
            );
            out body $limit;
        """.trimIndent().replace("\n", "")
        return parseOsmRailwayResponse(query, location, catalog)
    }

    private fun fetchOsmRailwayStationsByName(
        name: String,
        location: Location?,
        catalog: List<TrainStationCache.CachedStation>
    ): List<TrainStation> {
        val encoded = URLEncoder.encode("$name vasútállomás Magyarország", "UTF-8")
        val url = "https://nominatim.openstreetmap.org/search?q=$encoded&format=json&limit=8&accept-language=hu"
        return try {
            val array = JSONArray(fetchText(url))
            buildList {
                for (i in 0 until array.length()) {
                    val item = array.optJSONObject(i) ?: continue
                    val display = item.optString("display_name").ifBlank { item.optString("name") }
                    val shortName = item.optString("name").ifBlank { display.substringBefore(",") }
                    val lat = item.optString("lat").toDoubleOrNull() ?: continue
                    val lon = item.optString("lon").toDoubleOrNull() ?: continue
                    val distance = location?.let { dist(it, lat, lon) }
                    val matchedId = matchStationIdByName(shortName, catalog)
                    add(
                        TrainStation(
                            name = shortName,
                            address = display,
                            distanceMeters = distance,
                            latitude = lat,
                            longitude = lon,
                            stationId = matchedId
                        )
                    )
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun parseOsmRailwayResponse(
        query: String,
        location: Location,
        catalog: List<TrainStationCache.CachedStation>
    ): List<TrainStation> {
        return try {
            val url = "https://overpass-api.de/api/interpreter"
            val body = fetchPost(url, "data=$query")
            val elements = JSONObject(body).optJSONArray("elements") ?: JSONArray()
            val places = mutableListOf<TrainStation>()
            for (i in 0 until elements.length()) {
                val item = elements.optJSONObject(i) ?: continue
                val tags = item.optJSONObject("tags") ?: continue
                val name = tags.optString("name")
                if (name.isBlank()) continue
                val lat = item.optDouble("lat")
                val lon = item.optDouble("lon")
                val matchedId = matchStationIdByName(name, catalog)
                    ?: mavIdFromUicRef(tags.optString("uic_ref"))
                places.add(
                    TrainStation(
                        name = name,
                        address = tags.optString("operator").ifBlank { "OpenStreetMap" },
                        distanceMeters = dist(location, lat, lon),
                        latitude = lat,
                        longitude = lon,
                        stationId = matchedId
                    )
                )
            }
            places.distinctBy { it.stationId ?: it.name }
                .sortedBy { it.distanceMeters ?: Int.MAX_VALUE }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun matchStationIdByName(
        name: String,
        catalog: List<TrainStationCache.CachedStation>
    ): String? {
        val normalized = normalizeStationQuery(name)
        return catalog.firstOrNull { station ->
            val stationNorm = normalizeStationQuery(station.name)
            stationNorm == normalized ||
                stationNorm.contains(normalized) ||
                normalized.contains(stationNorm)
        }?.id
    }

    /**
     * Az OpenStreetMap uic_ref tagjéből MÁV állomás ID-t képez.
     * Az OSM uic_ref (pl. "5510017") vezető nullákkal kiegészítve adja a
     * MÁV AllomasID-t (pl. "005510017"), amivel lekérdezhető a menetrend.
     * Ez megkerüli a MÁV katalógus (GetAlapadatok) hiányát.
     */
    private fun mavIdFromUicRef(uicRef: String?): String? {
        val digits = uicRef?.trim()?.filter { it.isDigit() } ?: return null
        if (digits.length < 6) return null
        // 9 számjegyre egészítjük ki vezető nullákkal (MÁV formátum)
        return digits.padStart(9, '0')
    }

    private fun computeDelayMinutes(scheduledSec: Long, actualSec: Long?): Int? {
        actualSec ?: return null
        val diff = ((actualSec - scheduledSec) / 60L).toInt()
        return diff.takeIf { it > 0 }
    }

    private fun parseHungarianCoordinate(raw: String): Double? {
        if (raw.isBlank()) return null
        return raw.replace(",", ".").toDoubleOrNull()
    }

    private fun normalizeStationQuery(query: String): String =
        query.lowercase(Locale("hu", "HU"))
            .replace("állomás", "")
            .replace("allomas", "")
            .replace(Regex("\\s+"), " ")
            .trim()

    private fun matchesStationQuery(stationName: String, normalizedQuery: String): Boolean {
        val normalizedStation = normalizeStationQuery(stationName)
        return normalizedStation.contains(normalizedQuery) ||
            normalizedQuery.contains(normalizedStation) ||
            normalizedStation.split(" ").any {
                it.startsWith(normalizedQuery) || normalizedQuery.startsWith(it)
            }
    }

    private fun budapestDayStartEpochSec(): Long {
        val tz = TimeZone.getTimeZone("Europe/Budapest")
        val cal = Calendar.getInstance(tz).apply {
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        return cal.timeInMillis / 1000L
    }

    private fun postMavJson(endpoint: String, body: JSONObject): JSONObject? {
        for (base in MAV_BASE_URLS) {
            try {
                val url = "$base$endpoint"
                val connection = (URL(url).openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = 15000
                    readTimeout = 20000
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json; charset=UTF-8")
                    setRequestProperty("Accept", "application/json")
                    setRequestProperty("User-Agent", USER_AGENT)
                }
                OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                    writer.write(body.toString())
                }
                if (connection.responseCode !in 200..299) continue
                val text = connection.inputStream.bufferedReader().use { it.readText() }
                if (text.isBlank() || text.startsWith("<")) continue
                return JSONObject(text)
            } catch (_: Exception) {
                continue
            }
        }
        return null
    }

    private fun dist(origin: Location, lat: Double, lon: Double): Int {
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
                mainHandler.post { onError(e.message ?: "Vonat információ hiba.") }
            } catch (_: Exception) {
                mainHandler.post {
                    onError("Vonat információ lekérdezés sikertelen. Ellenőrizd az internetkapcsolatot.")
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

    private data class LiveTrain(
        val trainNumber: String,
        val latitude: Double?,
        val longitude: Double?,
        val delayMinutes: Int?
    ) {
        fun delayText(): String? = delayMinutes?.takeIf { it > 0 }?.let { "$it perces késés" }
    }
}