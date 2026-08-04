package com.superdl.launcher.sos

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class SosConfigReceiver : BroadcastReceiver() {

    companion object {
        const val ACTION_SET_SOS = "com.superdl.launcher.SET_SOS"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION_SET_SOS) return

        for (slot in 1..4) {
            val key = "sos_$slot"
            if (intent.hasExtra(key)) {
                val value = intent.getStringExtra(key) ?: ""
                SosPreferences.setNumber(context, slot, value)
            }
        }
    }
}