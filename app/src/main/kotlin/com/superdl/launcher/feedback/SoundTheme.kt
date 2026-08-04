package com.superdl.launcher.feedback

import com.superdl.launcher.R

enum class SoundTheme(
    val id: String,
    val label: String,
    val description: String
) {
    DEFAULT(
        id = "default",
        label = "Alapértelmezett",
        description = "Klasszikus sípoló söprés hangok."
    ),
    CLICK_FLICK(
        id = "click_flick",
        label = "Kattintás és flick",
        description = "Apró kattintás és lapcsapás hangok a gesztusokhoz."
    ),
    SWISH(
        id = "swish",
        label = "Suhogás",
        description = "Gyors suhogó és csúszó hangok a gesztusokhoz."
    ),
    KOPPANOS(
        id = "koppanos",
        label = "Koppanós",
        description = "Tiszta, éles koppanó kattanások a gesztusokhoz."
    ),
    GOMB(
        id = "gomb",
        label = "Gombnyomás",
        description = "Változatos gombnyomás hangok a gesztusokhoz."
    ),
    SCIFI(
        id = "scifi",
        label = "Sci-fi",
        description = "Űrhajós, elektronikus hangeffektek. Hosszabb, dallamos indítóhang."
    );

    fun resIdFor(type: SoundType): Int = when (this) {
        DEFAULT -> type.defaultResId
        CLICK_FLICK -> clickFlickRes(type)
        SWISH -> swishRes(type)
        KOPPANOS -> koppanosRes(type)
        GOMB -> gombRes(type)
        SCIFI -> scifiRes(type)
    }

    fun previewSwipeTypes(): List<SoundType> = listOf(
        SoundType.SWIPE_UP,
        SoundType.SWIPE_DOWN,
        SoundType.SWIPE_LEFT,
        SoundType.SWIPE_RIGHT
    )

    private fun clickFlickRes(type: SoundType): Int = when (type) {
        SoundType.SWIPE_UP -> R.raw.snd_menu_nav
        SoundType.SWIPE_DOWN -> R.raw.snd_card_place
        SoundType.SWIPE_LEFT -> R.raw.snd_card_flick
        SoundType.SWIPE_RIGHT -> R.raw.snd_slot_lever
        SoundType.MENU_NAV -> R.raw.snd_menu_nav
        else -> type.defaultResId
    }

    private fun swishRes(type: SoundType): Int = when (type) {
        SoundType.SWIPE_UP -> R.raw.snd_slot_spin
        SoundType.SWIPE_DOWN -> R.raw.snd_slot_reel_stop
        SoundType.SWIPE_LEFT -> R.raw.snd_card_flick
        SoundType.SWIPE_RIGHT -> R.raw.snd_card_deal
        SoundType.MENU_NAV -> R.raw.snd_card_place
        SoundType.ACTION_OK -> R.raw.snd_game_win
        SoundType.ACTION_ERROR -> R.raw.snd_game_lose
        else -> type.defaultResId
    }

    private fun koppanosRes(type: SoundType): Int = when (type) {
        SoundType.SWIPE_UP -> R.raw.snd_koppanos_up
        SoundType.SWIPE_DOWN -> R.raw.snd_koppanos_down
        SoundType.SWIPE_LEFT -> R.raw.snd_koppanos_left
        SoundType.SWIPE_RIGHT -> R.raw.snd_koppanos_right
        SoundType.MENU_NAV -> R.raw.snd_koppanos_nav
        SoundType.ACTION_OK -> R.raw.snd_koppanos_ok
        else -> type.defaultResId
    }

    private fun gombRes(type: SoundType): Int = when (type) {
        SoundType.SWIPE_UP -> R.raw.snd_gomb_up
        SoundType.SWIPE_DOWN -> R.raw.snd_gomb_down
        SoundType.SWIPE_LEFT -> R.raw.snd_gomb_left
        SoundType.SWIPE_RIGHT -> R.raw.snd_gomb_right
        SoundType.MENU_NAV -> R.raw.snd_gomb_nav
        SoundType.ACTION_OK -> R.raw.snd_gomb_ok
        else -> type.defaultResId
    }

    // Sci-fi téma: minden hangtípushoz saját effekt. A STARTUP a leghosszabb,
    // dallamos indítóhang (a felhasználó kérése volt a hosszabb bekapcsolóhang).
    private fun scifiRes(type: SoundType): Int = when (type) {
        SoundType.STARTUP -> R.raw.snd_scifi_startup
        SoundType.SWIPE_UP -> R.raw.snd_scifi_up
        SoundType.SWIPE_DOWN -> R.raw.snd_scifi_down
        SoundType.SWIPE_LEFT -> R.raw.snd_scifi_left
        SoundType.SWIPE_RIGHT -> R.raw.snd_scifi_right
        SoundType.MENU_NAV -> R.raw.snd_scifi_nav
        SoundType.ACTION_OK -> R.raw.snd_scifi_ok
        SoundType.ACTION_ERROR -> R.raw.snd_scifi_error
    }

    companion object {
        val selectable: List<SoundTheme> = entries

        fun fromId(id: String?): SoundTheme =
            entries.firstOrNull { it.id == id } ?: DEFAULT
    }
}