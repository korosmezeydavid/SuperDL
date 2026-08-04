package com.superdl.launcher.games.millebornes

import kotlin.random.Random

object MilleBornesDeck {

    fun createShuffled(random: Random = Random.Default): ArrayDeque<MilleBornesCard> {
        val cards = buildList {
            repeat(10) { add(MilleBornesCard.Distance(25)) }
            repeat(10) { add(MilleBornesCard.Distance(50)) }
            repeat(10) { add(MilleBornesCard.Distance(75)) }
            repeat(12) { add(MilleBornesCard.Distance(100)) }
            repeat(4) { add(MilleBornesCard.Distance(200)) }
            repeat(5) { add(MilleBornesCard.Stop) }
            repeat(4) { add(MilleBornesCard.SpeedLimit) }
            repeat(3) { add(MilleBornesCard.OutOfGas) }
            repeat(3) { add(MilleBornesCard.FlatTire) }
            repeat(3) { add(MilleBornesCard.Accident) }
            repeat(14) { add(MilleBornesCard.Roll) }
            repeat(6) { add(MilleBornesCard.EndOfLimit) }
            repeat(6) { add(MilleBornesCard.Gasoline) }
            repeat(6) { add(MilleBornesCard.SpareTire) }
            repeat(6) { add(MilleBornesCard.Repairs) }
            SafetyType.entries.forEach { type ->
                add(MilleBornesCard.Safety(type))
            }
        }
        return ArrayDeque(cards.shuffled(random))
    }

    fun draw(deck: ArrayDeque<MilleBornesCard>, count: Int): List<MilleBornesCard> {
        val drawn = mutableListOf<MilleBornesCard>()
        repeat(count) {
            val card = deck.removeFirstOrNull() ?: return drawn
            drawn += card
        }
        return drawn
    }
}