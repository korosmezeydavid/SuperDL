package com.superdl.launcher.feedback

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager

object GestureSoundHelper {

    private const val PREFS = "superdl"
    private const val KEY_LEGACY_PREV_RINGER = "quiet_mode_prev_ringer_mode"
    private const val KEY_RINGER_FIXUP_DONE = "phone_ringer_fixup_v1"

    /** Média csatorna – ezen a készüléken hallható, és nem némítja a rezgés mód. */
    private const val GESTURE_STREAM = AudioManager.STREAM_MUSIC

    fun gestureAudioAttributes(): AudioAttributes =
        AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .setLegacyStreamType(GESTURE_STREAM)
            .build()

    fun ensureGestureStreamAudible(context: Context) {
        ensureStreamAudible(
            context = context,
            stream = GESTURE_STREAM,
            scale = AlertSoundSettingsStore.volumeScale(context)
        )
    }

    fun ensureRingStreamAudible(context: Context) {
        ensureStreamAudible(context, AudioManager.STREAM_RING, 0.75f)
    }

    fun ensureAlarmStreamAudible(context: Context) {
        ensureStreamAudible(
            context = context,
            stream = AudioManager.STREAM_ALARM,
            scale = AlertSoundSettingsStore.volumeScale(context)
        )
    }

    fun restorePhoneRingerIfNeeded(context: Context) {
        if (AlertSoundSettingsStore.isSilentMode(context)) return
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager ?: return

        val previousRinger = prefs.getInt(KEY_LEGACY_PREV_RINGER, -1)
        if (previousRinger >= 0) {
            try {
                audio.ringerMode = previousRinger
            } catch (_: Exception) {
            }
            prefs.edit().remove(KEY_LEGACY_PREV_RINGER).apply()
        }

        if (prefs.getBoolean(KEY_RINGER_FIXUP_DONE, false)) return

        try {
            if (audio.ringerMode != AudioManager.RINGER_MODE_NORMAL) {
                audio.ringerMode = AudioManager.RINGER_MODE_NORMAL
            }
            ensureRingStreamAudible(context)
            ensureStreamAudible(context, AudioManager.STREAM_NOTIFICATION, 0.7f)
            ensureStreamAudible(context, AudioManager.STREAM_SYSTEM, 0.7f)
        } catch (_: Exception) {
        }

        prefs.edit().putBoolean(KEY_RINGER_FIXUP_DONE, true).apply()
    }

    private fun ensureStreamAudible(context: Context, stream: Int, scale: Float) {
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager ?: return
        if (audio.getStreamVolume(stream) > 0) return
        val max = audio.getStreamMaxVolume(stream)
        if (max <= 0) return
        val target = (max * scale).toInt().coerceIn(1, max)
        try {
            audio.setStreamVolume(stream, target, 0)
        } catch (_: Exception) {
        }
    }
}