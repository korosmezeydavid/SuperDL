package com.superdl.launcher.games.poker

import com.superdl.launcher.games.cards.PlayingCard
import com.superdl.launcher.games.cards.Rank
import com.superdl.launcher.games.cards.Suit

enum class HandRank(val labelHu: String, val strength: Int) {
    HIGH_CARD("magas lap", 1),
    PAIR("pár", 2),
    TWO_PAIR("két pár", 3),
    THREE_OF_A_KIND("drill", 4),
    STRAIGHT("sor", 5),
    FLUSH("flös", 6),
    FULL_HOUSE("full", 7),
    FOUR_OF_A_KIND("póker", 8),
    STRAIGHT_FLUSH("színsor", 9),
    ROYAL_FLUSH("royal flös", 10)
}

data class EvaluatedHand(
    val rank: HandRank,
    val tiebreak: List<Int>,
    val label: String
) : Comparable<EvaluatedHand> {
    override fun compareTo(other: EvaluatedHand): Int {
        if (rank.strength != other.rank.strength) return rank.strength - other.rank.strength
        tiebreak.forEachIndexed { i, value ->
            val otherValue = other.tiebreak.getOrElse(i) { 0 }
            if (value != otherValue) return value - otherValue
        }
        return 0
    }
}

object PokerHandEvaluator {

    fun evaluate(cards: List<PlayingCard>): EvaluatedHand {
        require(cards.size == 5) { "Pontosan 5 lap kell." }
        val ranks = cards.map { it.rank.value }.sortedDescending()
        val rankCounts = ranks.groupingBy { it }.eachCount()
        val counts = rankCounts.values.sortedDescending()
        val isFlush = cards.map { it.suit }.distinct().size == 1
        val straightHigh = straightHighValue(ranks)
        val isStraight = straightHigh != null

        if (isFlush && isStraight) {
            val rank = if (straightHigh == 14) HandRank.ROYAL_FLUSH else HandRank.STRAIGHT_FLUSH
            return EvaluatedHand(rank, listOf(straightHigh!!), rank.labelHu)
        }
        if (counts == listOf(4, 1)) {
            val quad = rankCounts.entries.first { it.value == 4 }.key
            val kicker = rankCounts.entries.first { it.value == 1 }.key
            return EvaluatedHand(HandRank.FOUR_OF_A_KIND, listOf(quad, kicker), HandRank.FOUR_OF_A_KIND.labelHu)
        }
        if (counts == listOf(3, 2)) {
            val triple = rankCounts.entries.first { it.value == 3 }.key
            val pair = rankCounts.entries.first { it.value == 2 }.key
            return EvaluatedHand(HandRank.FULL_HOUSE, listOf(triple, pair), HandRank.FULL_HOUSE.labelHu)
        }
        if (isFlush) {
            return EvaluatedHand(HandRank.FLUSH, ranks, HandRank.FLUSH.labelHu)
        }
        if (isStraight) {
            return EvaluatedHand(HandRank.STRAIGHT, listOf(straightHigh!!), HandRank.STRAIGHT.labelHu)
        }
        if (counts == listOf(3, 1, 1)) {
            val triple = rankCounts.entries.first { it.value == 3 }.key
            val kickers = rankCounts.filter { it.value == 1 }.keys.sortedDescending()
            return EvaluatedHand(HandRank.THREE_OF_A_KIND, listOf(triple) + kickers, HandRank.THREE_OF_A_KIND.labelHu)
        }
        if (counts == listOf(2, 2, 1)) {
            val pairs = rankCounts.filter { it.value == 2 }.keys.sortedDescending()
            val kicker = rankCounts.entries.first { it.value == 1 }.key
            return EvaluatedHand(HandRank.TWO_PAIR, pairs + kicker, HandRank.TWO_PAIR.labelHu)
        }
        if (counts == listOf(2, 1, 1, 1)) {
            val pair = rankCounts.entries.first { it.value == 2 }.key
            val kickers = rankCounts.filter { it.value == 1 }.keys.sortedDescending()
            return EvaluatedHand(HandRank.PAIR, listOf(pair) + kickers, HandRank.PAIR.labelHu)
        }
        return EvaluatedHand(HandRank.HIGH_CARD, ranks, HandRank.HIGH_CARD.labelHu)
    }

    private fun straightHighValue(ranks: List<Int>): Int? {
        val unique = ranks.distinct().sortedDescending()
        if (unique.size != 5) return null
        if (unique.first() - unique.last() == 4) return unique.first()
        // A-2-3-4-5 wheel
        if (unique == listOf(14, 5, 4, 3, 2)) return 5
        return null
    }
}