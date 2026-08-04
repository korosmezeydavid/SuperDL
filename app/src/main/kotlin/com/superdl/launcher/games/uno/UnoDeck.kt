package com.superdl.launcher.games.uno

import kotlin.random.Random

object UnoDeck {

    fun createShuffled(random: Random = Random.Default): ArrayDeque<UnoCard> {
        val cards = mutableListOf<UnoCard>()
        for (color in UnoColor.PLAY_COLORS) {
            cards += UnoCard(color, UnoKind.NUMBER, 0)
            for (number in 1..9) {
                cards += UnoCard(color, UnoKind.NUMBER, number)
                cards += UnoCard(color, UnoKind.NUMBER, number)
            }
            repeat(2) {
                cards += UnoCard(color, UnoKind.SKIP)
                cards += UnoCard(color, UnoKind.REVERSE)
                cards += UnoCard(color, UnoKind.DRAW_TWO)
            }
        }
        repeat(4) {
            cards += UnoCard(UnoColor.WILD, UnoKind.WILD)
            cards += UnoCard(UnoColor.WILD, UnoKind.WILD_DRAW_FOUR)
        }
        cards.shuffle(random)
        return ArrayDeque(cards)
    }

    fun draw(deck: ArrayDeque<UnoCard>, count: Int = 1): List<UnoCard> {
        val drawn = mutableListOf<UnoCard>()
        repeat(count) {
            if (deck.isEmpty()) return drawn
            drawn += deck.removeFirst()
        }
        return drawn
    }
}