package com.superdl.launcher.feedback

enum class AlertSoundCategory(
    val label: String,
    val defaultPreset: AlertSoundPreset
) {
    CALENDAR("Program emlékeztető", AlertSoundPreset.ALARM),
    MEDICATION("Gyógyszer emlékeztető", AlertSoundPreset.NOTIFICATION),
    ALARM_CLOCK("Ébresztő", AlertSoundPreset.ALARM),
    SMS("SMS üzenet", AlertSoundPreset.NOTIFICATION),
    EMAIL("E-mail", AlertSoundPreset.NOTIFICATION),
    GENERAL_NOTIFICATION("Egyéb értesítés", AlertSoundPreset.NOTIFICATION);

    companion object {
        val settingsOrder: List<AlertSoundCategory> = listOf(
            CALENDAR,
            MEDICATION,
            ALARM_CLOCK,
            SMS,
            EMAIL,
            GENERAL_NOTIFICATION
        )
    }
}