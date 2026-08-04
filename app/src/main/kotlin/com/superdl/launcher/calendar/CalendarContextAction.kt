package com.superdl.launcher.calendar

enum class CalendarContextAction(val label: String) {
    READ("Program felolvasása"),
    EDIT("Program szerkesztése"),
    DELETE("Program törlése");

    companion object {
        val browseActions: List<CalendarContextAction> = listOf(READ, EDIT, DELETE)
        val alarmActions: List<CalendarAlarmAction> = CalendarAlarmAction.entries.toList()
    }
}

enum class CalendarAlarmAction(val label: String) {
    REMIND_ONE_HOUR("Emlékeztetés 1 óra múlva"),
    MARK_COMPLETE("Megjelölés teljesítettként");
}