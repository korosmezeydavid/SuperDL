package com.superdl.launcher.route

import android.content.Context
import android.content.Intent
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

object GpsRouteStore {

    private const val PREFS = "superdl"
    private const val KEY = "gps_routes"
    private const val MAX_ROUTES = 20

    fun getAll(context: Context): List<GpsRouteRecording> =
        loadRaw(context).sortedByDescending { it.createdAtMs }

    fun getById(context: Context, id: String): GpsRouteRecording? =
        loadRaw(context).firstOrNull { it.id == id }

    fun save(context: Context, route: GpsRouteRecording): GpsRouteRecording {
        val current = loadRaw(context).toMutableList()
        val index = current.indexOfFirst { it.id == route.id }
        if (index >= 0) {
            current[index] = route
        } else {
            current.add(0, route)
        }
        val trimmed = current.sortedByDescending { it.createdAtMs }.take(MAX_ROUTES)
        persist(context, trimmed)
        return route
    }

    fun remove(context: Context, id: String): Boolean {
        val current = loadRaw(context)
        val updated = current.filterNot { it.id == id }
        if (updated.size == current.size) return false
        persist(context, updated)
        return true
    }

    fun startRecording(context: Context, name: String) {
        GpsRouteSession.clearRecording()
        GpsRouteSession.isRecording = true
        GpsRouteSession.recordingName = name.trim().ifBlank { "Útvonal" }
        val intent = Intent(context, GpsRouteRecorderService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        } catch (_: Exception) {
        }
    }

    fun stopRecording(context: Context): GpsRouteRecording? {
        GpsRouteSession.isRecording = false
        context.stopService(Intent(context, GpsRouteRecorderService::class.java))
        if (GpsRouteSession.points.isEmpty()) {
            GpsRouteSession.clearRecording()
            return null
        }
        val lastPoint = GpsRouteSession.points.last()
        GpsRouteSession.events.add(
            RouteEvent(
                type = RouteEventType.STOP,
                latitude = lastPoint.latitude,
                longitude = lastPoint.longitude,
                timestampMs = System.currentTimeMillis()
            )
        )
        val route = GpsRouteRecording(
            id = UUID.randomUUID().toString(),
            name = GpsRouteSession.recordingName,
            createdAtMs = System.currentTimeMillis(),
            points = GpsRouteSession.points.toList(),
            events = GpsRouteSession.events.toList()
        )
        save(context, route)
        GpsRouteSession.clearRecording()
        return route
    }

    fun startGuidance(context: Context, route: GpsRouteRecording) {
        GpsRouteSession.clearGuidance()
        GpsRouteSession.activeRoute = route
        GpsRouteSession.isGuiding = true
        val intent = Intent(context, GpsRouteGuideService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        } catch (_: Exception) {
        }
    }

    fun stopGuidance(context: Context) {
        GpsRouteSession.isGuiding = false
        GpsRouteSession.activeRoute = null
        context.stopService(Intent(context, GpsRouteGuideService::class.java))
        GpsRouteSession.clearGuidance()
    }

    private fun loadRaw(context: Context): List<GpsRouteRecording> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY, null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val item = array.getJSONObject(i)
                    val name = item.optString("name").trim()
                    if (name.isBlank()) continue
                    add(
                        GpsRouteRecording(
                            id = item.optString("id", UUID.randomUUID().toString()),
                            name = name,
                            createdAtMs = item.optLong("createdAtMs", System.currentTimeMillis()),
                            points = parsePoints(item.optJSONArray("points")),
                            events = parseEvents(item.optJSONArray("events"))
                        )
                    )
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun parsePoints(array: JSONArray?): List<RoutePoint> {
        if (array == null) return emptyList()
        return buildList {
            for (i in 0 until array.length()) {
                val item = array.optJSONObject(i) ?: continue
                add(
                    RoutePoint(
                        latitude = item.optDouble("latitude"),
                        longitude = item.optDouble("longitude"),
                        timestampMs = item.optLong("timestampMs"),
                        accuracyM = if (item.has("accuracyM") && !item.isNull("accuracyM")) {
                            item.optInt("accuracyM").takeIf { it > 0 }
                        } else {
                            null
                        },
                        bearing = if (item.has("bearing") && !item.isNull("bearing")) {
                            item.optDouble("bearing").toFloat()
                        } else {
                            null
                        }
                    )
                )
            }
        }
    }

    private fun parseEvents(array: JSONArray?): List<RouteEvent> {
        if (array == null) return emptyList()
        return buildList {
            for (i in 0 until array.length()) {
                val item = array.optJSONObject(i) ?: continue
                val type = runCatching {
                    RouteEventType.valueOf(item.optString("type"))
                }.getOrNull() ?: continue
                add(
                    RouteEvent(
                        type = type,
                        latitude = item.optDouble("latitude"),
                        longitude = item.optDouble("longitude"),
                        timestampMs = item.optLong("timestampMs"),
                        label = item.optString("label").takeIf { it.isNotBlank() }
                    )
                )
            }
        }
    }

    private fun persist(context: Context, routes: List<GpsRouteRecording>) {
        val array = JSONArray()
        routes.forEach { route ->
            val points = JSONArray()
            route.points.forEach { point ->
                points.put(
                    JSONObject()
                        .put("latitude", point.latitude)
                        .put("longitude", point.longitude)
                        .put("timestampMs", point.timestampMs)
                        .put("accuracyM", point.accuracyM ?: JSONObject.NULL)
                        .put("bearing", point.bearing ?: JSONObject.NULL)
                )
            }
            val events = JSONArray()
            route.events.forEach { event ->
                events.put(
                    JSONObject()
                        .put("type", event.type.name)
                        .put("latitude", event.latitude)
                        .put("longitude", event.longitude)
                        .put("timestampMs", event.timestampMs)
                        .put("label", event.label ?: JSONObject.NULL)
                )
            }
            array.put(
                JSONObject()
                    .put("id", route.id)
                    .put("name", route.name)
                    .put("createdAtMs", route.createdAtMs)
                    .put("points", points)
                    .put("events", events)
            )
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY, array.toString())
            .apply()
    }
}