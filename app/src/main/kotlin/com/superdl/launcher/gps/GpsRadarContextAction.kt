package com.superdl.launcher.gps

enum class GpsRadarContextAction(val label: String) {
    LOCK_TARGET("Célzárolás"),
    HEAR_INTERSECTION_AHEAD("Kereszteződés előre"),
    WHERE_AM_I("Hol vagyok?"),
    TOGGLE_STREET_MONITORING("Utcabemondás ki-be"),
    SAVE_OWN_LOCATION("Saját hely mentése"),
    SAVE_POI("Kiválasztott hely mentése")
}