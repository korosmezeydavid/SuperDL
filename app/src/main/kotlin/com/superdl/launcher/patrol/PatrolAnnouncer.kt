package com.superdl.launcher.patrol

import android.content.Context
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import com.superdl.launcher.feedback.AlertSoundCategory
import com.superdl.launcher.feedback.AlertSoundPlayer
import com.superdl.launcher.system.QuietModeHelper
import com.superdl.launcher.tts.TtsEngineStore
import com.superdl.launcher.tts.TtsSettingsStore
import java.util.Locale
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.atomic.AtomicBoolean

object PatrolAnnouncer {

    private const val TAG = "SuperDL.PatrolAnnouncer"
    private const val MAX_QUEUE_SIZE = 12

    private data class AnnounceRequest(
        val appContext: Context,
        val message: String,
        val withBeep: Boolean,
        val soundCategory: AlertSoundCategory,
        val softChime: Boolean = false,
        val onDone: (() -> Unit)?
    )

    private val speaking = AtomicBoolean(false)
    private val queue = ConcurrentLinkedQueue<AnnounceRequest>()
    private val mainHandler = Handler(Looper.getMainLooper())

    fun announce(
        context: Context,
        message: String,
        withBeep: Boolean = true,
        soundCategory: AlertSoundCategory = AlertSoundCategory.GENERAL_NOTIFICATION,
        critical: Boolean = false,
        softChime: Boolean = false,
        onDone: (() -> Unit)? = null
    ) {
        val trimmed = message.trim()
        if (trimmed.isEmpty()) {
            onDone?.let { mainHandler.post(it) }
            return
        }
        // A kritikus bejelentések (pl. aktív navigáció kanyarai) átlépnek a
        // néma módon: a felhasználó kifejezetten kérte őket a vezetés indításával,
        // és biztonsági szempontból nem szabad elnémítani.
        if (!critical && QuietModeHelper.shouldSuppressNotificationAnnouncements(context)) {
            onDone?.let { mainHandler.post(it) }
            return
        }
        val request = AnnounceRequest(
            appContext = context.applicationContext,
            message = trimmed,
            withBeep = withBeep,
            soundCategory = soundCategory,
            softChime = softChime,
            onDone = onDone
        )
        if (speaking.compareAndSet(false, true)) {
            deliver(request)
        } else {
            if (queue.size >= MAX_QUEUE_SIZE) {
                val dropped = queue.poll()
                dropped?.onDone?.let { mainHandler.post(it) }
                Log.w(TAG, "Announcement queue full; dropped oldest pending message")
            }
            queue.offer(request)
        }
    }

    private fun deliver(request: AnnounceRequest) {
        val wakeLock = acquireWakeLock(request.appContext)
        val finish: () -> Unit = {
            releaseWakeLock(wakeLock)
            speaking.set(false)
            request.onDone?.let { mainHandler.post(it) }
            processNextQueued()
        }
        if (request.softChime) {
            // Egyetlen rövid, lágy csendülés az egész értesítő-hangsor helyett
            // (pl. óránkénti időbemondás, feloldás) – kevésbé zavaró.
            playSoftChime(request.appContext)
            mainHandler.postDelayed({
                speak(request.appContext, request.message, finish)
            }, 700L)
        } else if (request.withBeep) {
            AlertSoundPlayer.playOnce(request.appContext, request.soundCategory)
            mainHandler.postDelayed({
                speak(request.appContext, request.message, finish)
            }, 320L)
        } else {
            speak(request.appContext, request.message, finish)
        }
    }

    private fun processNextQueued() {
        val next = queue.poll() ?: return
        if (speaking.compareAndSet(false, true)) {
            deliver(next)
        } else {
            queue.offer(next)
        }
    }

    private fun speak(context: Context, message: String, onDone: () -> Unit) {
        var tts: TextToSpeech? = null
        val enginePackage = TtsEngineStore.getSelectedPackage(context)
        val listener = TextToSpeech.OnInitListener { status ->
            if (status != TextToSpeech.SUCCESS) {
                tts?.shutdown()
                playFallbackBeep()
                mainHandler.post(onDone)
                return@OnInitListener
            }
            val engine = tts ?: run {
                mainHandler.post(onDone)
                return@OnInitListener
            }
            val lang = engine.setLanguage(Locale("hu", "HU"))
            if (lang == TextToSpeech.LANG_MISSING_DATA || lang == TextToSpeech.LANG_NOT_SUPPORTED) {
                engine.setLanguage(Locale.getDefault())
            }
            engine.setSpeechRate(TtsSettingsStore.getSpeechRate(context))
            engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {}
                override fun onDone(utteranceId: String?) {
                    if (utteranceId == "patrol_announce") {
                        engine.shutdown()
                        mainHandler.post(onDone)
                    }
                }
                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    if (utteranceId == "patrol_announce") {
                        engine.shutdown()
                        playFallbackBeep()
                        mainHandler.post(onDone)
                    }
                }
            })
            engine.speak(message, TextToSpeech.QUEUE_FLUSH, null, "patrol_announce")
        }
        tts = if (enginePackage.isNullOrBlank()) {
            TextToSpeech(context, listener)
        } else {
            TextToSpeech(context, listener, enginePackage)
        }
    }

    private fun acquireWakeLock(context: Context): PowerManager.WakeLock? =
        try {
            val pm = context.getSystemService(Context.POWER_SERVICE) as PowerManager
            pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "SuperDL:PatrolAnnounce").apply {
                setReferenceCounted(false)
                acquire(45_000L)
            }
        } catch (e: Exception) {
            Log.w(TAG, "Wake lock acquire failed", e)
            null
        }

    private fun releaseWakeLock(wakeLock: PowerManager.WakeLock?) {
        try {
            if (wakeLock?.isHeld == true) wakeLock.release()
        } catch (e: Exception) {
            Log.w(TAG, "Wake lock release failed", e)
        }
    }

    private fun playSoftChime(context: Context) {
        try {
            // A periodikus időbemondás kezdőhangja: egy kellemes "kling"
            // hangfájl (snd_time_chime) a régi szintetikus ToneGenerator-bleep
            // helyett. A lejátszás után magától elengedi az erőforrást.
            val mp = android.media.MediaPlayer.create(
                context, com.superdl.launcher.R.raw.snd_time_chime
            )
            if (mp != null) {
                mp.setOnCompletionListener { it.release() }
                mp.start()
            } else {
                // Ha valamiért nem tölthető be a fájl, marad a régi bleep.
                val tone = ToneGenerator(AudioManager.STREAM_MUSIC, 60)
                tone.startTone(ToneGenerator.TONE_PROP_ACK, 130)
                mainHandler.postDelayed({ tone.release() }, 200L)
            }
        } catch (e: Exception) {
            Log.w(TAG, "Soft chime failed", e)
        }
    }

    private fun playFallbackBeep() {
        try {
            val tone = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 90)
            tone.startTone(ToneGenerator.TONE_PROP_BEEP2, 200)
            mainHandler.postDelayed({ tone.release() }, 260L)
        } catch (e: Exception) {
            Log.w(TAG, "Fallback beep failed", e)
        }
    }
}