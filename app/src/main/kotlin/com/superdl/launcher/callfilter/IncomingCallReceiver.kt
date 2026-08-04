package com.superdl.launcher.callfilter

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.superdl.launcher.call.IncomingCallNotifier

class IncomingCallReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        IncomingCallNotifier.handlePhoneStateChanged(context, intent)
    }
}