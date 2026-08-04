package com.superdl.launcher.transit

enum class TransitContextAction(val label: String) {
    SPEAK_FULL("Részletes felolvasás"),
    SAVE_FAVORITE("Megálló mentése kedvencekbe"),
    REMOVE_FAVORITE("Kedvenc törlése"),
    TOGGLE_RADIUS("Keresési kör váltása"),
    REFRESH("Frissítés")
}