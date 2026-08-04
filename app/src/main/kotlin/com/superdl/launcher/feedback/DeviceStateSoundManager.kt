package com.superdl.launcher.feedback

import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat

object DeviceStateSoundManager {

    fun start(context: Context) {
        if (!DeviceStateStore.isEnabled(context)) return
        val appContext = context.applicationContext
        val intent = Intent(appContext, DeviceStateSoundService::class.java)
        ContextCompat.startForegroundService(appContext, intent)
    }

    fun stop(context: Context) {
        context.applicationContext.stopService(
            Intent(context.applicationContext, DeviceStateSoundService::class.java)
        )
    }

    fun setEnabled(context: Context, enabled: Boolean) {
        DeviceStateStore.setEnabled(context, enabled)
        if (enabled) start(context) else stop(context)
    }

    fun isEnabled(context: Context): Boolean = DeviceStateStore.isEnabled(context)
}