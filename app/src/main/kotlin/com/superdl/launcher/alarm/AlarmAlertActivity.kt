package com.superdl.launcher.alarm

import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.superdl.launcher.R
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager

/**
 * Az ébresztő megszólalásakor felugró képernyő (a hangot az AlarmService adja).
 * Bemondja az ébresztő nevét a hang mellett, majd:
 *  - jobbra söprés = szundi (ha engedélyezett), 10 perc múlva újra
 *  - balra söprés = leállítás
 * Zárolt képernyőn is megjelenik.
 */
class AlarmAlertActivity : AppCompatActivity() {

    private lateinit var tts: TtsManager
    private lateinit var gestureListener: SwipeGestureListener

    private var alarmId = -1
    private var label = "Ébresztő"
    private var toneUri: String? = null
    private var snoozeEnabled = true

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        showOnLockedScreen()
        setContentView(R.layout.activity_media_player)
        applyImmersive()

        alarmId = intent.getIntExtra(EXTRA_ALARM_ID, -1)
        label = intent.getStringExtra(EXTRA_LABEL)?.takeIf { it.isNotBlank() } ?: "Ébresztő"
        toneUri = intent.getStringExtra(EXTRA_TONE_URI)
        snoozeEnabled = intent.getBooleanExtra(EXTRA_SNOOZE_ENABLED, true)

        findViewById<TextView>(R.id.tvPlayerTitle).text = label
        findViewById<TextView>(R.id.tvPlayerPosition).text = "Ébresztő"
        findViewById<TextView>(R.id.tvPlayerStatus).text = ""
        findViewById<TextView>(R.id.tvPlayerHint).text = if (snoozeEnabled) {
            "Jobbra: szundi. Balra: leállítás."
        } else {
            "Balra: leállítás."
        }

        tts = TtsManager(this)
        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = { announce() },
            onSwipeDown = { announce() },
            onSwipeRight = { if (snoozeEnabled) snooze() else announce() },
            onSwipeLeft = { dismissAlarm() }
        )

        // Hangos, ismételt bemondás a hang fölött (a hangot nem nyomja el, csak kíséri).
        tts.runWhenReady { announce() }
    }

    private fun announce() {
        tts.speak("$label. Ébresztő. ${if (snoozeEnabled) "Jobbra szundi, balra leállítás." else "Balra leállítás."}")
    }

    private fun snooze() {
        stopAlarmSound()
        AlarmScheduler.scheduleSnooze(this, alarmId, label, toneUri, snoozeEnabled)
        tts.speakThen("Szundi. 10 perc múlva újra.") { finish() }
    }

    private fun dismissAlarm() {
        stopAlarmSound()
        // Egyszeri ébresztőnél kikapcsoljuk; ismétlődőnél a következő alkalom már be van ütemezve.
        AlarmScheduler.onAlarmDismissed(this, alarmId)
        tts.speakThen("Ébresztő leállítva.") { finish() }
    }

    private fun stopAlarmSound() {
        val stop = Intent(this, AlarmService::class.java).apply {
            action = AlarmService.ACTION_STOP
        }
        try {
            startService(stop)
        } catch (_: Exception) {
        }
    }

    private fun showOnLockedScreen() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                    WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON or
                    WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
            )
        }
    }

    private fun applyImmersive() {
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            )
    }

    override fun onTouchEvent(event: MotionEvent): Boolean =
        gestureListener.detector.onTouchEvent(event) || super.onTouchEvent(event)

    override fun onDestroy() {
        tts.shutdown()
        super.onDestroy()
    }

    companion object {
        const val EXTRA_ALARM_ID = "alarm_id"
        const val EXTRA_LABEL = "label"
        const val EXTRA_TONE_URI = "tone_uri"
        const val EXTRA_SNOOZE_ENABLED = "snooze_enabled"
    }
}
