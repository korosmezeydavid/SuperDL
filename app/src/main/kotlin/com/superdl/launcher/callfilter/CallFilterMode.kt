package com.superdl.launcher.callfilter

enum class CallFilterMode(val id: String, val menuLabel: String, val speakLabel: String) {
    TOTAL_DND(
        id = "total_dnd",
        menuLabel = "Teljes Ne Zavarj",
        speakLabel = "Teljes Ne Zavarj. Minden bejövő hívás automatikusan elutasítva."
    ),
    PRIORITY_ONLY(
        id = "priority_only",
        menuLabel = "Részleges",
        speakLabel = "Részleges szűrés. Csak kedvenc és csillagozott névjegyek jönnek át."
    ),
    CONTACTS_ONLY(
        id = "contacts_only",
        menuLabel = "Laza",
        speakLabel = "Laza szűrés. Csak ismert névjegyek hívhatnak."
    ),
    ACCEPT_ALL(
        id = "accept_all",
        menuLabel = "Mindent Fogad",
        speakLabel = "Mindent fogad. Rejtett és ismeretlen számok tiltva."
    );

    fun next(): CallFilterMode {
        val values = entries.toTypedArray()
        return values[(ordinal + 1) % values.size]
    }

    companion object {
        fun fromId(id: String?): CallFilterMode =
            entries.firstOrNull { it.id == id } ?: ACCEPT_ALL
    }
}