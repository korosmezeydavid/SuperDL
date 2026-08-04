package com.superdl.launcher.medication

import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager
import androidx.appcompat.app.AppCompatActivity
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsEngineStore
import java.util.Locale

class MedicationAlertActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_HOUR = "medication_alert_hour"
        const val EXTRA_MINUTE = "medication_alert_minute"
        const val EXTRA_REMINDER_IDS = "medication_alert_reminder_ids"
        private const val REPEAT_DELAY_MS = 12_000L
    }

    private val handler = Handler(Looper.getMainLooper())
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var dueReminders: List<MedicationReminder> = emptyList()
    private lateinit var gestureListener: SwipeGestureListener
    private val actions = MedicationAlarmAction.entries.toList()
    private var actionIndex = 0

    private var initTtsRunnable: Runnable? = null
    private var finishRunnable: Runnable? = null

    private val repeatRunnable = object : Runnable {
        override fun run() {
            if (isFinishing || isDestroyed) return
            speakAlert()
            handler.postDelayed(this, REPEAT_DELAY_MS)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
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

        dueReminders = loadDueReminders()
        if (dueReminders.isEmpty()) {
            MedicationAlertService.stop(this)
            finish()
            return
        }

        val root = View(this)
        setContentView(root)
        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = { navigateAction(-1) },
            onSwipeDown = { navigateAction(+1) },
            onSwipeRight = { activateAction() },
            onSwipeLeft = { dismissAlert() }
        )
        root.setOnTouchListener { _, event ->
            gestureListener.detector.onTouchEvent(event)
            true
        }
        initTtsRunnable = Runnable {
            if (!isFinishing && !isDestroyed) initTts()
        }
        handler.postDelayed(initTtsRunnable!!, 600L)
    }

    override fun onDestroy() {
        initTtsRunnable?.let { handler.removeCallbacks(it) }
        initTtsRunnable = null
        finishRunnable?.let { handler.removeCallbacks(it) }
        finishRunnable = null
        handler.removeCallbacks(repeatRunnable)
        handler.removeCallbacksAndMessages(null)
        tts?.stop()
        tts?.shutdown()
        tts = null
        super.onDestroy()
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.action == KeyEvent.ACTION_DOWN &&
            (event.keyCode == KeyEvent.KEYCODE_VOLUME_UP || event.keyCode == KeyEvent.KEYCODE_VOLUME_DOWN)
        ) {
            dismissAlert()
            return true
        }
        return super.dispatchKeyEvent(event)
    }

    private fun loadDueReminders(): List<MedicationReminder> {
        val ids = intent.getIntArrayExtra(EXTRA_REMINDER_IDS)
        if (ids != null && ids.isNotEmpty()) {
            return ids.toList().mapNotNull { id -> MedicationStore.getById(this, id) }
                .filter { reminder -> reminder.enabled }
        }
        val hour = intent.getIntExtra(EXTRA_HOUR, -1)
        val minute = intent.getIntExtra(EXTRA_MINUTE, -1)
        if (hour < 0 || minute < 0) return emptyList()
        return MedicationStore.getDueAt(this, hour, minute)
    }

    private fun initTts() {
        val enginePackage = TtsEngineStore.getSelectedPackage(this)
        val listener = TextToSpeech.OnInitListener { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.setLanguage(Locale("hu", "HU"))
                ttsReady = true
                speakAlert()
                speakActionHint()
                handler.postDelayed(repeatRunnable, REPEAT_DELAY_MS)
            } else {
                finish()
            }
        }
        tts = if (enginePackage.isNullOrBlank()) {
            TextToSpeech(this, listener)
        } else {
            TextToSpeech(this, listener, enginePackage)
        }
    }

    private fun speakAlert() {
        if (!ttsReady || dueReminders.isEmpty()) return
        val message = MedicationSpeech.alertMessage(dueReminders)
        tts?.speak(message, TextToSpeech.QUEUE_FLUSH, null, "medication_alert_${System.currentTimeMillis()}")
    }

    private fun speakActionHint() {
        if (!ttsReady) return
        tts?.speak(
            "${actions[actionIndex].label}. Söpörj fel-le választás, jobbra végrehajtás, balra bezárás.",
            TextToSpeech.QUEUE_ADD,
            null,
            "medication_alert_hint_${System.currentTimeMillis()}"
        )
    }

    private fun navigateAction(delta: Int) {
        actionIndex = (actionIndex + delta + actions.size) % actions.size
        if (ttsReady) {
            tts?.speak(
                actions[actionIndex].label,
                TextToSpeech.QUEUE_FLUSH,
                null,
                "medication_alert_nav_${System.currentTimeMillis()}"
            )
        }
    }

    private fun activateAction() {
        handler.removeCallbacks(repeatRunnable)
        when (actions[actionIndex]) {
            MedicationAlarmAction.REMIND_ONE_HOUR -> {
                MedicationAlertService.stop(this)
                MedicationScheduler.scheduleSnoozeOneHour(this, dueReminders)
                val names = dueReminders.joinToString(", ") { it.name }
                speakThenFinish("Emlékeztető egy óra múlva: $names.")
            }
            MedicationAlarmAction.MARK_COMPLETE -> confirmIntake()
        }
    }

    private fun confirmIntake() {
        MedicationAlertService.stop(this)
        MedicationStore.logIngestion(this, dueReminders)
        MedicationScheduler.rescheduleAfterTrigger(this, dueReminders)
        speakThenFinish("Gyógyszer bevétele megerősítve.")
    }

    private fun dismissAlert() {
        handler.removeCallbacks(repeatRunnable)
        MedicationAlertService.stop(this)
        speakThenFinish("Gyógyszer emlékeztető bezárva.")
    }

    private fun speakThenFinish(message: String) {
        if (ttsReady) {
            tts?.speak(message, TextToSpeech.QUEUE_FLUSH, null, "medication_alert_done_${System.currentTimeMillis()}")
            finishRunnable?.let { handler.removeCallbacks(it) }
            val runnable = Runnable { if (!isFinishing && !isDestroyed) finish() }
            finishRunnable = runnable
            handler.postDelayed(runnable, 2_500L)
        } else {
            finish()
        }
    }
}