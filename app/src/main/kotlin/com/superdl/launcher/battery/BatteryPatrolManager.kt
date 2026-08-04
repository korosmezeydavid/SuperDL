package com.superdl.launcher.battery

import android.content.Context
import android.content.Intent
import android.os.Build

object BatteryPatrolManager {

    fun start(context: Context) {
        if (!BatteryPatrolStore.isEnabled(context)) return
        val intent = Intent(context, BatteryPatrolService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        } catch (_: Exception) {}
    }

    fun stop(context: Context) {
        context.stopService(Intent(context, BatteryPatrolService::class.java))
    }

    fun setEnabled(context: Context, enabled: Boolean) {
        BatteryPatrolStore.setEnabled(context, enabled)
        if (enabled) {
            start(context)
        } else {
            stop(context)
        }
    }

    fun isEnabled(context: Context): Boolean = BatteryPatrolStore.isEnabled(context)
}