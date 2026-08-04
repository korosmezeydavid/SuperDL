package com.superdl.launcher.train

enum class TrainContextAction(val label: String) {
    SPEAK_FULL("Részletes felolvasás"),
    SAVE_FAVORITE("Állomás mentése kedvencekbe"),
    REMOVE_FAVORITE("Kedvenc törlése"),
    TOGGLE_RADIUS("Keresési kör váltása"),
    REFRESH("Frissítés")
}