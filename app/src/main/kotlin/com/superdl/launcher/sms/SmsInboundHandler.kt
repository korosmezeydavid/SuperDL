package com.superdl.launcher.sms

import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.telephony.SubscriptionManager
import android.util.Log

object SmsInboundHandler {

    private const val TAG = "SmsInboundHandler"

    fun handleIntent(context: Context, intent: Intent, source: String): Boolean {
        val action = intent.action.orEmpty()
        SmsDebugLog.append(
            context,
            "Fogadás indul ($source, action=$action, default=${SmsRoleHelper.isDefaultSmsApp(context)})"
        )

        if (action == Telephony.Sms.Intents.SMS_RECEIVED_ACTION &&
            !SmsRoleHelper.isDefaultSmsApp(context)
        ) {
            SmsDebugLog.append(context, "SMS_RECEIVED – nem vagyunk default app, kihagyva.")
            return false
        }

        val messages = SmsPduParser.parse(intent)
        if (messages.isEmpty()) {
            SmsDebugLog.append(context, "PDU üres ($source, keys=${intent.extras?.keySet()})")
            return false
        }

        val first = messages.first()
        val sender = first.displayOriginatingAddress?.trim()
            ?: first.originatingAddress?.trim().orEmpty()
        val body = messages.joinToString("") { it.displayMessageBody.orEmpty() }
        val timestamp = normalizeTimestamp(first.timestampMillis)
        val serviceCenter = first.serviceCenterAddress?.trim().orEmpty()
        val subscriptionId = resolveSubscriptionId(intent)

        if (sender.isBlank()) {
            SmsDebugLog.append(context, "Hiányzó feladó ($source)")
            return false
        }

        if (SmsHelper.messageExists(context, sender, body, timestamp)) {
            SmsDebugLog.append(context, "Duplikált SMS – $sender ($source)")
            return true
        }

        val stored = SmsHelper.storeIncomingMessage(
            context = context.applicationContext,
            address = sender,
            body = body,
            timestamp = timestamp,
            subscriptionId = subscriptionId,
            serviceCenter = serviceCenter
        )
        if (stored) {
            Log.i(TAG, "SMS mentve – $sender ($source)")
            SmsDebugLog.append(context, "SMS mentve – $sender, hossz=${body.length} ($source)")
            SmsIncomingNotifier.notify(context.applicationContext, sender, body)
        } else {
            Log.w(TAG, "SMS mentés sikertelen – $sender ($source)")
            SmsDebugLog.append(context, "SMS mentés SIKERTELEN – $sender ($source)")
        }
        return stored
    }

    private fun resolveSubscriptionId(intent: Intent): Int {
        val candidates = listOf(
            SubscriptionManager.EXTRA_SUBSCRIPTION_INDEX,
            SubscriptionManager.EXTRA_SLOT_INDEX,
            "subscription",
            "sub_id",
            "subscription_id"
        )
        for (key in candidates) {
            val value = intent.getIntExtra(key, SubscriptionManager.INVALID_SUBSCRIPTION_ID)
            if (value != SubscriptionManager.INVALID_SUBSCRIPTION_ID) return value
        }
        return SubscriptionManager.INVALID_SUBSCRIPTION_ID
    }

    private fun normalizeTimestamp(timestamp: Long): Long =
        if (timestamp > 0L) timestamp else System.currentTimeMillis()
}