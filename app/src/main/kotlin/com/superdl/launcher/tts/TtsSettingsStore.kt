package com.superdl.launcher.tts

import android.content.Context

object TtsSettingsStore {

    private const val PREFS = "superdl"
    private const val KEY_SPEECH_RATE = "tts_speech_rate"

    fun getSpeechRate(context: Context): Float =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getFloat(KEY_SPEECH_RATE, 1.0f)
            .coerceIn(0.5f, 2.5f)

    fun setSpeechRate(context: Context, rate: Float) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putFloat(KEY_SPEECH_RATE, rate.coerceIn(0.5f, 2.5f))
            .apply()
    }
}