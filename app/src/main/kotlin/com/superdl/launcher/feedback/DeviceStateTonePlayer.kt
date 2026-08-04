package com.superdl.launcher.feedback

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.media.ToneGenerator
import android.os.Handler
import android.os.Looper
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import kotlin.math.PI
import kotlin.math.sin

object DeviceStateTonePlayer {

    private val handler = Handler(Looper.getMainLooper())
    private val audioExecutor: ExecutorService = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "SuperDL-DeviceTone")
    }
    private val pendingToneReleases = mutableListOf<ToneGenerator>()

    fun play(event: DeviceStateEvent, context: Context? = null) {
        if (context != null && AlertSoundSettingsStore.isSilentMode(context)) return
        context?.let { GestureSoundHelper.ensureGestureStreamAudible(it) }
        handler.post {
            when (event) {
                DeviceStateEvent.CHARGER_CONNECTED -> playSequence(
                    listOf(523 to 90, 784 to 90, 1046 to 120)
                )
                DeviceStateEvent.CHARGER_DISCONNECTED -> playSequence(
                    listOf(988 to 90, 587 to 130)
                )
                DeviceStateEvent.BATTERY_FULL -> playSequence(
                    listOf(880 to 80, 1175 to 80, 1568 to 80, 1976 to 140)
                )
                DeviceStateEvent.SCREEN_OFF ->
                    if (context != null) playRawSound(context, com.superdl.launcher.R.raw.snd_screen_lock)
                    else playBurst(280, 110)
                DeviceStateEvent.SCREEN_ON ->
                    if (context != null) playRawSound(context, com.superdl.launcher.R.raw.snd_screen_unlock)
                    else playBurst(1175, 95)
            }
        }
    }

    private fun playSequence(notes: List<Pair<Int, Int>>) {
        audioExecutor.execute {
            for ((index, note) in notes.withIndex()) {
                if (Thread.currentThread().isInterrupted) return@execute
                playBurstSync(note.first, note.second)
                if (index < notes.lastIndex) sleepInterruptibly(70L)
            }
        }
    }

    private fun playBurst(freq: Int, durationMs: Int) {
        audioExecutor.execute { playBurstSync(freq, durationMs) }
    }

    /** Egy raw hangfájl lejátszása (képernyőzár/feloldás egyedi hangjai). */
    private fun playRawSound(context: Context, resId: Int) {
        try {
            val mp = android.media.MediaPlayer.create(context.applicationContext, resId)
            if (mp != null) {
                mp.setOnCompletionListener { it.release() }
                mp.start()
            }
        } catch (_: Exception) {
        }
    }

    fun playBurstSync(freq: Int, durationMs: Int) {
        try {
            val sampleRate = 22050
            val sampleCount = (sampleRate * durationMs / 1000).coerceAtLeast(1)
            val buffer = ShortArray(sampleCount)
            val phaseInc = 2.0 * PI * freq / sampleRate
            var phase = 0.0
            for (i in 0 until sampleCount) {
                val attack = minOf(1.0, i / (sampleRate * 0.01))
                val release = minOf(1.0, (sampleCount - i) / (sampleRate * 0.03))
                val env = attack * release
                phase += phaseInc
                buffer[i] = (sin(phase) * Short.MAX_VALUE * 0.55 * env).toInt().toShort()
            }
            val track = AudioTrack.Builder()
                .setAudioAttributes(GestureSoundHelper.gestureAudioAttributes())
                .setAudioFormat(
                    AudioFormat.Builder()
                        .setSampleRate(sampleRate)
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .build()
                )
                .setBufferSizeInBytes(buffer.size * 2)
                .setTransferMode(AudioTrack.MODE_STATIC)
                .build()
            track.write(buffer, 0, buffer.size)
            track.play()
            sleepInterruptibly(durationMs.toLong() + 40L)
            track.stop()
            track.release()
        } catch (_: Exception) {
            playToneGeneratorFallback(freq, durationMs)
        }
    }

    private fun playToneGeneratorFallback(freq: Int, durationMs: Int) {
        try {
            val toneType = when {
                freq >= 1400 -> ToneGenerator.TONE_PROP_BEEP2
                freq >= 900 -> ToneGenerator.TONE_PROP_BEEP
                freq >= 600 -> ToneGenerator.TONE_PROP_ACK
                else -> ToneGenerator.TONE_PROP_NACK
            }
            val tone = ToneGenerator(AudioManager.STREAM_MUSIC, 85)
            synchronized(pendingToneReleases) {
                pendingToneReleases.add(tone)
            }
            tone.startTone(toneType, durationMs)
            handler.postDelayed({
                synchronized(pendingToneReleases) {
                    pendingToneReleases.remove(tone)
                }
                runCatching { tone.release() }
            }, (durationMs + 80).toLong())
        } catch (_: Exception) {
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