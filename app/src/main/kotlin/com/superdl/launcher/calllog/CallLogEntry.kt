package com.superdl.launcher.calllog

import android.provider.CallLog
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class CallLogEntry(
    val number: String,
    val name: String,
    val date: Long,
    val type: Int,
    val durationSeconds: Int
) {
    fun speakPreview(): String {
        val who = if (name.isNotBlank()) name else number
        return "${typeLabel()}. $who. ${formatDate()}"
    }

    fun speakFull(): String {
        val who = if (name.isNotBlank()) "$name, $number" else number
        val duration = if (durationSeconds > 0) " Időtartam: ${durationSeconds} másodperc." else ""
        return "${typeLabel()}. $who. ${formatDate()}.$duration"
    }

    private fun typeLabel(): String = when (type) {
        CallLog.Calls.INCOMING_TYPE -> "Bejövő hívás"
        CallLog.Calls.OUTGOING_TYPE -> "Kimenő hívás"
        CallLog.Calls.MISSED_TYPE -> "Nem fogadott hívás"
        CallLog.Calls.REJECTED_TYPE -> "Elutasított hívás"
        CallLog.Calls.BLOCKED_TYPE -> "Blokkolt hívás"
        else -> "Hívás"
    }

    private fun formatDate(): String {
        val fmt = SimpleDateFormat("MMMM d. H:mm", Locale("hu", "HU"))
        return fmt.format(Date(date))
    }
}