package com.superdl.launcher.gps

import android.content.Context
import android.location.Location
import android.os.Handler
import android.os.Looper

object GpsRadarHelper {

    fun loadNearbyPois(
        context: Context,
        headingDegrees: Float,
        onResult: (List<GpsPoi>) -> Unit,
        onError: (String) -> Unit
    ) {
        val location = GpsLocationHelper.getLastLocation(context)
            ?: run {
                onError("Helymeghatározás nem elérhető. Kapcsold be a G P S-t.")
                return
            }
        runAsync(
            onError = onError,
            block = {
                GpsRadarStore.lastLocation = location
                buildPoiList(location.latitude, location.longitude, headingDegrees)
            },
            onResult = onResult
        )
    }

    fun refreshPoisWithLocation(
        location: Location,
        headingDegrees: Float,
        onUpdated: ((List<GpsPoi>) -> Unit)? = null
    ) {
        runAsync(
            onError = { },
            block = {
                GpsRadarStore.lastLocation = location
                val pois = buildPoiList(location.latitude, location.longitude, headingDegrees)
                val targetId = GpsRadarStore.targetPoi?.id
                if (targetId != null) {
                    GpsRadarStore.targetPoi = pois.firstOrNull { it.id == targetId }
                        ?: GpsRadarStore.targetPoi?.let { old ->
                            GpsRadarMath.enrichPoi(
                                GpsPoiRaw(old.id, old.name, old.category, old.latitude, old.longitude),
                                location.latitude,
                                location.longitude,
                                headingDegrees
                            ).copy(detailText = old.detailText)
                        }
                }
                pois
            },
            onResult = { onUpdated?.invoke(it) }
        )
    }

    fun updatePoiDirections(pois: List<GpsPoi>, location: Location, headingDegrees: Float): List<GpsPoi> =
        pois.map { poi ->
            GpsRadarMath.enrichPoi(
                GpsPoiRaw(poi.id, poi.name, poi.category, poi.latitude, poi.longitude),
                location.latitude,
                location.longitude,
                headingDegrees
            )
        }.sortedBy { it.distanceMeters }

    fun speakAllPois(pois: List<GpsPoi>): String {
        if (pois.isEmpty()) return "Nincs közeli hely a 300 méteres körzetben."
        val streets = pois.filter { it.category == "utca" || it.category == "kereszteződés" }
        val places = pois.filter { it.category != "utca" && it.category != "kereszteződés" }
        val parts = mutableListOf<String>()
        streets.take(3).forEach { parts.add(it.speakRadar()) }
        places.take(9).forEach { parts.add(it.speakRadar()) }
        val suffix = buildString {
            append(" Összesen ${pois.size} elem.")
            if (pois.any { it.category == "kereszteződés" }) {
                append(" A kereszteződéseknél az utcák iránya a te tájolásodhoz képest van megadva.")
            }
        }
        val monitorHint = if (GpsRadarStore.streetMonitoringEnabled) {
            " Utcabemondás aktív: séta közben automatikusan szólok az utcanevekről és kereszteződésekről."
        } else {
            " Utcabemondás ki van kapcsolva. A műveletek menüben bekapcsolható."
        }
        return "G P S kitekintő. ${parts.joinToString(" ")}$suffix$monitorHint Söpörj fel-le választás, jobbra műveletek, le saját hely mentése."
    }

    private fun buildPoiList(latitude: Double, longitude: Double, headingDegrees: Float): List<GpsPoi> {
        val raw = GpsOverpassHelper.fetchNearbyPois(latitude, longitude)
        val placePois = raw.map { GpsRadarMath.enrichPoi(it, latitude, longitude, headingDegrees) }
        val streetContext = try {
            GpsStreetHelper.fetchStreetContext(latitude, longitude, headingDegrees)
        } catch (_: Exception) {
            StreetContext(null, emptyList())
        }
        GpsRadarStore.streetContext = streetContext
        val streetPois = GpsStreetHelper.intersectionsToPois(streetContext, headingDegrees)
        val merged = (streetPois + placePois).sortedBy { it.distanceMeters }
        GpsRadarStore.lastHeading = headingDegrees
        GpsRadarStore.nearbyPois = merged
        return merged
    }

    private fun <T> runAsync(
        onError: (String) -> Unit,
        block: () -> T,
        onResult: (T) -> Unit
    ) {
        Thread {
            try {
                val result = block()
                Handler(Looper.getMainLooper()).post { onResult(result) }
            } catch (e: GpsRadarException) {
                Handler(Looper.getMainLooper()).post { onError(e.message ?: "G P S kitekintő hiba.") }
            } catch (_: Exception) {
                Handler(Looper.getMainLooper()).post {
                    onError("G P S kitekintő lekérdezés sikertelen. Ellenőrizd az internetet és a G P S-t.")
                }
            }
        }.start()
    }
}