package com.superdl.launcher.lock

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.view.View
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.superdl.launcher.R
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.input.NumberPadHelper
import com.superdl.launcher.input.NumberPadItem
import com.superdl.launcher.input.NumberPadKey
import com.superdl.launcher.security.LockPinStore
import com.superdl.launcher.security.LockSession
import com.superdl.launcher.tts.TtsManager

class LockScreenActivity : AppCompatActivity() {

    private lateinit var tvItem: TextView
    private lateinit var tvHint: TextView
    private lateinit var tvPosition: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gestureListener: SwipeGestureListener
    private var vibrator: Vibrator? = null

    private var padIndex = 0
    private var pinBuffer = ""
    private val items: List<NumberPadItem> = NumberPadHelper.pinItems

    private var screenReceiver: BroadcastReceiver? = null
    private val handler = Handler(Looper.getMainLooper())
    private var introRunnable: Runnable? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!LockSession.needsUnlock(this)) {
            finish()
            return
        }

        setContentView(R.layout.activity_main)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        }
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            )

        tvItem = findViewById(R.id.tvItem)
        tvHint = findViewById(R.id.tvHint)
        tvPosition = findViewById(R.id.tvPosition)

        tts = TtsManager(this)
        sounds = SoundFeedback(this)
        vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            (getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            getSystemService(VIBRATOR_SERVICE) as Vibrator
        }

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = { feedbackSwipeUp(); navigatePad(-1) },
            onSwipeDown = { feedbackSwipeDown(); navigatePad(+1) },
            onSwipeRight = { feedbackSwipeRight(); activatePad() },
            onSwipeLeft = { feedbackSwipeLeft(); backspacePad() }
        )

        findViewById<View>(R.id.rootLayout).setOnTouchListener { _, event ->
            gestureListener.detector.onTouchEvent(event)
            true
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = backspacePad()
        })

        LockSession.lockScreenVisible = true
        updatePadDisplay()
        introRunnable = Runnable {
            if (isFinishing || isDestroyed) return@Runnable
            tts.speak(
                "Super DL zárolva. Add meg a PIN kódot a feloldáshoz. " +
                    "Egyestől nulláig, alul a Törlés és Megerősítés gomb. " +
                    "Fel-le választás, jobbra beírás, balra egy számjegy törlése."
            )
            tts.speakAdd(items.first().speakLabel())
        }
        handler.postDelayed(introRunnable!!, 400)
    }

    override fun onStart() {
        super.onStart()
        registerScreenReceiver()
    }

    override fun onStop() {
        screenReceiver?.let { unregisterReceiver(it) }
        screenReceiver = null
        super.onStop()
    }

    override fun onDestroy() {
        introRunnable?.let { handler.removeCallbacks(it) }
        introRunnable = null
        handler.removeCallbacksAndMessages(null)
        if (LockSession.needsUnlock(this)) {
            LockSession.lockScreenVisible = false
        }
        tts.shutdown()
        sounds.release()
        super.onDestroy()
    }

    private fun registerScreenReceiver() {
        if (screenReceiver != null) return
        val filter = IntentFilter(Intent.ACTION_SCREEN_OFF)
        screenReceiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                if (intent.action == Intent.ACTION_SCREEN_OFF) {
                    LockSession.lock()
                    pinBuffer = ""
                    padIndex = 0
                    updatePadDisplay()
                }
            }
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(screenReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(screenReceiver, filter)
        }
    }

    private fun navigatePad(delta: Int) {
        padIndex = (padIndex + delta + items.size) % items.size
        updatePadDisplay()
        tts.speak(items[padIndex].speakLabel())
    }

    private fun activatePad() {
        val item = items[padIndex]
        when (item.key) {
            NumberPadKey.DIGIT -> {
                if (pinBuffer.length >= LockPinStore.MAX_PIN_LENGTH) {
                    feedbackError()
                    tts.speak("Maximum ${LockPinStore.MAX_PIN_LENGTH} számjegy.")
                    return
                }
                pinBuffer += item.value
                updatePadDisplay()
                sounds.play(SoundType.MENU_NAV)
                vibrate(25)
                tts.speak(NumberPadHelper.speakPinDigitEntered(pinBuffer))
            }
            NumberPadKey.CLEAR -> {
                pinBuffer = NumberPadHelper.clear()
                updatePadDisplay()
                sounds.play(SoundType.ACTION_OK)
                tts.speak("Teljes bevitel törölve.")
            }
            NumberPadKey.CONFIRM -> submitPin()
            else -> Unit
        }
    }

    private fun backspacePad() {
        if (pinBuffer.isEmpty()) {
            feedbackError()
            tts.speak("Add meg a PIN kódot a feloldáshoz.")
            return
        }
        pinBuffer = NumberPadHelper.backspace(pinBuffer)
        updatePadDisplay()
        sounds.play(SoundType.SWIPE_LEFT)
        tts.speak(NumberPadHelper.speakPinBackspace(pinBuffer))
    }

    private fun submitPin() {
        if (pinBuffer.length < LockPinStore.MIN_PIN_LENGTH) {
            feedbackError()
            tts.speak("Legalább ${LockPinStore.MIN_PIN_LENGTH} számjegy szükséges.")
            return
        }
        if (LockPinStore.verifyPin(this, pinBuffer)) {
            LockSession.unlock()
            pinBuffer = ""
            feedbackSuccess()
            tts.speakThen("PIN helyes. Super DL feloldva.") {
                finish()
            }
        } else {
            pinBuffer = ""
            padIndex = 0
            updatePadDisplay()
            feedbackError()
            tts.speak("Helytelen PIN. Próbáld újra.")
            tts.speakAdd(items.first().speakLabel())
        }
    }

    private fun updatePadDisplay() {
        val item = items[padIndex]
        tvItem.text = item.label
        tvPosition.text = "Zárolás  •  ${padIndex + 1} / ${items.size}"
        val lengthHint = if (pinBuffer.isEmpty()) "" else "  •  ${pinBuffer.length} számjegy"
        tvHint.text = "⬆⬇ ${item.label}$lengthHint  •  ➡ beír  •  ⬅ egy törlés"
    }

    private fun feedbackSwipeUp() {
        sounds.play(SoundType.SWIPE_UP)
        vibrate(30)
    }

    private fun feedbackSwipeDown() {
        sounds.play(SoundType.SWIPE_DOWN)
        vibrate(30)
    }

    private fun feedbackSwipeLeft() {
        sounds.play(SoundType.SWIPE_LEFT)
        vibrate(40)
    }

    private fun feedbackSwipeRight() {
        sounds.play(SoundType.SWIPE_RIGHT)
        vibrate(60)
    }

    private fun feedbackSuccess() = sounds.play(SoundType.ACTION_OK)

    private fun feedbackError() = sounds.play(SoundType.ACTION_ERROR)

    private fun vibrate(ms: Long) {
        val v = vibrator ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            v.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION")
            v.vibrate(ms)
        }
    }
}