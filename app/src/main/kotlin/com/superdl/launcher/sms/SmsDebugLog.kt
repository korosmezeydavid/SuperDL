package com.superdl.launcher.sms

import android.content.Context
import android.util.Log
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object SmsDebugLog {

    private const val TAG = "SuperDL.SmsDebug"
    private const val FILE_NAME = "sms_inbound.log"
    private const val MAX_BYTES = 256 * 1024

    fun append(context: Context, message: String) {
        val line = "${timestamp()} $message"
        Log.i(TAG, message)
        try {
            val file = File(context.applicationContext.filesDir, FILE_NAME)
            if (file.length() > MAX_BYTES) {
                val tail = file.readText().takeLast(MAX_BYTES / 2)
                file.writeText(tail)
            }
            file.appendText(line + "\n")
        } catch (_: Exception) {
        }
    }

    private fun timestamp(): String =
        SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US).format(Date())
}