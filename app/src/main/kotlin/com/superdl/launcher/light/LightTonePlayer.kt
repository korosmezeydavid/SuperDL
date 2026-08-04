package com.superdl.launcher.light

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.PI
import kotlin.math.pow
import kotlin.math.sin

class LightTonePlayer {

    private val running = AtomicBoolean(false)
    private val targetFrequency = AtomicInteger(320)
    private val targetAmplitude = AtomicInteger(20)
    private var audioTrack: AudioTrack? = null
    private var thread: Thread? = null

    fun luminanceToFrequency(luminance: Int): Int {
        val t = (luminance.coerceIn(0, 255)) / 255.0
        val minF = 280.0
        val maxF = 3900.0
        return (minF * (maxF / minF).pow(t)).toInt()
    }

    fun update(luminance: Int) {
        targetFrequency.set(luminanceToFrequency(luminance))
        val amp = 18 + ((luminance.coerceIn(0, 255) * 77) / 255)
        targetAmplitude.set(amp.coerceIn(18, 95))
    }

    fun start() {
        if (!running.compareAndSet(false, true)) return
        val sampleRate = 22050
        val minBuf = AudioTrack.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )
        val track = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setSampleRate(sampleRate)
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build()
            )
            .setBufferSizeInBytes(minBuf * 2)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()
        audioTrack = track
        track.play()
        thread = Thread {
            val buffer = ShortArray(1024)
            var phase = 0.0
            var currentFreq = targetFrequency.get().toDouble()
            while (running.get()) {
                val goalFreq = targetFrequency.get().toDouble()
                currentFreq += (goalFreq - currentFreq) * 0.18
                val amp = targetAmplitude.get() / 100.0
                val phaseInc = 2.0 * PI * currentFreq / sampleRate
                for (i in buffer.indices) {
                    phase += phaseInc
                    if (phase > 2.0 * PI) phase -= 2.0 * PI
                    buffer[i] = (sin(phase) * Short.MAX_VALUE * amp).toInt().toShort()
                }
                track.write(buffer, 0, buffer.size)
            }
            try {
                track.stop()
                track.release()
            } catch (_: Exception) {}
        }.apply {
            name = "LightTonePlayer"
            start()
        }
    }

    fun stop() {
        running.set(false)
        thread?.join(400)
        thread = null
        audioTrack = null
    }
}