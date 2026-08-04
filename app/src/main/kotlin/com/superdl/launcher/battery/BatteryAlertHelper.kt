package com.superdl.launcher.battery

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import com.superdl.launcher.tts.TtsEngineStore
import com.superdl.launcher.tts.TtsSettingsStore
import androidx.core.app.NotificationCompat
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean

object BatteryAlertHelper {

    private const val ALERT_CHANNEL_ID = "BATTERY_ALERT_CHANNEL"
    private const val ALERT_NOTIFICATION_ID = 7202
    private val alerting = AtomicBoolean(false)

    fun alert(context: Context, level: Int, threshold: Int) {
        if (!alerting.compareAndSet(false, true)) return
        val appContext = context.applicationContext
        val wakeLock = acquireWakeLock(appContext)
        vibrateAlert(appContext)
        playAlertBeeps {
            speakAlert(appContext, level, threshold) {
                showAlertNotification(appContext, threshold)
                releaseWakeLock(wakeLock)
                alerting.set(false)
            }
        }
    }

    private fun acquireWakeLock(context: Context): PowerManager.WakeLock? {
        return try {
            val pm = context.getSystemService(Context.POWER_SERVICE) as PowerManager
            pm.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK,
                "SuperDL:BatteryPatrolAlert"
            ).apply {
                setReferenceCounted(false)
                acquire(60_000L)
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun releaseWakeLock(wakeLock: PowerManager.WakeLock?) {
        try {
            if (wakeLock?.isHeld == true) wakeLock.release()
        } catch (_: Exception) {}
    }

    private fun vibrateAlert(context: Context) {
        try {
            val pattern = longArrayOf(0, 280, 120, 280, 120, 420)
            val vibrator = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
                val manager = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
                manager.defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
            }
            vibrator.vibrate(VibrationEffect.createWaveform(pattern, -1))
        } catch (_: Exception) {}
    }

    private fun playAlertBeeps(onDone: () -> Unit) {
        val handler = Handler(Looper.getMainLooper())
        try {
            val tone = ToneGenerator(AudioManager.STREAM_ALARM, 100)
            val beepMs = 320
            val gapMs = 180L
            tone.startTone(ToneGenerator.TONE_CDMA_ALERT_CALL_GUARD, beepMs)
            handler.postDelayed({
                tone.startTone(ToneGenerator.TONE_CDMA_ALERT_CALL_GUARD, beepMs)
                handler.postDelayed({
                    tone.startTone(ToneGenerator.TONE_CDMA_EMERGENCY_RINGBACK, beepMs)
                    handler.postDelayed({
                        tone.release()
                        onDone()
                    }, beepMs.toLong() + 80L)
                }, beepMs.toLong() + gapMs)
            }, beepMs.toLong() + gapMs)
        } catch (_: Exception) {
            handler.post(onDone)
        }
    }

    private fun speakAlert(context: Context, @Suppress("UNUSED_PARAMETER") level: Int, threshold: Int, onDone: () -> Unit) {
        val message = BatteryPatrolLogic.speakMessage(threshold)
        val handler = Handler(Looper.getMainLooper())
        var tts: TextToSpeech? = null
        val enginePackage = TtsEngineStore.getSelectedPackage(context)
        val createTts: (TextToSpeech.OnInitListener) -> TextToSpeech = { listener ->
            if (enginePackage.isNullOrBlank()) {
                TextToSpeech(context, listener)
            } else {
                TextToSpeech(context, listener, enginePackage)
            }
        }
        val listener = TextToSpeech.OnInitListener { status ->
            if (status != TextToSpeech.SUCCESS) {
                handler.post(onDone)
                tts?.shutdown()
                return@OnInitListener
            }
            val engine = tts ?: run {
                handler.post(onDone)
                return@OnInitListener
            }
            val lang = engine.setLanguage(Locale("hu", "HU"))
            if (lang == TextToSpeech.LANG_MISSING_DATA || lang == TextToSpeech.LANG_NOT_SUPPORTED) {
                engine.setLanguage(Locale.getDefault())
            }
            engine.setSpeechRate(TtsSettingsStore.getSpeechRate(context))
            engine.setPitch(1.05f)
            engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {}
                override fun onDone(utteranceId: String?) {
                    if (utteranceId == "battery_patrol_alert") {
                        engine.shutdown()
                        handler.post(onDone)
                    }
                }
                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    if (utteranceId == "battery_patrol_alert") {
                        engine.shutdown()
                        handler.post(onDone)
                    }
                }
            })
            engine.speak(message, TextToSpeech.QUEUE_FLUSH, null, "battery_patrol_alert")
        }
        tts = createTts(listener)
    }

    private fun showAlertNotification(context: Context, threshold: Int) {
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                ALERT_CHANNEL_ID,
                "Akkumulátor figyelmeztetés",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Alacsony akkumulátor szint hangos és vizuális jelzése"
                enableVibration(true)
                setBypassDnd(true)
            }
            manager.createNotificationChannel(channel)
        }
        val notification = NotificationCompat.Builder(context, ALERT_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle("Akkumulátor alacsony")
            .setContentText("Töltöttség: $threshold százalék. Csatlakoztasd a töltőt!")
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setAutoCancel(true)
            .build()
        manager.notify(ALERT_NOTIFICATION_ID, notification)
    }
}