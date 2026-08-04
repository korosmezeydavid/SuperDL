package com.superdl.launcher.gps

import android.location.Location

/**
 * Voice Vista / Microsoft Soundscape-szerű környezeti utcabemondás.
 * Utcaváltáskor és közeledő kereszteződéseknél ad hangos visszajelzést.
 */
object GpsStreetAnnouncer {

    private val INTERSECTION_APPROACH_THRESHOLDS_M = listOf(80, 50, 25, 12)
    private const val INTERSECTION_PASS_DISTANCE_M = 18
    private const val MIN_MOVE_BETWEEN_FETCH_M = 12f
    private const val MIN_FETCH_INTERVAL_MS = 7_000L

    @Volatile
    private var lastFetchAt = 0L

    @Volatile
    private var lastFetchLat = 0.0

    @Volatile
    private var lastFetchLon = 0.0

    @Volatile
    private var fetchInFlight = false

    fun resetSession() {
        lastFetchAt = 0L
        lastFetchLat = 0.0
        lastFetchLon = 0.0
        fetchInFlight = false
        GpsRadarStore.lastAnnouncedStreet = null
        GpsRadarStore.announcedIntersectionKeys.clear()
        GpsRadarStore.announcedIntersectionMilestones.clear()
        GpsRadarStore.streetContext = null
    }

    fun shouldFetchContext(location: Location, now: Long = System.currentTimeMillis()): Boolean {
        if (fetchInFlight) return false
        if (now - lastFetchAt < MIN_FETCH_INTERVAL_MS) return false
        if (lastFetchLat == 0.0 && lastFetchLon == 0.0) return true
        val moved = movedMeters(lastFetchLat, lastFetchLon, location.latitude, location.longitude)
        return moved >= MIN_MOVE_BETWEEN_FETCH_M
    }

    fun fetchContextAsync(
        latitude: Double,
        longitude: Double,
        headingDegrees: Float,
        onResult: (StreetContext?) -> Unit
    ) {
        if (fetchInFlight) return
        fetchInFlight = true
        Thread {
            val context = try {
                GpsStreetHelper.fetchStreetContext(latitude, longitude, headingDegrees)
            } catch (_: Exception) {
                null
            }
            lastFetchAt = System.currentTimeMillis()
            lastFetchLat = latitude
            lastFetchLon = longitude
            fetchInFlight = false
            if (context != null) {
                GpsRadarStore.streetContext = context
            }
            onResult(context)
        }.start()
    }

    fun evaluate(context: StreetContext, headingDegrees: Float): List<String> {
        if (!GpsRadarStore.streetMonitoringEnabled) return emptyList()
        val messages = mutableListOf<String>()

        context.currentStreet?.let { street ->
            if (street != GpsRadarStore.lastAnnouncedStreet) {
                GpsRadarStore.lastAnnouncedStreet = street
                messages.add("Most a $street utcán vagy.")
            }
        }

        val ahead = GpsStreetHelper.intersectionAhead(context, headingDegrees)
        if (ahead != null) {
            for (threshold in INTERSECTION_APPROACH_THRESHOLDS_M) {
                if (ahead.distanceMeters > threshold) continue
                val key = "${ahead.id}_approach_$threshold"
                if (key in GpsRadarStore.announcedIntersectionMilestones) continue
                GpsRadarStore.announcedIntersectionMilestones.add(key)
                messages.add(buildApproachMessage(ahead, threshold))
            }
        }

        context.intersections.forEach { intersection ->
            if (intersection.distanceMeters > INTERSECTION_PASS_DISTANCE_M) return@forEach
            if (intersection.id in GpsRadarStore.announcedIntersectionKeys) return@forEach
            GpsRadarStore.announcedIntersectionKeys.add(intersection.id)
            messages.add(intersection.speakPassing())
        }

        pruneStaleIntersectionState(context)
        return messages
    }

    fun introMessage(): String =
        "Környezeti figyelő aktív. Utcaneveket és kereszteződéseket mondok be séta közben, " +
            "mint a Voice Vista programban. A műveletek menüben ki-be kapcsolható."

    private fun buildApproachMessage(intersection: StreetIntersection, threshold: Int): String =
        buildString {
            append("Kereszteződés ")
            when (threshold) {
                80 -> append("közeledik, ")
                50 -> append(" ")
                25 -> append("hamarosan, ")
                else -> append(" ")
            }
            append(com.superdl.launcher.transit.TransitPlace.formatDistance(intersection.distanceMeters))
            append("re, ${intersection.clockDirection} irányban. ")
            append(intersection.speakBranches())
            append(".")
        }

    private fun pruneStaleIntersectionState(context: StreetContext) {
        val nearbyIds = context.intersections
            .filter { it.distanceMeters <= 120 }
            .map { it.id }
            .toSet()
        if (nearbyIds.isEmpty()) return
        GpsRadarStore.announcedIntersectionKeys.retainAll(nearbyIds)
        GpsRadarStore.announcedIntersectionMilestones.removeIf { milestone ->
            val intersectionId = milestone.substringBefore("_approach_")
            intersectionId !in nearbyIds
        }
    }

    private fun movedMeters(fromLat: Double, fromLon: Double, toLat: Double, toLon: Double): Float {
        val result = FloatArray(1)
        Location.distanceBetween(fromLat, fromLon, toLat, toLon, result)
        return result[0]
    }
}