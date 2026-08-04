package com.superdl.launcher.crash

import android.content.Context
import android.util.Log
import java.io.File
import java.io.PrintWriter
import java.io.StringWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object CrashLogHandler {

    private const val TAG = "SuperDL.Crash"
    private const val LOG_FILE = "crash_log.txt"
    private const val MAX_LOG_BYTES = 256 * 1024

    fun install(context: Context) {
        val appContext = context.applicationContext
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            try {
                appendCrash(appContext, thread, throwable)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to write crash log", e)
            }
            previous?.uncaughtException(thread, throwable)
        }
    }

    fun readRecent(context: Context, maxChars: Int = 8000): String {
        val file = logFile(context)
        if (!file.exists()) return ""
        val text = file.readText()
        return if (text.length <= maxChars) text else text.takeLast(maxChars)
    }

    private fun appendCrash(context: Context, thread: Thread, throwable: Throwable) {
        val sw = StringWriter()
        throwable.printStackTrace(PrintWriter(sw))
        val timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date())
        val entry = buildString {
            appendLine("=== $timestamp ===")
            appendLine("Thread: ${thread.name}")
            append(sw.toString())
            appendLine()
        }
        val file = logFile(context)
        file.parentFile?.mkdirs()
        file.appendText(entry)
        trimIfNeeded(file)
        Log.e(TAG, "Uncaught exception on ${thread.name}", throwable)
    }

    private fun logFile(context: Context): File =
        File(context.filesDir, LOG_FILE)

    private fun trimIfNeeded(file: File) {
        if (file.length() <= MAX_LOG_BYTES) return
        val text = file.readText()
        file.writeText(text.takeLast(MAX_LOG_BYTES))
    }
}