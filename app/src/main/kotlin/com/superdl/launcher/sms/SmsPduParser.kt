package com.superdl.launcher.sms

import android.content.Intent
import android.os.Build
import android.provider.Telephony
import android.telephony.SmsMessage

object SmsPduParser {

    fun parse(intent: Intent): Array<SmsMessage> {
        Telephony.Sms.Intents.getMessagesFromIntent(intent)?.takeIf { it.isNotEmpty() }?.let {
            return it
        }
        return parseFromPdus(intent)
    }

    @Suppress("DEPRECATION")
    private fun parseFromPdus(intent: Intent): Array<SmsMessage> {
        val pdus = when {
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU -> {
                intent.getSerializableExtra("pdus", Array<ByteArray>::class.java)
            }
            else -> {
                (intent.getSerializableExtra("pdus") as? Array<*>)?.mapNotNull { item ->
                    when (item) {
                        is ByteArray -> item
                        else -> null
                    }
                }?.toTypedArray()
            }
        } ?: return emptyArray()

        if (pdus.isEmpty()) return emptyArray()

        val format = intent.getStringExtra("format")
        return pdus.mapNotNull { pdu ->
            try {
                when {
                    !format.isNullOrBlank() && Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ->
                        SmsMessage.createFromPdu(pdu, format)
                    else -> SmsMessage.createFromPdu(pdu)
                }
            } catch (_: Exception) {
                null
            }
        }.toTypedArray()
    }
}