package com.superdl.launcher.gps

import android.content.Context
import android.content.Intent
import android.os.Build

object GpsSurroundingsManager {

    fun start(context: Context) {
        if (GpsRadarStore.surroundingsMonitoringActive) return
        val intent = Intent(context, GpsSurroundingsService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        } catch (_: Exception) {
        }
    }

    fun stop(context: Context) {
        context.stopService(Intent(context, GpsSurroundingsService::class.java))
        GpsRadarStore.surroundingsMonitoringActive = false
    }

    fun isRunning(): Boolean = GpsRadarStore.surroundingsMonitoringActive
}