package com.superdl.launcher.feedback

import com.superdl.launcher.R

enum class SoundType(
    val defaultResId: Int,
    val label: String,
    val description: String
) {
    STARTUP(
        R.raw.snd_startup,
        "Indítás",
        "A program elindulásakor hallható üdvözlő hang."
    ),
    SWIPE_UP(
        R.raw.snd_swipe_up,
        "Söpörj fel",
        "Felfelé húzás. Menüben előző elem, folyamatban felfelé lépkedés."
    ),
    SWIPE_DOWN(
        R.raw.snd_swipe_down,
        "Söpörj le",
        "Lefelé húzás. Menüben következő elem, folyamatban lefelé lépkedés."
    ),
    SWIPE_LEFT(
        R.raw.snd_swipe_left,
        "Söpörj balra",
        "Balra húzás. Visszalépés, megszakítás, kilépés."
    ),
    SWIPE_RIGHT(
        R.raw.snd_swipe_right,
        "Söpörj jobbra",
        "Jobbra húzás. Kiválasztás, megerősítés, végrehajtás."
    ),
    ACTION_OK(
        R.raw.snd_action_ok,
        "Sikeres művelet",
        "Ha egy művelet sikeresen lefutott."
    ),
    ACTION_ERROR(
        R.raw.snd_action_error,
        "Hibás művelet",
        "Ha valami nem sikerült, vagy nem elérhető."
    ),
    MENU_NAV(
        R.raw.snd_menu_nav,
        "Menü navigáció",
        "Finom kattanás menüpontok között."
    );

    companion object {
        val trainingOrder: List<SoundType> = listOf(
            STARTUP,
            SWIPE_UP,
            SWIPE_DOWN,
            SWIPE_LEFT,
            SWIPE_RIGHT,
            ACTION_OK,
            ACTION_ERROR,
            MENU_NAV
        )
    }
}