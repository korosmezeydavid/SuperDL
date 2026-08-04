package com.superdl.launcher.dictaphone

import android.content.Context

object DictaphoneSettingsStore {

    private const val PREFS = "dictaphone_settings"
    private const val KEY_FORMAT = "format"
    private const val KEY_SAMPLE_RATE = "sample_rate"
    private const val KEY_BITRATE = "bitrate"
    private const val KEY_CHANNELS = "channels"
    private const val KEY_NOISE = "noise_suppression"
    private const val KEY_RAW = "raw_capture"

    fun load(context: Context): DictaphoneConfig =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).let { prefs ->
            DictaphoneConfig(
                format = DictaphoneFormat.entries.getOrElse(prefs.getInt(KEY_FORMAT, 0)) { DictaphoneFormat.WAV },
                sampleRate = DictaphoneSampleRate.entries.getOrElse(prefs.getInt(KEY_SAMPLE_RATE, 4)) {
                    DictaphoneSampleRate.RATE_44K
                },
                bitrate = DictaphoneBitrate.entries.getOrElse(prefs.getInt(KEY_BITRATE, 4)) {
                    DictaphoneBitrate.B192
                },
                channels = DictaphoneChannels.entries.getOrElse(prefs.getInt(KEY_CHANNELS, 0)) {
                    DictaphoneChannels.MONO
                },
                noiseSuppressionEnabled = prefs.getBoolean(KEY_NOISE, false),
                rawCapture = prefs.getBoolean(KEY_RAW, false)
            )
        }

    fun save(context: Context, config: DictaphoneConfig) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putInt(KEY_FORMAT, config.format.ordinal)
            .putInt(KEY_SAMPLE_RATE, config.sampleRate.ordinal)
            .putInt(KEY_BITRATE, config.bitrate.ordinal)
            .putInt(KEY_CHANNELS, config.channels.ordinal)
            .putBoolean(KEY_NOISE, config.noiseSuppressionEnabled)
            .putBoolean(KEY_RAW, config.rawCapture)
            .apply()
    }

    fun updateFormat(context: Context, format: DictaphoneFormat) =
        save(context, load(context).copy(format = format))

    fun updateSampleRate(context: Context, sampleRate: DictaphoneSampleRate) =
        save(context, load(context).copy(sampleRate = sampleRate))

    fun updateBitrate(context: Context, bitrate: DictaphoneBitrate) =
        save(context, load(context).copy(bitrate = bitrate))

    fun updateChannels(context: Context, channels: DictaphoneChannels) =
        save(context, load(context).copy(channels = channels))

    fun toggleNoiseSuppression(context: Context): Boolean {
        val config = load(context)
        val next = !config.noiseSuppressionEnabled
        save(context, config.copy(noiseSuppressionEnabled = next))
        return next
    }

    /**
     * Teljesen nyers felvétel ki/be. Bekapcsoláskor a zajszűrést is kikapcsoljuk,
     * mert a kettő együtt értelmetlen lenne.
     */
    fun toggleRawCapture(context: Context): Boolean {
        val config = load(context)
        val next = !config.rawCapture
        save(
            context,
            config.copy(
                rawCapture = next,
                noiseSuppressionEnabled = if (next) false else config.noiseSuppressionEnabled
            )
        )
        return next
    }
}