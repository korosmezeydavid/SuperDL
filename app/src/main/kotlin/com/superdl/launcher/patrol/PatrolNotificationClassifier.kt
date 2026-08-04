package com.superdl.launcher.patrol

import android.app.Notification
import android.service.notification.StatusBarNotification

object PatrolNotificationClassifier {

    enum class Kind { CALL, SMS, OTHER }

    fun classify(sbn: StatusBarNotification): Kind {
        val notification = sbn.notification ?: return Kind.OTHER
        val category = notification.category
        when (category) {
            Notification.CATEGORY_CALL -> return Kind.CALL
            Notification.CATEGORY_MESSAGE -> return Kind.SMS
        }
        val pkg = sbn.packageName.lowercase()
        if (pkg.contains("dialer") || pkg.contains("phone") || pkg.contains("incallui")) {
            return Kind.CALL
        }
        if (pkg.contains("messaging") || pkg.contains("sms") || pkg.contains("mms")) {
            return Kind.SMS
        }
        return Kind.OTHER
    }

    fun speakMessage(kind: Kind, appLabel: String, title: String, text: String): String {
        val content = listOf(title, text).filter { it.isNotBlank() }.joinToString(". ")
        return when (kind) {
            Kind.CALL -> "Bejövő hívás. $appLabel. $content"
            Kind.SMS -> "Új üzenet. $appLabel. $content"
            Kind.OTHER -> "Új értesítés. $appLabel. $content"
        }.trim()
    }
}