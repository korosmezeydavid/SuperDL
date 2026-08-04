package com.superdl.launcher.dictaphone

import android.content.Context
import android.content.Intent
import android.os.Build

object DictaphoneManager {

    private var recorder: DictaphoneRecorder? = null

    fun isRecording(): Boolean = DictaphoneStore.isRecording

    fun isPaused(): Boolean = DictaphoneStore.isPaused

    fun elapsedMillis(): Long = DictaphoneStore.elapsedMillis()

    fun lastError(): String? = DictaphoneStore.lastError

    fun startRecording(context: Context): Boolean {
        if (DictaphoneStore.isRecording) return true
        DictaphoneStore.lastError = null
        val config = DictaphoneSettingsStore.load(context)
        val output = DictaphoneLibrary.createOutputFile(context, config.format)
        val engine = DictaphoneRecorder(context.applicationContext, config)
        if (!engine.start(output)) {
            engine.cancel()
            return false
        }
        recorder = engine
        DictaphoneStore.markStarted()
        DictaphoneStore.config = config
        startService(context)
        return true
    }

    fun pauseRecording() {
        recorder?.pause()
        DictaphoneStore.markPaused()
    }

    fun resumeRecording() {
        recorder?.resume()
        DictaphoneStore.markResumed()
    }

    fun togglePause() {
        if (DictaphoneStore.isPaused) resumeRecording() else pauseRecording()
    }

    fun stopAndSave(context: Context): DictaphoneRecordingEntry? {
        val savedFile = recorder?.stopAndSave()
        recorder = null
        stopService(context)
        DictaphoneStore.clear()
        if (savedFile == null || !savedFile.exists()) return null
        val format = DictaphoneFormat.entries.firstOrNull { savedFile.name.endsWith(".${it.extension}") }
            ?: DictaphoneFormat.WAV
        return DictaphoneRecordingEntry(savedFile, savedFile.lastModified(), format)
    }

    fun cancelRecording(context: Context) {
        recorder?.cancel()
        recorder = null
        stopService(context)
        DictaphoneStore.clear()
    }

    /**
     * Returns a recording-fatal error message if the capture thread failed.
     * Clears the stored error so it is announced only once.
     */
    fun consumeRecordingFailure(): String? {
        if (!DictaphoneStore.isRecording) return null
        val recorderActive = recorder?.isActive == true
        if (recorderActive) return null
        return DictaphoneStore.consumeError()
    }

    private fun startService(context: Context) {
        val intent = Intent(context, DictaphoneService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        } catch (_: Exception) {
        }
    }

    private fun stopService(context: Context) {
        context.stopService(Intent(context, DictaphoneService::class.java))
    }
}