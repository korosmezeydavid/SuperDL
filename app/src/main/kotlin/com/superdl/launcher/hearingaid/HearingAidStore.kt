package com.superdl.launcher.hearingaid

import android.content.Context

object HearingAidStore {

    private const val PREFS = "superdl_hearing_aid"
    private const val KEY_MASTER = "master_gain"
    private const val KEY_MIC = "mic_gain"
    private const val KEY_BASS = "bass_gain"
    private const val KEY_MID = "mid_gain"
    private const val KEY_TREBLE = "treble_gain"
    private const val KEY_BALANCE = "balance"
    private const val KEY_MIC_SOURCE = "mic_source"

    @Volatile
    var isRunning: Boolean = false

    fun load(context: Context): HearingAidSettings {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return HearingAidSettings(
            masterGain = prefs.getFloat(KEY_MASTER, 1.5f),
            micGain = prefs.getFloat(KEY_MIC, 1.2f),
            bassGain = prefs.getFloat(KEY_BASS, 1.0f),
            midGain = prefs.getFloat(KEY_MID, 1.0f),
            trebleGain = prefs.getFloat(KEY_TREBLE, 1.0f),
            balance = HearingAidSettings.BalanceMode.entries.getOrElse(
                prefs.getInt(KEY_BALANCE, 1).coerceIn(0, 2)
            ) { HearingAidSettings.BalanceMode.BOTH },
            micSource = HearingAidSettings.MicSource.entries.getOrElse(
                prefs.getInt(KEY_MIC_SOURCE, 0).coerceIn(0, 2)
            ) { HearingAidSettings.MicSource.AUTO }
        )
    }

    fun save(context: Context, settings: HearingAidSettings) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putFloat(KEY_MASTER, settings.masterGain)
            .putFloat(KEY_MIC, settings.micGain)
            .putFloat(KEY_BASS, settings.bassGain)
            .putFloat(KEY_MID, settings.midGain)
            .putFloat(KEY_TREBLE, settings.trebleGain)
            .putInt(KEY_BALANCE, settings.balance.ordinal)
            .putInt(KEY_MIC_SOURCE, settings.micSource.ordinal)
            .apply()
    }

    fun adjustGain(current: Float, delta: Int): Float {
        val next = current + delta * HearingAidSettings.GAIN_STEP
        return next.coerceIn(HearingAidSettings.GAIN_MIN, HearingAidSettings.GAIN_MAX)
    }

    fun cycleBalance(current: HearingAidSettings.BalanceMode): HearingAidSettings.BalanceMode {
        val values = HearingAidSettings.BalanceMode.entries
        val next = (current.ordinal + 1) % values.size
        return values[next]
    }

    fun cycleMicSource(current: HearingAidSettings.MicSource): HearingAidSettings.MicSource {
        val values = HearingAidSettings.MicSource.entries
        val next = (current.ordinal + 1) % values.size
        return values[next]
    }
}