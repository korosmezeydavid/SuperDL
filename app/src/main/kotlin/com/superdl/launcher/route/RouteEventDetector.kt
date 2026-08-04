package com.superdl.launcher.route

import android.location.Location
import com.superdl.launcher.gps.CrossingPoint
import com.superdl.launcher.gps.GpsOverpassHelper
import com.superdl.launcher.gps.GpsRadarMath
import kotlin.math.abs

class RouteEventDetector {

    companion object {
        private const val TURN_THRESHOLD_DEG = 40f
        private const val SLIGHT_TURN_THRESHOLD_DEG = 25f
        private const val U_TURN_THRESHOLD_DEG = 150f
        private const val MIN_SEGMENT_METERS = 8
        private const val CROSSING_RADIUS_M = 12
        private const val CROSSING_FETCH_INTERVAL_MS = 12_000L

        // Kanyar-simítás: hány szegmens irányát átlagoljuk, és mekkora
        // minimális távolság kell két rögzített kanyar között (GPS-zaj szűrése).
        private const val BEARING_SMOOTHING_WINDOW = 3
        private const val MIN_DISTANCE_BETWEEN_TURNS_M = 15
    }

    private var lastBearing: Float? = null
    private val recentBearings = ArrayDeque<Float>()
    private var lastTurnLat: Double? = null
    private var lastTurnLon: Double? = null
    private val announcedCrossingKeys = mutableSetOf<String>()
    private var lastCrossingFetchAt = 0L
    private var cachedCrossings: List<CrossingPoint> = emptyList()

    fun reset() {
        lastBearing = null
        recentBearings.clear()
        lastTurnLat = null
        lastTurnLon = null
        announcedCrossingKeys.clear()
        lastCrossingFetchAt = 0L
        cachedCrossings = emptyList()
    }

    fun onLocation(location: Location, previousPoint: RoutePoint?): List<RouteEvent> {
        val events = mutableListOf<RouteEvent>()
        val timestampMs = location.time.takeIf { it > 0L } ?: System.currentTimeMillis()

        if (previousPoint != null) {
            val segmentDistance = GpsRadarMath.distanceMeters(
                previousPoint.latitude,
                previousPoint.longitude,
                location.latitude,
                location.longitude
            )
            if (segmentDistance >= MIN_SEGMENT_METERS) {
                val bearing = GpsRadarMath.bearingDegrees(
                    previousPoint.latitude,
                    previousPoint.longitude,
                    location.latitude,
                    location.longitude
                )
                detectTurn(
                    bearing = bearing,
                    latitude = location.latitude,
                    longitude = location.longitude,
                    timestampMs = timestampMs
                )?.let(events::add)
            }
        }

        detectCrossing(
            latitude = location.latitude,
            longitude = location.longitude,
            timestampMs = timestampMs
        )?.let(events::add)

        return events
    }

    fun refreshCrossings(latitude: Double, longitude: Double) {
        val now = System.currentTimeMillis()
        if (now - lastCrossingFetchAt < CROSSING_FETCH_INTERVAL_MS) return
        lastCrossingFetchAt = now
        Thread {
            cachedCrossings = GpsOverpassHelper.fetchNearbyCrossings(latitude, longitude)
        }.start()
    }

    private fun detectTurn(
        bearing: Float,
        latitude: Double,
        longitude: Double,
        timestampMs: Long
    ): RouteEvent? {
        // Az előző haladási irány a simított (átlagolt) irány, nem egyetlen
        // zajos szegmens. Így a GPS-ingadozás nem okoz hamis kanyarokat.
        val previous = smoothedBearing()

        // Az aktuális szegmens irányát hozzáadjuk a simító ablakhoz.
        recentBearings.addLast(bearing)
        while (recentBearings.size > BEARING_SMOOTHING_WINDOW) {
            recentBearings.removeFirst()
        }
        lastBearing = bearing

        if (previous == null) return null

        val delta = bearingDelta(previous, bearing)
        val absDelta = abs(delta)
        val type = when {
            absDelta >= U_TURN_THRESHOLD_DEG -> RouteEventType.U_TURN
            absDelta >= TURN_THRESHOLD_DEG -> if (delta > 0f) {
                RouteEventType.TURN_RIGHT
            } else {
                RouteEventType.TURN_LEFT
            }
            absDelta >= SLIGHT_TURN_THRESHOLD_DEG -> RouteEventType.TURN_SLIGHT
            else -> return null
        }

        // Ne rögzítsünk két kanyart túl közel egymáshoz (GPS-zaj szűrése).
        val prevLat = lastTurnLat
        val prevLon = lastTurnLon
        if (prevLat != null && prevLon != null) {
            val distSinceLastTurn = GpsRadarMath.distanceMeters(prevLat, prevLon, latitude, longitude)
            if (distSinceLastTurn < MIN_DISTANCE_BETWEEN_TURNS_M) return null
        }
        lastTurnLat = latitude
        lastTurnLon = longitude

        return RouteEvent(
            type = type,
            latitude = latitude,
            longitude = longitude,
            timestampMs = timestampMs
        )
    }

    /** A legutóbbi néhány szegmens átlagolt iránya (kör-átlag fokban). */
    private fun smoothedBearing(): Float? {
        if (recentBearings.isEmpty()) return null
        var sinSum = 0.0
        var cosSum = 0.0
        for (b in recentBearings) {
            val rad = Math.toRadians(b.toDouble())
            sinSum += kotlin.math.sin(rad)
            cosSum += kotlin.math.cos(rad)
        }
        val avg = Math.toDegrees(kotlin.math.atan2(sinSum, cosSum)).toFloat()
        return (avg + 360f) % 360f
    }

    private fun detectCrossing(
        latitude: Double,
        longitude: Double,
        timestampMs: Long
    ): RouteEvent? {
        for (crossing in cachedCrossings) {
            val key = "${crossing.latitude}_${crossing.longitude}"
            if (key in announcedCrossingKeys) continue
            val distance = GpsRadarMath.distanceMeters(
                latitude,
                longitude,
                crossing.latitude,
                crossing.longitude
            )
            if (distance <= CROSSING_RADIUS_M) {
                announcedCrossingKeys.add(key)
                return RouteEvent(
                    type = RouteEventType.CROSSING,
                    latitude = crossing.latitude,
                    longitude = crossing.longitude,
                    timestampMs = timestampMs,
                    label = "Kereszteződés"
                )
            }
        }
        return null
    }

    private fun bearingDelta(from: Float, to: Float): Float {
        var delta = to - from
        while (delta > 180f) delta -= 360f
        while (delta < -180f) delta += 360f
        return delta
    }
}