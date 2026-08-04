package com.superdl.launcher.calendar

import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.WindowManager
import android.speech.tts.TextToSpeech
import android.view.KeyEvent
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsEngineStore
import java.util.Locale

class CalendarAlertActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_EVENT_ID = CalendarAlarmReceiver.EXTRA_EVENT_ID
        const val EXTRA_TITLE = CalendarAlarmReceiver.EXTRA_TITLE
        const val EXTRA_BEGIN_MS = CalendarAlarmReceiver.EXTRA_BEGIN_MS
        const val EXTRA_END_MS = CalendarAlarmReceiver.EXTRA_END_MS
        private const val REPEAT_DELAY_MS = 12_000L
    }

    private val handler = Handler(Looper.getMainLooper())
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private lateinit var gestureListener: SwipeGestureListener
    private lateinit var event: CalendarEvent
    private val actions = CalendarAlarmAction.entries.toList()
    private var actionIndex = 0

    private var initTtsRunnable: Runnable? = null
    private var finishRunnable: Runnable? = null

    private val repeatRunnable = object : Runnable {
        override fun run() {
            if (isFinishing || isDestroyed) return
            speakPrompt()
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

        val eventId = intent.getLongExtra(EXTRA_EVENT_ID, -1L)
        if (eventId < 0L) {
            CalendarAlarmService.stop(this)
            finish()
            return
        }
        val title = intent.getStringExtra(EXTRA_TITLE).orEmpty()
        val beginMs = intent.getLongExtra(EXTRA_BEGIN_MS, 0L)
        val endMs = intent.getLongExtra(EXTRA_END_MS, 0L)
        event = CalendarEvent(eventId, title, beginMs, endMs)

        val root = View(this)
        setContentView(root)
        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = { navigateAction(-1) },
            onSwipeDown = { navigateAction(+1) },
            onSwipeRight = { activateAction() },
            onSwipeLeft = { dismissAlert() }
        )
        root.setOnTouchListener { _, motion ->
            gestureListener.detector.onTouchEvent(motion)
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

    private fun initTts() {
        val enginePackage = TtsEngineStore.getSelectedPackage(this)
        val listener = TextToSpeech.OnInitListener { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.setLanguage(Locale("hu", "HU"))
                ttsReady = true
                speakPrompt()
                speakAction()
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

    private fun speakPrompt() {
        if (!ttsReady) return
        tts?.speak(
            CalendarHelper.speakAlarmPrompt(event),
            TextToSpeech.QUEUE_FLUSH,
            null,
            "calendar_alert_prompt_${System.currentTimeMillis()}"
        )
    }

    private fun speakAction() {
        if (!ttsReady) return
        tts?.speak(
            actions[actionIndex].label,
            TextToSpeech.QUEUE_ADD,
            null,
            "calendar_alert_action_${System.currentTimeMillis()}"
        )
    }

    private fun navigateAction(delta: Int) {
        actionIndex = (actionIndex + delta + actions.size) % actions.size
        if (ttsReady) {
            tts?.speak(
                actions[actionIndex].label,
                TextToSpeech.QUEUE_FLUSH,
                null,
                "calendar_alert_nav_${System.currentTimeMillis()}"
            )
        }
    }

    private fun activateAction() {
        handler.removeCallbacks(repeatRunnable)
        when (actions[actionIndex]) {
            CalendarAlarmAction.REMIND_ONE_HOUR -> {
                CalendarAlarmService.stop(this)
                CalendarReminderScheduler.scheduleSnoozeOneHour(
                    this,
                    event.eventId,
                    event.title,
                    event.begin,
                    event.end
                )
                speakThenFinish("Emlékeztető egy óra múlva: ${event.title}.")
            }
            CalendarAlarmAction.MARK_COMPLETE -> {
                CalendarAlarmService.stop(this)
                CalendarReminderScheduler.cancelInstance(this, event.eventId, event.begin)
                CalendarReminderStore.markCompleted(this, event.eventId, event.begin)
                speakThenFinish("${event.title} teljesítettként megjelölve.")
            }
        }
    }

    private fun dismissAlert() {
        handler.removeCallbacks(repeatRunnable)
        CalendarAlarmService.stop(this)
        speakThenFinish("Program emlékeztető bezárva.")
    }

    private fun speakThenFinish(message: String) {
        if (ttsReady) {
            tts?.speak(message, TextToSpeech.QUEUE_FLUSH, null, "calendar_alert_done_${System.currentTimeMillis()}")
            finishRunnable?.let { handler.removeCallbacks(it) }
            val runnable = Runnable { if (!isFinishing && !isDestroyed) finish() }
            finishRunnable = runnable
            handler.postDelayed(runnable, 2_500L)
        } else {
            finish()
        }
    }
}