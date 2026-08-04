package com.superdl.launcher.games.poker

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
import com.superdl.launcher.games.cards.speakHand
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager

class PokerActivity : AppCompatActivity() {

    private lateinit var tvStatus: TextView
    private lateinit var tvCard: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gameSounds: GameSoundFeedback

    private val game = PokerGame()

    private enum class ScreenPhase { MODE_SELECT, PLAYING }
    private var screenPhase = ScreenPhase.MODE_SELECT
    private var modeIndex = 0
    private var selectedMode = PlayerMode.FOUR_PLAYER
    private var discardCount = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_poker)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvStatus = findViewById(R.id.tvPokerStatus)
        tvCard = findViewById(R.id.tvPokerCard)
        tts = TtsManager(this)
        sounds = SoundFeedback(this)
        gameSounds = GameSoundFeedback(this)

        val gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                when (screenPhase) {
                    ScreenPhase.MODE_SELECT -> cycleMode(-1)
                    ScreenPhase.PLAYING -> cycleDiscard(-1)
                }
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                when (screenPhase) {
                    ScreenPhase.MODE_SELECT -> cycleMode(1)
                    ScreenPhase.PLAYING -> cycleDiscard(1)
                }
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                when (screenPhase) {
                    ScreenPhase.MODE_SELECT -> confirmMode()
                    ScreenPhase.PLAYING -> confirmDiscard()
                }
            },
            onSwipeLeft = {
                sounds.play(SoundType.SWIPE_LEFT)
                finishGame()
            }
        )

        findViewById<View>(R.id.pokerRoot).setOnTouchListener { _, event ->
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
            "Póker. Ötlapos húzás. Válaszd ki a játékosok számát. " +
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
        discardCount = 0
        val state = game.startNewRound(selectedMode.botCount)
        val opponents = state.players.drop(1).joinToString(", ") { it.name }
        val hand = game.humanHand()
        val evaluated = PokerHandEvaluator.evaluate(hand)
        gameSounds.playSequence(List(5) { GameSoundType.CARD_DEAL }, 80L)
        refreshUi()
        tts.speakThen(
            "Póker. ${selectedMode.labelHu} mód. Ellenfelek: $opponents. " +
                "Kezed: ${hand.speakHand()}. ${evaluated.label}. " +
                "Fel-le: cserélendő lapok száma, nulla és öt között. Jobbra: megerősítés. Balra: kilépés. " +
                "Cserélendő: $discardCount lap."
        ) {}
    }

    private fun cycleDiscard(delta: Int) {
        val state = game.currentState() ?: return
        if (state.phase == PokerGame.Phase.FINISHED) return
        if (state.currentPlayerIndex != 0) {
            tts.speak("Most nem a te köröd.")
            return
        }
        discardCount = (discardCount + delta).coerceIn(0, 5)
        refreshUi()
        tts.speak("Cserélendő: $discardCount lap.")
    }

    private fun confirmDiscard() {
        val state = game.currentState() ?: return
        if (state.phase == PokerGame.Phase.FINISHED) {
            tts.speak("Új kör indul. ${state.lastAction}")
            startRound()
            return
        }
        if (state.currentPlayerIndex != 0) {
            tts.speak("Most nem a te köröd. Várj.")
            return
        }
        if (discardCount > 0) {
            gameSounds.playSequence(List(discardCount.coerceAtMost(5)) { GameSoundType.CARD_FLICK }, 70L)
        } else {
            gameSounds.play(GameSoundType.CARD_PLACE)
        }
        val msg = game.humanDiscard(discardCount) + " " + game.runBotsUntilHuman()
        refreshUi()
        tts.speak(msg.trim())
        if (game.currentState()?.phase == PokerGame.Phase.FINISHED) {
            playRoundResultSound()
            tts.speakAdd("Kör vége. Jobbra söprés az új körhöz.")
        }
    }

    private fun playRoundResultSound() {
        val winner = game.currentState()?.winner
        if (winner == "Te") {
            gameSounds.play(GameSoundType.GAME_WIN)
        } else {
            gameSounds.play(GameSoundType.GAME_LOSE)
        }
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
                    if (state?.phase == PokerGame.Phase.DISCARD) {
                        append("\nKövetkező: ${state.players.getOrNull(state.currentPlayerIndex)?.name.orEmpty()}")
                    }
                    if (state?.phase == PokerGame.Phase.FINISHED) {
                        append("\nGyőztes: ${state.winner.orEmpty()}")
                    }
                }
                tvCard.text = when (state?.phase) {
                    PokerGame.Phase.FINISHED -> {
                        val eval = PokerHandEvaluator.evaluate(hand)
                        "${eval.label} – ${hand.speakHand()}"
                    }
                    else -> "Cserélendő: $discardCount / Kezed: ${hand.size} lap"
                }
            }
        }
    }

    private fun finishGame() {
        tts.speak("Póker bezárva.")
        finish()
    }

    override fun onDestroy() {
        tts.shutdown()
        sounds.release()
        gameSounds.release()
        super.onDestroy()
    }
}