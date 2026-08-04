package com.superdl.launcher.patrol

import android.content.Context
import java.util.Calendar

object PatrolStore {

    private const val PREFS = "superdl"
    private const val KEY_MASTER = "patrol_master_enabled"
    private const val KEY_BATTERY = "patrol_battery_enabled"
    private const val KEY_CALL_ALERT = "patrol_call_alert_enabled"
    private const val KEY_SMS_ALERT = "patrol_sms_alert_enabled"
    private const val KEY_NOTIFICATION_ALERT = "patrol_notification_alert_enabled"
    private const val KEY_TIME_ANNOUNCE = "patrol_time_announce_enabled"
    private const val KEY_TIME_INTERVAL = "patrol_time_interval_minutes"
    private const val KEY_NIGHT_MODE = "patrol_night_mode_enabled"
    private const val KEY_NIGHT_START = "patrol_night_start_minutes"
    private const val KEY_NIGHT_END = "patrol_night_end_minutes"
    private const val KEY_POWER_BUTTON_TIME = "patrol_power_button_time_enabled"
    private const val KEY_LAST_ALERTED = "battery_last_alerted_threshold"

    val TIME_INTERVALS = listOf(5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60)

    fun isMasterEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_MASTER, true)

    fun setMasterEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putBoolean(KEY_MASTER, enabled).apply()
    }

    fun isBatteryEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_BATTERY, true)

    fun setBatteryEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putBoolean(KEY_BATTERY, enabled).apply()
    }

    fun isCallAlertEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_CALL_ALERT, false)

    fun setCallAlertEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putBoolean(KEY_CALL_ALERT, enabled).apply()
    }

    fun isSmsAlertEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_SMS_ALERT, false)

    fun setSmsAlertEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putBoolean(KEY_SMS_ALERT, enabled).apply()
    }

    fun isNotificationAlertEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_NOTIFICATION_ALERT, false)

    fun setNotificationAlertEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putBoolean(KEY_NOTIFICATION_ALERT, enabled).apply()
    }

    fun isTimeAnnounceEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_TIME_ANNOUNCE, false)

    fun setTimeAnnounceEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putBoolean(KEY_TIME_ANNOUNCE, enabled).apply()
    }

    fun getTimeIntervalMinutes(context: Context): Int {
        val stored = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getInt(KEY_TIME_INTERVAL, 60)
        return TIME_INTERVALS.firstOrNull { it == stored } ?: 60
    }

    fun setTimeIntervalMinutes(context: Context, minutes: Int) {
        val value = TIME_INTERVALS.firstOrNull { it == minutes } ?: 60
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putInt(KEY_TIME_INTERVAL, value).apply()
    }

    fun cycleTimeInterval(context: Context): Int {
        val current = getTimeIntervalMinutes(context)
        val index = TIME_INTERVALS.indexOf(current).let { if (it < 0) TIME_INTERVALS.lastIndex else it }
        val next = TIME_INTERVALS[(index + 1) % TIME_INTERVALS.size]
        setTimeIntervalMinutes(context, next)
        return next
    }

    fun isNightModeEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_NIGHT_MODE, false)

    fun setNightModeEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putBoolean(KEY_NIGHT_MODE, enabled).apply()
    }

    fun getNightStartMinutes(context: Context): Int =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getInt(KEY_NIGHT_START, 22 * 60)

    fun getNightEndMinutes(context: Context): Int =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getInt(KEY_NIGHT_END, 7 * 60)

    fun setNightStartMinutes(context: Context, minutes: Int) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putInt(KEY_NIGHT_START, minutes.coerceIn(0, 23 * 60 + 59)).apply()
    }

    fun setNightEndMinutes(context: Context, minutes: Int) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putInt(KEY_NIGHT_END, minutes.coerceIn(0, 23 * 60 + 59)).apply()
    }

    fun isPowerButtonTimeEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_POWER_BUTTON_TIME, false)

    fun setPowerButtonTimeEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putBoolean(KEY_POWER_BUTTON_TIME, enabled).apply()
    }

    fun getLastAlertedThreshold(context: Context): Int =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getInt(KEY_LAST_ALERTED, 100)

    fun setLastAlertedThreshold(context: Context, threshold: Int) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putInt(KEY_LAST_ALERTED, threshold).apply()
    }

    fun resetAlertState(context: Context) {
        setLastAlertedThreshold(context, 100)
    }

    fun speakNightStart(context: Context): String = speakClock(getNightStartMinutes(context))

    fun speakNightEnd(context: Context): String = speakClock(getNightEndMinutes(context))

    fun speakClock(totalMinutes: Int): String {
        val hour = totalMinutes / 60
        val minute = totalMinutes % 60
        return when {
            minute == 0 -> "$hour óra"
            else -> "$hour óra $minute perc"
        }
    }

    fun isQuietNow(context: Context, now: Calendar = Calendar.getInstance()): Boolean {
        if (!isNightModeEnabled(context)) return false
        val current = now.get(Calendar.HOUR_OF_DAY) * 60 + now.get(Calendar.MINUTE)
        val start = getNightStartMinutes(context)
        val end = getNightEndMinutes(context)
        return if (start == end) {
            false
        } else if (start < end) {
            current in start until end
        } else {
            current >= start || current < end
        }
    }
}