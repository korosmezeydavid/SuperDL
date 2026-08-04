package com.superdl.launcher.tts

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Build
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.speech.tts.Voice
import android.util.Log
import java.util.Locale

class TtsManager(context: Context) : TextToSpeech.OnInitListener {

    private val appContext = context.applicationContext
    private val handler = Handler(Looper.getMainLooper())
    private var selectedVoiceName: String? = TtsEngineStore.getSelectedVoiceName(appContext)
    private var tts: TextToSpeech = createEngine(TtsEngineStore.getSelectedPackage(appContext))
    private var isReady = false
    private var initFailed = false
    private var onUtteranceDone: (() -> Unit)? = null
    private var pendingOnReady: (() -> Unit)? = null
    private val readyCallbacks = mutableListOf<() -> Unit>()

    var speechRate: Float = TtsSettingsStore.getSpeechRate(appContext)
        set(value) {
            field = value.coerceIn(0.5f, 2.5f)
            TtsSettingsStore.setSpeechRate(appContext, field)
            if (isReady) tts.setSpeechRate(field)
        }

    private fun createEngine(enginePackage: String?): TextToSpeech =
        if (enginePackage.isNullOrBlank()) {
            TextToSpeech(appContext, this)
        } else {
            TextToSpeech(appContext, this, enginePackage)
        }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            initFailed = false
            val result = tts.setLanguage(Locale("hu", "HU"))
            isReady = result != TextToSpeech.LANG_MISSING_DATA &&
                result != TextToSpeech.LANG_NOT_SUPPORTED
            if (!isReady) {
                Log.w("TTS", "Magyar nyelv nem érhető el, visszaesés angolra")
                tts.setLanguage(Locale.ENGLISH)
                isReady = true
            }
            applySelectedVoice()
            configureAudioRouting()
            tts.setSpeechRate(speechRate)
            tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {}
                override fun onDone(utteranceId: String?) {
                    if (utteranceId?.startsWith("SDL_DONE_") == true) {
                        val callback = onUtteranceDone
                        onUtteranceDone = null
                        callback?.let { handler.post(it) }
                    }
                }
                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    if (utteranceId?.startsWith("SDL_DONE_") == true) {
                        val callback = onUtteranceDone
                        onUtteranceDone = null
                        callback?.let { handler.post(it) }
                    }
                }
            })
            pendingOnReady?.let { handler.post(it) }
            pendingOnReady = null
            if (readyCallbacks.isNotEmpty()) {
                val callbacks = readyCallbacks.toList()
                readyCallbacks.clear()
                callbacks.forEach { handler.post(it) }
            }
        } else {
            Log.e("TTS", "TTS motor inicializálás sikertelen: $status")
            isReady = false
            initFailed = true
            val pending = pendingOnReady
            pendingOnReady = null
            val queued = readyCallbacks.toList()
            readyCallbacks.clear()
            handler.post {
                pending?.invoke()
                queued.forEach { it.invoke() }
            }
        }
    }

    fun switchEngine(
        packageName: String?,
        voiceName: String? = selectedVoiceName,
        onReady: (() -> Unit)? = null,
        onFailed: (() -> Unit)? = null
    ) {
        selectedVoiceName = voiceName?.takeIf { it.isNotBlank() }
        TtsEngineStore.setSelection(appContext, packageName, selectedVoiceName)
        pendingOnReady = if (onReady != null || onFailed != null) {
            {
                if (isReady) onReady?.invoke() else onFailed?.invoke()
            }
        } else null
        onUtteranceDone = null
        isReady = false
        initFailed = false
        val rate = speechRate
        tts.stop()
        tts.shutdown()
        speechRate = rate
        tts = createEngine(packageName)
    }

    fun runWhenReady(action: () -> Unit) {
        if (isReady) {
            handler.post(action)
        } else {
            readyCallbacks.add(action)
        }
    }

    fun speak(text: String) {
        if (initFailed) {
            Log.w("TTS", "TTS nem elérhető, kihagyva: $text")
            return
        }
        if (!isReady) {
            runWhenReady { speak(text) }
            return
        }
        onUtteranceDone = null
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, speakParams(), "SDL_${System.currentTimeMillis()}")
    }

    fun speakThen(text: String, onDone: () -> Unit) {
        if (initFailed) {
            Log.w("TTS", "TTS nem elérhető, speakThen kihagyva")
            handler.post(onDone)
            return
        }
        if (!isReady) {
            runWhenReady { speakThen(text, onDone) }
            return
        }
        onUtteranceDone = onDone
        val id = "SDL_DONE_${System.currentTimeMillis()}"
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, speakParams(), id)
    }

    /**
     * Kimondja a szöveget, ÉS AZONNAL elvégzi a műveletet — NEM várja meg a
     * beszéd végét.
     *
     * MIÉRT KELL: a speakThen a művelet elvégzését a beszéd BEFEJEZÉSÉHEZ köti,
     * ezért egy hosszabb mondat után a felhasználó fölöslegesen várt: rápöccintett
     * valamire, és a parancs csak másodpercekkel később indult el.
     * Ezzel a metódussal a művelet azonnal fut, a beszéd pedig közben szól.
     *
     * MIKOR NE HASZNÁLD:
     *  - ha utána MIKROFON indul (diktálás, hangfelvétel) — ott a beszéd
     *    belemondana a felvételbe, maradjon a speakThen,
     *  - ha a művelet elvégzése előtt a felhasználónak feltétlenül hallania kell
     *    a figyelmeztetést.
     */
    fun speakAndRun(text: String, action: () -> Unit) {
        speak(text)
        handler.post(action)
    }

    fun speakAdd(text: String) {
        if (initFailed) return
        if (!isReady) {
            runWhenReady { speakAdd(text) }
            return
        }
        tts.speak(text, TextToSpeech.QUEUE_ADD, speakParams(), "SDL_ADD_${System.currentTimeMillis()}")
    }

    fun isSpeaking(): Boolean = isReady && tts.isSpeaking

    fun stop() {
        onUtteranceDone = null
        tts.stop()
    }

    fun speedUp() {
        speechRate += 0.1f
        speak("Sebesség: ${String.format(Locale.getDefault(), "%.1f", speechRate)}")
    }

    fun speedDown() {
        speechRate -= 0.1f
        speak("Sebesség: ${String.format(Locale.getDefault(), "%.1f", speechRate)}")
    }

    private fun configureAudioRouting() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            val attributes = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .setFlags(AudioAttributes.FLAG_AUDIBILITY_ENFORCED)
                .build()
            tts.setAudioAttributes(attributes)
        }
    }

    private fun speakParams(): Bundle = Bundle().apply {
        putInt(TextToSpeech.Engine.KEY_PARAM_STREAM, AudioManager.STREAM_ACCESSIBILITY)
        putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, 1.0f)
    }

    private fun applySelectedVoice() {
        val voiceName = selectedVoiceName?.takeIf { it.isNotBlank() } ?: return
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.LOLLIPOP) return
        val voices = tts.voices ?: return
        val voice = voices.firstOrNull { it.name == voiceName } ?: return
        tts.voice = voice
    }

    fun shutdown() {
        handler.removeCallbacksAndMessages(null)
        onUtteranceDone = null
        pendingOnReady = null
        readyCallbacks.clear()
        tts.stop()
        tts.shutdown()
    }
}