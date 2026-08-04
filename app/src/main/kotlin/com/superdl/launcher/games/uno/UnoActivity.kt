package com.superdl.launcher.games.uno

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

class UnoActivity : AppCompatActivity() {

    private lateinit var tvStatus: TextView
    private lateinit var tvCard: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gameSounds: GameSoundFeedback

    private val game = UnoGame()
    private var handIndex = 0
    private var pickingWildColor = false
    private var pendingWildCardIndex = -1
    private var wildColorIndex = 0

    private enum class Phase { MODE_SELECT, PLAYING }
    private var phase = Phase.MODE_SELECT
    private var modeIndex = 0
    private var selectedMode = PlayerMode.FOUR_PLAYER

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_uno)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvStatus = findViewById(R.id.tvUnoStatus)
        tvCard = findViewById(R.id.tvUnoCard)
        tts = TtsManager(this)
        sounds = SoundFeedback(this)
        gameSounds = GameSoundFeedback(this)

        val gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                when (phase) {
                    Phase.MODE_SELECT -> cycleMode(-1)
                    Phase.PLAYING -> if (pickingWildColor) cycleWildColor(-1) else cycleHand(-1)
                }
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                when (phase) {
                    Phase.MODE_SELECT -> cycleMode(1)
                    Phase.PLAYING -> if (pickingWildColor) cycleWildColor(1) else cycleHand(1)
                }
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                when (phase) {
                    Phase.MODE_SELECT -> confirmMode()
                    Phase.PLAYING -> if (pickingWildColor) confirmWildColor() else playOrDraw()
                }
            },
            onSwipeLeft = {
                sounds.play(SoundType.SWIPE_LEFT)
                when (phase) {
                    Phase.MODE_SELECT -> finishGame()
                    Phase.PLAYING -> if (pickingWildColor) {
                        pickingWildColor = false
                        pendingWildCardIndex = -1
                        refreshUi()
                        tts.speak("Színválasztás megszakítva.")
                    } else {
                        finishGame()
                    }
                }
            }
        )

        findViewById<View>(R.id.unoRoot).setOnTouchListener { _, event ->
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
        modeIndex = 1
        refreshUi()
        tts.speakThen(
            "UNO kártyajáték. Válaszd ki a játékosok számát. " +
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
        val state = game.startNewGame(selectedMode.botCount)
        handIndex = 0
        pickingWildColor = false
        val opponents = state.players.drop(1).joinToString(", ") { it.name }
        gameSounds.playSequence(List(4) { GameSoundType.CARD_DEAL }, 90L)
        refreshUi()
        tts.speakThen(
            "UNO. ${selectedMode.labelHu} mód. Ellenfelek: $opponents. " +
                "Fel-le: lap választása a kezedben. Jobbra: lap lerakása vagy húzás. Balra: kilépés. " +
                state.lastAction
        ) {
            speakCurrentCard()
        }
        game.runBotsUntilHuman().let { if (it.isNotBlank()) tts.speakAdd(it) }
        refreshUi()
    }

    private fun cycleHand(delta: Int) {
        val hand = game.humanHand()
        if (hand.isEmpty()) return
        handIndex = (handIndex + delta + hand.size) % hand.size
        refreshUi()
        speakCurrentCard()
    }

    private fun cycleWildColor(delta: Int) {
        val colors = UnoColor.PLAY_COLORS
        wildColorIndex = (wildColorIndex + delta + colors.size) % colors.size
        refreshUi()
        tts.speak("Szín: ${colors[wildColorIndex].labelHu}")
    }

    private fun playOrDraw() {
        val state = game.currentState()
        if (state?.winner != null) {
            tts.speak("A játék véget ért. ${state.winner} nyert. Új játék indul.")
            startGame()
            return
        }
        if (state?.currentPlayerIndex != 0) {
            tts.speak("Most nem a te köröd. Várj.")
            return
        }
        val hand = game.humanHand()
        if (hand.isEmpty()) return
        val playable = game.playableIndices(hand)
        if (handIndex !in playable) {
            val msg = game.humanDraw()
            gameSounds.play(GameSoundType.CARD_FLICK)
            refreshUi()
            tts.speak(msg)
            return
        }
        val card = hand[handIndex]
        if (card.kind == UnoKind.WILD || card.kind == UnoKind.WILD_DRAW_FOUR) {
            pickingWildColor = true
            pendingWildCardIndex = handIndex
            wildColorIndex = 0
            refreshUi()
            tts.speak("Válassz színt. Fel-le, majd jobbra söprés.")
            return
        }
        val msg = game.playHumanCard(handIndex)
        gameSounds.play(GameSoundType.CARD_PLACE)
        handIndex = 0
        refreshUi()
        tts.speak(msg)
        checkWinner()
    }

    private fun confirmWildColor() {
        if (!pickingWildColor || pendingWildCardIndex < 0) return
        val color = UnoColor.PLAY_COLORS[wildColorIndex]
        val msg = game.playHumanCard(pendingWildCardIndex, color)
        gameSounds.play(GameSoundType.CARD_PLACE)
        pickingWildColor = false
        pendingWildCardIndex = -1
        handIndex = 0
        refreshUi()
        tts.speak(msg)
        checkWinner()
    }

    private fun checkWinner() {
        val winner = game.currentState()?.winner ?: return
        if (winner == "Te") {
            gameSounds.play(GameSoundType.GAME_WIN)
        } else {
            gameSounds.play(GameSoundType.GAME_LOSE)
        }
        tts.speakAdd("Játék vége. Győztes: $winner. Jobbra söprés az újrakezdéshez.")
    }

    private fun speakCurrentCard() {
        val hand = game.humanHand()
        if (hand.isEmpty()) {
            tts.speak("Nincs lap a kezedben.")
            return
        }
        val card = hand[handIndex]
        val playable = handIndex in game.playableIndices(hand)
        val hint = if (playable) "játszható" else "nem játszható most"
        tts.speak("Lap ${handIndex + 1} a ${hand.size}-ból. ${card.speak()}. $hint.")
    }

    private fun refreshUi() {
        when (phase) {
            Phase.MODE_SELECT -> {
                val mode = PlayerMode.OPTIONS[modeIndex]
                tvStatus.text = "Játékosok száma"
                tvCard.text = mode.labelHu
            }
            Phase.PLAYING -> {
                val state = game.currentState()
                val hand = game.humanHand()
                val top = game.topCard()
                tvStatus.text = buildString {
                    append(state?.lastAction.orEmpty())
                    if (state?.winner == null) {
                        append("\nAktív szín: ${state?.activeColor?.labelHu.orEmpty()}")
                        append("\nKövetkező: ${state?.players?.getOrNull(state.currentPlayerIndex)?.name.orEmpty()}")
                    }
                }
                tvCard.text = when {
                    pickingWildColor -> "Szín: ${UnoColor.PLAY_COLORS[wildColorIndex].labelHu}"
                    hand.isNotEmpty() -> hand[handIndex].speak()
                    else -> top?.speak().orEmpty()
                }
            }
        }
    }

    private fun finishGame() {
        tts.speak("UNO bezárva.")
        finish()
    }

    override fun onDestroy() {
        tts.shutdown()
        sounds.release()
        gameSounds.release()
        super.onDestroy()
    }
}