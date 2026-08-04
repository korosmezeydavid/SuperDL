package com.superdl.launcher.screenreader

import android.graphics.Bitmap
import android.graphics.Color

/**
 * SZÍNFELISMERÉS a kurzor alatt.
 *
 * MIÉRT HASZNOS: a színnel nagyon sok információt közölnek az alkalmazások, és
 * ez a vak felhasználó elől teljesen rejtve marad. A hibaüzenet piros, a siker
 * zöld, az inaktív gomb szürke, a kijelölt sor kiemelt. Ezek nélkül csak a
 * szöveget hallod — de nem tudod, hogy figyelmeztetés-e vagy megerősítés.
 *
 * MŰKÖDÉS: az elem területéről mintát veszünk a képernyőképből, megkeressük a
 * leggyakoribb színt (a háttér) és a leginkább eltérőt (jellemzően a szöveg),
 * majd mindkettőt emberi néven mondjuk ki.
 */
object ScreenReaderColors {

    /** Egy felismert szín: neve és mennyire uralja a képet. */
    data class ColorReading(
        val backgroundName: String,
        val foregroundName: String,
        val hasContrast: Boolean
    ) {
        fun speak(): String = if (hasContrast) {
            "Háttér: $backgroundName. Szöveg vagy jelölés: $foregroundName."
        } else {
            "Egyszínű terület: $backgroundName."
        }
    }

    /**
     * A kép színeinek elemzése.
     * Ritkított mintavétellel dolgozunk (nem minden képpont), hogy gyors legyen.
     */
    fun analyze(bitmap: Bitmap): ColorReading {
        val step = maxOf(1, minOf(bitmap.width, bitmap.height) / 40)
        val counts = HashMap<Int, Int>()
        var total = 0

        var y = 0
        while (y < bitmap.height) {
            var x = 0
            while (x < bitmap.width) {
                val quantized = quantize(bitmap.getPixel(x, y))
                counts[quantized] = (counts[quantized] ?: 0) + 1
                total++
                x += step
            }
            y += step
        }
        if (total == 0) return ColorReading("ismeretlen", "ismeretlen", false)

        val sorted = counts.entries.sortedByDescending { it.value }
        val background = sorted.first().key

        // A "szöveg" az a gyakori szín, ami a LEGJOBBAN eltér a háttértől.
        val foreground = sorted
            .take(8)
            .filter { it.value > total / 50 }          // a nagyon ritkát kihagyjuk
            .maxByOrNull { distance(it.key, background) }
            ?.key ?: background

        val contrast = distance(foreground, background) > 90
        return ColorReading(nameOf(background), nameOf(foreground), contrast)
    }

    /** Színek durvítása, hogy az árnyalatok egy csoportba essenek. */
    private fun quantize(color: Int): Int {
        val r = (Color.red(color) / 32) * 32
        val g = (Color.green(color) / 32) * 32
        val b = (Color.blue(color) / 32) * 32
        return Color.rgb(r, g, b)
    }

    private fun distance(a: Int, b: Int): Int {
        val dr = Color.red(a) - Color.red(b)
        val dg = Color.green(a) - Color.green(b)
        val db = Color.blue(a) - Color.blue(b)
        return kotlin.math.sqrt((dr * dr + dg * dg + db * db).toDouble()).toInt()
    }

    /**
     * A szín MAGYAR NEVE.
     *
     * Nem a pontos árnyalat a cél, hanem a használható információ: a
     * felhasználónak az számít, hogy PIROS-e (figyelmeztetés) vagy ZÖLD
     * (rendben), nem az, hogy "középtelített cinóber".
     */
    fun nameOf(color: Int): String {
        val hsv = FloatArray(3)
        Color.colorToHSV(color, hsv)
        val hue = hsv[0]
        val sat = hsv[1]
        val value = hsv[2]

        // Előbb a szürkeárnyalatok — ezeknél a színezet nem mond semmit.
        if (sat < 0.12f) {
            return when {
                value < 0.12f -> "fekete"
                value < 0.32f -> "sötétszürke"
                value < 0.65f -> "szürke"
                value < 0.90f -> "világosszürke"
                else -> "fehér"
            }
        }
        if (value < 0.15f) return "majdnem fekete"

        val base = when {
            hue < 12f -> "piros"
            hue < 38f -> "narancssárga"
            hue < 68f -> "sárga"
            hue < 90f -> "sárgászöld"
            hue < 150f -> "zöld"
            hue < 190f -> "türkiz"
            hue < 250f -> "kék"
            hue < 285f -> "lila"
            hue < 330f -> "rózsaszín"
            else -> "piros"
        }
        // Barna: a sötét narancs valójában barnának látszik.
        if ((hue in 12f..45f) && value < 0.55f) return "barna"

        val shade = when {
            value < 0.40f -> "sötét"
            value > 0.85f && sat < 0.45f -> "világos"
            else -> ""
        }
        return (shade + base).trim()
    }
}
