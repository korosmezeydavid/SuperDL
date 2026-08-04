package com.superdl.launcher.keyboard

import android.content.Context

/**
 * A mátrix-billentyűzet beállításai.
 *
 * Mindkét érték ERŐSEN egyéni: a cellaméret a kéz- és kijelzőmérettől függ,
 * a pörgetési sebesség pedig a gyakorlottságtól — kezdetben lassabb kell,
 * később gyorsítani érdemes.
 */
object MatrixKeyboardPrefs {

    private const val PREFS = "superdl_matrix_keyboard"
    private const val KEY_CELL = "cell_size_dp"
    private const val KEY_SPEED = "cycle_ms"
    private const val KEY_SPEAK_CHARS = "speak_chars"

    /** Alapértelmezett pörgetési sebesség: egy karakter ennyi ideig hangzik. */
    const val DEFAULT_CYCLE_MS = 900L
    const val MIN_CYCLE_MS = 300L
    const val MAX_CYCLE_MS = 2500L

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun getCellSizeDp(context: Context): Float =
        prefs(context).getFloat(KEY_CELL, MatrixLayout.DEFAULT_CELL_DP)

    fun setCellSizeDp(context: Context, dp: Float) {
        prefs(context).edit()
            .putFloat(KEY_CELL, dp.coerceIn(MatrixLayout.MIN_CELL, MatrixLayout.MAX_CELL))
            .apply()
    }

    fun getCycleMs(context: Context): Long =
        prefs(context).getLong(KEY_SPEED, DEFAULT_CYCLE_MS)

    fun setCycleMs(context: Context, ms: Long) {
        prefs(context).edit()
            .putLong(KEY_SPEED, ms.coerceIn(MIN_CYCLE_MS, MAX_CYCLE_MS))
            .apply()
    }

    /** Kimondja-e a beírt karaktert megerősítésként. */
    fun isSpeakChars(context: Context): Boolean =
        prefs(context).getBoolean(KEY_SPEAK_CHARS, true)

    fun setSpeakChars(context: Context, on: Boolean) {
        prefs(context).edit().putBoolean(KEY_SPEAK_CHARS, on).apply()
    }

    fun speakSettings(context: Context): String =
        "Gombok távolsága: ${cellStepName(context)}. " +
            "Pörgetés: ${speedStepName(context)}."

    // ── NÉGY FOKOZAT — a lépkedés egyszerűbb, mint a szabad állítgatás ───────

    /**
     * A gombok távolsága négy fokozatban. Nagyobb kijelzőn és nagyobb kézzel a
     * szélesebb a kényelmes, kisebb kézzel a szűkebb.
     */
    private val CELL_STEPS = floatArrayOf(44f, 56f, 72f, 92f)
    private val CELL_NAMES = arrayOf("szűk", "közepes", "széles", "nagyon széles")

    /**
     * A karakterek pörgetési sebessége négy fokozatban.
     * A leggyorsabb SEM lehet kapkodó: a felolvasásnak be kell férnie.
     */
    private val SPEED_STEPS = longArrayOf(1200L, 900L, 700L, 550L)
    private val SPEED_NAMES = arrayOf("lassú", "közepes", "gyors", "nagyon gyors")

    /** Léptetés a következő fokozatra (körbe). */
    fun nextCellStep(context: Context): String {
        val current = getCellSizeDp(context)
        val idx = CELL_STEPS.indexOfFirst { kotlin.math.abs(it - current) < 1f }
        val next = if (idx < 0) 1 else (idx + 1) % CELL_STEPS.size
        setCellSizeDp(context, CELL_STEPS[next])
        return CELL_NAMES[next]
    }

    fun nextSpeedStep(context: Context): String {
        val current = getCycleMs(context)
        val idx = SPEED_STEPS.indexOfFirst { it == current }
        val next = if (idx < 0) 1 else (idx + 1) % SPEED_STEPS.size
        setCycleMs(context, SPEED_STEPS[next])
        return SPEED_NAMES[next]
    }

    fun cellStepName(context: Context): String {
        val current = getCellSizeDp(context)
        val idx = CELL_STEPS.indexOfFirst { kotlin.math.abs(it - current) < 1f }
        return if (idx >= 0) CELL_NAMES[idx] else "egyedi"
    }

    fun speedStepName(context: Context): String {
        val current = getCycleMs(context)
        val idx = SPEED_STEPS.indexOfFirst { it == current }
        return if (idx >= 0) SPEED_NAMES[idx] else "egyedi"
    }
}
