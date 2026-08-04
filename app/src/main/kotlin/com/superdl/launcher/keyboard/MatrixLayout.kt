package com.superdl.launcher.keyboard

import kotlin.math.roundToInt

/**
 * A 3x4-es mátrix elhelyezése a képernyőn, a felhasználó ujja köré.
 *
 * MŰKÖDÉS: ahová a felhasználó leteszi az ujját, oda kerül a mátrix KÖZEPE
 * (az 5-ös gomb). Onnan számolva helyezkednek el körülötte a többi gombok.
 * Így nem kell megkeresni a billentyűzetet — a billentyűzet találja meg a kezet.
 *
 * A cellaméret ÁLLÍTHATÓ: nagyobb kijelzőn kényelmesebb a szélesebb cella,
 * kisebb kézzel a szűkebb.
 */
class MatrixLayout(
    /** Egy cella szélessége/magassága képpontban. */
    private var cellSize: Float
) {
    private var centerX: Float = 0f
    private var centerY: Float = 0f
    private var calibrated = false

    /** A mátrix középpontjának rögzítése oda, ahol az ujj leért. */
    fun calibrate(x: Float, y: Float) {
        centerX = x
        centerY = y
        calibrated = true
    }

    fun isCalibrated(): Boolean = calibrated

    fun reset() {
        calibrated = false
    }

    fun setCellSize(size: Float) {
        cellSize = size.coerceIn(MIN_CELL, MAX_CELL)
    }

    fun getCellSize(): Float = cellSize

    /**
     * Melyik gomb fölött van most az ujj?
     *
     * A középponttól mért távolságot elosztjuk a cellamérettel, és a legközelebbi
     * egészre kerekítünk — így a cellák határa a szomszédok közti felezővonal.
     * A mátrixon kívülre csúszva null-t adunk (a szélső gomb "elengedése").
     */
    fun keyAt(x: Float, y: Float): MatrixKey? {
        if (!calibrated) return null
        val col = ((x - centerX) / cellSize).roundToInt()
        val row = ((y - centerY) / cellSize).roundToInt()
        // Kis ráhagyás: a mátrixon épphogy kívülre csúszva még a szélső gombot adjuk.
        val clampedCol = col.coerceIn(-1, 1)
        val clampedRow = row.coerceIn(-1, 2)
        // Ha nagyon messze csúszott (két cellányira a rácson kívül), nincs gomb.
        if (col < -2 || col > 2 || row < -2 || row > 3) return null
        return MatrixKey.at(clampedCol, clampedRow)
    }

    companion object {
        /** Ujjnyi alapérték; a beállításokban változtatható. */
        const val DEFAULT_CELL_DP = 56f
        const val MIN_CELL = 30f
        const val MAX_CELL = 200f
    }
}
