package com.superdl.launcher.games.millebornes

import android.os.Bundle
import android.view.View
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.superdl.launcher.R
import com.superdl.launcher.feedback.GameSoundFeedback
import com.superdl.launcher.feedback.GameSoundType
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.games.PlayerMode
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager

class MilleBornesActivity : AppCompatActivity() {

    private lateinit var tvStatus: TextView
    private lateinit var tvCard: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gameSounds: GameSoundFeedback

    private val game = MilleBornesGame()
    private var handIndex = 0
    private var targetIndex = 1

    private enum class Phase { MODE_SELECT, PLAYING }
    private var phase = Phase.MODE_SELECT
    private var modeIndex = 0
    private var selectedMode = PlayerMode.TWO_PLAYER

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_mille_bornes)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvStatus = findViewById(R.id.tvMilleBornesStatus)
        tvCard = findViewById(R.id.tvMilleBornesCard)
        tts = TtsManager(this)
        sounds = SoundFeedback(this)
        gameSounds = GameSoundFeedback(this)

        val gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                when (phase) {
                    Phase.MODE_SELECT -> cycleMode(-1)
                    Phase.PLAYING -> cycleSelection(-1)
                }
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                when (phase) {
                    Phase.MODE_SELECT -> cycleMode(1)
                    Phase.PLAYING -> cycleSelection(1)
                }
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                when (phase) {
                    Phase.MODE_SELECT -> confirmMode()
                    Phase.PLAYING -> playOrDiscard()
                }
            },
            onSwipeLeft = {
                sounds.play(SoundType.SWIPE_LEFT)
                finishGame()
            }
        )

        findViewById<View>(R.id.milleBornesRoot).setOnTouchListener { _, event ->
            gestureListener.detector.onTouchEvent(event)
            true
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = finishGame()
        })

        showModeSelect()
    }

    private fun showModeSelect() {
        phase = Phase.MODE_SELECT
        modeIndex = 0
        refreshUi()
        tts.speakThen(
            "Mille Bornes. Ezer mérföldes kártyajáték. Válaszd ki a játékosok számát. " +
                "Fel-le: mód választása. Jobbra: megerősítés. Balra: kilépés. " +
                PlayerMode.OPTIONS[modeIndex].labelHu
        ) {}
    }

    private fun cycleMode(delta: Int) {
        val modes = PlayerMode.OPTIONS
        modeIndex = (modeIndex + delta + modes.size) % modes.size
        refreshUi()
        tts.speak(modes[modeIndex].labelHu)
    }

    private fun confirmMode() {
        selectedMode = PlayerMode.OPTIONS[modeIndex]
        startGame()
    }

    private fun startGame() {
        phase = Phase.PLAYING
        handIndex = 0
        val state = game.startNewGame(selectedMode.botCount)
        syncTargetForCurrentCard()
        val opponents = state.players.drop(1).joinToString(", ") { it.name }
        gameSounds.playSequence(List(4) { GameSoundType.CARD_DEAL }, 90L)
        refreshUi()
        tts.speakThen(
            "Mille Bornes. ${selectedMode.labelHu} mód. Ellenfelek: $opponents. Cél: 1000 km. " +
                "Fel-le: lap vagy célpont választása. Jobbra: lap lerakása vagy eldobás. Balra: kilépés. " +
                state.lastAction
        ) {
            speakCurrentCard()
        }
        game.runBotsUntilHuman().let { if (it.isNotBlank()) tts.speakAdd(it) }
        refreshUi()
    }

    private fun syncTargetForCurrentCard() {
        val hand = game.humanHand()
        if (hand.isEmpty()) return
        val card = hand.getOrNull(handIndex) ?: return
        val targets = game.playableTargets(card)
        targetIndex = when {
            targets.isEmpty() -> game.opponentIndices().firstOrNull() ?: 1
            targetIndex in targets -> targetIndex
            else -> targets.first()
        }
    }

    private fun cycleSelection(delta: Int) {
        val hand = game.humanHand()
        if (hand.isEmpty()) return
        val card = hand[handIndex]
        val targets = game.playableTargets(card)
        if (targets.size > 1) {
            val currentPos = targets.indexOf(targetIndex).let { if (it < 0) 0 else it }
            val nextPos = (currentPos + delta + targets.size) % targets.size
            targetIndex = targets[nextPos]
            refreshUi()
            tts.speak("Célpont: ${game.currentState()?.players?.get(targetIndex)?.name.orEmpty()}")
        } else {
            handIndex = (handIndex + delta + hand.size) % hand.size
            syncTargetForCurrentCard()
            refreshUi()
            speakCurrentCard()
        }
    }

    private fun playOrDiscard() {
        val state = game.currentState()
        if (state?.winner != null) {
            playResultSound(state.winner == "Te")
            tts.speak("A játék véget ért. Győztes: ${state.winner}. Jobbra söprés az újrakezdéshez.")
            startGame()
            return
        }
        if (state?.currentPlayerIndex != game.humanPlayerIndex()) {
            tts.speak("Most nem a te köröd. Várj.")
            return
        }
        val hand = game.humanHand()
        if (hand.isEmpty()) return
        syncTargetForCurrentCard()
        val card = hand[handIndex]
        val msg = if (game.isPlayable(card, targetIndex)) {
            game.playHumanCard(handIndex, targetIndex)
        } else {
            game.humanDiscard(handIndex)
        }
        playCardSound(game.lastPlayedSoundCard())
        handIndex = 0
        syncTargetForCurrentCard()
        refreshUi()
        tts.speak(msg)
        checkWinner()
    }

    private fun checkWinner() {
        val winner = game.currentState()?.winner ?: return
        playResultSound(winner == "Te")
        tts.speakAdd("Játék vége. Győztes: $winner. Jobbra söprés az újrakezdéshez.")
    }

    private fun playCardSound(card: MilleBornesCard?) {
        when (card) {
            MilleBornesCard.Roll -> gameSounds.play(GameSoundType.MB_GREEN_LIGHT)
            MilleBornesCard.Stop -> gameSounds.play(GameSoundType.MB_STOP)
            MilleBornesCard.FlatTire -> gameSounds.play(GameSoundType.MB_FLAT_TIRE)
            MilleBornesCard.Accident -> gameSounds.play(GameSoundType.MB_ACCIDENT)
            MilleBornesCard.OutOfGas -> gameSounds.play(GameSoundType.MB_OUT_OF_GAS)
            MilleBornesCard.SpeedLimit -> gameSounds.play(GameSoundType.MB_SPEED_LIMIT)
            is MilleBornesCard.Distance -> gameSounds.play(GameSoundType.MB_MILEAGE)
            is MilleBornesCard.Safety -> gameSounds.play(GameSoundType.MB_SAFETY)
            MilleBornesCard.Gasoline,
            MilleBornesCard.SpareTire,
            MilleBornesCard.Repairs,
            MilleBornesCard.EndOfLimit -> gameSounds.play(GameSoundType.CARD_PLACE)
            null -> gameSounds.play(GameSoundType.CARD_FLICK)
            else -> gameSounds.play(GameSoundType.CARD_PLACE)
        }
    }

    private fun playResultSound(won: Boolean) {
        if (won) gameSounds.play(GameSoundType.GAME_WIN) else gameSounds.play(GameSoundType.GAME_LOSE)
    }

    private fun speakCurrentCard() {
        val hand = game.humanHand()
        if (hand.isEmpty()) {
            tts.speak("Nincs lap a kezedben.")
            return
        }
        syncTargetForCurrentCard()
        val card = hand[handIndex]
        val playable = game.isPlayable(card, targetIndex)
        val hint = if (playable) "játszható" else "eldobható"
        val targetName = game.currentState()?.players?.getOrNull(targetIndex)?.name
        val targetHint = if (game.playableTargets(card).size > 1 && targetName != null) {
            " Célpont: $targetName."
        } else {
            ""
        }
        tts.speak("Lap ${handIndex + 1} a ${hand.size}-ból. ${card.speak()}.$targetHint $hint.")
    }

    private fun refreshUi() {
        when (phase) {
            Phase.MODE_SELECT -> {
                tvStatus.text = "Játékosok száma"
                tvCard.text = PlayerMode.OPTIONS[modeIndex].labelHu
            }
            Phase.PLAYING -> {
                val state = game.currentState()
                val hand = game.humanHand()
                val board = game.humanBoard()
                tvStatus.text = buildString {
                    append(state?.lastAction.orEmpty())
                    if (state?.winner == null) {
                        append("\nKm: ${board?.miles ?: 0} / 1000")
                        append("\nÁllapot: ${board?.battleStatus?.labelHu.orEmpty()}")
                        if (board?.speedLimitActive == true) append(" – sebességkorlát")
                        append("\nKövetkező: ${state?.players?.getOrNull(state.currentPlayerIndex)?.name.orEmpty()}")
                    }
                }
                tvCard.text = when {
                    hand.isNotEmpty() -> {
                        val card = hand[handIndex]
                        val targetName = state?.players?.getOrNull(targetIndex)?.name
                        if (game.playableTargets(card).size > 1 && targetName != null) {
                            "${card.speak()} → $targetName"
                        } else {
                            card.speak()
                        }
                    }
                    else -> ""
                }
            }
        }
    }

    private fun finishGame() {
        tts.speak("Mille Bornes bezárva.")
        finish()
    }

    override fun onDestroy() {
        tts.shutdown()
        sounds.release()
        gameSounds.release()
        super.onDestroy()
    }
}