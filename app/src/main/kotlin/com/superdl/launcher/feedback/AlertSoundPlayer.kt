package com.superdl.launcher.feedback

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.RingtoneManager
import android.media.ToneGenerator
import android.net.Uri
import android.util.Log
import java.util.concurrent.atomic.AtomicBoolean

object AlertSoundPlayer {

    private const val TAG = "AlertSoundPlayer"

    const val DELAY_AFTER_WAKE_BEEP_MS = 700L
    const val DELAY_BEFORE_ALERT_UI_MS = 450L

    private val WAKE_DOUBLE_BEEP = listOf(
        1046 to 160,
        0 to 240,
        1046 to 160
    )

    private val DEFAULT_ALARM_SEQUENCE = listOf(
        880 to 220,
        0 to 200,
        1100 to 280,
        0 to 350,
        880 to 220
    )

    fun playAlertWakeBeep(context: Context? = null, force: Boolean = true) {
        if (context != null && !AlertSoundSettingsStore.shouldPlay(context, force)) return
        context?.let { ensureAlarmAudible(it) }
        playToneSequenceSync(context, WAKE_DOUBLE_BEEP, force = true)
    }

    fun resolveUri(context: Context, preset: AlertSoundPreset): Uri? {
        val type = preset.ringtoneType ?: return null
        return RingtoneManager.getDefaultUri(type)
            ?: RingtoneManager.getActualDefaultRingtoneUri(context, type)
    }

    fun startLooping(context: Context, category: AlertSoundCategory): () -> Unit {
        if (!AlertSoundSettingsStore.shouldPlay(context)) return {}
        val preset = AlertSoundStore.getPreset(context, category)
        return startLoopingPreset(context, preset)
    }

    fun startLoopingPreset(
        context: Context,
        preset: AlertSoundPreset
    ): () -> Unit {
        if (!AlertSoundSettingsStore.shouldPlay(context)) return {}
        ensureAlarmAudible(context)
        val sequence = effectiveSequence(preset)
        val running = AtomicBoolean(true)
        val thread = Thread(
            {
                while (running.get() && !Thread.currentThread().isInterrupted) {
                    playToneSequenceSync(context, sequence, force = false)
                    if (running.get() && !Thread.currentThread().isInterrupted) {
                        sleepInterruptibly(700L)
                    }
                }
            },
            "SuperDL-AlertToneLoop"
        )
        thread.start()
        return {
            running.set(false)
            thread.interrupt()
        }
    }

    fun playOnce(context: Context, category: AlertSoundCategory) {
        preview(context, AlertSoundStore.getPreset(context, category))
    }

    fun preview(context: Context, preset: AlertSoundPreset) {
        if (!AlertSoundSettingsStore.shouldPlay(context, force = true)) return
        ensureAlarmAudible(context)
        Thread({
            playToneSequenceSync(context, effectiveSequence(preset), force = true)
            tryPlaySystemRingtone(context, preset)
        }, "SuperDL-AlertPreview").start()
    }

    private fun effectiveSequence(preset: AlertSoundPreset): List<Pair<Int, Int>> =
        preset.toneSequence ?: DEFAULT_ALARM_SEQUENCE

    private fun tryPlaySystemRingtone(context: Context, preset: AlertSoundPreset) {
        if (preset.ringtoneType == null) return
        val uri = resolveUri(context, preset) ?: return
        try {
            val ringtone = RingtoneManager.getRingtone(context, uri) ?: return
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.LOLLIPOP) {
                ringtone.audioAttributes = AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build()
            } else {
                @Suppress("DEPRECATION")
                ringtone.streamType = AudioManager.STREAM_ALARM
            }
            ringtone.play()
        } catch (e: Exception) {
            Log.w(TAG, "Rendszer csengő nem játszható le", e)
        }
    }

    private fun ensureAlarmAudible(context: Context) {
        try {
            val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            if (audioManager.getStreamVolume(AudioManager.STREAM_ALARM) == 0) {
                val max = audioManager.getStreamMaxVolume(AudioManager.STREAM_ALARM)
                val target = (max * AlertSoundSettingsStore.volumeScale(context))
                    .toInt()
                    .coerceIn(1, max)
                audioManager.setStreamVolume(AudioManager.STREAM_ALARM, target, 0)
            }
        } catch (e: Exception) {
            Log.w(TAG, "Ébresztő hangerő beállítás sikertelen", e)
        }
    }

    private fun toneVolume(context: Context?): Int {
        val percent = context?.let { AlertSoundSettingsStore.getVolumePercent(it) } ?: 100
        return (percent * ToneGenerator.MAX_VOLUME / 100).coerceIn(40, ToneGenerator.MAX_VOLUME)
    }

    private fun playToneSequenceSync(
        context: Context?,
        notes: List<Pair<Int, Int>>,
        force: Boolean
    ) {
        if (context != null && !AlertSoundSettingsStore.shouldPlay(context, force)) return
        if (Thread.currentThread().isInterrupted) return
        val volume = toneVolume(context)
        for ((index, note) in notes.withIndex()) {
            if (Thread.currentThread().isInterrupted) return
            if (note.first > 0 && note.second > 0) {
                playAlarmBurst(note.first, note.second, volume)
            } else if (note.second > 0) {
                sleepInterruptibly(note.second.toLong())
            }
            if (index < notes.lastIndex) sleepInterruptibly(60L)
        }
    }

    private fun playAlarmBurst(freq: Int, durationMs: Int, volume: Int) {
        try {
            val tone = ToneGenerator(AudioManager.STREAM_ALARM, volume)
            val toneType = when {
                freq >= 1200 -> ToneGenerator.TONE_CDMA_ALERT_CALL_GUARD
                freq >= 900 -> ToneGenerator.TONE_PROP_BEEP2
                freq >= 600 -> ToneGenerator.TONE_PROP_BEEP
                else -> ToneGenerator.TONE_PROP_ACK
            }
            tone.startTone(toneType, durationMs.coerceIn(80, 2000))
            sleepInterruptibly((durationMs + 60).toLong())
            tone.release()
        } catch (e: Exception) {
            Log.w(TAG, "Beépített síp lejátszás sikertelen", e)
        }
    }

    private fun sleepInterruptibly(delayMs: Long) {
        if (delayMs <= 0L || Thread.currentThread().isInterrupted) return
        try {
            Thread.sleep(delayMs)
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        }
    }
}