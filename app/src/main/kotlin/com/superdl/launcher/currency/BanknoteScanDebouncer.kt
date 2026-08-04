package com.superdl.launcher.currency

/**
 * TTS lifecycle debouncer: egy bankjegy-jelenlét alatt EGYSZER szólal meg.
 *
 * MIÉRT: a régi logika cooldown után újra bemondta ugyanezt a címletet
 * (hurkolás / flicker). Vak felhasználónál ez zavaró és veszélyes.
 *
 * Szabályok:
 *  - Bill belép → első stabil eredmény: Announce + entry beep
 *  - Ugyanaz a címlet, amíg a bill bent van → soha nem ismétel
 *  - Más címlet (csere a keretben) → új Announce (beep nélkül), ha stabil
 *  - Bill kikerül (absence) → session reset, legközelebb újra bemondható
 */
class BanknoteScanDebouncer(
    private val absenceFramesRequired: Int = 6
) {
    private var billInFrame = false
    private var absenceStreak = 0
    private var lastAnnouncedDenomination: BanknoteDenomination? = null
    private var lastAnnouncedAt: Long = 0L

    fun onAbsentFrame(): BillPresenceEvent {
        if (!billInFrame) {
            absenceStreak = 0
            return BillPresenceEvent.NONE
        }
        absenceStreak++
        if (absenceStreak >= absenceFramesRequired) {
            billInFrame = false
            absenceStreak = 0
            lastAnnouncedDenomination = null
            lastAnnouncedAt = 0L
            return BillPresenceEvent.REMOVED
        }
        return BillPresenceEvent.STILL_SCANNING
    }

    fun onDetected(
        result: BanknoteClassificationResult,
        now: Long = System.currentTimeMillis()
    ): ScanDecision {
        if (!result.isReliable(strictColor = false)) {
            return when (onAbsentFrame()) {
                BillPresenceEvent.REMOVED -> ScanDecision.BillRemoved
                else -> ScanDecision.Ignored
            }
        }

        absenceStreak = 0
        val entered = !billInFrame
        billInFrame = true

        // Ugyanaz a címlet már elhangzott ebben a jelenlét-sessionben → csend.
        if (result.denomination == lastAnnouncedDenomination) {
            return ScanDecision.Ignored
        }

        if (entered) {
            return ScanDecision.Announce(result, playEntryBeep = true)
        }

        // Más címlet a keretben (csere) — egyszer bemondjuk.
        return ScanDecision.Announce(result, playEntryBeep = false)
    }

    fun markAnnounced(denomination: BanknoteDenomination, now: Long = System.currentTimeMillis()) {
        lastAnnouncedDenomination = denomination
        lastAnnouncedAt = now
        billInFrame = true
    }

    fun reset() {
        billInFrame = false
        absenceStreak = 0
        lastAnnouncedDenomination = null
        lastAnnouncedAt = 0L
    }

    enum class BillPresenceEvent {
        NONE,
        STILL_SCANNING,
        REMOVED
    }

    sealed class ScanDecision {
        data object Ignored : ScanDecision()
        data object BillRemoved : ScanDecision()
        data class Announce(
            val result: BanknoteClassificationResult,
            val playEntryBeep: Boolean
        ) : ScanDecision()
    }
}
