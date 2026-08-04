package com.superdl.launcher.files

import android.app.Activity
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.MotionEvent
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.TextView
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager

/**
 * A "Hol a telóm?" csörgetés leállítása a TELEFONON.
 *
 * Amikor a portálról elindul a csörgetés, ez a képernyő jön elő, hogy a
 * megtaláló a készüléken is le tudja állítani — ne kelljen visszamenni a
 * számítógéphez.
 *
 * KÉT jobbra söprés kell a leállításhoz: az első jelzi a szándékot, a második
 * megerősíti. Így egy véletlen mozdulat (zsebben, táskában) nem hallgattatja el
 * a csörgést, ami épp a megtalálást szolgálja.
 *
 * Zárolt képernyőn is megjelenik, és felébreszti a kijelzőt.
 */
class FindPhoneStopActivity : Activity() {

    private lateinit var tts: TtsManager
    private lateinit var gestureListener: SwipeGestureListener
    private lateinit var label: TextView
    private var confirmStep = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        showOverLockScreen()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(Color.BLACK)
            setPadding(48, 48, 48, 48)
        }
        label = TextView(this).apply {
            text = getString(com.superdl.launcher.R.string.find_phone_stop_hint)
            textSize = 28f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        }
        root.addView(label)
        setContentView(root)

        tts = TtsManager(this)
        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = { speakHint() },
            onSwipeDown = { speakHint() },
            onSwipeRight = { onConfirmStep() },
            onSwipeLeft = { speakHint() }
        )

        tts.speak(
            "A telefon csörög. Megvan? Söpörj jobbra kétszer a leállításhoz."
        )
    }

    private fun speakHint() {
        confirmStep = 0
        tts.speak("Söpörj jobbra kétszer, ha megtaláltad a telefont.")
    }

    private fun onConfirmStep() {
        confirmStep++
        if (confirmStep == 1) {
            label.text = getString(com.superdl.launcher.R.string.find_phone_stop_confirm)
            tts.speak("Még egyszer jobbra a megerősítéshez.")
            return
        }
        // Második söprés: tényleg megvan.
        FindPhoneHelper.stop(this)
        tts.speak("Csörgetés leállítva. Örülök, hogy megvan!")
        finish()
    }

    override fun onTouchEvent(event: MotionEvent): Boolean =
        gestureListener.detector.onTouchEvent(event) || super.onTouchEvent(event)

    private fun showOverLockScreen() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                    WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
            )
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    override fun onDestroy() {
        try {
            tts.shutdown()
        } catch (_: Exception) {
        }
        super.onDestroy()
    }
}
