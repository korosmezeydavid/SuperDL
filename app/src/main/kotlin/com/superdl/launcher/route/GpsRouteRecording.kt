package com.superdl.launcher.route

import android.location.Location

enum class RouteEventType {
    START,
    STOP,
    TURN_LEFT,
    TURN_RIGHT,
    TURN_SLIGHT,
    U_TURN,
    CROSSING,
    WAYPOINT
}

data class RoutePoint(
    val latitude: Double,
    val longitude: Double,
    val timestampMs: Long,
    val accuracyM: Int? = null,
    val bearing: Float? = null
)

data class RouteEvent(
    val type: RouteEventType,
    val latitude: Double,
    val longitude: Double,
    val timestampMs: Long,
    val label: String? = null
)

data class GpsRouteRecording(
    val id: String,
    val name: String,
    val createdAtMs: Long,
    val points: List<RoutePoint>,
    val events: List<RouteEvent>
) {
    fun speakPreview(): String = name

    fun totalDistanceMeters(): Int {
        if (points.size < 2) return 0
        var total = 0
        for (i in 1 until points.size) {
            val prev = points[i - 1]
            val curr = points[i]
            total += distanceBetween(prev, curr)
        }
        return total
    }

    private fun distanceBetween(from: RoutePoint, to: RoutePoint): Int {
        val result = FloatArray(1)
        Location.distanceBetween(
            from.latitude,
            from.longitude,
            to.latitude,
            to.longitude,
            result
        )
        return result[0].toInt().coerceAtLeast(0)
    }
}

object GpsRouteSession {
    @Volatile
    var isRecording: Boolean = false

    @Volatile
    var recordingName: String = ""

    @Volatile
    var points: MutableList<RoutePoint> = mutableListOf()

    @Volatile
    var events: MutableList<RouteEvent> = mutableListOf()

    @Volatile
    var isGuiding: Boolean = false

    @Volatile
    var activeRoute: GpsRouteRecording? = null

    @Volatile
    var lastLocation: Location? = null

    @Volatile
    var lastAnnouncedEventIndex: Int = -1

    @Volatile
    var lastApproachThreshold: Int? = null

    @Volatile
    var lastPointIndex: Int = -1

    @Volatile
    var guidanceReversed: Boolean = false

    @Volatile
    var announcedReverseDirection: Boolean = false

    fun clearRecording() {
        isRecording = false
        recordingName = ""
        points = mutableListOf()
        events = mutableListOf()
    }

    fun clearGuidance() {
        isGuiding = false
        activeRoute = null
        lastLocation = null
        lastAnnouncedEventIndex = -1
        lastApproachThreshold = null
        lastPointIndex = -1
        guidanceReversed = false
        announcedReverseDirection = false
    }
}