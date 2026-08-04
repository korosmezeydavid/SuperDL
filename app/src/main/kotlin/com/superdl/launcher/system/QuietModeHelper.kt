package com.superdl.launcher.system

import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.provider.Settings
import com.superdl.launcher.feedback.AlertSoundSettingsStore
import com.superdl.launcher.feedback.GestureSoundHelper

object QuietModeHelper {

    private const val PREFS = "superdl"
    private const val KEY_PREV_FILTER = "quiet_mode_prev_interruption_filter"
    private const val KEY_SYSTEM_APPLIED = "quiet_mode_system_applied"

    data class Result(
        val success: Boolean,
        val dndApplied: Boolean = false,
        val needsPolicyAccess: Boolean = false
    )

    /** Super DL néma mód aktív (app-szintű csend). */
    fun isActive(context: Context): Boolean = AlertSoundSettingsStore.isSilentMode(context)

    /** Bejövő hívás csengőhangját a telefon saját csengőállapota kezeli. */
    fun shouldSuppressIncomingCalls(context: Context): Boolean = false

    fun shouldSuppressNotificationAnnouncements(context: Context): Boolean = isActive(context)

    fun reconcileOnStartup(context: Context) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val systemApplied = prefs.getBoolean(KEY_SYSTEM_APPLIED, false)
        if (!AlertSoundSettingsStore.isSilentMode(context) && systemApplied) {
            disable(context)
        }
        GestureSoundHelper.restorePhoneRingerIfNeeded(context)
    }

    fun isSystemDndActive(context: Context): Boolean {
        val manager = context.getSystemService(NotificationManager::class.java) ?: return false
        return manager.currentInterruptionFilter == NotificationManager.INTERRUPTION_FILTER_PRIORITY ||
            manager.currentInterruptionFilter == NotificationManager.INTERRUPTION_FILTER_NONE
    }

    fun hasPolicyAccess(context: Context): Boolean {
        val manager = context.getSystemService(NotificationManager::class.java) ?: return false
        return manager.isNotificationPolicyAccessGranted
    }

    fun openPolicyAccessSettings(context: Context): Boolean {
        val intent = Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        return try {
            context.startActivity(intent)
            true
        } catch (_: Exception) {
            false
        }
    }

    fun apply(context: Context, enabled: Boolean): Result =
        if (enabled) enable(context) else disable(context)

    private fun enable(context: Context): Result {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val notificationManager = context.getSystemService(NotificationManager::class.java)
        val alreadyApplied = prefs.getBoolean(KEY_SYSTEM_APPLIED, false)

        var dndApplied = false
        if (notificationManager != null && notificationManager.isNotificationPolicyAccessGranted) {
            if (!alreadyApplied) {
                prefs.edit()
                    .putInt(KEY_PREV_FILTER, notificationManager.currentInterruptionFilter)
                    .apply()
            }
            try {
                notificationManager.setInterruptionFilter(
                    NotificationManager.INTERRUPTION_FILTER_PRIORITY
                )
                dndApplied = notificationManager.currentInterruptionFilter ==
                    NotificationManager.INTERRUPTION_FILTER_PRIORITY
            } catch (_: Exception) {
            }
        }

        prefs.edit().putBoolean(KEY_SYSTEM_APPLIED, true).apply()

        return Result(
            success = dndApplied,
            dndApplied = dndApplied,
            needsPolicyAccess = !dndApplied && !hasPolicyAccess(context)
        )
    }

    private fun disable(context: Context): Result {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!prefs.getBoolean(KEY_SYSTEM_APPLIED, false)) {
            return Result(success = true)
        }

        val notificationManager = context.getSystemService(NotificationManager::class.java)

        if (notificationManager != null && notificationManager.isNotificationPolicyAccessGranted) {
            try {
                val previousFilter = prefs.getInt(
                    KEY_PREV_FILTER,
                    NotificationManager.INTERRUPTION_FILTER_ALL
                )
                notificationManager.setInterruptionFilter(previousFilter)
            } catch (_: Exception) {
            }
        }

        prefs.edit()
            .putBoolean(KEY_SYSTEM_APPLIED, false)
            .remove(KEY_PREV_FILTER)
            .apply()

        return Result(success = true)
    }
}