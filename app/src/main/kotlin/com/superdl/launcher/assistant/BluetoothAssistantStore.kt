package com.superdl.launcher.assistant

import android.content.Context

object BluetoothAssistantStore {

    private const val PREFS = "bluetooth_assistant"
    private const val KEY_ENABLED = "enabled"

    fun isEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_ENABLED, true)

    fun setEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_ENABLED, enabled)
            .apply()
    }

    fun toggle(context: Context): Boolean {
        val next = !isEnabled(context)
        setEnabled(context, next)
        return next
    }
}