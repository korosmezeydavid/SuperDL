package com.superdl.launcher.voice

import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

data class SpeechRecognitionResult(
    val hypotheses: List<String>,
    val confidences: FloatArray?
)

class VoiceInput(context: Context) {

    enum class ListenProfile {
        DEFAULT,
        ASSISTANT,
        WAKE_WORD
    }

    private val recognizerContext = context.applicationContext
    private val handler = Handler(Looper.getMainLooper())
    private var recognizer: SpeechRecognizer? = null
    private var onResultCallback: ((String) -> Unit)? = null
    private var onRichResultCallback: ((SpeechRecognitionResult) -> Unit)? = null
    private var onErrorCallback: (() -> Unit)? = null
    private var onErrorCodeCallback: ((Int) -> Unit)? = null
    private var pendingIntent: Intent? = null
    private var retryCount = 0
    private var maxRetries = 1
    private var toneGenerator: ToneGenerator? = null
    private var listenGeneration = 0
    private var activeProfile = ListenProfile.DEFAULT

    fun isAvailable(): Boolean = SpeechRecognizer.isRecognitionAvailable(recognizerContext)

    fun listen(
        prompt: String,
        speakFirst: (String, () -> Unit) -> Unit,
        onResult: (String) -> Unit,
        onError: () -> Unit
    ) {
        speakFirst(prompt) {
            listenPrompt(prompt, onResult, onError)
        }
    }

    fun listenPrompt(
        prompt: String,
        onResult: (String) -> Unit,
        onError: () -> Unit,
        profile: ListenProfile = ListenProfile.DEFAULT
    ) {
        listenPromptRich(
            prompt = prompt,
            hints = emptyList(),
            profile = profile,
            onResult = { result -> onResult(result.hypotheses.firstOrNull().orEmpty()) },
            onError = { onError() }
        )
    }

    fun listenPromptAssistant(
        prompt: String,
        hints: List<String>,
        onResult: (SpeechRecognitionResult) -> Unit,
        onError: (Int) -> Unit
    ) {
        listenPromptRich(
            prompt = prompt,
            hints = hints,
            profile = ListenProfile.ASSISTANT,
            onResult = onResult,
            onError = onError
        )
    }

    fun listenPromptWakeWord(
        hints: List<String>,
        onResult: (SpeechRecognitionResult) -> Unit,
        onError: (Int) -> Unit
    ) {
        listenPromptRich(
            prompt = "",
            hints = hints,
            profile = ListenProfile.WAKE_WORD,
            onResult = onResult,
            onError = onError
        )
    }

    private fun listenPromptRich(
        prompt: String,
        hints: List<String>,
        profile: ListenProfile,
        onResult: (SpeechRecognitionResult) -> Unit,
        onError: (Int) -> Unit
    ) {
        if (!isAvailable()) {
            onError(SpeechRecognizer.ERROR_CLIENT)
            return
        }

        val generation = ++listenGeneration
        onResultCallback = null
        onRichResultCallback = onResult
        onErrorCallback = null
        onErrorCodeCallback = onError
        activeProfile = profile
        maxRetries = when (profile) {
            ListenProfile.ASSISTANT -> 2
            ListenProfile.WAKE_WORD -> 0
            ListenProfile.DEFAULT -> 1
        }
        retryCount = 0
        prepareRecognizer(generation)
        pendingIntent = buildIntent(prompt, hints, profile)
        val preDelay = when (profile) {
            ListenProfile.WAKE_WORD -> 120L
            ListenProfile.ASSISTANT -> 500L
            ListenProfile.DEFAULT -> 400L
        }
        handler.postDelayed({ startListeningInternal(generation, profile) }, preDelay)
    }

    private fun buildIntent(prompt: String, hints: List<String>, profile: ListenProfile): Intent =
        Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "hu-HU")
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "hu-HU")
            putExtra(RecognizerIntent.EXTRA_ONLY_RETURN_LANGUAGE_PREFERENCE, true)
            putExtra(RecognizerIntent.EXTRA_PROMPT, prompt)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)

            val maxResults = when (profile) {
                ListenProfile.ASSISTANT -> 5
                ListenProfile.WAKE_WORD -> 3
                ListenProfile.DEFAULT -> 3
            }
            val silenceMs = when (profile) {
                ListenProfile.ASSISTANT -> 2800L
                ListenProfile.WAKE_WORD -> 1100L
                ListenProfile.DEFAULT -> 1800L
            }
            val minimumMs = when (profile) {
                ListenProfile.WAKE_WORD -> 250L
                else -> 400L
            }

            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, maxResults)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, silenceMs)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, silenceMs)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, minimumMs)

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, false)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, recognizerContext.packageName)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE && hints.isNotEmpty()) {
                putStringArrayListExtra(RecognizerIntent.EXTRA_BIASING_STRINGS, ArrayList(hints.take(120)))
            }
        }

    private fun startListeningInternal(generation: Int, profile: ListenProfile = activeProfile) {
        if (generation != listenGeneration) return
        val intent = pendingIntent ?: return
        if (profile != ListenProfile.WAKE_WORD) {
            playListeningEarcon()
        }
        try {
            recognizer?.startListening(intent)
        } catch (_: Exception) {
            if (generation == listenGeneration) {
                handler.post { onErrorCodeCallback?.invoke(SpeechRecognizer.ERROR_CLIENT) }
            }
        }
    }

    private fun playListeningEarcon() {
        try {
            toneGenerator?.release()
            toneGenerator = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 90)
            toneGenerator?.startTone(ToneGenerator.TONE_PROP_BEEP2, 130)
            handler.postDelayed({
                toneGenerator?.release()
                toneGenerator = null
            }, 180L)
        } catch (_: Exception) {
        }
    }

    private fun prepareRecognizer(generation: Int) {
        recognizer?.destroy()
        recognizer = SpeechRecognizer.createSpeechRecognizer(recognizerContext).apply {
            setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) {}
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() {}
                override fun onPartialResults(partialResults: Bundle?) {}
                override fun onEvent(eventType: Int, params: Bundle?) {}

                override fun onError(error: Int) {
                    if (generation != listenGeneration) return
                    if (shouldRetry(error) && retryCount < maxRetries) {
                        retryCount++
                        handler.postDelayed({ startListeningInternal(generation, activeProfile) }, 600L)
                        return
                    }
                    val errorCb = onErrorCallback
                    val errorCodeCb = onErrorCodeCallback
                    handler.post {
                        if (generation != listenGeneration) return@post
                        errorCodeCb?.invoke(error) ?: errorCb?.invoke()
                    }
                }

                override fun onResults(results: Bundle?) {
                    if (generation != listenGeneration) return
                    val hypotheses = results
                        ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        ?.map { it.trim() }
                        ?.filter { it.isNotBlank() }
                        .orEmpty()
                    val confidences = results?.getFloatArray(SpeechRecognizer.CONFIDENCE_SCORES)
                    val resultCb = onResultCallback
                    val richResultCb = onRichResultCallback
                    val errorCb = onErrorCallback
                    val errorCodeCb = onErrorCodeCallback
                    handler.post {
                        if (generation != listenGeneration) return@post
                        if (hypotheses.isEmpty()) {
                            errorCodeCb?.invoke(SpeechRecognizer.ERROR_NO_MATCH) ?: errorCb?.invoke()
                            return@post
                        }
                        val payload = SpeechRecognitionResult(hypotheses, confidences)
                        richResultCb?.invoke(payload) ?: resultCb?.invoke(hypotheses.first())
                    }
                }
            })
        }
    }

    private fun shouldRetry(error: Int): Boolean =
        error == SpeechRecognizer.ERROR_NO_MATCH ||
            error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT ||
            error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY ||
            error == SpeechRecognizer.ERROR_NETWORK ||
            error == SpeechRecognizer.ERROR_NETWORK_TIMEOUT

    fun cancel() {
        listenGeneration++
        handler.removeCallbacksAndMessages(null)
        onResultCallback = null
        onRichResultCallback = null
        onErrorCallback = null
        onErrorCodeCallback = null
        pendingIntent = null
        retryCount = 0
        try {
            recognizer?.stopListening()
            recognizer?.cancel()
        } catch (_: Exception) {}
    }

    fun destroy() {
        cancel()
        toneGenerator?.release()
        toneGenerator = null
        recognizer?.destroy()
        recognizer = null
    }
}