package com.superdl.launcher.voice

import java.util.Calendar
import java.util.Locale

object VoiceDateParser {

    private val weekdayMap = mapOf(
        "vasárnap" to Calendar.SUNDAY,
        "vasarnap" to Calendar.SUNDAY,
        "hétfő" to Calendar.MONDAY,
        "hetfo" to Calendar.MONDAY,
        "kedd" to Calendar.TUESDAY,
        "szerda" to Calendar.WEDNESDAY,
        "csütörtök" to Calendar.THURSDAY,
        "csutortok" to Calendar.THURSDAY,
        "péntek" to Calendar.FRIDAY,
        "pentek" to Calendar.FRIDAY,
        "szombat" to Calendar.SATURDAY
    )

    private val monthMap = mapOf(
        "január" to Calendar.JANUARY,
        "januar" to Calendar.JANUARY,
        "február" to Calendar.FEBRUARY,
        "februar" to Calendar.FEBRUARY,
        "március" to Calendar.MARCH,
        "marcius" to Calendar.MARCH,
        "április" to Calendar.APRIL,
        "aprilis" to Calendar.APRIL,
        "május" to Calendar.MAY,
        "majus" to Calendar.MAY,
        "június" to Calendar.JUNE,
        "junius" to Calendar.JUNE,
        "július" to Calendar.JULY,
        "julius" to Calendar.JULY,
        "augusztus" to Calendar.AUGUST,
        "szeptember" to Calendar.SEPTEMBER,
        "október" to Calendar.OCTOBER,
        "oktober" to Calendar.OCTOBER,
        "november" to Calendar.NOVEMBER,
        "december" to Calendar.DECEMBER
    )

    fun parseDayStartMs(spoken: String, base: Calendar = Calendar.getInstance()): Long? {
        val normalized = spoken.trim().lowercase(Locale("hu", "HU"))
            .replace("ő", "o")
            .replace("ű", "u")
            .replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
            .replace("ö", "o")
            .replace("ü", "u")
            .replace(Regex("\\s+"), " ")
            .trim()

        if (normalized.isBlank()) return null

        when {
            normalized == "ma" || normalized.startsWith("ma ") -> return midnightAfter(base, 0)
            normalized == "holnap" || normalized.startsWith("holnap ") -> return midnightAfter(base, 1)
            normalized == "holnaputan" || normalized == "holnap utan" -> return midnightAfter(base, 2)
        }

        val nextWeekday = normalized.startsWith("kovetkezo ") || normalized.startsWith("következő ")
        val weekdayText = normalized
            .removePrefix("kovetkezo ")
            .removePrefix("következő ")
            .trim()

        weekdayMap[weekdayText]?.let { targetDay ->
            return midnightOnWeekday(base, targetDay, forceNext = nextWeekday)
        }

        for ((name, month) in monthMap) {
            if (!normalized.contains(name)) continue
            val day = Regex("(\\d{1,2})").findAll(normalized).map { it.value.toInt() }.lastOrNull()
                ?: return null
            val year = Regex("(20\\d{2})").find(normalized)?.value?.toInt() ?: base.get(Calendar.YEAR)
            val cal = Calendar.getInstance().apply {
                set(Calendar.YEAR, year)
                set(Calendar.MONTH, month - 1)
                set(Calendar.DAY_OF_MONTH, day.coerceIn(1, 31))
                set(Calendar.HOUR_OF_DAY, 0)
                set(Calendar.MINUTE, 0)
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
            }
            if (cal.get(Calendar.MONTH) != month - 1) return null
            return cal.timeInMillis
        }

        val digits = Regex("(\\d{1,2})").findAll(normalized).map { it.value.toInt() }.toList()
        if (digits.size == 1 && digits[0] in 1..31) {
            val cal = Calendar.getInstance().apply {
                timeInMillis = base.timeInMillis
                set(Calendar.DAY_OF_MONTH, digits[0])
                set(Calendar.HOUR_OF_DAY, 0)
                set(Calendar.MINUTE, 0)
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
            }
            if (cal.before(base)) {
                cal.add(Calendar.MONTH, 1)
            }
            return cal.timeInMillis
        }

        return null
    }

    fun parseDurationMinutes(spoken: String): Int? {
        val normalized = spoken.trim().lowercase(Locale("hu", "HU"))
            .replace("óra", "ora")
            .replace("perc", "perc")
            .replace(Regex("\\s+"), " ")
            .trim()

        if (normalized.isBlank()) return null

        when {
            normalized.contains("fel ora") || normalized == "fel" -> return 30
            normalized.contains("egy ora") || normalized == "egy" -> return 60
            normalized.contains("ket ora") || normalized.contains("kettő ora") || normalized.contains("ketto ora") -> return 120
            normalized.contains("harom ora") -> return 180
        }

        val hourMatch = Regex("(\\d+)\\s*ora").find(normalized)
        val minuteMatch = Regex("(\\d+)\\s*perc").find(normalized)
        val hours = hourMatch?.groupValues?.get(1)?.toIntOrNull() ?: 0
        val minutes = minuteMatch?.groupValues?.get(1)?.toIntOrNull() ?: 0
        val total = hours * 60 + minutes
        return if (total > 0) total else null
    }

    private fun midnightAfter(base: Calendar, dayOffset: Int): Long {
        val cal = Calendar.getInstance().apply {
            timeInMillis = base.timeInMillis
            add(Calendar.DAY_OF_YEAR, dayOffset)
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        return cal.timeInMillis
    }

    private fun midnightOnWeekday(base: Calendar, targetDay: Int, forceNext: Boolean): Long {
        val cal = Calendar.getInstance().apply { timeInMillis = base.timeInMillis }
        val currentDay = cal.get(Calendar.DAY_OF_WEEK)
        var diff = targetDay - currentDay
        if (diff < 0) diff += 7
        if (forceNext && diff == 0) diff = 7
        cal.add(Calendar.DAY_OF_YEAR, diff)
        cal.set(Calendar.HOUR_OF_DAY, 0)
        cal.set(Calendar.MINUTE, 0)
        cal.set(Calendar.SECOND, 0)
        cal.set(Calendar.MILLISECOND, 0)
        return cal.timeInMillis
    }
}