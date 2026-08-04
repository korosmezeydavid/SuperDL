package com.superdl.launcher.currency

import com.superdl.launcher.currency.cascade.BanknoteCascadeConfig

/**
 * Multi-frame temporal consistency.
 *
 * Minimum [BanknoteCascadeConfig.TEMPORAL_REQUIRED] egymást követő azonos
 * megbízható eredmény kell a TTS megszólalása előtt — flicker és téves
 * villanások elkerülése.
 */
class BanknoteConsensusFilter(
    private val windowSize: Int = BanknoteCascadeConfig.TEMPORAL_WINDOW,
    private val requiredAgreements: Int = BanknoteCascadeConfig.TEMPORAL_REQUIRED
) {
    private val recent = ArrayDeque<BanknoteClassificationResult?>(windowSize)

    fun submit(
        frameDecision: BanknoteFrameGate.Decision,
        result: BanknoteClassificationResult?
    ): BanknoteClassificationResult? {
        val candidate = when {
            frameDecision.isEmptySlot -> null
            result == null -> null
            result.isReliable(strictColor = false) -> result
            else -> null
        }

        if (recent.size >= windowSize) recent.removeFirst()
        recent.addLast(candidate)

        if (recent.size < windowSize) return null

        // Szigorú: az ablak utolsó requiredAgreements eleme MIND ugyanaz a címlet
        // és nem null — nem elég a majority vote, ha közben null/más villan.
        val tail = recent.toList().takeLast(requiredAgreements)
        if (tail.any { it == null }) return null

        val denoms = tail.map { it!!.denomination }
        val winner = denoms.first()
        if (denoms.any { it != winner }) return null

        return tail
            .filterNotNull()
            .maxByOrNull { it.confidence }
    }

    fun reset() {
        recent.clear()
    }
}
