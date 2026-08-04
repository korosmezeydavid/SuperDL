package com.superdl.launcher.gps

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.core.content.ContextCompat

object GpsLocationHelper {

    fun getLastLocation(context: Context): Location? {
        if (!hasPermission(context)) return null
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

    fun hasPermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

    @SuppressLint("MissingPermission")
    fun requestUpdates(
        context: Context,
        minIntervalMs: Long = 3_000L,
        onLocation: (Location) -> Unit
    ): LocationListener? {
        if (!hasPermission(context)) return null
        val manager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        val listener = object : LocationListener {
            override fun onLocationChanged(location: Location) = onLocation(location)
            @Deprecated("Deprecated in Java")
            override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) = Unit
            override fun onProviderEnabled(provider: String) = Unit
            override fun onProviderDisabled(provider: String) = Unit
        }
        val handler = Handler(Looper.getMainLooper())
        try {
            manager.requestLocationUpdates(
                LocationManager.GPS_PROVIDER,
                minIntervalMs,
                2f,
                listener,
                handler.looper
            )
        } catch (_: Exception) {
            try {
                manager.requestLocationUpdates(
                    LocationManager.NETWORK_PROVIDER,
                    minIntervalMs,
                    5f,
                    listener,
                    handler.looper
                )
            } catch (_: Exception) {
                return null
            }
        }
        return listener
    }

    fun removeUpdates(context: Context, listener: LocationListener?) {
        if (listener == null) return
        if (!hasPermission(context)) return
        val manager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        try {
            manager.removeUpdates(listener)
        } catch (_: Exception) {
        }
    }
}