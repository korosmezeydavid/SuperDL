package com.superdl.launcher.games.uno

import com.superdl.launcher.games.BotNames
import kotlin.random.Random

class UnoGame(
    private val random: Random = Random.Default
) {
    data class PlayerState(
        val name: String,
        val isHuman: Boolean,
        val hand: MutableList<UnoCard> = mutableListOf()
    )

    data class State(
        val players: List<PlayerState>,
        val deck: ArrayDeque<UnoCard>,
        val discard: MutableList<UnoCard>,
        val currentPlayerIndex: Int,
        val direction: Int,
        val activeColor: UnoColor,
        val drawStack: Int,
        val skipNext: Boolean,
        val winner: String?,
        val lastAction: String
    )

    private var state: State? = null

    fun startNewGame(botCount: Int = 3): State {
        val deck = UnoDeck.createShuffled(random)
        val botNames = BotNames.pick(botCount, random)
        val players = buildList {
            add(PlayerState("Te", isHuman = true))
            botNames.forEach { name ->
                add(PlayerState(name, isHuman = false))
            }
        }.map { player ->
            player.copy(hand = UnoDeck.draw(deck, 7).toMutableList())
        }

        var top = UnoDeck.draw(deck, 1).first()
        while (top.kind == UnoKind.WILD_DRAW_FOUR) {
            deck.addLast(top)
            top = UnoDeck.draw(deck, 1).first()
        }
        val activeColor = if (top.color == UnoColor.WILD) {
            UnoColor.PLAY_COLORS.random(random)
        } else {
            top.color
        }

        state = State(
            players = players,
            deck = deck,
            discard = mutableListOf(top),
            currentPlayerIndex = 0,
            direction = 1,
            activeColor = activeColor,
            drawStack = 0,
            skipNext = false,
            winner = null,
            lastAction = "Új játék. Felső lap: ${top.speak()}."
        )
        return state!!
    }

    fun currentState(): State? = state

    fun humanHand(): List<UnoCard> =
        state?.players?.firstOrNull { it.isHuman }?.hand.orEmpty()

    fun topCard(): UnoCard? = state?.discard?.lastOrNull()

    fun playableIndices(hand: List<UnoCard>): List<Int> {
        val s = state ?: return emptyList()
        val top = s.discard.last()
        return hand.mapIndexedNotNull { index, card ->
            if (card.matches(top, s.activeColor)) index else null
        }
    }

    fun playHumanCard(index: Int, chosenWildColor: UnoColor? = null): String {
        val s = state ?: return "Nincs aktív játék."
        if (s.winner != null) return "A játék véget ért."
        if (s.currentPlayerIndex != 0) return "Most nem a te köröd."
        val player = s.players[0]
        if (index !in player.hand.indices) return "Érvénytelen lap."
        val card = player.hand[index]
        if (index !in playableIndices(player.hand)) return "Ezt a lapot most nem dobhatod."

        return applyPlay(s, 0, card, chosenWildColor ?: defaultWildColor(card))
    }

    fun humanDraw(): String {
        val s = state ?: return "Nincs aktív játék."
        if (s.winner != null) return "A játék véget ért."
        if (s.currentPlayerIndex != 0) return "Most nem a te köröd."
        val playable = playableIndices(humanHand())
        if (playable.isNotEmpty()) return "Van játszható lapod, nem kell húzni."
        val drawn = UnoDeck.draw(s.deck, 1)
        if (drawn.isEmpty()) return "A pakli elfogyott."
        s.players[0].hand += drawn
        state = s.copy(lastAction = "Húztál egy lapot: ${drawn.first().speak()}.")
        advanceTurn(s)
        return state!!.lastAction + " " + runBotsUntilHuman()
    }

    fun runBotsUntilHuman(): String {
        val s = state ?: return ""
        if (s.winner != null) return s.lastAction
        val messages = StringBuilder(s.lastAction)
        var guard = 0
        while (guard < 24) {
            guard++
            val current = state ?: break
            if (current.winner != null) break
            if (current.currentPlayerIndex == 0) {
                messages.append(" Te jössz.")
                break
            }
            val botIndex = current.currentPlayerIndex
            val bot = current.players[botIndex]
            val playIndex = chooseBotCard(bot.hand, current)
            if (playIndex >= 0) {
                val card = bot.hand[playIndex]
                val msg = applyPlay(current, botIndex, card, defaultWildColor(card))
                messages.append(" ").append(msg)
            } else {
                val drawn = UnoDeck.draw(current.deck, 1)
                if (drawn.isEmpty()) {
                    state = current.copy(lastAction = "${bot.name} nem tudott húzni.")
                    break
                }
                bot.hand += drawn
                state = current.copy(lastAction = "${bot.name} húzott egy lapot.")
                advanceTurn(current)
            }
        }
        return messages.toString().trim()
    }

    private fun chooseBotCard(hand: List<UnoCard>, s: State): Int {
        val options = playableIndices(hand)
        if (options.isEmpty()) return -1
        return options.maxByOrNull { scoreCard(hand[it]) } ?: options.first()
    }

    private fun scoreCard(card: UnoCard): Int = when (card.kind) {
        UnoKind.WILD_DRAW_FOUR -> 50
        UnoKind.WILD -> 40
        UnoKind.DRAW_TWO -> 30
        UnoKind.SKIP, UnoKind.REVERSE -> 20
        UnoKind.NUMBER -> card.number
    }

    private fun defaultWildColor(card: UnoCard): UnoColor {
        if (card.kind != UnoKind.WILD && card.kind != UnoKind.WILD_DRAW_FOUR) return card.color
        val hand = state?.players?.get(state!!.currentPlayerIndex)?.hand.orEmpty()
        val counts = UnoColor.PLAY_COLORS.associateWith { color ->
            hand.count { it.color == color }
        }
        return counts.maxByOrNull { it.value }?.key ?: UnoColor.PLAY_COLORS.random(random)
    }

    private fun applyPlay(
        s: State,
        playerIndex: Int,
        card: UnoCard,
        wildColor: UnoColor
    ): String {
        val players = s.players.toMutableList()
        val hand = players[playerIndex].hand
        hand.remove(card)
        val discard = s.discard.toMutableList()
        discard += card

        var direction = s.direction
        var drawStack = s.drawStack
        var skipNext = false
        var activeColor = if (card.color == UnoColor.WILD) wildColor else card.color
        val playerName = players[playerIndex].name

        when (card.kind) {
            UnoKind.SKIP -> skipNext = true
            UnoKind.REVERSE -> direction *= -1
            UnoKind.DRAW_TWO -> drawStack += 2
            UnoKind.WILD_DRAW_FOUR -> drawStack += 4
            else -> Unit
        }

        var winner: String? = null
        var action = "$playerName lerakta: ${card.speak()}."
        if (hand.isEmpty()) {
            winner = playerName
            action = "$playerName győzött! Utolsó lap: ${card.speak()}."
        } else if (hand.size == 1 && playerIndex == 0) {
            action += " UNO!"
        }

        var next = State(
            players = players,
            deck = s.deck,
            discard = discard,
            currentPlayerIndex = playerIndex,
            direction = direction,
            activeColor = activeColor,
            drawStack = drawStack,
            skipNext = skipNext,
            winner = winner,
            lastAction = action
        )
        state = next
        if (winner != null) return action

        advanceTurn(next)
        return state!!.lastAction + if (playerIndex == 0) " " + runBotsUntilHuman() else ""
    }

    private fun advanceTurn(s: State) {
        if (s.winner != null) return
        var players = s.players.toMutableList()
        var index = s.currentPlayerIndex
        var direction = s.direction
        var drawStack = s.drawStack
        var skipNext = s.skipNext
        var lastAction = s.lastAction

        fun nextIndex(from: Int): Int =
            (from + direction + players.size) % players.size

        if (drawStack > 0) {
            val target = nextIndex(index)
            val drawn = UnoDeck.draw(s.deck, drawStack)
            players[target].hand.addAll(drawn)
            lastAction = "${players[target].name} $drawStack lapot húzott."
            drawStack = 0
            index = nextIndex(target)
        } else {
            index = nextIndex(index)
            if (skipNext) {
                lastAction += " ${players[index].name} kimarad."
                index = nextIndex(index)
                skipNext = false
            }
        }

        state = s.copy(
            players = players,
            currentPlayerIndex = index,
            direction = direction,
            drawStack = drawStack,
            skipNext = false,
            lastAction = lastAction
        )
    }
}