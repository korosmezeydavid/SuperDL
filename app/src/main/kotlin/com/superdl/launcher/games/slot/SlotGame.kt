package com.superdl.launcher.games.slot

import kotlin.random.Random

class SlotGame(
    private val random: Random = Random.Default,
    startCredits: Int = 100
) {
    data class SpinResult(
        val reels: List<SlotSymbol>,
        val winAmount: Int,
        val message: String,
        val isJackpot: Boolean,
        val isWin: Boolean
    )

    data class State(
        val credits: Int,
        val bet: Int,
        val lastResult: SpinResult?,
        val totalSpins: Int,
        val totalWon: Int
    )

    val betOptions = listOf(1, 5, 10, 25, 50)
    private var betIndex = 1
    private var credits = startCredits
    private var lastResult: SpinResult? = null
    private var totalSpins = 0
    private var totalWon = 0

    private val reelSymbols = listOf(
        SlotSymbol.CHERRY, SlotSymbol.CHERRY, SlotSymbol.CHERRY,
        SlotSymbol.LEMON, SlotSymbol.LEMON,
        SlotSymbol.PLUM, SlotSymbol.PLUM,
        SlotSymbol.BELL,
        SlotSymbol.STAR,
        SlotSymbol.DIAMOND,
        SlotSymbol.SEVEN
    )

    fun currentState(): State = State(
        credits = credits,
        bet = currentBet(),
        lastResult = lastResult,
        totalSpins = totalSpins,
        totalWon = totalWon
    )

    fun currentBet(): Int = betOptions[betIndex]

    fun changeBet(delta: Int): String {
        betIndex = (betIndex + delta + betOptions.size) % betOptions.size
        return "Tét: ${currentBet()} zseton."
    }

    fun canSpin(): Boolean = credits >= currentBet()

    fun spin(): SpinResult {
        val bet = currentBet()
        if (credits < bet) {
            return SpinResult(
                reels = lastResult?.reels ?: listOf(SlotSymbol.CHERRY, SlotSymbol.LEMON, SlotSymbol.PLUM),
                winAmount = 0,
                message = "Nincs elég zseton. Tét: $bet, egyenleg: $credits.",
                isJackpot = false,
                isWin = false
            ).also { lastResult = it }
        }
        credits -= bet
        totalSpins++

        val reels = List(3) { reelSymbols.random(random) }
        val payout = evaluatePayout(reels, bet)
        credits += payout
        totalWon += payout

        val isJackpot = payout >= bet * SlotSymbol.SEVEN.tripleMultiplier
        val isWin = payout > 0
        val message = buildString {
            append("Eredmény: ${reels.joinToString(", ") { it.labelHu }}. ")
            if (payout > 0) {
                append("Nyertél $payout zsetont! ")
                if (isJackpot) append("Jackpot! ")
            } else {
                append("Most nem nyert. ")
            }
            append("Egyenleg: $credits zseton.")
        }
        return SpinResult(
            reels = reels,
            winAmount = payout,
            message = message,
            isJackpot = isJackpot,
            isWin = isWin
        ).also { lastResult = it }
    }

    private fun evaluatePayout(reels: List<SlotSymbol>, bet: Int): Int {
        val counts = reels.groupingBy { it }.eachCount()
        val triple = counts.entries.firstOrNull { it.value == 3 }
        if (triple != null) {
            return bet * triple.key.tripleMultiplier
        }
        val pair = counts.entries.firstOrNull { it.value == 2 }
        if (pair != null) {
            return bet * 2
        }
        if (reels.count { it == SlotSymbol.CHERRY } >= 2) {
            return bet
        }
        return 0
    }

    fun addBonusCredits(amount: Int = 50): String {
        credits += amount
        return "Kaptál $amount bónusz zsetont. Egyenleg: $credits."
    }
}