package com.superdl.launcher.keyboard

import android.content.Context

/**
 * SZÖVEGTÁR — előre elmentett szövegek a mátrix billentyűzet gombjain.
 *
 * MIÉRT KELL: egy hosszú e-mail cím, egy számlaszám vagy egy gyakori válasz
 * betűnkénti bevitele lassú, és pont ott a legnagyobb az elgépelés esélye, ahol
 * a legnehezebb ellenőrizni. Ha egyszer eltároltad, onnantól EGY mozdulat.
 *
 * FELÉPÍTÉS: ugyanaz a 3x4-es rács, mint a betűbevitelnél — 1-től 9-ig, majd
 * csillag, nulla, kettőskereszt. Tizenkét hely, tizenkét szöveg.
 * Nem kell új mozdulatot tanulni: ugyanúgy leteszed az ujjad, csúsztatsz,
 * felengeded.
 */
object MatrixTextBank {

    private const val PREFS = "superdl_text_bank"

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun keyOf(slot: MatrixKey) = "slot_${slot.name}"

    /** A gombhoz tartozó szöveg, vagy null ha üres. */
    fun get(context: Context, slot: MatrixKey): String? =
        prefs(context).getString(keyOf(slot), null)?.takeIf { it.isNotBlank() }

    fun set(context: Context, slot: MatrixKey, text: String) {
        prefs(context).edit().putString(keyOf(slot), text.trim()).apply()
    }

    fun clear(context: Context, slot: MatrixKey) {
        prefs(context).edit().remove(keyOf(slot)).apply()
    }

    /** Hány hely van kitöltve. */
    fun count(context: Context): Int =
        MatrixKey.entries.count { get(context, it) != null }

    /**
     * A gomb tartalmának RÖVID bemondása navigáláskor.
     * Hosszú szövegnél csak az elejét mondjuk, különben a végigcsúsztatás
     * elviselhetetlenül lassú lenne.
     */
    fun speakPreview(context: Context, slot: MatrixKey): String {
        val text = get(context, slot)
            ?: return "${slot.label}: üres"
        val preview = if (text.length > 40) text.take(40) + "…" else text
        return "${slot.label}: $preview"
    }

    /** Az összes hely felolvasható listája (a menühöz). */
    fun speakAll(context: Context): String {
        val filled = MatrixKey.entries.mapNotNull { slot ->
            get(context, slot)?.let { text ->
                val preview = if (text.length > 30) text.take(30) + "…" else text
                "${slot.label}: $preview"
            }
        }
        return if (filled.isEmpty()) {
            "A szövegtár üres. A billentyűzeten két ujjal háromszor koppintva " +
                "nyithatod meg, és ott töltheted fel."
        } else {
            "${filled.size} mentett szöveg. ${filled.joinToString(". ")}"
        }
    }
}
