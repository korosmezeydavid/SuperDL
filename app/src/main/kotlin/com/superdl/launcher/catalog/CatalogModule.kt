package com.superdl.launcher.catalog

/**
 * Egy modul a SuperDL katalógusból.
 *
 * FONTOS ELV: a modul mindig ADAT, soha nem futtatható kód. A "motor" (pl. a
 * kvíz-játék) a SuperDL-ben van, a tartalom jön a katalógusból. Így egy új
 * kvízhez NEM kell új alkalmazás-verzió, és a Google Play szabályzatát sem
 * sértjük (az tiltja a futásidejű kód-letöltést).
 */
data class CatalogModule(
    val id: String,
    val name: String,
    val type: ModuleType,
    val version: Int,
    val description: String,
    val sizeBytes: Long,
    val filePath: String,
    val minAppVersion: String
) {
    /** Felolvasható összefoglaló a listához. */
    fun speakSummary(installedVersion: Int?): String {
        val state = when {
            installedVersion == null -> "nincs letöltve"
            installedVersion < version -> "frissítés érhető el"
            else -> "letöltve"
        }
        return "$name. ${type.label}. $state. ${speakSize()}."
    }

    fun speakSize(): String = when {
        sizeBytes < 1024 -> "$sizeBytes bájt"
        sizeBytes < 1024 * 1024 -> "${sizeBytes / 1024} kilobájt"
        else -> "${sizeBytes / 1024 / 1024} megabájt"
    }
}

/** A támogatott modul-típusok. Mindegyikhez van "motor" a SuperDL-ben. */
enum class ModuleType(val key: String, val label: String) {
    QUIZ("quiz", "kvíz játék"),
    WORD_GAME("wordgame", "szójáték"),
    SOUND_THEME("soundtheme", "hangkészlet"),
    RADIO_PACK("radiopack", "rádiócsomag"),
    GUIDE("guide", "útmutató"),
    RECIPES("recipes", "receptek"),
    TEXT_BANK("textbank", "szövegtár-készlet"),
    EXTERNAL_APP("externalapp", "külön alkalmazás"),
    UNKNOWN("unknown", "ismeretlen típus");

    companion object {
        fun fromKey(key: String?): ModuleType =
            entries.firstOrNull { it.key.equals(key, true) } ?: UNKNOWN
    }
}
