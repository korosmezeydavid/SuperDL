package com.superdl.launcher.games.blackjack

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
import com.superdl.launcher.games.cards.blackjackTotal
import com.superdl.launcher.games.cards.speakHand
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager

class BlackjackActivity : AppCompatActivity() {

    private lateinit var tvStatus: TextView
    private lateinit var tvCard: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gameSounds: GameSoundFeedback

    private val game = BlackjackGame()

    private enum class ScreenPhase { MODE_SELECT, PLAYING }
    private var screenPhase = ScreenPhase.MODE_SELECT
    private var modeIndex = 0
    private var selectedMode = PlayerMode.FOUR_PLAYER

    private enum class Action { HIT, STAND }
    private var actionIndex = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_blackjack)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvStatus = findViewById(R.id.tvBlackjackStatus)
        tvCard = findViewById(R.id.tvBlackjackCard)
        tts = TtsManager(this)
        sounds = SoundFeedback(this)
        gameSounds = GameSoundFeedback(this)

        val gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                when (screenPhase) {
                    ScreenPhase.MODE_SELECT -> cycleMode(-1)
                    ScreenPhase.PLAYING -> cycleAction(-1)
                }
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                when (screenPhase) {
                    ScreenPhase.MODE_SELECT -> cycleMode(1)
                    ScreenPhase.PLAYING -> cycleAction(1)
                }
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                when (screenPhase) {
                    ScreenPhase.MODE_SELECT -> confirmMode()
                    ScreenPhase.PLAYING -> confirmAction()
                }
            },
            onSwipeLeft = {
                sounds.play(SoundType.SWIPE_LEFT)
                finishGame()
            }
        )

        findViewById<View>(R.id.blackjackRoot).setOnTouchListener { _, event ->
            gestureListener.detector.onTouchEvent(event)
            true
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = finishGame()
        })

        showModeSelect()
    }

    private fun showModeSelect() {
        screenPhase = ScreenPhase.MODE_SELECT
        modeIndex = 1
        refreshUi()
        tts.speakThen(
            "Blackjack. Válaszd ki a játékosok számát. " +
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
        startRound()
    }

    private fun startRound() {
        screenPhase = ScreenPhase.PLAYING
        actionIndex = 0
        val state = game.startNewRound(selectedMode.botCount)
        val opponents = state.players.drop(1).joinToString(", ") { it.name }
        val dealerCard = state.dealer.hand.first().speak()
        gameSounds.playSequence(
            listOf(GameSoundType.CARD_DEAL, GameSoundType.CARD_DEAL, GameSoundType.CARD_DEAL),
            100L
        )
        refreshUi()
        tts.speakThen(
            "Blackjack. ${selectedMode.labelHu} mód. Ellenfelek: $opponents. " +
                "Krupié: ${state.dealer.name}. Felső krupié lap: $dealerCard. " +
                "Fel-le: húzás vagy megállás. Jobbra: megerősítés. Balra: kilépés. " +
                speakHumanHand()
        ) {
            game.runBotsUntilHuman().let { if (it.isNotBlank()) tts.speakAdd(it) }
            refreshUi()
        }
    }

    private fun cycleAction(delta: Int) {
        val actions = Action.entries
        actionIndex = (actionIndex + delta + actions.size) % actions.size
        refreshUi()
        tts.speak(actionLabel(Action.entries[actionIndex]))
    }

    private fun confirmAction() {
        val state = game.currentState() ?: return
        if (state.phase == BlackjackGame.Phase.FINISHED) {
            tts.speak("Új kör indul. ${state.lastAction}")
            startRound()
            return
        }
        if (state.currentPlayerIndex != 0) {
            tts.speak("Most nem a te köröd. Várj.")
            return
        }
        val msg = when (Action.entries[actionIndex]) {
            Action.HIT -> {
                gameSounds.play(GameSoundType.CARD_FLICK)
                game.humanHit()
            }
            Action.STAND -> {
                gameSounds.play(GameSoundType.CARD_PLACE)
                game.humanStand()
            }
        }
        refreshUi()
        tts.speak(msg)
        val finished = game.currentState()?.phase == BlackjackGame.Phase.FINISHED
        if (finished) {
            playRoundResultSound()
            tts.speakAdd("Kör vége. Jobbra söprés az új körhöz.")
        }
    }

    private fun playRoundResultSound() {
        val winners = game.currentState()?.winners.orEmpty()
        when {
            winners.contains("Te") -> gameSounds.play(GameSoundType.GAME_WIN)
            winners.isEmpty() -> gameSounds.play(GameSoundType.GAME_LOSE)
            else -> gameSounds.play(GameSoundType.GAME_LOSE)
        }
    }

    private fun actionLabel(action: Action): String = when (action) {
        Action.HIT -> "Húzás"
        Action.STAND -> "Megállás"
    }

    private fun speakHumanHand(): String {
        val hand = game.humanHand()
        return "Kezed: ${hand.speakHand()}. Összeg: ${hand.blackjackTotal()}."
    }

    private fun refreshUi() {
        when (screenPhase) {
            ScreenPhase.MODE_SELECT -> {
                tvStatus.text = "Játékosok száma"
                tvCard.text = PlayerMode.OPTIONS[modeIndex].labelHu
            }
            ScreenPhase.PLAYING -> {
                val state = game.currentState()
                val hand = game.humanHand()
                tvStatus.text = buildString {
                    append(state?.lastAction.orEmpty())
                    if (state?.phase == BlackjackGame.Phase.PLAYER_TURN) {
                        append("\nKövetkező: ${state.players.getOrNull(state.currentPlayerIndex)?.name.orEmpty()}")
                    }
                    if (state?.phase == BlackjackGame.Phase.FINISHED) {
                        append("\n${state.winners.joinToString(", ").ifEmpty { "Senki" }} nyert")
                    }
                }
                tvCard.text = when (state?.phase) {
                    BlackjackGame.Phase.FINISHED -> "Összeg: ${hand.blackjackTotal()}"
                    else -> "${actionLabel(Action.entries[actionIndex])} – ${hand.blackjackTotal()}"
                }
            }
        }
    }

    private fun finishGame() {
        tts.speak("Blackjack bezárva.")
        finish()
    }

    override fun onDestroy() {
        tts.shutdown()
        sounds.release()
        gameSounds.release()
        super.onDestroy()
    }
}