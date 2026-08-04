package com.superdl.launcher.games.millebornes

import com.superdl.launcher.games.BotNames
import kotlin.random.Random

class MilleBornesGame(
    private val random: Random = Random.Default
) {
    enum class BattleStatus(val labelHu: String) {
        AWAITING_ROLL("Várakozás indulásra"),
        GOING("Haladás"),
        STOPPED("Stop"),
        OUT_OF_GAS("Benzin fogyott"),
        FLAT_TIRE("Defekt"),
        ACCIDENT("Baleset")
    }

    data class PlayerBoard(
        val name: String,
        val isHuman: Boolean,
        val hand: MutableList<MilleBornesCard> = mutableListOf(),
        var miles: Int = 0,
        var battleStatus: BattleStatus = BattleStatus.AWAITING_ROLL,
        var speedLimitActive: Boolean = false,
        val safetiesPlayed: MutableSet<SafetyType> = mutableSetOf(),
        val distanceCards: MutableList<MilleBornesCard.Distance> = mutableListOf()
    )

    data class State(
        val players: List<PlayerBoard>,
        val stock: ArrayDeque<MilleBornesCard>,
        val currentPlayerIndex: Int,
        val winner: String?,
        val lastAction: String,
        val deckExhausted: Boolean
    )

    private var state: State? = null

    fun startNewGame(botCount: Int = 1): State {
        val stock = MilleBornesDeck.createShuffled(random)
        val botNames = BotNames.pick(botCount, random)
        val players = buildList {
            add(PlayerBoard("Te", isHuman = true))
            botNames.forEach { name ->
                add(PlayerBoard(name, isHuman = false))
            }
        }.map { player ->
            player.copy(hand = MilleBornesDeck.draw(stock, 6).toMutableList())
        }

        state = State(
            players = players,
            stock = stock,
            currentPlayerIndex = 0,
            winner = null,
            lastAction = "Új Mille Bornes játék. Cél: 1000 km.",
            deckExhausted = false
        )
        return state!!
    }

    fun currentState(): State? = state

    fun humanHand(): List<MilleBornesCard> =
        state?.players?.firstOrNull { it.isHuman }?.hand.orEmpty()

    fun humanBoard(): PlayerBoard? =
        state?.players?.firstOrNull { it.isHuman }

    fun opponentIndices(): List<Int> =
        state?.players?.indices?.filter { index -> index != humanPlayerIndex() }.orEmpty()

    fun humanPlayerIndex(): Int =
        state?.players?.indexOfFirst { it.isHuman }?.takeIf { it >= 0 } ?: 0

    fun playableTargets(card: MilleBornesCard): List<Int> {
        val s = state ?: return emptyList()
        val humanIndex = humanPlayerIndex()
        if (s.currentPlayerIndex != humanIndex) return emptyList()
        return when (card) {
            is MilleBornesCard.Distance,
            MilleBornesCard.Roll,
            MilleBornesCard.EndOfLimit,
            MilleBornesCard.Gasoline,
            MilleBornesCard.SpareTire,
            MilleBornesCard.Repairs,
            is MilleBornesCard.Safety -> listOf(humanIndex)
            else -> hazardTargets(s, humanIndex, card)
        }
    }

    fun isPlayable(card: MilleBornesCard, targetIndex: Int): Boolean {
        val s = state ?: return false
        val humanIndex = humanPlayerIndex()
        if (s.winner != null || s.currentPlayerIndex != humanIndex) return false
        if (targetIndex !in s.players.indices) return false
        val player = s.players[humanIndex]
        if (card !in player.hand) return false
        return when (card) {
            is MilleBornesCard.Distance -> targetIndex == humanIndex && canPlayDistance(player, card)
            MilleBornesCard.Roll -> targetIndex == humanIndex && canPlayRoll(player)
            MilleBornesCard.EndOfLimit -> targetIndex == humanIndex && player.speedLimitActive
            MilleBornesCard.Gasoline -> targetIndex == humanIndex && player.battleStatus == BattleStatus.OUT_OF_GAS
            MilleBornesCard.SpareTire -> targetIndex == humanIndex && player.battleStatus == BattleStatus.FLAT_TIRE
            MilleBornesCard.Repairs -> targetIndex == humanIndex && player.battleStatus == BattleStatus.ACCIDENT
            is MilleBornesCard.Safety -> targetIndex == humanIndex && card.type !in player.safetiesPlayed
            else -> targetIndex != humanIndex && targetIndex in hazardTargets(s, humanIndex, card)
        }
    }

    fun playHumanCard(handIndex: Int, targetIndex: Int): String {
        val s = state ?: return "Nincs aktív játék."
        val humanIndex = humanPlayerIndex()
        if (s.winner != null) return "A játék véget ért."
        if (s.currentPlayerIndex != humanIndex) return "Most nem a te köröd."
        val player = s.players[humanIndex]
        if (handIndex !in player.hand.indices) return "Érvénytelen lap."
        val card = player.hand[handIndex]
        if (!isPlayable(card, targetIndex)) return "Ezt a lapot most nem játszhatod."
        return executePlay(s, humanIndex, handIndex, card, targetIndex)
    }

    fun humanDiscard(handIndex: Int): String {
        val s = state ?: return "Nincs aktív játék."
        val humanIndex = humanPlayerIndex()
        if (s.winner != null) return "A játék véget ért."
        if (s.currentPlayerIndex != humanIndex) return "Most nem a te köröd."
        val player = s.players[humanIndex]
        if (handIndex !in player.hand.indices) return "Érvénytelen lap."
        val discarded = player.hand.removeAt(handIndex)
        lastSoundCard = null
        val drawn = drawToHand(player, s.stock, 1)
        val drawMsg = if (drawn.isNotEmpty()) " Húztál: ${drawn.first().speak()}." else " A pakli elfogyott."
        var updated = advanceTurn(s)
        updated = resolveWinner(updated)
        updated = updated.copy(lastAction = "Eldobtál: ${discarded.speak()}.$drawMsg")
        state = updated
        return updated.lastAction + " " + runBotsUntilHuman()
    }

    fun runBotsUntilHuman(): String {
        val s = state ?: return ""
        if (s.winner != null) return s.lastAction
        val messages = StringBuilder()
        var guard = 0
        while (guard < 48) {
            guard++
            val current = state ?: break
            if (current.winner != null) break
            val humanIndex = humanPlayerIndex()
            if (current.currentPlayerIndex == humanIndex) {
                refillHand(current.players[humanIndex], current.stock)
                var updated = resolveWinner(current)
                state = updated
                messages.append(" Te jössz.")
                break
            }
            val botIndex = current.currentPlayerIndex
            val bot = current.players[botIndex]
            refillHand(bot, current.stock)
            val action = chooseBotAction(current, botIndex)
            if (action != null) {
                val msg = executePlay(current, botIndex, action.handIndex, action.card, action.targetIndex)
                messages.append(" ").append(msg)
            } else {
                val discardIndex = chooseDiscardIndex(bot.hand)
                val discarded = bot.hand.removeAt(discardIndex)
                drawToHand(bot, current.stock, 1)
                var updated = advanceTurn(current)
                updated = resolveWinner(updated)
                updated = updated.copy(lastAction = "${bot.name} eldobott: ${discarded.speak()}.")
                state = updated
                messages.append(" ").append(updated.lastAction)
            }
        }
        return messages.toString().trim()
    }

    fun lastPlayedSoundCard(): MilleBornesCard? = lastSoundCard
    private var lastSoundCard: MilleBornesCard? = null

    private data class BotAction(
        val handIndex: Int,
        val card: MilleBornesCard,
        val targetIndex: Int
    )

    private fun hazardTargets(s: State, actorIndex: Int, card: MilleBornesCard): List<Int> =
        s.players.indices.filter { index ->
            index != actorIndex && canPlayHazardOn(s.players[index], card)
        }

    private fun isHazard(card: MilleBornesCard): Boolean = card.hazardType() != null

    private fun advanceTurn(s: State): State {
        if (s.winner != null) return s
        val next = (s.currentPlayerIndex + 1) % s.players.size
        return s.copy(currentPlayerIndex = next)
    }

    private fun resolveWinner(s: State): State {
        val reached = s.players.filter { it.miles >= 1000 }
        if (reached.isNotEmpty()) {
            val winner = reached.maxByOrNull { it.miles }!!
            return s.copy(
                winner = winner.name,
                lastAction = "${winner.name} elérte a 1000 km-t!"
            )
        }
        if (s.stock.isEmpty() && s.players.all { it.hand.size <= 6 }) {
            val leader = s.players.maxByOrNull { it.miles }!!
            return s.copy(
                winner = leader.name,
                deckExhausted = true,
                lastAction = "A pakli elfogyott. ${leader.name} vezet ${leader.miles} km-mel."
            )
        }
        return s
    }

    private fun canPlayRoll(player: PlayerBoard): Boolean = when (player.battleStatus) {
        BattleStatus.AWAITING_ROLL,
        BattleStatus.STOPPED -> true
        else -> false
    }

    private fun canPlayDistance(player: PlayerBoard, card: MilleBornesCard.Distance): Boolean {
        if (player.battleStatus != BattleStatus.GOING) return false
        if (card.km == 200 && player.speedLimitActive) return false
        if (player.speedLimitActive && card.km > 50) return false
        return true
    }

    private fun canPlayHazardOn(target: PlayerBoard, card: MilleBornesCard): Boolean {
        if (target.battleStatus != BattleStatus.GOING) return false
        return when (card) {
            MilleBornesCard.Stop,
            MilleBornesCard.SpeedLimit,
            MilleBornesCard.OutOfGas,
            MilleBornesCard.FlatTire,
            MilleBornesCard.Accident -> true
            else -> false
        }
    }

    private fun refillHand(player: PlayerBoard, stock: ArrayDeque<MilleBornesCard>) {
        val needed = 6 - player.hand.size
        if (needed > 0) drawToHand(player, stock, needed)
    }

    private fun drawToHand(
        player: PlayerBoard,
        stock: ArrayDeque<MilleBornesCard>,
        count: Int
    ): List<MilleBornesCard> {
        val drawn = MilleBornesDeck.draw(stock, count)
        player.hand += drawn
        return drawn
    }

    private fun executePlay(
        s: State,
        playerIndex: Int,
        handIndex: Int,
        card: MilleBornesCard,
        targetIndex: Int
    ): String {
        val player = s.players[playerIndex]
        if (handIndex !in player.hand.indices || player.hand[handIndex] != card) {
            return "Érvénytelen lap."
        }
        if (isHazard(card)) {
            if (targetIndex == playerIndex || targetIndex !in hazardTargets(s, playerIndex, card)) {
                return "Érvénytelen célpont."
            }
        } else if (targetIndex != playerIndex) {
            return "Érvénytelen célpont."
        }

        player.hand.removeAt(handIndex)
        lastSoundCard = card
        val msg = when (card) {
            is MilleBornesCard.Distance -> applyDistance(player, card)
            MilleBornesCard.Roll -> applyRoll(player)
            MilleBornesCard.EndOfLimit -> applyEndOfLimit(player)
            MilleBornesCard.Gasoline -> applyGasoline(player)
            MilleBornesCard.SpareTire -> applySpareTire(player)
            MilleBornesCard.Repairs -> applyRepairs(player)
            is MilleBornesCard.Safety -> applySafety(player, card.type)
            else -> applyHazard(s, playerIndex, s.players[targetIndex], card)
        }
        drawToHand(player, s.stock, 1)
        var updated = resolveWinner(s)
        if (updated.winner == null) updated = advanceTurn(updated)
        updated = updated.copy(lastAction = msg)
        state = updated
        return if (playerIndex == humanPlayerIndex() && updated.winner == null) {
            updated.lastAction + " " + runBotsUntilHuman()
        } else {
            updated.lastAction
        }
    }

    private fun applyDistance(player: PlayerBoard, card: MilleBornesCard.Distance): String {
        player.miles += card.km
        player.distanceCards += card
        return "${player.name} haladt ${card.km} km-t. Összesen ${player.miles} km."
    }

    private fun applyRoll(player: PlayerBoard): String {
        player.battleStatus = BattleStatus.GOING
        return "${player.name} elindult. Zöld lámpa!"
    }

    private fun applyEndOfLimit(player: PlayerBoard): String {
        player.speedLimitActive = false
        return "${player.name} feloldotta a sebességkorlátot."
    }

    private fun applyGasoline(player: PlayerBoard): String {
        player.battleStatus = BattleStatus.AWAITING_ROLL
        return "${player.name} tankolt. Indulás kell."
    }

    private fun applySpareTire(player: PlayerBoard): String {
        player.battleStatus = BattleStatus.AWAITING_ROLL
        return "${player.name} pótkereket szerelt. Indulás kell."
    }

    private fun applyRepairs(player: PlayerBoard): String {
        player.battleStatus = BattleStatus.AWAITING_ROLL
        return "${player.name} javított. Indulás kell."
    }

    private fun applySafety(player: PlayerBoard, type: SafetyType): String {
        player.safetiesPlayed += type
        return "${player.name} biztonsági lapot játszott: ${type.labelHu}."
    }

    private fun applyHazard(
        s: State,
        actorIndex: Int,
        target: PlayerBoard,
        card: MilleBornesCard
    ): String {
        val hazard = card.hazardType() ?: return "Érvénytelen támadó lap."
        val safety = target.hand.firstOrNull {
            it is MilleBornesCard.Safety && it.type.counters(hazard) && it.type !in target.safetiesPlayed
        } as? MilleBornesCard.Safety

        if (safety != null) {
            target.hand.remove(safety)
            target.safetiesPlayed += safety.type
            lastSoundCard = safety
            return "${target.name} védekezett: ${safety.type.labelHu}. ${hazard.labelHu} hatástalan."
        }

        when (card) {
            MilleBornesCard.Stop -> target.battleStatus = BattleStatus.STOPPED
            MilleBornesCard.SpeedLimit -> target.speedLimitActive = true
            MilleBornesCard.OutOfGas -> target.battleStatus = BattleStatus.OUT_OF_GAS
            MilleBornesCard.FlatTire -> target.battleStatus = BattleStatus.FLAT_TIRE
            MilleBornesCard.Accident -> target.battleStatus = BattleStatus.ACCIDENT
            else -> Unit
        }
        return "${s.players[actorIndex].name} ${hazard.labelHu} lapot játszott ${target.name} ellen."
    }

    private fun chooseBotAction(s: State, botIndex: Int): BotAction? {
        val bot = s.players[botIndex]
        val options = bot.hand.mapIndexedNotNull { index, card ->
            val targets = when (card) {
                is MilleBornesCard.Distance,
                MilleBornesCard.Roll,
                MilleBornesCard.EndOfLimit,
                MilleBornesCard.Gasoline,
                MilleBornesCard.SpareTire,
                MilleBornesCard.Repairs,
                is MilleBornesCard.Safety -> listOf(botIndex)
                else -> hazardTargets(s, botIndex, card)
            }
            targets.mapNotNull { target ->
                if (isBotPlayable(s, botIndex, card, target)) BotAction(index, card, target) else null
            }
        }.flatten()

        return options.maxByOrNull { scoreBotPlay(s, botIndex, it) }
    }

    private fun isBotPlayable(
        s: State,
        botIndex: Int,
        card: MilleBornesCard,
        targetIndex: Int
    ): Boolean {
        if (targetIndex !in s.players.indices) return false
        val bot = s.players[botIndex]
        return when (card) {
            is MilleBornesCard.Distance -> targetIndex == botIndex && canPlayDistance(bot, card)
            MilleBornesCard.Roll -> targetIndex == botIndex && canPlayRoll(bot)
            MilleBornesCard.EndOfLimit -> targetIndex == botIndex && bot.speedLimitActive
            MilleBornesCard.Gasoline -> targetIndex == botIndex && bot.battleStatus == BattleStatus.OUT_OF_GAS
            MilleBornesCard.SpareTire -> targetIndex == botIndex && bot.battleStatus == BattleStatus.FLAT_TIRE
            MilleBornesCard.Repairs -> targetIndex == botIndex && bot.battleStatus == BattleStatus.ACCIDENT
            is MilleBornesCard.Safety -> targetIndex == botIndex && card.type !in bot.safetiesPlayed
            else -> targetIndex != botIndex && targetIndex in hazardTargets(s, botIndex, card)
        }
    }

    private fun scoreBotPlay(s: State, botIndex: Int, action: BotAction): Int {
        val bot = s.players[botIndex]
        return when (val card = action.card) {
            is MilleBornesCard.Distance -> card.km * 10 + if (bot.miles + card.km >= 1000) 500 else 0
            MilleBornesCard.Roll -> if (bot.battleStatus != BattleStatus.GOING) 80 else 0
            MilleBornesCard.EndOfLimit -> 70
            MilleBornesCard.Gasoline, MilleBornesCard.SpareTire, MilleBornesCard.Repairs -> 90
            is MilleBornesCard.Safety -> 40
            else -> {
                val target = s.players[action.targetIndex]
                val lead = target.miles - bot.miles
                60 + lead / 10 + if (card == MilleBornesCard.Accident) 15 else 10
            }
        }
    }

    private fun chooseDiscardIndex(hand: List<MilleBornesCard>): Int {
        val priorities = hand.mapIndexed { index, card ->
            index to when (card) {
                is MilleBornesCard.Distance -> if (card.km == 200) 0 else 2
                is MilleBornesCard.Safety -> 1
                MilleBornesCard.Roll -> 3
                else -> 4
            }
        }
        return priorities.minByOrNull { it.second }?.first ?: 0
    }
}