package com.superdl.launcher.currency.trainer

import android.graphics.Bitmap
import com.superdl.launcher.locationwatch.VisualFingerprint

/**
 * A betanított bankjegy-profilok alapján felismeri a címletet egy kameraképből.
 *
 * A felismerés rétegei (a stratégia szerint):
 *  1. SZÍN-KAPU: ha a kép fakó (kevés színes pixel), nincs bankjegy → null.
 *     Ez akadályozza meg a "behallucinálást" üres asztalra/kézre.
 *  2. SZÍN-EGYEZÉS: a kamerakép Hue-hisztogramját minden profil ellen mérjük
 *     (fény-tűrő). A legjobb egyezés a jelölt.
 *  3. HASH-MEGERŐSÍTÉS: a perceptuális hash finomítja a döntést — ha két
 *     címlet színe közel áll, a mintázat (hash) dönt.
 *
 * Csak akkor ad címletet, ha a legjobb egyezés elér egy küszöböt ÉS érdemben
 * jobb a második legjobbnál (nincs "holtverseny"). Különben null (hallgat).
 */
object BanknoteTrainedMatcher {

    // Ennyi színes pixel kell legalább, hogy egyáltalán bankjegynek tekintsük.
    private const val MIN_COLORFUL_FRACTION = 0.25f

    // A szín-egyezésnek legalább ennyinek kell lennie (0..1).
    private const val MIN_COLOR_SIMILARITY = 0.55f

    // A legjobb és második legjobb címlet közti minimális előny (biztos döntés).
    private const val MIN_MARGIN = 0.08f

    data class Result(
        val denomination: String,
        val label: String,
        val confidence: Float
    )

    /**
     * Felismerés. Null, ha nincs betanított profil, nincs bankjegy a képen,
     * vagy a döntés bizonytalan.
     */
    fun recognize(
        profiles: List<BanknoteTrainedProfile>,
        bitmap: Bitmap
    ): Result? {
        if (profiles.isEmpty() || bitmap.isRecycled) return null

        // 1. réteg — szín-kapu (van-e egyáltalán bankjegy?)
        if (BanknoteColorFingerprint.colorfulFraction(bitmap) < MIN_COLORFUL_FRACTION) {
            return null
        }

        val candidateHist = BanknoteColorFingerprint.compute(bitmap)
        val candidateHash = VisualFingerprint.compute(bitmap)

        // 2-3. réteg — minden profilra egy összevont pontszám.
        // A szín a fő jel (75%), a hash a megerősítés (25%).
        val scored = profiles
            .filter { it.colorHistograms.isNotEmpty() }
            .map { profile ->
                val colorScore = BanknoteColorFingerprint.bestSimilarity(
                    profile.colorHistograms, candidateHist
                )
                val hashScore = if (profile.visualHashes.isNotEmpty()) {
                    VisualFingerprint.bestSimilarity(profile.visualHashes, candidateHash)
                } else 0f
                val combined = colorScore * 0.75f + hashScore * 0.25f
                Triple(profile, colorScore, combined)
            }
            .sortedByDescending { it.third }

        if (scored.isEmpty()) return null

        val best = scored[0]
        val bestColorScore = best.second
        val bestCombined = best.third

        // A szín-egyezésnek el kell érnie a küszöböt.
        if (bestColorScore < MIN_COLOR_SIMILARITY) return null

        // Biztos-e a döntés? A másodikhoz képest legyen érdemi előny.
        val secondCombined = scored.getOrNull(1)?.third ?: 0f
        if (bestCombined - secondCombined < MIN_MARGIN && scored.size > 1) {
            return null
        }

        return Result(
            denomination = best.first.denomination,
            label = best.first.label,
            confidence = bestCombined
        )
    }
}
