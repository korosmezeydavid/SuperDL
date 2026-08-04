package com.superdl.launcher.gps

import android.content.Context
import android.content.Intent
import android.os.Build

object CompassScanStore {
    @Volatile
    var isActive: Boolean = false
}

object CompassScanManager {

    fun start(context: Context) {
        CompassScanStore.isActive = true
        val intent = Intent(context, CompassScanService::class.java)
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
        CompassScanStore.isActive = false
        context.stopService(Intent(context, CompassScanService::class.java))
    }

    fun isActive(): Boolean = CompassScanStore.isActive
}
