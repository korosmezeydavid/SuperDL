package com.superdl.launcher.feedback

import android.content.Context

object SoundThemeStore {

    private const val PREFS = "superdl"
    private const val KEY_THEME = "gesture_sound_theme"

    fun get(context: Context): SoundTheme {
        val id = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_THEME, SoundTheme.DEFAULT.id)
        return SoundTheme.fromId(id)
    }

    fun set(context: Context, theme: SoundTheme) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_THEME, theme.id)
            .apply()
    }

    fun speakCurrent(context: Context): String {
        val theme = get(context)
        return "Söpörj hangtéma: ${theme.label}. ${theme.description}"
    }
}