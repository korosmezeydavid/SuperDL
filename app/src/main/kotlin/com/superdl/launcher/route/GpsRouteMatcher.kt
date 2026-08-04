package com.superdl.launcher.route

import com.superdl.launcher.gps.GpsRadarMath

data class RouteMatch(
    val pointIndex: Int,
    val distanceToRouteM: Int,
    val nextEvent: RouteEvent?,
    val nextEventIndex: Int,
    val distanceToNextEventM: Int?,
    val reversed: Boolean = false
)

object GpsRouteMatcher {

    private const val MAX_OFF_ROUTE_M = 35

    fun match(
        route: GpsRouteRecording,
        latitude: Double,
        longitude: Double,
        reversed: Boolean = false
    ): RouteMatch {
        val points = route.points
        if (points.isEmpty()) {
            return RouteMatch(-1, Int.MAX_VALUE, null, -1, null, reversed)
        }

        var closestIndex = 0
        var closestDistance = Int.MAX_VALUE
        for (i in points.indices) {
            val distance = GpsRadarMath.distanceMeters(
                latitude,
                longitude,
                points[i].latitude,
                points[i].longitude
            )
            if (distance < closestDistance) {
                closestDistance = distance
                closestIndex = i
            }
        }

        val eventIndices = route.events.mapIndexed { eventIndex, event ->
            Triple(eventIndex, event, nearestPointIndex(points, event.latitude, event.longitude))
        }
        val next = if (reversed) {
            eventIndices
                .filter { (_, _, pointIndex) -> pointIndex < closestIndex }
                .maxByOrNull { (_, _, pointIndex) -> pointIndex }
        } else {
            eventIndices
                .filter { (_, _, pointIndex) -> pointIndex > closestIndex }
                .minByOrNull { (_, _, pointIndex) -> pointIndex - closestIndex }
        }

        val nextEvent = next?.second
        val nextEventIndex = next?.first ?: -1
        val distanceToNextEvent = nextEvent?.let {
            GpsRadarMath.distanceMeters(latitude, longitude, it.latitude, it.longitude)
        }

        return RouteMatch(
            pointIndex = closestIndex,
            distanceToRouteM = closestDistance,
            nextEvent = nextEvent,
            nextEventIndex = nextEventIndex,
            distanceToNextEventM = distanceToNextEvent,
            reversed = reversed
        )
    }

    fun isOnRoute(match: RouteMatch): Boolean =
        match.pointIndex >= 0 && match.distanceToRouteM <= MAX_OFF_ROUTE_M

    private fun nearestPointIndex(points: List<RoutePoint>, latitude: Double, longitude: Double): Int {
        var closestIndex = 0
        var closestDistance = Int.MAX_VALUE
        for (i in points.indices) {
            val distance = GpsRadarMath.distanceMeters(
                latitude,
                longitude,
                points[i].latitude,
                points[i].longitude
            )
            if (distance < closestDistance) {
                closestDistance = distance
                closestIndex = i
            }
        }
        return closestIndex
    }
}