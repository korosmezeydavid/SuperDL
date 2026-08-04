package com.superdl.launcher.sms

import android.content.Context
import android.content.Intent
import com.superdl.launcher.feedback.AlertSoundCategory
import com.superdl.launcher.patrol.PatrolAnnouncer
import com.superdl.launcher.patrol.PatrolStore
import com.superdl.launcher.system.QuietModeHelper

object SmsIncomingNotifier {

    const val ACTION_SMS_INCOMING = "com.superdl.launcher.action.SMS_INCOMING"
    const val EXTRA_ADDRESS = "sms_address"
    const val EXTRA_BODY = "sms_body"

    fun notify(context: Context, address: String, body: String) {
        val appContext = context.applicationContext
        appContext.sendBroadcast(
            Intent(ACTION_SMS_INCOMING).apply {
                setPackage(appContext.packageName)
                putExtra(EXTRA_ADDRESS, address)
                putExtra(EXTRA_BODY, body)
            }
        )
        maybeAnnounce(appContext, address, body)
    }

    private fun maybeAnnounce(context: Context, address: String, body: String) {
        if (!PatrolStore.isMasterEnabled(context)) return
        if (QuietModeHelper.shouldSuppressNotificationAnnouncements(context)) return
        if (PatrolStore.isQuietNow(context)) return
        if (!PatrolStore.isSmsAlertEnabled(context)) return

        val label = SmsHelper.resolveSenderLabel(context, address)
        val preview = body.trim().ifBlank { "üres üzenet" }
        val spokenPreview = if (preview.length > 80) preview.take(80) + "…" else preview
        PatrolAnnouncer.announce(
            context = context,
            message = "Új üzenet. Feladó: $label. $spokenPreview",
            soundCategory = AlertSoundCategory.SMS
        )
    }
}