package com.superdl.launcher.games.blackjack

import com.superdl.launcher.games.BotNames
import com.superdl.launcher.games.cards.PlayingCard
import com.superdl.launcher.games.cards.PlayingDeck
import com.superdl.launcher.games.cards.blackjackTotal
import com.superdl.launcher.games.cards.speakHand
import kotlin.random.Random

class BlackjackGame(private val random: Random = Random.Default) {

    data class PlayerState(
        val name: String,
        val isHuman: Boolean,
        val hand: MutableList<PlayingCard> = mutableListOf(),
        var stood: Boolean = false,
        var busted: Boolean = false
    )

    enum class Phase { DEALING, PLAYER_TURN, DEALER_TURN, FINISHED }

    data class State(
        val players: List<PlayerState>,
        val dealer: PlayerState,
        val deck: ArrayDeque<PlayingCard>,
        val currentPlayerIndex: Int,
        val phase: Phase,
        val winners: List<String>,
        val lastAction: String
    )

    private var state: State? = null

    fun startNewRound(botCount: Int = 3): State {
        val deck = PlayingDeck.createShuffled()
        val dealerName = BotNames.pick(1, random).first() + " krupié"
        val botNames = BotNames.pick(botCount, random)
        val players = buildList {
            add(PlayerState("Te", isHuman = true))
            botNames.forEach { name -> add(PlayerState(name, isHuman = false)) }
        }.map { player ->
            player.copy(hand = PlayingDeck.draw(deck, 2).toMutableList())
        }
        val dealer = PlayerState(dealerName, isHuman = false, hand = PlayingDeck.draw(deck, 2).toMutableList())

        state = State(
            players = players,
            dealer = dealer,
            deck = deck,
            currentPlayerIndex = 0,
            phase = Phase.PLAYER_TURN,
            winners = emptyList(),
            lastAction = "Osztás kész. Te kezdesz."
        )
        return state!!
    }

    fun currentState(): State? = state

    fun humanHand(): List<PlayingCard> =
        state?.players?.firstOrNull { it.isHuman }?.hand.orEmpty()

    fun dealerVisibleCard(): PlayingCard? = state?.dealer?.hand?.firstOrNull()

    fun humanHit(): String {
        val s = state ?: return "Nincs aktív játék."
        if (s.phase != Phase.PLAYER_TURN || s.currentPlayerIndex != 0) return "Most nem a te köröd."
        return hitPlayer(s, 0)
    }

    fun humanStand(): String {
        val s = state ?: return "Nincs aktív játék."
        if (s.phase != Phase.PLAYER_TURN || s.currentPlayerIndex != 0) return "Most nem a te köröd."
        return standPlayer(s, 0)
    }

    fun runBotsUntilHuman(): String {
        val s = state ?: return ""
        if (s.phase != Phase.PLAYER_TURN) return s.lastAction
        val messages = StringBuilder()
        var guard = 0
        while (guard < 12) {
            guard++
            val current = state ?: break
            if (current.phase != Phase.PLAYER_TURN) break
            if (current.currentPlayerIndex == 0) {
                messages.append(" Te jössz.")
                break
            }
            val idx = current.currentPlayerIndex
            val bot = current.players[idx]
            val total = bot.hand.blackjackTotal()
            val msg = if (total < 17) hitPlayer(current, idx) else standPlayer(current, idx)
            messages.append(" ").append(msg)
        }
        return messages.toString().trim()
    }

    private fun hitPlayer(s: State, playerIndex: Int): String {
        val players = s.players.toMutableList()
        val player = players[playerIndex]
        val drawn = PlayingDeck.draw(s.deck, 1)
        if (drawn.isEmpty()) return "A pakli elfogyott."
        player.hand.addAll(drawn)
        val total = player.hand.blackjackTotal()
        var action = "${player.name} húzott: ${drawn.first().speak()}. Összeg: $total."
        if (total > 21) {
            player.busted = true
            player.stood = true
            action = "${player.name} besokallt, összeg: $total."
        }
        state = s.copy(players = players, lastAction = action)
        if (total <= 21) return action
        return advanceAfterPlayer(s.copy(players = players, lastAction = action), playerIndex)
    }

    private fun standPlayer(s: State, playerIndex: Int): String {
        val players = s.players.toMutableList()
        players[playerIndex].stood = true
        val total = players[playerIndex].hand.blackjackTotal()
        val action = "${players[playerIndex].name} megállt. Összeg: $total."
        state = s.copy(players = players, lastAction = action)
        return advanceAfterPlayer(s.copy(players = players, lastAction = action), playerIndex)
    }

    private fun advanceAfterPlayer(s: State, playerIndex: Int): String {
        var nextIndex = playerIndex + 1
        while (nextIndex < s.players.size && (s.players[nextIndex].stood || s.players[nextIndex].busted)) {
            nextIndex++
        }
        if (nextIndex < s.players.size) {
            state = s.copy(currentPlayerIndex = nextIndex, lastAction = s.lastAction)
            return state!!.lastAction + if (nextIndex == 0) "" else " " + runBotsUntilHuman()
        }
        return playDealer(s)
    }

    private fun playDealer(s: State): String {
        val dealer = s.dealer.copy(hand = s.dealer.hand.toMutableList())
        var deck = s.deck
        var action = "${dealer.name} felfedi a lapjait: ${dealer.hand.speakHand()}."
        while (dealer.hand.blackjackTotal() < 17) {
            val drawn = PlayingDeck.draw(deck, 1)
            if (drawn.isEmpty()) break
            dealer.hand += drawn
            action += " Krupié húz: ${drawn.first().speak()}."
        }
        val dealerTotal = dealer.hand.blackjackTotal()
        val dealerBusted = dealerTotal > 21
        action += " Krupié összeg: $dealerTotal."

        val winners = mutableListOf<String>()
        for (player in s.players) {
            val total = player.hand.blackjackTotal()
            when {
                player.busted -> Unit
                dealerBusted -> winners += player.name
                total > dealerTotal -> winners += player.name
                total == dealerTotal -> winners += player.name
            }
        }

        val result = when {
            winners.isEmpty() -> "A krupié nyert."
            winners.size == s.players.size -> "Mindenki nyert a krupié ellen!"
            else -> "Győztesek: ${winners.joinToString(", ")}."
        }
        action += " $result"

        state = s.copy(
            dealer = dealer,
            deck = deck,
            phase = Phase.FINISHED,
            currentPlayerIndex = 0,
            winners = winners,
            lastAction = action
        )
        return action
    }
}