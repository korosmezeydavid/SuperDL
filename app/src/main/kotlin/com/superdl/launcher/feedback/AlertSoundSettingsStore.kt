package com.superdl.launcher.feedback

import android.content.Context

object AlertSoundSettingsStore {

    private const val PREFS = "superdl"
    private const val KEY_VOLUME_PERCENT = "alert_sound_volume_percent"
    private const val KEY_SILENT_MODE = "alert_silent_mode"

    val VOLUME_STEPS = listOf(25, 50, 75, 100)

    fun getVolumePercent(context: Context): Int {
        val stored = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getInt(KEY_VOLUME_PERCENT, 100)
        return VOLUME_STEPS.firstOrNull { it == stored } ?: 100
    }

    fun setVolumePercent(context: Context, percent: Int) {
        val value = VOLUME_STEPS.firstOrNull { it == percent } ?: 100
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putInt(KEY_VOLUME_PERCENT, value)
            .apply()
    }

    fun cycleVolumePercent(context: Context): Int {
        val current = getVolumePercent(context)
        val index = VOLUME_STEPS.indexOf(current).let { if (it < 0) VOLUME_STEPS.lastIndex else it }
        val next = VOLUME_STEPS[(index + 1) % VOLUME_STEPS.size]
        setVolumePercent(context, next)
        return next
    }

    fun isSilentMode(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_SILENT_MODE, false)

    fun setSilentMode(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_SILENT_MODE, enabled)
            .apply()
    }

    fun toggleSilentMode(context: Context): Boolean {
        val next = !isSilentMode(context)
        setSilentMode(context, next)
        return next
    }

    fun volumeScale(context: Context): Float =
        getVolumePercent(context) / 100f

    fun shouldPlay(context: Context, force: Boolean = false): Boolean =
        force || !isSilentMode(context)

    fun speakVolume(context: Context): String =
        "Csengőhang hangerő: ${getVolumePercent(context)} százalék."

    fun speakSilentMode(context: Context): String =
        if (isSilentMode(context)) "Néma mód: bekapcsolva." else "Néma mód: kikapcsolva."
}