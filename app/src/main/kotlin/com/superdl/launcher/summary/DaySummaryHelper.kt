package com.superdl.launcher.summary

import android.content.Context
import android.os.BatteryManager
import android.provider.Telephony
import com.superdl.launcher.calendar.CalendarHelper
import com.superdl.launcher.info.InfoHelper
import com.superdl.launcher.medication.MedicationScheduler
import com.superdl.launcher.medication.MedicationStore
import com.superdl.launcher.weather.WeatherCityStore
import com.superdl.launcher.weather.WeatherHelper
import java.util.concurrent.atomic.AtomicInteger

object DaySummaryHelper {

    fun fetchAndSpeak(
        context: Context,
        onSpeak: (String) -> Unit,
        onError: (String) -> Unit
    ) {
        val parts = mutableListOf<String>()
        parts.add(InfoHelper.speakDateTime())

        val pending = AtomicInteger(4)
        fun tryFinish() {
            if (pending.decrementAndGet() == 0) {
                onSpeak(parts.joinToString(" "))
            }
        }

        // Akkumulátor (szinkron)
        val bm = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val level = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        parts.add("Akkumulátor: $level százalék.")

        // SMS olvasatlan
        Thread {
            parts.add(countUnreadSms(context))
            tryFinish()
        }.start()

        // Időjárás
        val city = WeatherCityStore.get(context)
        WeatherHelper.fetch(
            city = city,
            onResult = { info ->
                parts.add("Időjárás: ${info.speakSummary()}")
                tryFinish()
            },
            onError = {
                parts.add("Időjárás: nem áll rendelkezésre.")
                tryFinish()
            }
        )

        // Naptár
        Thread {
            val events = CalendarHelper.getTodayEvents(context).take(3)
            parts.add(
                if (events.isEmpty()) "Ma nincs program a naptárban."
                else CalendarHelper.speakAllEvents(events)
            )
            tryFinish()
        }.start()

        // Gyógyszer
        Thread {
            parts.add(nextMedicationLine(context))
            tryFinish()
        }.start()
    }

    private fun countUnreadSms(context: Context): String {
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

    private fun nextMedicationLine(context: Context): String {
        val enabled = MedicationStore.getEnabled(context)
        if (enabled.isEmpty()) return "Nincs gyógyszer-emlékeztető."
        val next = enabled.minByOrNull { MedicationScheduler.millisUntil(it) } ?: return "Nincs következő gyógyszer."
        val mins = (MedicationScheduler.millisUntil(next) / 60_000).toInt().coerceAtLeast(0)
        val time = String.format("%02d:%02d", next.hour, next.minute)
        return "Következő gyógyszer: ${next.name}, $time-kor, kb. $mins perc múlva."
    }
}