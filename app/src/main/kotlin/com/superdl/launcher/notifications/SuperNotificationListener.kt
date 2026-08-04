package com.superdl.launcher.notifications

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import com.superdl.launcher.patrol.PatrolAnnouncer
import com.superdl.launcher.patrol.PatrolNotificationClassifier
import com.superdl.launcher.patrol.PatrolStore
import com.superdl.launcher.system.QuietModeHelper

class SuperNotificationListener : NotificationListenerService() {

    override fun onListenerConnected() {
        super.onListenerConnected()
        activeNotifications?.forEach { postNotification(it) }
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        postNotification(sbn)
        maybeAnnounceNotification(sbn)
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        NotificationStore.remove(sbn.key)
    }

    private fun postNotification(sbn: StatusBarNotification) {
        val label = try {
            packageManager.getApplicationLabel(
                packageManager.getApplicationInfo(sbn.packageName, 0)
            ).toString()
        } catch (_: Exception) {
            sbn.packageName
        }
        NotificationStore.add(sbn, label)
    }

    private fun isEmailNotification(sbn: StatusBarNotification): Boolean {
        val pkg = sbn.packageName.lowercase()
        if (pkg.contains("mail") || pkg.contains("gmail") || pkg.contains("outlook") ||
            pkg.contains("yahoo") || pkg.contains("email")
        ) {
            return true
        }
        val category = sbn.notification?.category
        return category == android.app.Notification.CATEGORY_EMAIL
    }

    private fun maybeAnnounceNotification(sbn: StatusBarNotification) {
        if (!PatrolStore.isMasterEnabled(this)) return
        if (QuietModeHelper.shouldSuppressNotificationAnnouncements(this)) return
        if (PatrolStore.isQuietNow(this)) return

        val kind = PatrolNotificationClassifier.classify(sbn)
        val enabled = when (kind) {
            PatrolNotificationClassifier.Kind.CALL -> PatrolStore.isCallAlertEnabled(this)
            PatrolNotificationClassifier.Kind.SMS -> PatrolStore.isSmsAlertEnabled(this)
            PatrolNotificationClassifier.Kind.OTHER -> PatrolStore.isNotificationAlertEnabled(this)
        }
        if (!enabled) return

        val extras = sbn.notification.extras
        val title = extras?.getCharSequence(android.app.Notification.EXTRA_TITLE)?.toString().orEmpty()
        val text = extras?.getCharSequence(android.app.Notification.EXTRA_TEXT)?.toString().orEmpty()
        val label = try {
            packageManager.getApplicationLabel(
                packageManager.getApplicationInfo(sbn.packageName, 0)
            ).toString()
        } catch (_: Exception) {
            sbn.packageName
        }
        val message = PatrolNotificationClassifier.speakMessage(kind, label, title, text)
        val soundCategory = when (kind) {
            PatrolNotificationClassifier.Kind.CALL ->
                com.superdl.launcher.feedback.AlertSoundCategory.ALARM_CLOCK
            PatrolNotificationClassifier.Kind.SMS ->
                com.superdl.launcher.feedback.AlertSoundCategory.SMS
            PatrolNotificationClassifier.Kind.OTHER ->
                if (isEmailNotification(sbn)) {
                    com.superdl.launcher.feedback.AlertSoundCategory.EMAIL
                } else {
                    com.superdl.launcher.feedback.AlertSoundCategory.GENERAL_NOTIFICATION
                }
        }
        PatrolAnnouncer.announce(this, message, soundCategory = soundCategory)
    }
}