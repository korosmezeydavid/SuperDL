package com.superdl.launcher.gps

import android.location.Location
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin

object GpsRadarMath {

    const val FACING_TOLERANCE_DEGREES = 28f

    fun distanceMeters(fromLat: Double, fromLon: Double, toLat: Double, toLon: Double): Int {
        val result = FloatArray(1)
        Location.distanceBetween(fromLat, fromLon, toLat, toLon, result)
        return result[0].toInt().coerceAtLeast(0)
    }

    fun bearingDegrees(fromLat: Double, fromLon: Double, toLat: Double, toLon: Double): Float {
        val lat1 = Math.toRadians(fromLat)
        val lat2 = Math.toRadians(toLat)
        val dLon = Math.toRadians(toLon - fromLon)
        val y = sin(dLon) * cos(lat2)
        val x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dLon)
        return ((Math.toDegrees(atan2(y, x)) + 360) % 360).toFloat()
    }

    fun relativeBearing(absoluteBearing: Float, headingDegrees: Float): Float =
        ((absoluteBearing - headingDegrees + 360) % 360)

    fun clockDirection(relativeBearing: Float): String {
        val hour = (((relativeBearing + 15f) / 30f).toInt()) % 12
        val clockHour = if (hour == 0) 12 else hour
        return "$clockHour óra"
    }

    fun isFacingTarget(relativeBearing: Float, tolerance: Float = FACING_TOLERANCE_DEGREES): Boolean =
        relativeBearing <= tolerance || relativeBearing >= 360f - tolerance

    fun turnHint(relativeBearing: Float): String = when {
        isFacingTarget(relativeBearing) -> "Jó irány, egyenesen."
        relativeBearing in 1f..180f -> "Fordulj jobbra."
        else -> "Fordulj balra."
    }

    fun isAhead(absoluteBearing: Float, headingDegrees: Float, tolerance: Float = 45f): Boolean {
        val relative = relativeBearing(absoluteBearing, headingDegrees)
        return relative <= tolerance || relative >= 360f - tolerance
    }

    fun relativePositionLabel(relativeBearing: Float): String = when {
        relativeBearing <= 25f || relativeBearing >= 335f -> "előtted"
        relativeBearing in 26f..70f -> "jobbra előtted"
        relativeBearing in 71f..110f -> "jobbra"
        relativeBearing in 111f..160f -> "jobbra mögötted"
        relativeBearing in 161f..199f -> "mögötted"
        relativeBearing in 200f..249f -> "balra mögötted"
        relativeBearing in 250f..289f -> "balra"
        else -> "balra előtted"
    }

    fun enrichPoi(
        raw: GpsPoiRaw,
        userLat: Double,
        userLon: Double,
        headingDegrees: Float
    ): GpsPoi {
        val distance = distanceMeters(userLat, userLon, raw.latitude, raw.longitude)
        val bearing = bearingDegrees(userLat, userLon, raw.latitude, raw.longitude)
        val relative = relativeBearing(bearing, headingDegrees)
        return GpsPoi(
            id = raw.id,
            name = raw.name,
            category = raw.category,
            latitude = raw.latitude,
            longitude = raw.longitude,
            distanceMeters = distance,
            bearingDegrees = bearing,
            clockDirection = clockDirection(relative)
        )
    }
}

data class GpsPoiRaw(
    val id: String,
    val name: String,
    val category: String,
    val latitude: Double,
    val longitude: Double
)