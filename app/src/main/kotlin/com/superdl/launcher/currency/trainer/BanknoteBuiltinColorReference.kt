package com.superdl.launcher.currency.trainer

import android.graphics.Bitmap
import android.graphics.Color

/**
 * TANÍTÁS NÉLKÜLI felismerés: a magyar forint-címletek beépített, jellemző
 * alapszíne alapján. Így a felhasználó AZONNAL próbálkozhat, mielőtt egyetlen
 * saját fotót is készítene — a saját tanítás ezt CSAK pontosítja.
 *
 * A jellemző Hue-tartományokat a bankjegyek domináns alapszínéből vezetjük le
 * (HSV, 0..360°). Ezek közelítő értékek — a saját tanítás (BanknoteTrainedMatcher)
 * felülírja/pontosítja őket, ha van rá profil.
 *
 * Fontos: a felismerés a DOMINÁNS Hue-t nézi (a legtöbb színes pixel hova esik),
 * nem az OCR-t — az OCR csak megerősít (a hibrid felismerőben).
 */
object BanknoteBuiltinColorReference {

    /**
     * Egy címlet beépített szín-jellemzője: a Hue középértéke és megengedett
     * távolsága (fokban). A magyar sorozat alapszínei:
     *   500   – barnás-vöröses  (~15°)
     *   1000  – kékes           (~205°)
     *   2000  – barnás-drapp    (~30°)
     *   5000  – zöld            (~110°)
     *   10000 – rózsaszín-lila  (~320°)
     *   20000 – zöldes-drapp    (~75°)
     */
    data class ColorRef(
        val denomination: String,
        val label: String,
        val hueCenter: Float,
        val hueTolerance: Float
    )

    /**
     * Magyar forint (2014+ sorozat) HSV Hue középpontok és tűrések.
     *
     * A tűréseket ÚGY állítottuk be, hogy a sávok SEHOL NE FEDJENEK ÁT
     * (lásd [validateNoOverlap]). Korábban két veszélyes átfedés volt:
     *   - 500 (12°±14 = 358..26) és 2000 (36°±18 = 18..54)  -> 18..26 közös
     *   - 20000 (75°±20 = 55..95) és 5000 (108°±30 = 78..138) -> 78..95 közös
     * Az 5000/20000 átfedés a legveszélyesebb: NÉGYSZERES tévedés.
     *
     * A felhasználó VALÓS mért értékei (éles teszt naplója) mind a sávon belül
     * maradnak:  500: 7-19° | 1000: 195-202° | 2000: 29-44° | 5000: 108° |
     *            10000: 298-335°
     *
     * Az így keletkező RÉSEK (két sáv közti holt zóna) szándékosak: ha a mért
     * szín oda esik, egyik címlet sem kap pontot -> a rendszer HALLGAT, és
     * megvárja az OCR-t. Inkább nem mond semmit, mint hogy tévedjen.
     */
    val REFERENCES: List<ColorRef> = listOf(
        ColorRef("500", "500 forint", 13f, 11f),      // 2..24
        ColorRef("2000", "2000 forint", 37f, 11f),    // 26..48
        ColorRef("20000", "20000 forint", 72f, 12f),  // 60..84
        ColorRef("5000", "5000 forint", 110f, 18f),   // 92..128
        ColorRef("1000", "1000 forint", 200f, 20f),   // 180..220
        ColorRef("10000", "10000 forint", 316f, 26f), // 290..342
    )

    /**
     * Fejlesztői védőháló: ellenőrzi, hogy a fenti sávok nem fednek-e át.
     * Átfedés = két címlet ugyanarra a színre kaphat pontot, ami téves
     * azonosításhoz vezethet. Naplóz, ha bajt talál.
     *
     * @return az átfedő párok leírása (üres lista = rendben)
     */
    fun validateNoOverlap(): List<String> {
        val problems = mutableListOf<String>()
        for (i in REFERENCES.indices) {
            for (j in i + 1 until REFERENCES.size) {
                val a = REFERENCES[i]
                val b = REFERENCES[j]
                val centerDist = hueDistance(a.hueCenter, b.hueCenter)
                val needed = a.hueTolerance + b.hueTolerance
                if (centerDist < needed) {
                    val overlap = needed - centerDist
                    problems.add(
                        "${a.denomination} es ${b.denomination} savja ${"%.0f".format(overlap)} fokkal ATFED"
                    )
                }
            }
        }
        if (problems.isNotEmpty()) {
            android.util.Log.e("SDL_CASH", "SZIN-SAV ATFEDES: ${problems.joinToString("; ")}")
        }
        return problems
    }

    // A színes pixelek küszöbei (a hallucináció-kapuval összhangban).
    private const val MIN_SATURATION = 0.18f
    private const val MIN_VALUE = 0.12f
    private const val MAX_VALUE = 0.97f
    private const val SAMPLE_SIZE = 64

    data class BuiltinResult(
        val denomination: String,
        val label: String,
        val confidence: Float
    )

    /**
     * A domináns Hue kiszámítása (a színes pixelek súlyozott átlaga körkörösen).
     * Null, ha nincs elég színes pixel (nincs bankjegy).
     */
    fun dominantHue(bitmap: Bitmap): Float? {
        if (bitmap.isRecycled) return null
        val scaled = Bitmap.createScaledBitmap(bitmap, SAMPLE_SIZE, SAMPLE_SIZE, true)
        return try {
            val pixels = IntArray(SAMPLE_SIZE * SAMPLE_SIZE)
            scaled.getPixels(pixels, 0, SAMPLE_SIZE, 0, 0, SAMPLE_SIZE, SAMPLE_SIZE)
            val hsv = FloatArray(3)
            // Körkörös átlag: a Hue szög, ezért vektorösszegzéssel átlagolunk.
            var sumSin = 0.0
            var sumCos = 0.0
            var count = 0
            for (pixel in pixels) {
                Color.colorToHSV(pixel, hsv)
                if (hsv[1] < MIN_SATURATION || hsv[2] < MIN_VALUE || hsv[2] > MAX_VALUE) continue
                val rad = Math.toRadians(hsv[0].toDouble())
                sumSin += Math.sin(rad)
                sumCos += Math.cos(rad)
                count++
            }
            if (count < pixels.size * 0.25) return null  // szín-kapu: kevés szín -> nincs bankjegy
            var deg = Math.toDegrees(Math.atan2(sumSin, sumCos)).toFloat()
            if (deg < 0) deg += 360f
            deg
        } catch (_: Exception) {
            null
        } finally {
            if (scaled !== bitmap) scaled.recycle()
        }
    }

    /** Körkörös Hue-távolság (0..180). */
    private fun hueDistance(a: Float, b: Float): Float {
        val d = Math.abs(a - b) % 360f
        return if (d > 180f) 360f - d else d
    }

    /**
     * Címlet-tipp a domináns szín alapján, tanítás nélkül. Null, ha nincs
     * bankjegy vagy a szín egyik referenciához sem áll elég közel.
     */
    fun recognize(bitmap: Bitmap): BuiltinResult? {
        val hue = dominantHue(bitmap) ?: return null
        val scored = REFERENCES
            .map { ref ->
                val dist = hueDistance(hue, ref.hueCenter)
                // A tolerancián belül lineáris pontszám: közép=1.0, szél=0.
                val score = (1f - dist / ref.hueTolerance).coerceAtLeast(0f)
                ref to score
            }
            .sortedByDescending { it.second }

        val best = scored.first()
        // DIAGNOSZTIKA: a mért domináns Hue és a legjobb tipp — a hangoláshoz.
        android.util.Log.i(
            "SDL_CASH",
            "Hue=${"%.0f".format(hue)}° -> ${best.first.denomination} " +
                "(pont=${"%.2f".format(best.second)}, 2.=${"%.2f".format(scored.getOrNull(1)?.second ?: 0f)})"
        )
        if (best.second <= 0f) return null

        // Csak MAGABIZTOS mérés adjon eredményt. A napló szerint a téves
        // villanások (pl. a 10000 szélső pixelei "500"-ként) mind alacsony
        // pontszámúak (0.1-0.4), a valódi találatok 0.6-1.0 közöttiek. A 0.5-ös
        // küszöb kiszűri a bizonytalan, ugráló méréseket -> stabilabb bemondás.
        if (best.second < 0.5f) return null

        // Biztos-e? A második legjobbhoz képest legyen érdemi előny.
        val second = scored.getOrNull(1)?.second ?: 0f
        if (best.second - second < 0.12f && best.second < 0.6f) return null

        return BuiltinResult(best.first.denomination, best.first.label, best.second)
    }
}
