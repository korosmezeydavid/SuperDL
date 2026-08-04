package com.superdl.launcher.games.poker

import com.superdl.launcher.games.BotNames
import com.superdl.launcher.games.cards.PlayingCard
import com.superdl.launcher.games.cards.PlayingDeck
import com.superdl.launcher.games.cards.speakHand
import kotlin.random.Random

class PokerGame(private val random: Random = Random.Default) {

    data class PlayerState(
        val name: String,
        val isHuman: Boolean,
        val hand: MutableList<PlayingCard> = mutableListOf(),
        var discardCount: Int = -1
    )

    enum class Phase { DEALING, DISCARD, SHOWDOWN, FINISHED }

    data class State(
        val players: List<PlayerState>,
        val deck: ArrayDeque<PlayingCard>,
        val currentPlayerIndex: Int,
        val phase: Phase,
        val winner: String?,
        val lastAction: String
    )

    private var state: State? = null

    fun startNewRound(botCount: Int = 3): State {
        val deck = PlayingDeck.createShuffled()
        val botNames = BotNames.pick(botCount, random)
        val players = buildList {
            add(PlayerState("Te", isHuman = true))
            botNames.forEach { name -> add(PlayerState(name, isHuman = false)) }
        }.map { player ->
            player.copy(hand = PlayingDeck.draw(deck, 5).toMutableList(), discardCount = -1)
        }

        state = State(
            players = players,
            deck = deck,
            currentPlayerIndex = 0,
            phase = Phase.DISCARD,
            winner = null,
            lastAction = "Öt lapot kaptál. Válaszd ki, hány lapot cserélsz."
        )
        return state!!
    }

    fun currentState(): State? = state

    fun humanHand(): List<PlayingCard> =
        state?.players?.firstOrNull { it.isHuman }?.hand.orEmpty()

    fun humanDiscard(count: Int): String {
        val s = state ?: return "Nincs aktív játék."
        if (s.phase != Phase.DISCARD || s.currentPlayerIndex != 0) return "Most nem a te köröd."
        return applyDiscard(s, 0, count)
    }

    fun runBotsUntilHuman(): String {
        val s = state ?: return ""
        if (s.phase != Phase.DISCARD) return s.lastAction
        val messages = StringBuilder()
        var guard = 0
        while (guard < 12) {
            guard++
            val current = state ?: break
            if (current.phase != Phase.DISCARD) break
            if (current.currentPlayerIndex == 0) {
                messages.append(" Te jössz.")
                break
            }
            val idx = current.currentPlayerIndex
            val bot = current.players[idx]
            val discardCount = chooseBotDiscard(bot.hand)
            val msg = applyDiscard(current, idx, discardCount)
            messages.append(" ").append(msg)
        }
        return messages.toString().trim()
    }

    private fun chooseBotDiscard(hand: List<PlayingCard>): Int {
        val evaluated = PokerHandEvaluator.evaluate(hand)
        if (evaluated.rank.strength >= HandRank.THREE_OF_A_KIND.strength) return 0
        val rankCounts = hand.groupingBy { it.rank.value }.eachCount()
        val keptValues = rankCounts.filter { it.value >= 2 }.keys
        if (keptValues.isNotEmpty()) {
            return hand.count { it.rank.value !in keptValues }.coerceAtMost(3)
        }
        val suitCounts = hand.groupingBy { it.suit }.eachCount()
        val flushSuit = suitCounts.maxByOrNull { it.value }?.key
        if (flushSuit != null && suitCounts[flushSuit]!! >= 4) {
            return hand.count { it.suit != flushSuit }.coerceAtMost(3)
        }
        val sorted = hand.sortedByDescending { it.rank.value }
        val highCard = sorted.take(2).map { it.rank.value }.toSet()
        return hand.count { it.rank.value !in highCard }.coerceAtMost(3)
    }

    private fun applyDiscard(s: State, playerIndex: Int, count: Int): String {
        val players = s.players.toMutableList()
        val player = players[playerIndex]
        val safeCount = count.coerceIn(0, 5)
        val toRemove = player.hand.sortedBy { it.rank.value }.take(safeCount)
        player.hand.removeAll(toRemove.toSet())
        val drawn = PlayingDeck.draw(s.deck, safeCount)
        player.hand.addAll(drawn)
        player.discardCount = safeCount

        val action = if (safeCount == 0) {
            "${player.name} nem cserél lapot."
        } else {
            "${player.name} $safeCount lapot cserél."
        }

        var nextIndex = playerIndex + 1
        while (nextIndex < players.size && players[nextIndex].discardCount >= 0) {
            nextIndex++
        }

        if (nextIndex < players.size) {
            state = s.copy(players = players, currentPlayerIndex = nextIndex, lastAction = action)
            return state!!.lastAction + if (nextIndex == 0) "" else " " + runBotsUntilHuman()
        }
        return showdown(s.copy(players = players, lastAction = action))
    }

    private fun showdown(s: State): String {
        val results = s.players.map { player ->
            val evaluated = PokerHandEvaluator.evaluate(player.hand)
            player.name to evaluated
        }
        val best = results.maxByOrNull { it.second }!!
        val winners = results.filter { it.second == best.second }.map { it.first }
        val winnerText = winners.joinToString(", ")
        val details = results.joinToString(". ") { (name, eval) ->
            "$name: ${eval.label}, ${s.players.first { it.name == name }.hand.speakHand()}"
        }
        val action = "Mutatás. $details. Győztes: $winnerText, ${best.second.label}."
        state = s.copy(phase = Phase.FINISHED, currentPlayerIndex = 0, winner = winnerText, lastAction = action)
        return action
    }
}