package com.superdl.launcher.medication

object MedicationSpeech {

    fun alertMessage(reminders: List<MedicationReminder>): String {
        val names = reminders.map { it.name }.filter { it.isNotBlank() }
        val nameText = when (names.size) {
            0 -> "a gyógyszert"
            1 -> names.first()
            else -> names.joinToString(" és ")
        }
        return "Kérlek vedd be a gyógyszered! $nameText."
    }

    fun readAll(reminders: List<MedicationReminder>): String {
        if (reminders.isEmpty()) return "Nincs beállított gyógyszer emlékeztető."
        val intro = "${reminders.size} gyógyszer emlékeztető."
        val items = reminders.joinToString(". ") { it.speakSummary() }
        return "$intro $items"
    }

    fun confirmSummary(
        name: String,
        hour: Int,
        minute: Int,
        cycleType: MedicationCycleType,
        weekDays: Set<Int>
    ): String {
        val preview = MedicationReminder(
            id = 0,
            name = name,
            hour = hour,
            minute = minute,
            cycleType = cycleType,
            weekDays = weekDays
        )
        return preview.speakSummary()
    }
}