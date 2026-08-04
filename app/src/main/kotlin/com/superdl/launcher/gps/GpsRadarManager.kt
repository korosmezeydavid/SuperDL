package com.superdl.launcher.gps

import android.content.Context
import android.content.Intent
import android.os.Build

object GpsRadarManager {

    fun startGuidance(context: Context, target: GpsPoi) {
        GpsRadarStore.targetPoi = target
        GpsRadarStore.isGuiding = true
        val intent = Intent(context, GpsRadarService::class.java)
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
        GpsRadarStore.isGuiding = false
        GpsRadarStore.targetPoi = null
        context.stopService(Intent(context, GpsRadarService::class.java))
    }

    fun isGuiding(): Boolean = GpsRadarStore.isGuiding
}