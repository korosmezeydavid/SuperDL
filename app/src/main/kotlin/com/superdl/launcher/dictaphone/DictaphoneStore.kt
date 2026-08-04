package com.superdl.launcher.dictaphone

import java.io.File

object DictaphoneStore {

    @Volatile
    var isRecording: Boolean = false

    @Volatile
    var isPaused: Boolean = false

    @Volatile
    var startedAtMillis: Long = 0L

    @Volatile
    var pausedAtMillis: Long = 0L

    @Volatile
    var totalPausedMillis: Long = 0L

    @Volatile
    var outputFile: File? = null

    @Volatile
    var config: DictaphoneConfig? = null

    @Volatile
    var currentLabel: String = ""

    @Volatile
    var lastError: String? = null

    fun setError(message: String) {
        lastError = message
    }

    fun consumeError(): String? {
        val error = lastError
        lastError = null
        return error
    }

    fun elapsedMillis(): Long {
        if (!isRecording) return 0L
        val now = System.currentTimeMillis()
        val pauseExtra = if (isPaused && pausedAtMillis > 0L) now - pausedAtMillis else 0L
        return (now - startedAtMillis - totalPausedMillis - pauseExtra).coerceAtLeast(0L)
    }

    fun markStarted() {
        isRecording = true
        isPaused = false
        startedAtMillis = System.currentTimeMillis()
        pausedAtMillis = 0L
        totalPausedMillis = 0L
        lastError = null
    }

    fun markPaused() {
        if (!isRecording || isPaused) return
        isPaused = true
        pausedAtMillis = System.currentTimeMillis()
    }

    fun markResumed() {
        if (!isRecording || !isPaused) return
        if (pausedAtMillis > 0L) {
            totalPausedMillis += System.currentTimeMillis() - pausedAtMillis
        }
        isPaused = false
        pausedAtMillis = 0L
    }

    fun clear() {
        isRecording = false
        isPaused = false
        startedAtMillis = 0L
        pausedAtMillis = 0L
        totalPausedMillis = 0L
        outputFile = null
        config = null
        currentLabel = ""
        lastError = null
    }
}