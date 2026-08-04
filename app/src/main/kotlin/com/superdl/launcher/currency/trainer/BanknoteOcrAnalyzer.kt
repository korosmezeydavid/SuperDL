package com.superdl.launcher.currency.trainer

/**
 * A bankjegyen lévő nagy, kontrasztos címletszám kiolvasása OCR-szövegből.
 *
 * A szerepe MEGERŐSÍTŐ, nem elsődleges: a szín dönt (az stabil), az OCR csak
 * finomít vagy feloldja a szín-holtversenyt. Ha az OCR semmit nem lát (gyűrött,
 * takart, ferde szám), az nem baj — nem blokkol.
 *
 * A magyar bankjegyeken több szám is van (évszám 1999-2020 körül, sorozatszám),
 * ezért CSAK a hat valódi címletértéket fogadjuk el, és a hosszabb egyezést
 * részesítjük előnyben (5000 erősebb, mint az 500, ha mindkettő illeszkedne).
 */
object BanknoteOcrAnalyzer {

    // A hat érvényes címlet, HOSSZ szerint csökkenő sorrendben — így a "20000"
    // előbb illeszkedik, mint a "2000", és az "5000" előbb, mint az "500".
    private val DENOMINATIONS = listOf("20000", "10000", "5000", "2000", "1000", "500")

    // Évszám-tartomány, amit KI kell zárni (a bankjegyeken nyomtatott évszámok).
    private val YEAR_REGEX = Regex("(19|20)\\d{2}")

    /**
     * A szövegből kinyeri a legvalószínűbb címletet, vagy null-t, ha nincs
     * egyértelmű címletszám.
     */
    fun extractDenomination(ocrText: String): String? {
        if (ocrText.isBlank()) return null

        // Csak a számjegyeket tartjuk meg, a többi karaktert szóközzé tesszük,
        // hogy a "10 000" és "10.000" formák is "10000"-ként álljanak össze.
        val digitsOnly = ocrText
            .replace(Regex("[\\s.,]"), "")       // szóköz, pont, vessző eltávolítása
            .replace(Regex("[^0-9]"), " ")        // minden más -> szóköz-határ

        // Az évszámokat kimaszkoljuk, hogy pl. a "2000" évszám ne tűnjön címletnek.
        // (Óvatosan: a 2000 Ft címlet is létezik — ezért csak a 4-jegyű, önálló,
        //  év-tartományba eső számokat maszkoljuk, ha NEM követi/előzi címlet-kontextus.
        //  Egyszerűbb és biztonságosabb: a teljes digit-folyamban keresünk címletet.)

        val candidates = mutableListOf<Pair<String, Int>>() // címlet -> előfordulás
        for (denom in DENOMINATIONS) {
            var idx = digitsOnly.indexOf(denom)
            var count = 0
            while (idx >= 0) {
                // Ellenőrizzük, hogy ez ne egy HOSSZABB szám része legyen
                // (pl. "500" a "5000"-ben) — a bal/jobb szomszéd ne legyen számjegy.
                val leftOk = idx == 0 || !digitsOnly[idx - 1].isDigit()
                val rightIdx = idx + denom.length
                val rightOk = rightIdx >= digitsOnly.length || !digitsOnly[rightIdx].isDigit()
                if (leftOk && rightOk) count++
                idx = digitsOnly.indexOf(denom, idx + 1)
            }
            if (count > 0) candidates.add(denom to count)
        }

        if (candidates.isEmpty()) return null

        // A legtöbbször, önállóan előforduló címlet nyer; azonos előfordulásnál
        // a hosszabb (nagyobb) érték, mert a bankjegyen a fő címlet többször,
        // nagy méretben szerepel.
        return candidates
            .sortedWith(
                compareByDescending<Pair<String, Int>> { it.second }
                    .thenByDescending { it.first.length }
            )
            .first()
            .first
    }
}
