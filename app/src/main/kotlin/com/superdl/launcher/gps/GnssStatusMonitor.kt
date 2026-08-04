package com.superdl.launcher.gps

import android.annotation.SuppressLint
import android.content.Context
import android.location.GnssStatus
import android.location.LocationManager
import android.os.Build
import android.os.Handler
import android.os.Looper

object GnssStatusMonitor {

    private val NOOP_CANCEL: () -> Unit = { }

    @SuppressLint("MissingPermission")
    fun start(context: Context, onSatellites: (Int) -> Unit): () -> Unit {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.N) return NOOP_CANCEL
        if (!GpsLocationHelper.hasPermission(context)) return NOOP_CANCEL

        val manager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        val handler = Handler(Looper.getMainLooper())
        val callback = object : GnssStatus.Callback() {
            override fun onSatelliteStatusChanged(status: GnssStatus) {
                var usedInFix = 0
                for (i in 0 until status.satelliteCount) {
                    if (status.usedInFix(i)) usedInFix++
                }
                handler.post { onSatellites(usedInFix) }
            }
        }
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                manager.registerGnssStatusCallback(callback, handler)
            } else {
                @Suppress("DEPRECATION")
                manager.registerGnssStatusCallback(callback)
            }
            {
                try {
                    manager.unregisterGnssStatusCallback(callback)
                } catch (_: Exception) {
                }
            }
        } catch (_: Exception) {
            NOOP_CANCEL
        }
    }
}