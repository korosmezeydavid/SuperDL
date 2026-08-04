package com.superdl.launcher.sound

import android.content.Context
import android.media.RingtoneManager
import android.net.Uri

/**
 * A felhasználó által választott csengő- és értesítési hang tárolása.
 * Ha nincs választás, a rendszer alapértelmezettje érvényes.
 */
object RingtonePreferenceStore {

    private const val PREFS = "superdl"
    private const val KEY_RINGTONE_URI = "user_ringtone_uri"
    private const val KEY_RINGTONE_TITLE = "user_ringtone_title"
    private const val KEY_NOTIFICATION_URI = "user_notification_uri"
    private const val KEY_NOTIFICATION_TITLE = "user_notification_title"

    fun setRingtone(context: Context, uri: String?, title: String?) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().apply {
            if (uri.isNullOrBlank()) {
                remove(KEY_RINGTONE_URI)
                remove(KEY_RINGTONE_TITLE)
            } else {
                putString(KEY_RINGTONE_URI, uri)
                putString(KEY_RINGTONE_TITLE, title ?: "")
            }
            apply()
        }
    }

    /** A híváshoz használandó csengőhang: a felhasználó választása, vagy a rendszer alapértelmezettje. */
    fun getRingtoneUri(context: Context): Uri? {
        val saved = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_RINGTONE_URI, null)
        if (!saved.isNullOrBlank()) {
            return try {
                Uri.parse(saved)
            } catch (_: Exception) {
                null
            }
        }
        return RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE)
    }

    fun getRingtoneTitle(context: Context): String? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_RINGTONE_TITLE, null)?.ifBlank { null }

    fun setNotificationTone(context: Context, uri: String?, title: String?) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().apply {
            if (uri.isNullOrBlank()) {
                remove(KEY_NOTIFICATION_URI)
                remove(KEY_NOTIFICATION_TITLE)
            } else {
                putString(KEY_NOTIFICATION_URI, uri)
                putString(KEY_NOTIFICATION_TITLE, title ?: "")
            }
            apply()
        }
    }

    fun getNotificationUri(context: Context): Uri? {
        val saved = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_NOTIFICATION_URI, null)
        if (!saved.isNullOrBlank()) {
            return try {
                Uri.parse(saved)
            } catch (_: Exception) {
                null
            }
        }
        return RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
    }
}
