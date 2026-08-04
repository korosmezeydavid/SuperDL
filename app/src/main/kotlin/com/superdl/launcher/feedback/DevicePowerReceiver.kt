package com.superdl.launcher.feedback

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class DevicePowerReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (!DeviceStateStore.isEnabled(context)) return
        when (intent.action) {
            Intent.ACTION_POWER_CONNECTED -> {
                DeviceStateStore.setFullAnnounced(context, false)
                DeviceStateTonePlayer.play(DeviceStateEvent.CHARGER_CONNECTED)
            }
            Intent.ACTION_POWER_DISCONNECTED -> {
                DeviceStateStore.setFullAnnounced(context, false)
                DeviceStateTonePlayer.play(DeviceStateEvent.CHARGER_DISCONNECTED)
            }
        }
    }
}