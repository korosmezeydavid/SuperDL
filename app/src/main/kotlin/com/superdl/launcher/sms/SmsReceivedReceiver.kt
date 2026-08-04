package com.superdl.launcher.sms

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony

/**
 * Tartalék fogadó – egyes gyártók (pl. Ulefone) csak SMS_RECEIVED-et küldenek megbízhatóan.
 */
class SmsReceivedReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return
        SmsDebugLog.append(context, "SmsReceivedReceiver.onReceive")
        SmsInboundService.start(context, intent, "SMS_RECEIVED")
    }
}