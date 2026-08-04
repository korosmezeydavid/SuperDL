package com.superdl.launcher.games.slot

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
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager

class SlotActivity : AppCompatActivity() {

    private lateinit var tvStatus: TextView
    private lateinit var tvReels: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gameSounds: GameSoundFeedback

    private val game = SlotGame()
    private var spinning = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_slot)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvStatus = findViewById(R.id.tvSlotStatus)
        tvReels = findViewById(R.id.tvSlotReels)
        tts = TtsManager(this)
        sounds = SoundFeedback(this)
        gameSounds = GameSoundFeedback(this)

        val gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                if (!spinning) changeBet(-1)
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                if (!spinning) changeBet(+1)
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                if (!spinning) pullLever()
            },
            onSwipeLeft = {
                sounds.play(SoundType.SWIPE_LEFT)
                if (!spinning) finishGame()
            }
        )

        findViewById<View>(R.id.slotRoot).setOnTouchListener { _, event ->
            gestureListener.detector.onTouchEvent(event)
            true
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (!spinning) finishGame()
            }
        })

        refreshUi()
        tts.speakThen(
            "Félkarú rabló. Három tárcsás nyerőgép. Kezdesz 100 zsetonnal. " +
                "Fel-le: tét választása. Jobbra: kar meghúzása, pörgetés. Balra: kilépés. " +
                "Tét: ${game.currentBet()} zseton."
        ) {}
    }

    private fun changeBet(delta: Int) {
        val msg = game.changeBet(delta)
        refreshUi()
        tts.speak(msg)
    }

    private fun pullLever() {
        if (!game.canSpin()) {
            gameSounds.play(GameSoundType.SLOT_LOSE, 0.7f)
            val bonus = game.addBonusCredits(50)
            refreshUi()
            tts.speak("$bonus Próbáld újra.")
            return
        }
        spinning = true
        gameSounds.play(GameSoundType.SLOT_LEVER)
        gameSounds.playDelayed(GameSoundType.SLOT_SPIN, 120L)
        refreshUi()
        tts.speak("Pörgetés indul.")

        window.decorView.postDelayed({
            val result = game.spin()
            gameSounds.playDelayed(GameSoundType.SLOT_REEL_STOP, 0L)
            gameSounds.playDelayed(GameSoundType.SLOT_REEL_STOP, 220L)
            gameSounds.playDelayed(GameSoundType.SLOT_REEL_STOP, 440L)

            window.decorView.postDelayed({
                when {
                    result.isJackpot -> gameSounds.play(GameSoundType.SLOT_JACKPOT)
                    result.isWin -> gameSounds.play(GameSoundType.SLOT_WIN)
                    else -> gameSounds.play(GameSoundType.SLOT_LOSE)
                }
                spinning = false
                refreshUi()
                tts.speak(result.message)
            }, 520L)
        }, 600L)
    }

    private fun refreshUi() {
        val state = game.currentState()
        tvStatus.text = buildString {
            append("Egyenleg: ${state.credits} zseton")
            append("\nTét: ${state.bet} zseton")
            if (state.totalSpins > 0) {
                append("\nPörgetések: ${state.totalSpins}, nyeremény összesen: ${state.totalWon}")
            }
        }
        tvReels.text = state.lastResult?.reels?.joinToString(" | ") { it.labelHu }
            ?: "— | — | —"
    }

    private fun finishGame() {
        tts.speak("Félkarú rabló bezárva.")
        finish()
    }

    override fun onDestroy() {
        tts.shutdown()
        sounds.release()
        gameSounds.release()
        super.onDestroy()
    }
}