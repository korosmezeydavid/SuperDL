package com.superdl.launcher.currency

import android.media.AudioManager
import android.media.ToneGenerator
import java.io.Closeable

class ScanBeepPlayer : Closeable {

    private val toneGenerator = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 90)
    private val tickGenerator = ToneGenerator(AudioManager.STREAM_SYSTEM, WORKING_TICK_VOLUME)

    /** Halk, rövid kattintás – jelzi, hogy a felismerő aktívan dolgozik. */
    fun playWorkingTick() {
        tickGenerator.startTone(ToneGenerator.TONE_PROP_ACK, WORKING_TICK_MS)
    }

    fun playScanStart() {
        toneGenerator.startTone(ToneGenerator.TONE_PROP_BEEP2, 130)
    }

    override fun close() {
        toneGenerator.release()
        tickGenerator.release()
    }

    companion object {
        private const val WORKING_TICK_VOLUME = 28
        private const val WORKING_TICK_MS = 35
    }
}