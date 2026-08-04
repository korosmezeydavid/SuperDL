package com.superdl.launcher.gps

import com.superdl.launcher.transit.TransitPlace
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import kotlin.math.abs

object GpsStreetHelper {

    private const val USER_AGENT = "SuperDL/1.48 (vak-barat launcher; korosmezey.david.richard@gmail.com)"
    private const val INTERSECTION_RADIUS_M = 150
    private const val AHEAD_TOLERANCE_DEG = 50f

    fun fetchStreetContext(
        latitude: Double,
        longitude: Double,
        headingDegrees: Float
    ): StreetContext {
        val currentStreet = fetchCurrentStreet(latitude, longitude)
        val intersections = GpsOverpassHelper.fetchNearbyIntersections(latitude, longitude, INTERSECTION_RADIUS_M)
            .mapNotNull { enrichIntersection(it, latitude, longitude, headingDegrees, currentStreet) }
            .distinctBy { it.id }
            .sortedBy { it.distanceMeters }
        return StreetContext(currentStreet = currentStreet, intersections = intersections)
    }

    fun intersectionAhead(context: StreetContext, headingDegrees: Float): StreetIntersection? =
        context.intersections
            .filter { GpsRadarMath.isAhead(it.bearingDegrees, headingDegrees, AHEAD_TOLERANCE_DEG) }
            .minByOrNull { it.distanceMeters }

    fun refreshContext(
        context: StreetContext,
        userLat: Double,
        userLon: Double,
        headingDegrees: Float
    ): StreetContext {
        val refreshed = context.intersections.mapNotNull { intersection ->
            refreshIntersection(intersection, userLat, userLon, headingDegrees)
        }.sortedBy { it.distanceMeters }
        return context.copy(intersections = refreshed)
    }

    private fun refreshIntersection(
        intersection: StreetIntersection,
        userLat: Double,
        userLon: Double,
        headingDegrees: Float
    ): StreetIntersection? {
        val distance = GpsRadarMath.distanceMeters(
            userLat, userLon, intersection.latitude, intersection.longitude
        )
        if (distance > INTERSECTION_RADIUS_M + 30) return null
        val bearing = GpsRadarMath.bearingDegrees(
            userLat, userLon, intersection.latitude, intersection.longitude
        )
        val relative = GpsRadarMath.relativeBearing(bearing, headingDegrees)
        return intersection.copy(
            distanceMeters = distance,
            bearingDegrees = bearing,
            clockDirection = GpsRadarMath.clockDirection(relative),
            isAhead = GpsRadarMath.isAhead(bearing, headingDegrees, AHEAD_TOLERANCE_DEG)
        )
    }

    fun intersectionsToPois(context: StreetContext, headingDegrees: Float): List<GpsPoi> {
        val result = mutableListOf<GpsPoi>()
        context.currentStreet?.let { street ->
            result.add(
                GpsPoi(
                    id = "street_current",
                    name = street,
                    category = "utca",
                    latitude = 0.0,
                    longitude = 0.0,
                    distanceMeters = 0,
                    bearingDegrees = headingDegrees,
                    clockDirection = "12 óra",
                    detailText = "Jelenleg a $street utcán vagy."
                )
            )
        }
        context.intersections.forEach { intersection ->
            result.add(intersection.toGpsPoi(headingDegrees))
        }
        return result
    }

    fun speakWhereAmI(context: StreetContext, headingDegrees: Float): String {
        val streetPart = context.currentStreet?.let { "A $it utcán vagy." } ?: "Utcanév nem állapítható meg."
        val ahead = intersectionAhead(context, headingDegrees)
        val aheadPart = ahead?.speakAhead() ?: "Nincs kereszteződés közvetlenül előtted a közelben."
        return "$streetPart $aheadPart"
    }

    private fun enrichIntersection(
        raw: IntersectionRaw,
        userLat: Double,
        userLon: Double,
        headingDegrees: Float,
        currentStreet: String?
    ): StreetIntersection? {
        if (raw.streetNames.size < 2) return null
        val distance = GpsRadarMath.distanceMeters(userLat, userLon, raw.latitude, raw.longitude)
        val bearing = GpsRadarMath.bearingDegrees(userLat, userLon, raw.latitude, raw.longitude)
        val relative = GpsRadarMath.relativeBearing(bearing, headingDegrees)
        val branches = raw.streetNames
            .filter { currentStreet == null || !namesMatch(it, currentStreet) }
            .map { streetName ->
                val branchBearing = raw.branchBearings[streetName]
                    ?: bearing
                val branchRelative = GpsRadarMath.relativeBearing(branchBearing, headingDegrees)
                CrossStreetBranch(
                    name = streetName,
                    clockDirection = GpsRadarMath.clockDirection(branchRelative),
                    positionLabel = GpsRadarMath.relativePositionLabel(branchRelative)
                )
            }
            .distinctBy { it.name }
        if (branches.isEmpty()) return null
        return StreetIntersection(
            id = "intersection_${raw.latitude}_${raw.longitude}",
            latitude = raw.latitude,
            longitude = raw.longitude,
            distanceMeters = distance,
            bearingDegrees = bearing,
            clockDirection = GpsRadarMath.clockDirection(relative),
            crossStreets = branches,
            isAhead = GpsRadarMath.isAhead(bearing, headingDegrees, AHEAD_TOLERANCE_DEG)
        )
    }

    private fun namesMatch(a: String, b: String): Boolean {
        val na = normalizeStreetName(a)
        val nb = normalizeStreetName(b)
        return na == nb || na.contains(nb) || nb.contains(na)
    }

    private fun normalizeStreetName(name: String): String =
        name.lowercase()
            .replace("út", "")
            .replace("utca", "")
            .replace("tér", "")
            .replace("körút", "")
            .replace("sétány", "")
            .replace(Regex("\\s+"), "")
            .trim()

    fun fetchCurrentStreet(latitude: Double, longitude: Double): String? {
        fetchCurrentStreetFromNominatim(latitude, longitude)?.let { return it }
        return GpsOverpassHelper.fetchNearestStreetName(latitude, longitude)
    }

    private fun fetchCurrentStreetFromNominatim(latitude: Double, longitude: Double): String? {
        // Stabilizált: több Nominatim-tükör + újrapróbálkozás.
        val json = GpsNetworkClient.getWithFailover(GpsNetworkClient.NOMINATIM_MIRRORS) { base ->
            "$base/reverse?lat=$latitude&lon=$longitude" +
                "&format=json&accept-language=hu&zoom=19&addressdetails=1"
        } ?: return null
        return try {
            val address = JSONObject(json).optJSONObject("address") ?: return null
            address.optString("road")
                .ifBlank { address.optString("pedestrian") }
                .ifBlank { address.optString("footway") }
                .ifBlank { address.optString("cycleway") }
                .ifBlank { address.optString("path") }
                .ifBlank { address.optString("residential") }
                .ifBlank { null }
        } catch (_: Exception) {
            null
        }
    }

    private fun fetchText(url: String): String {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.connectTimeout = 12_000
        connection.readTimeout = 12_000
        connection.setRequestProperty("User-Agent", USER_AGENT)
        if (connection.responseCode !in 200..299) {
            throw GpsRadarException("Utcanév lekérdezés sikertelen.")
        }
        return connection.inputStream.bufferedReader().readText()
    }
}

data class StreetContext(
    val currentStreet: String?,
    val intersections: List<StreetIntersection>
)

data class CrossStreetBranch(
    val name: String,
    val clockDirection: String,
    val positionLabel: String
)

data class StreetIntersection(
    val id: String,
    val latitude: Double,
    val longitude: Double,
    val distanceMeters: Int,
    val bearingDegrees: Float,
    val clockDirection: String,
    val crossStreets: List<CrossStreetBranch>,
    val isAhead: Boolean
) {
    fun speakBranches(): String =
        crossStreets.joinToString(", ") { "${it.name} ${it.positionLabel}" }

    fun speakAhead(): String = buildString {
        append("Kereszteződés ")
        append(TransitPlace.formatDistance(distanceMeters))
        append("re, $clockDirection irányában. ")
        append(speakBranches())
        append(".")
    }

    fun speakRadar(): String = buildString {
        append("Kereszteződés, ")
        append(TransitPlace.formatDistance(distanceMeters))
        append("re, $clockDirection irányában. ")
        append(speakBranches())
    }

    fun speakPassing(): String = buildString {
        append("Kereszteződés. ")
        append(speakBranches())
        append(".")
    }

    fun toGpsPoi(headingDegrees: Float): GpsPoi {
        val relative = GpsRadarMath.relativeBearing(bearingDegrees, headingDegrees)
        return GpsPoi(
            id = id,
            name = "Kereszteződés",
            category = "kereszteződés",
            latitude = latitude,
            longitude = longitude,
            distanceMeters = distanceMeters,
            bearingDegrees = bearingDegrees,
            clockDirection = GpsRadarMath.clockDirection(relative),
            detailText = speakBranches()
        )
    }
}

data class IntersectionRaw(
    val latitude: Double,
    val longitude: Double,
    val streetNames: List<String>,
    val branchBearings: Map<String, Float>
)