package com.superdl.launcher.assistant

import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognitionService
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

/**
 * Kötelező a rendszer számára, hogy a VoiceInteractionService aktív legyen.
 * A Super DL saját hangfelismerőjét a VoiceInput osztály kezeli; ez a szolgáltatás
 * csak a platform-asszisztens aktiválásához szükséges híd.
 */
class SuperRecognitionService : RecognitionService() {

    private var speechRecognizer: SpeechRecognizer? = null

    override fun onStartListening(recognizerIntent: Intent, callback: Callback) {
        val recognizer = SpeechRecognizer.createSpeechRecognizer(applicationContext)
        speechRecognizer = recognizer
        recognizer.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {
                callback.readyForSpeech(params)
            }

            override fun onBeginningOfSpeech() {
                callback.beginningOfSpeech()
            }

            override fun onRmsChanged(rmsdB: Float) {
                callback.rmsChanged(rmsdB)
            }

            override fun onBufferReceived(buffer: ByteArray?) = Unit

            override fun onEndOfSpeech() {
                callback.endOfSpeech()
            }

            override fun onError(error: Int) {
                callback.error(error)
                destroyRecognizer()
            }

            override fun onResults(results: Bundle?) {
                callback.results(results)
                destroyRecognizer()
            }

            override fun onPartialResults(partialResults: Bundle?) {
                callback.partialResults(partialResults)
            }

            override fun onEvent(eventType: Int, params: Bundle?) = Unit
        })

        val listenIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "hu-HU")
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "hu-HU")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5)
            recognizerIntent.extras?.let { putExtras(it) }
        }
        recognizer.startListening(listenIntent)
    }

    override fun onCancel(callback: Callback) {
        speechRecognizer?.cancel()
        destroyRecognizer()
    }

    override fun onStopListening(callback: Callback) {
        speechRecognizer?.stopListening()
        callback.endOfSpeech()
    }

    override fun onDestroy() {
        destroyRecognizer()
        super.onDestroy()
    }

    private fun destroyRecognizer() {
        speechRecognizer?.destroy()
        speechRecognizer = null
    }
}