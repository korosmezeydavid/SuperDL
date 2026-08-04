package com.superdl.launcher.feedback

enum class DeviceStateEvent(
    val label: String,
    val description: String
) {
    CHARGER_CONNECTED(
        "Töltő csatlakoztatva",
        "A telefon töltőre lett dugva. Három felmenő síp."
    ),
    CHARGER_DISCONNECTED(
        "Töltő leválasztva",
        "A töltő ki lett húzva. Két lemenő síp."
    ),
    BATTERY_FULL(
        "Telefon teljesen feltöltve",
        "Az akkumulátor száz százalékra töltődött. Három magas síp."
    ),
    SCREEN_OFF(
        "Képernyő lezárva",
        "A kijelző kialudt vagy le lett zárva. Mély rövid síp."
    ),
    SCREEN_ON(
        "Képernyő feloldva",
        "A kijelző bekapcsolt vagy feloldódott. Magas rövid síp."
    )
}