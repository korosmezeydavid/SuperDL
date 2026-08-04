package com.superdl.launcher.info

import android.content.Context
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object DayGreetingStore {

    private const val PREFS = "superdl"
    private const val KEY_STARTUP_ENABLED = "day_greeting_startup"
    private const val KEY_LAST_GREETED_DATE = "day_greeting_last_date"

    fun isStartupEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_STARTUP_ENABLED, true)

    fun setStartupEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_STARTUP_ENABLED, enabled)
            .apply()
    }

    fun shouldGreetOnStartup(context: Context): Boolean {
        if (!isStartupEnabled(context)) return false
        val today = todayKey()
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getString(KEY_LAST_GREETED_DATE, null) == today) return false
        prefs.edit().putString(KEY_LAST_GREETED_DATE, today).apply()
        return true
    }

    private fun todayKey(): String =
        SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
}