package com.superdl.launcher.navigation

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.location.Location
import android.location.LocationManager
import android.os.Handler
import android.os.Looper
import androidx.core.content.ContextCompat
import com.superdl.launcher.transit.OsmHelper
import com.superdl.launcher.transit.TransitApiException
import com.superdl.launcher.transit.TransitRoute
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

object NavigationHelper {

    private val ioExecutor: ExecutorService = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "SuperDL-NavigationIO")
    }

    fun speakCurrentLocation(
        context: Context,
        onResult: (String) -> Unit,
        onError: (String) -> Unit
    ) {
        val location = getLastLocation(context)
            ?: run {
                onError("Helymeghatározás nem elérhető. Kapcsold be a G P S-t.")
                return
            }
        runAsync(onError, {
            val address = OsmHelper.reverseGeocode(location.latitude, location.longitude)
                ?: "ismeretlen cím"
            val accuracy = location.accuracy.toInt().coerceAtLeast(0)
            val accuracyText = when {
                accuracy <= 0 -> ""
                accuracy < 30 -> " Pontosság kb. $accuracy méter."
                else -> " Pontosság kb. $accuracy méter, lehet eltérés."
            }
            "Jelenlegi helyed: $address.$accuracyText"
        }) { message ->
            onResult(message)
        }
    }

    fun searchPlaces(
        context: Context,
        query: String,
        onResult: (List<NavPlace>) -> Unit,
        onError: (String) -> Unit
    ) {
        val trimmed = query.trim()
        if (trimmed.isBlank()) {
            onError("Üres keresés.")
            return
        }
        val location = getLastLocation(context)
        runAsync(onError, {
            OsmHelper.geocode(trimmed).map { geo ->
                val distance = location?.let { dist(it, geo.lat, geo.lon) }
                NavPlace(geo.shortName, geo.fullName, distance, geo.lat, geo.lon)
            }.distinctBy { it.fullName }
        }) { places ->
            if (places.isEmpty()) onError("Nem találtam helyet: $trimmed.")
            else onResult(places)
        }
    }

    fun fetchWalkingRoute(
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
            buildWalkingRoute(location, target.lat, target.lon, target.shortName)
        }) { route ->
            onResult(route)
        }
    }

    fun fetchWalkingRouteToCoords(
        context: Context,
        lat: Double,
        lon: Double,
        label: String = "cél",
        onResult: (TransitRoute) -> Unit,
        onError: (String) -> Unit
    ) {
        val location = getLastLocation(context)
            ?: run {
                onError("Helymeghatározás nem elérhető. Kapcsold be a G P S-t.")
                return
            }
        runAsync(onError, {
            buildWalkingRoute(location, lat, lon, label)
        }) { route ->
            onResult(route)
        }
    }

    private fun buildWalkingRoute(origin: Location, lat: Double, lon: Double, label: String): TransitRoute {
        return OsmHelper.walkingRoute(origin.latitude, origin.longitude, lat, lon)
            ?: throw TransitApiException("Nem sikerült gyalogos útvonalat tervezni ide: $label.")
    }

    fun openInMaps(context: Context, place: NavPlace): Boolean {
        val query = Uri.encode(place.fullName.ifBlank { place.shortName })
        val uri = if (place.hasCoordinates()) {
            Uri.parse("geo:${place.latitude},${place.longitude}?q=$query")
        } else {
            Uri.parse("geo:0,0?q=$query")
        }
        val intent = Intent(Intent.ACTION_VIEW, uri)
        return if (intent.resolveActivity(context.packageManager) != null) {
            context.startActivity(intent)
            true
        } else {
            false
        }
    }

    private fun dist(origin: Location, lat: Double, lon: Double): Int {
        val result = FloatArray(1)
        Location.distanceBetween(origin.latitude, origin.longitude, lat, lon, result)
        return result[0].toInt()
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
                mainHandler.post { onError(e.message ?: "Navigáció hiba.") }
            } catch (_: Exception) {
                mainHandler.post {
                    onError("Navigáció lekérdezés sikertelen. Ellenőrizd az internetkapcsolatot.")
                }
            }
        }
    }
}