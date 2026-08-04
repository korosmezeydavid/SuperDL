package com.superdl.launcher.sms

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony

class SmsDeliverReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_DELIVER_ACTION) return
        SmsDebugLog.append(context, "SmsDeliverReceiver.onReceive")
        SmsInboundService.start(context, intent, "SMS_DELIVER")
    }
}