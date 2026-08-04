package com.superdl.launcher.environment

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.os.Build
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.util.Log
import java.io.Closeable
import java.util.Locale

class AccessibilityTts(context: Context) : TextToSpeech.OnInitListener, Closeable {

    private val appContext = context.applicationContext
    private var tts: TextToSpeech = TextToSpeech(appContext, this)
    private var ready = false

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            val result = tts.setLanguage(Locale("hu", "HU"))
            ready = result != TextToSpeech.LANG_MISSING_DATA &&
                result != TextToSpeech.LANG_NOT_SUPPORTED
            if (!ready) {
                Log.w(TAG, "Magyar TTS nem elérhető, angol visszaesés")
                tts.setLanguage(Locale.ENGLISH)
                ready = true
            }
            configureAudioRouting()
        } else {
            Log.e(TAG, "TTS inicializálás sikertelen: $status")
            ready = false
        }
    }

    fun speakImmediate(text: String) {
        if (!ready || text.isBlank()) return
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, accessibilityParams(), utteranceId("flush"))
    }

    fun speakAdd(text: String) {
        if (!ready || text.isBlank()) return
        tts.speak(text, TextToSpeech.QUEUE_ADD, accessibilityParams(), utteranceId("add"))
    }

    fun stop() {
        tts.stop()
    }

    override fun close() {
        tts.stop()
        tts.shutdown()
    }

    private fun configureAudioRouting() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            tts.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .setFlags(AudioAttributes.FLAG_AUDIBILITY_ENFORCED)
                    .build()
            )
        }
    }

    private fun accessibilityParams(): Bundle =
        Bundle().apply {
            putInt(TextToSpeech.Engine.KEY_PARAM_STREAM, AudioManager.STREAM_ACCESSIBILITY)
            putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, 1.0f)
        }

    private fun utteranceId(prefix: String): String =
        "ENV_${prefix}_${System.currentTimeMillis()}"

    companion object {
        private const val TAG = "EnvScannerTts"
    }
}