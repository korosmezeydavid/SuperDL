package com.superdl.launcher.notifications

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.text.TextUtils
import com.superdl.launcher.settings.PermissionGuideTexts
import com.superdl.launcher.settings.PermissionGuideType

object NotificationHelper {

    fun isListenerEnabled(context: Context): Boolean {
        val flat = Settings.Secure.getString(
            context.contentResolver,
            "enabled_notification_listeners"
        ) ?: return false
        val component = ComponentName(context, SuperNotificationListener::class.java)
        return flat.split(":").any { TextUtils.equals(it, component.flattenToString()) }
    }

    fun setupGuideSpeech(): String =
        PermissionGuideTexts.sections(PermissionGuideType.NOTIFICATION_LISTENER)
            .joinToString(" ") { it.body }

    fun createListenerSettingsIntent(context: Context): Intent? {
        val intent = Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
        return if (intent.resolveActivity(context.packageManager) != null) intent else null
    }
}