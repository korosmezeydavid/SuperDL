package com.superdl.launcher.files

import android.content.Context
import android.media.AudioManager
import android.media.Ringtone
import android.media.RingtoneManager
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator

/**
 * "Hol a telóm?" — a portálról indítható hangos csörgetés, hogy az elkallódott
 * (pl. ágy mögé csúszott) telefon megtalálható legyen.
 *
 * Maximumra állítja a csengő-hangerőt, lejátssza az alapértelmezett csengőhangot
 * és rezgést, majd egy megadott idő után magától leáll (és VISSZAÁLLÍTJA az
 * eredeti hangerőt, hogy ne maradjon feltekerve).
 */
object FindPhoneHelper {

    private var ringtone: Ringtone? = null
    private var vibrator: Vibrator? = null
    private var previousVolume: Int = -1
    private val handler = Handler(Looper.getMainLooper())
    private var stopRunnable: Runnable? = null

    private const val DEFAULT_DURATION_MS = 30_000L

    /** Csörgetés indítása. Ha már szól, előbb leállítja (újraindítás). */
    fun start(context: Context, durationMs: Long = DEFAULT_DURATION_MS) {
        stop(context)
        val app = context.applicationContext
        try {
            val am = app.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            // Csengő-hangerő maximumra (az eredetit megjegyezzük a visszaállításhoz).
            previousVolume = am.getStreamVolume(AudioManager.STREAM_RING)
            val max = am.getStreamMaxVolume(AudioManager.STREAM_RING)
            am.setStreamVolume(AudioManager.STREAM_RING, max, 0)

            val uri = RingtoneManager.getActualDefaultRingtoneUri(app, RingtoneManager.TYPE_RINGTONE)
                ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE)
            ringtone = RingtoneManager.getRingtone(app, uri)?.apply {
                @Suppress("DEPRECATION")
                streamType = AudioManager.STREAM_RING
                isLooping = true
                play()
            }

            // Rezgés is (folyamatos minta), hogy tapintással is megtalálható legyen.
            vibrator = (app.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator)?.apply {
                val pattern = longArrayOf(0, 600, 400)
                vibrate(VibrationEffect.createWaveform(pattern, 0))
            }
        } catch (_: Exception) {
        }

        // Automatikus leállás a megadott idő után.
        stopRunnable = Runnable { stop(app) }.also {
            handler.postDelayed(it, durationMs)
        }

        // A TELEFONON is jelenjen meg egy leállító képernyő, hogy a megtaláló ne
        // kényszerüljön visszamenni a számítógéphez. Két jobbra söprés kell hozzá,
        // nehogy egy véletlen mozdulat (zsebben, táskában) elhallgattassa.
        try {
            val intent = android.content.Intent(app, FindPhoneStopActivity::class.java).apply {
                addFlags(
                    android.content.Intent.FLAG_ACTIVITY_NEW_TASK or
                        android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP
                )
            }
            app.startActivity(intent)
        } catch (_: Exception) {
        }
    }

    /** Csörgetés leállítása és az eredeti hangerő visszaállítása. */
    fun stop(context: Context) {
        val app = context.applicationContext
        stopRunnable?.let { handler.removeCallbacks(it) }
        stopRunnable = null
        try {
            ringtone?.stop()
        } catch (_: Exception) {
        }
        ringtone = null
        try {
            vibrator?.cancel()
        } catch (_: Exception) {
        }
        vibrator = null
        // Eredeti csengő-hangerő visszaállítása.
        if (previousVolume >= 0) {
            try {
                val am = app.getSystemService(Context.AUDIO_SERVICE) as AudioManager
                am.setStreamVolume(AudioManager.STREAM_RING, previousVolume, 0)
            } catch (_: Exception) {
            }
            previousVolume = -1
        }
    }

    fun isRinging(): Boolean = ringtone?.isPlaying == true
}
