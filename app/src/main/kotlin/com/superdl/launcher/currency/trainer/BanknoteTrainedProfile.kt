package com.superdl.launcher.currency.trainer

/**
 * Egy betanított címlet profilja: a felhasználó saját fotóiból épül.
 *
 * Minden fotó két ujjlenyomatot ad: egy fény-tűrő szín-hisztogramot
 * (BanknoteColorFingerprint) és egy perceptuális hash-t (a mintázathoz).
 * A kettő együtt azonosít: a szín a fő jel, a hash a megerősítés.
 *
 * A denomination a gépi kulcs (pl. "500"), a label a kimondott szöveg
 * (pl. "500 forint").
 */
data class BanknoteTrainedProfile(
    val id: String,
    val denomination: String,
    val label: String,
    val createdAt: Long,
    val colorHistograms: List<FloatArray>,
    val visualHashes: List<String>,
    val referenceImagePaths: List<String> = emptyList()
) {
    val sampleCount: Int get() = colorHistograms.size
}

/**
 * Egy elkészült tanító-fotó nyers eredménye (mentés előtt).
 */
data class BanknoteCaptureDraft(
    val colorHistogram: FloatArray,
    val visualHash: String,
    val thumbnailPath: String?
)
