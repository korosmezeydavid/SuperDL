package com.superdl.launcher.games.cards

enum class Suit(val labelHu: String) {
    HEARTS("kőr"),
    DIAMONDS("káró"),
    CLUBS("treff"),
    SPADES("pikk")
}

enum class Rank(val labelHu: String, val value: Int) {
    TWO("kettő", 2),
    THREE("három", 3),
    FOUR("négy", 4),
    FIVE("öt", 5),
    SIX("hat", 6),
    SEVEN("hét", 7),
    EIGHT("nyolc", 8),
    NINE("kilenc", 9),
    TEN("tíz", 10),
    JACK("bubi", 10),
    QUEEN("dáma", 10),
    KING("király", 10),
    ACE("ász", 11)
}

data class PlayingCard(val suit: Suit, val rank: Rank) {
    fun speak(): String = "${suit.labelHu} ${rank.labelHu}"

    fun blackjackValue(): Int = when (rank) {
        Rank.ACE -> 11
        else -> rank.value
    }
}

object PlayingDeck {
    fun createShuffled(): ArrayDeque<PlayingCard> {
        val cards = mutableListOf<PlayingCard>()
        for (suit in Suit.entries) {
            for (rank in Rank.entries) {
                cards += PlayingCard(suit, rank)
            }
        }
        return ArrayDeque(cards.shuffled())
    }

    fun draw(deck: ArrayDeque<PlayingCard>, count: Int = 1): List<PlayingCard> {
        val drawn = mutableListOf<PlayingCard>()
        repeat(count) {
            if (deck.isNotEmpty()) drawn += deck.removeFirst()
        }
        return drawn
    }
}

fun List<PlayingCard>.blackjackTotal(): Int {
    var total = sumOf { it.blackjackValue() }
    var aces = count { it.rank == Rank.ACE }
    while (total > 21 && aces > 0) {
        total -= 10
        aces--
    }
    return total
}

fun List<PlayingCard>.speakHand(): String =
    joinToString(", ") { it.speak() }