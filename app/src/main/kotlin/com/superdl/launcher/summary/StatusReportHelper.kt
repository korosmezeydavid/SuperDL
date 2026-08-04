package com.superdl.launcher.summary

import android.content.Context
import android.provider.CallLog
import android.provider.Telephony
import com.superdl.launcher.alarm.AlarmStore
import com.superdl.launcher.calendar.CalendarHelper
import com.superdl.launcher.info.InfoHelper

/**
 * Gyors, offline "helyzetjelentés" – egyetlen paranccsal felolvassa a
 * legfontosabb aktuális információkat vak felhasználónak:
 * idő, akku + térerő, nem fogadott hívások, olvasatlan üzenetek,
 * következő ébresztő, következő naptár esemény.
 *
 * Ellentétben a DaySummaryHelper-rel, ez NEM hálózatfüggő (nincs időjárás),
 * ezért azonnal, internet nélkül is teljes választ ad.
 */
object StatusReportHelper {

    fun buildReport(context: Context): String {
        val parts = mutableListOf<String>()

        // Idő
        parts.add(InfoHelper.speakDateTime())

        // Akku + térerő (a beépített InfoHelper-ből)
        parts.add(InfoHelper.batteryAndSignalReport(context))

        // Nem fogadott hívások
        parts.add(missedCallsLine(context))

        // Olvasatlan üzenetek
        parts.add(unreadSmsLine(context))

        // Következő ébresztő
        parts.add(nextAlarmLine(context))

        // Következő naptár esemény
        parts.add(nextEventLine(context))

        return parts.joinToString(" ")
    }

    private fun missedCallsLine(context: Context): String {
        return try {
            var count = 0
            context.contentResolver.query(
                CallLog.Calls.CONTENT_URI,
                arrayOf(CallLog.Calls._ID),
                "${CallLog.Calls.TYPE} = ? AND ${CallLog.Calls.NEW} = 1",
                arrayOf(CallLog.Calls.MISSED_TYPE.toString()),
                null
            )?.use { cursor ->
                count = cursor.count
            }
            when (count) {
                0 -> "Nincs nem fogadott hívás."
                1 -> "1 nem fogadott hívás."
                else -> "$count nem fogadott hívás."
            }
        } catch (_: Exception) {
            "Nem fogadott hívások: nem elérhető."
        }
    }

    private fun unreadSmsLine(context: Context): String {
        return try {
            var count = 0
            context.contentResolver.query(
                Telephony.Sms.Inbox.CONTENT_URI,
                arrayOf(Telephony.Sms._ID),
                "${Telephony.Sms.READ} = 0",
                null,
                null
            )?.use { cursor ->
                count = cursor.count
            }
            when (count) {
                0 -> "Nincs olvasatlan üzenet."
                1 -> "1 olvasatlan üzenet."
                else -> "$count olvasatlan üzenet."
            }
        } catch (_: Exception) {
            "Üzenetek: nem elérhető."
        }
    }

    private fun nextAlarmLine(context: Context): String {
        val next = AlarmStore.getNextAlarm(context)
            ?: return "Nincs beállított ébresztő."
        return "Következő ébresztő: ${next.speakSummary()}."
    }

    private fun nextEventLine(context: Context): String {
        return try {
            val events = CalendarHelper.getTodayEvents(context)
            if (events.isEmpty()) {
                "Ma nincs több program a naptárban."
            } else {
                "Következő program: ${CalendarHelper.speakEvent(events.first())}."
            }
        } catch (_: Exception) {
            "Naptár: nem elérhető."
        }
    }
}
