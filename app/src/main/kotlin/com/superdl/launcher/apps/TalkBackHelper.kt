package com.superdl.launcher.apps

import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.view.accessibility.AccessibilityManager

object TalkBackHelper {

    private const val TALKBACK_KEYWORD = "talkback"

    fun isEnabled(context: Context): Boolean {
        val manager = context.getSystemService(Context.ACCESSIBILITY_SERVICE) as AccessibilityManager
        if (!manager.isEnabled) return false
        return manager.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_SPOKEN)
            .any { it.id.contains(TALKBACK_KEYWORD, ignoreCase = true) }
    }

    fun openAccessibilitySettings(context: Context) {
        val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS).apply {
            if (context !is android.app.Activity) {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
        }
        context.startActivity(intent)
    }

    fun warningIfDisabled(): String =
        "A TalkBack képernyőolvasó jelenleg ki van kapcsolva. " +
            "A külső alkalmazások vakos használatához kapcsold be a Kisegítő lehetőségek menüben."
}