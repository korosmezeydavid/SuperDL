package com.superdl.launcher.call

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.telephony.TelephonyManager
import com.superdl.launcher.util.cancelUiCallbacks
import android.view.View
import android.view.accessibility.AccessibilityNodeInfo
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.accessibility.AccessibilityNodeInfoCompat
import com.superdl.launcher.R
import com.superdl.launcher.contacts.ContactHelper
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.input.NumberPadHelper
import com.superdl.launcher.input.NumberPadKey
import com.superdl.launcher.tts.TtsManager

class InCallActivity : AppCompatActivity() {

    private enum class InCallPanel {
        STATUS,
        KEYPAD,
        CONTROLS
    }

    private lateinit var tvName: TextView
    private lateinit var tvNumber: TextView
    private lateinit var tvStatus: TextView
    private lateinit var tvHint: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gestureListener: SwipeGestureListener
    private val handler = Handler(Looper.getMainLooper())
    private var callStarted = false
    private var placedAt = 0L
    private var launchedAt = 0L
    private var seenOffhook = false
    private var connectedAt = 0L
    private var callState = TelephonyManager.CALL_STATE_IDLE
    private var durationRunnable: Runnable? = null
    private var phone = ""
    private var displayName = ""

    private var mode = MODE_OUTGOING
    private var panel = InCallPanel.STATUS
    private var keypadItems = NumberPadHelper.dtmfItems
    private var keypadIndex = 0
    private var speakerOn = false
    private var micMuted = false

    private var callStateWatcher: CallStateWatcher? = null
    private var endCallCheckRunnable: Runnable? = null
    private var endCallRetryRunnable: Runnable? = null
    private var bringToFrontRunnable: Runnable? = null
    private var endCallAttemptCount = 0
    private var endingCall = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        applyLockScreenFlags()
        setContentView(R.layout.activity_in_call)
        applyImmersive()
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvName = findViewById(R.id.tvCallName)
        tvNumber = findViewById(R.id.tvCallNumber)
        tvStatus = findViewById(R.id.tvCallStatus)
        tvHint = findViewById(R.id.tvCallHint)

        phone = intent.getStringExtra(EXTRA_PHONE).orEmpty()
        displayName = intent.getStringExtra(EXTRA_NAME).orEmpty().ifBlank { "Ismeretlen" }
        mode = intent.getStringExtra(EXTRA_MODE) ?: MODE_OUTGOING
        launchedAt = SystemClock.elapsedRealtime()
        CallSession.markInCallUiStarted(incomingHandoff = mode == MODE_INCOMING)

        tvName.text = displayName
        tvNumber.text = ContactHelper.maskPhone(phone)
        tvStatus.text = when (mode) {
            MODE_INCOMING -> getString(R.string.call_status_connecting)
            else -> getString(R.string.call_status_dialing)
        }
        updateHint()
        bindAccessibility()

        tts = TtsManager(this)
        sounds = SoundFeedback(this)

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = { onSwipeUp() },
            onSwipeDown = { onSwipeDown() },
            onSwipeRight = { onSwipeRight() },
            onSwipeLeft = { onSwipeLeft() }
        )

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = onUserEndRequest()
        })

        findViewById<View>(R.id.rootLayout).setOnTouchListener { _, event ->
            gestureListener.detector.onTouchEvent(event)
            true
        }

        if (phone.isBlank()) {
            speakAndFinishCall("Érvénytelen telefonszám.")
            return
        }

        registerPhoneListener()

        when (mode) {
            MODE_INCOMING -> {
                callStarted = true
                tts.speakThen("Hívás fogadva: $displayName.") { speakPanelIntro() }
            }
            else -> {
                if (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE)
                    != PackageManager.PERMISSION_GRANTED
                ) {
                    speakAndFinishCall("Hívás engedély szükséges.")
                    return
                }
                tts.speakThen("Hívás indítása: $displayName.") {
                    if (!CallHelper.placeCall(this, phone)) {
                        speakAndFinishCall("Hívás indítása sikertelen.")
                    } else {
                        callStarted = true
                        placedAt = SystemClock.elapsedRealtime()
                    }
                }
            }
        }
    }

    private fun onSwipeUp() {
        sounds.play(SoundType.SWIPE_UP)
        when (panel) {
            InCallPanel.STATUS -> speakStatus()
            InCallPanel.KEYPAD -> navigateKeypad(-1)
            InCallPanel.CONTROLS -> {
                val speakerLabel = if (speakerOn) "bekapcsolva" else "kikapcsolva"
                val micLabel = if (micMuted) "némítva" else "bekapcsolva"
                tts.speak("Kihangosítás $speakerLabel. Mikrofon $micLabel.")
            }
        }
    }

    private fun onSwipeDown() {
        sounds.play(SoundType.SWIPE_DOWN)
        when (panel) {
            InCallPanel.STATUS -> {
                panel = InCallPanel.KEYPAD
                keypadIndex = 0
                updateHint()
                tts.speak("DTMF billentyűzet. ${keypadItems[keypadIndex].speakLabel()}.")
            }
            InCallPanel.KEYPAD -> navigateKeypad(+1)
            InCallPanel.CONTROLS -> toggleMicMute()
        }
    }

    private fun onSwipeRight() {
        sounds.play(SoundType.SWIPE_RIGHT)
        when (panel) {
            InCallPanel.STATUS -> openControlsPanel()
            InCallPanel.KEYPAD -> pressKeypadDigit()
            InCallPanel.CONTROLS -> toggleSpeaker()
        }
    }

    private fun onSwipeLeft() {
        sounds.play(SoundType.SWIPE_LEFT)
        onUserEndRequest()
    }

    private fun navigateKeypad(delta: Int) {
        keypadIndex = (keypadIndex + delta + keypadItems.size) % keypadItems.size
        tts.speak(keypadItems[keypadIndex].speakLabel())
    }

    private fun pressKeypadDigit() {
        val item = keypadItems[keypadIndex]
        if (item.key != NumberPadKey.DIGIT && item.key != NumberPadKey.OPERATOR) return
        val digit = item.value.firstOrNull() ?: return
        if (CallHelper.sendDtmfTone(this, digit)) {
            tts.speak("${item.speakLabel()} elküldve.")
        } else {
            tts.speak("A hangjel nem sikerült.")
        }
    }

    private fun toggleSpeaker() {
        speakerOn = !speakerOn
        CallHelper.setSpeakerphone(this, speakerOn)
        tts.speak(if (speakerOn) "Kihangosítás bekapcsolva." else "Kihangosítás kikapcsolva.")
    }

    private fun toggleMicMute() {
        micMuted = !micMuted
        CallHelper.setMicrophoneMute(this, micMuted)
        tts.speak(if (micMuted) "Mikrofon némítva." else "Mikrofon visszakapcsolva.")
    }

    private fun openControlsPanel() {
        panel = InCallPanel.CONTROLS
        updateHint()
        val speakerLabel = if (speakerOn) "bekapcsolva" else "kikapcsolva"
        val micLabel = if (micMuted) "némítva" else "bekapcsolva"
        tts.speak(
            "Hívás vezérlők. Fel: állapot felolvasás. Le: mikrofon némítás. " +
                "Jobbra: kihangosítás váltás, jelenleg $speakerLabel. " +
                "Balra: vissza. Mikrofon jelenleg $micLabel."
        )
    }

    private fun speakPanelIntro() {
        tts.speakAdd(
            "Fel: állapot. Le: DTMF billentyűzet ügyfélszolgálathoz. " +
                "Jobbra: kihangosítás és mikrofon. Balra: hívás befejezése, bármelyik módban."
        )
    }

    private fun updateHint() {
        tvHint.text = when (panel) {
            InCallPanel.STATUS -> getString(R.string.in_call_hint)
            InCallPanel.KEYPAD -> getString(R.string.in_call_keypad_hint)
            InCallPanel.CONTROLS -> getString(R.string.in_call_controls_hint)
        }
    }

    private fun registerPhoneListener() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_PHONE_STATE)
            != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.READ_PHONE_STATE),
                READ_PHONE_STATE_REQUEST
            )
            return
        }
        callStateWatcher = CallStateWatcher(this) { state ->
            if (!isFinishing && !isDestroyed) handleCallState(state)
        }.also { it.register() }
    }

    private fun unregisterPhoneListener() {
        callStateWatcher?.unregister()
        callStateWatcher = null
    }

    private fun handleCallState(state: Int) {
        if (callState == state) return
        callState = state
        when (state) {
            TelephonyManager.CALL_STATE_OFFHOOK -> onConnected()
            TelephonyManager.CALL_STATE_IDLE -> onIdle()
            TelephonyManager.CALL_STATE_RINGING -> {
                tvStatus.text = getString(R.string.call_status_ringing)
            }
        }
    }

    private fun onConnected() {
        seenOffhook = true
        CallSession.markOffhookConfirmed()
        if (connectedAt > 0L) return
        connectedAt = SystemClock.elapsedRealtime()
        tvStatus.text = getString(R.string.call_status_connected)
        sounds.play(SoundType.ACTION_OK)
        tts.speak("Kapcsolódva.")
        if (mode != MODE_INCOMING) {
            speakPanelIntro()
        }
        startDurationUpdates()
        updateAccessibilityPaneTitle()
    }

    private fun onIdle() {
        if (!callStarted) return
        if (!seenOffhook) {
            val elapsed = SystemClock.elapsedRealtime() - if (mode == MODE_INCOMING) {
                launchedAt
            } else {
                placedAt
            }
            if (elapsed < IDLE_GRACE_MS) return
            stopDurationUpdates()
            unregisterPhoneListener()
            speakAndFinishCall("A hívás nem jött létre.")
            return
        }
        stopDurationUpdates()
        unregisterPhoneListener()
        endingCall = false
        endCallAttemptCount = 0
        endCallCheckRunnable?.let { handler.removeCallbacks(it) }
        endCallRetryRunnable?.let { handler.removeCallbacks(it) }
        val duration = formatDuration(currentDurationSeconds())
        tvStatus.text = getString(R.string.call_status_ended)
        sounds.play(SoundType.SWIPE_LEFT)
        speakAndFinishCall("Hívás vége. Időtartam: $duration.")
    }

    private fun onUserEndRequest() {
        if (!callStarted) {
            finishCallUi()
            return
        }
        if (callState == TelephonyManager.CALL_STATE_IDLE && !seenOffhook) {
            if (SystemClock.elapsedRealtime() - launchedAt < IDLE_GRACE_MS) return
            finishCallUi()
            return
        }
        if (callState == TelephonyManager.CALL_STATE_IDLE) {
            finishCallUi()
            return
        }

        endingCall = true
        endCallAttemptCount++
        val attempted = CallHelper.endCallAggressive(this)
        scheduleEndCallVerification()

        if (attempted) {
            if (endCallAttemptCount == 1) {
                tts.speak("Hívás befejezése.")
            } else {
                tts.speak("Hívás befejezése, újrapróbálás.")
            }
            return
        }

        if (endCallAttemptCount < MAX_END_CALL_ATTEMPTS) {
            scheduleEndCallRetry()
            return
        }

        tts.speak(
            "A hívás befejezése nem sikerült automatikusan. " +
                "Próbáld újra balra pöccintéssel, vagy használd a telefon befejezés gombját."
        )
    }

    private fun scheduleEndCallRetry() {
        endCallRetryRunnable?.let { handler.removeCallbacks(it) }
        val runnable = Runnable {
            if (isFinishing || isDestroyed || !endingCall) return@Runnable
            if (callState == TelephonyManager.CALL_STATE_IDLE) {
                finishCallUi()
                return@Runnable
            }
            onUserEndRequest()
        }
        endCallRetryRunnable = runnable
        handler.postDelayed(runnable, END_CALL_RETRY_MS)
    }

    private fun scheduleEndCallVerification() {
        endCallCheckRunnable?.let { handler.removeCallbacks(it) }
        val runnable = Runnable {
            if (isFinishing || isDestroyed) return@Runnable
            if (callState == TelephonyManager.CALL_STATE_IDLE || !callStarted) {
                endingCall = false
                finishCallUi()
                return@Runnable
            }
            if (endingCall && endCallAttemptCount < MAX_END_CALL_ATTEMPTS) {
                CallHelper.endCallAggressive(this@InCallActivity)
                scheduleEndCallRetry()
            }
        }
        endCallCheckRunnable = runnable
        handler.postDelayed(runnable, END_CALL_VERIFY_MS)
    }

    private fun applyLockScreenFlags() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(
                android.view.WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                    android.view.WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
            )
        }
    }

    private fun speakStatus() {
        val status = when (callState) {
            TelephonyManager.CALL_STATE_OFFHOOK -> {
                val duration = formatDuration(currentDurationSeconds())
                val extras = buildList {
                    add("Kapcsolódva. Időtartam: $duration.")
                    if (speakerOn) add("Kihangosítás be.")
                    if (micMuted) add("Mikrofon némítva.")
                }
                extras.joinToString(" ")
            }
            TelephonyManager.CALL_STATE_RINGING -> "Csengés."
            TelephonyManager.CALL_STATE_IDLE -> "Nincs aktív hívás."
            else -> tvStatus.text.toString()
        }
        tts.speak(status)
    }

    private fun startDurationUpdates() {
        stopDurationUpdates()
        durationRunnable = object : Runnable {
            override fun run() {
                if (isFinishing || isDestroyed) return
                tvStatus.text = getString(
                    R.string.call_status_duration,
                    formatDuration(currentDurationSeconds())
                )
                handler.postDelayed(this, 1000L)
            }
        }
        durationRunnable?.let { handler.post(it) }
    }

    private fun stopDurationUpdates() {
        durationRunnable?.let { handler.removeCallbacks(it) }
        durationRunnable = null
    }

    private fun currentDurationSeconds(): Int {
        if (connectedAt <= 0L) return 0
        return ((SystemClock.elapsedRealtime() - connectedAt) / 1000L).toInt()
    }

    private fun formatDuration(totalSeconds: Int): String {
        if (totalSeconds <= 0) return "0 másodperc"
        val mins = totalSeconds / 60
        val secs = totalSeconds % 60
        return when {
            mins > 0 && secs > 0 -> "$mins perc $secs másodperc"
            mins > 0 -> "$mins perc"
            else -> "$secs másodperc"
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == READ_PHONE_STATE_REQUEST &&
            grantResults.isNotEmpty() &&
            grantResults[0] == PackageManager.PERMISSION_GRANTED
        ) {
            registerPhoneListener()
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

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        phone = intent.getStringExtra(EXTRA_PHONE).orEmpty().ifBlank { phone }
        displayName = intent.getStringExtra(EXTRA_NAME).orEmpty().ifBlank { displayName }
        mode = intent.getStringExtra(EXTRA_MODE) ?: mode
        launchedAt = SystemClock.elapsedRealtime()
        CallSession.markInCallUiStarted(incomingHandoff = mode == MODE_INCOMING)
        tvName.text = displayName
        tvNumber.text = ContactHelper.maskPhone(phone)
        updateAccessibilityPaneTitle()
    }

    override fun onResume() {
        super.onResume()
        applyLockScreenFlags()
        applyImmersive()
        if (callStarted && seenOffhook) {
            updateAccessibilityPaneTitle()
        }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (!hasFocus && callStarted && CallSession.isInCallUiActive) {
            bringToFrontRunnable?.let { handler.removeCallbacks(it) }
            val runnable = Runnable {
                bringToFrontRunnable = null
                if (callStarted && CallSession.isInCallUiActive && !isFinishing && !isDestroyed) {
                    CallHelper.bringInCallToFront(this)
                }
            }
            bringToFrontRunnable = runnable
            handler.postDelayed(runnable, 150L)
        }
    }

    override fun onDestroy() {
        stopDurationUpdates()
        endCallCheckRunnable?.let { handler.removeCallbacks(it) }
        endCallRetryRunnable?.let { handler.removeCallbacks(it) }
        bringToFrontRunnable?.let { handler.removeCallbacks(it) }
        endCallCheckRunnable = null
        endCallRetryRunnable = null
        bringToFrontRunnable = null
        endingCall = false
        endCallAttemptCount = 0
        cancelUiCallbacks(handler)
        unregisterPhoneListener()
        panel = InCallPanel.STATUS
        keypadIndex = 0
        CallHelper.setSpeakerphone(this, false)
        CallHelper.setMicrophoneMute(this, false)
        CallHelper.restoreDefaultAudioRoute(this)
        CallSession.markInCallUiEnded()
        tts.shutdown()
        if (::sounds.isInitialized) sounds.release()
        super.onDestroy()
    }

    /**
     * Bemondja az üzenetet, majd bezárja a hívás-képernyőt.
     *
     * BIZTONSÁGI HÁLÓ: korábban a bezárás KIZÁRÓLAG a beszéd befejezésének
     * visszajelzésére várt (speakThen { finishCallUi() }). Ha az a visszajelzés
     * elmaradt — megszakadt beszéd, elveszett jelzés, néma TTS —, a képernyő
     * OTT RAGADT a hívás után, és csak balra söpréssel lehetett kilépni.
     * Most egy időzítő is bezár, ha a beszéd nem jelentkezik időben. Akármelyik
     * ág fut le előbb, a bezárás CSAK EGYSZER történik meg.
     */
    private fun speakAndFinishCall(message: String, timeoutMs: Long = 4000L) {
        var closed = false
        val closeOnce = {
            if (!closed) {
                closed = true
                finishCallUi()
            }
        }
        try {
            tts.speakThen(message) { closeOnce() }
        } catch (e: Exception) {
            android.util.Log.w("SDL_CALL", "TTS hiba a hivas vegen: ${e.message}")
            closeOnce()
            return
        }
        handler.postDelayed({ closeOnce() }, timeoutMs)
    }

    private fun finishCallUi() {
        callStarted = false
        panel = InCallPanel.STATUS
        keypadIndex = 0
        CallHelper.setSpeakerphone(this, false)
        CallHelper.setMicrophoneMute(this, false)
        CallSession.markInCallUiEnded()
        finish()
    }

    private fun bindAccessibility() {
        val root = findViewById<View>(R.id.rootLayout)
        root.contentDescription = getString(R.string.in_call_screen_desc, displayName)
        ViewCompat.setAccessibilityPaneTitle(root, getString(R.string.in_call_pane_title, displayName))

        tvName.contentDescription = getString(R.string.in_call_caller_name_desc, displayName)
        tvNumber.contentDescription = getString(R.string.in_call_caller_number_desc, tvNumber.text)
        tvStatus.contentDescription = getString(R.string.in_call_status_desc)
        tvHint.contentDescription = getString(R.string.in_call_hint_desc)

        ViewCompat.addAccessibilityAction(
            root,
            getString(R.string.in_call_action_mute)
        ) { _, _ ->
            toggleMicMute()
            true
        }
        ViewCompat.addAccessibilityAction(
            root,
            getString(R.string.in_call_action_speaker)
        ) { _, _ ->
            toggleSpeaker()
            true
        }
        ViewCompat.addAccessibilityAction(
            root,
            getString(R.string.in_call_action_keypad)
        ) { _, _ ->
            panel = InCallPanel.KEYPAD
            keypadIndex = 0
            updateHint()
            tts.speak("DTMF billentyűzet. ${keypadItems[keypadIndex].speakLabel()}.")
            true
        }
        ViewCompat.addAccessibilityAction(
            root,
            getString(R.string.in_call_action_end)
        ) { _, _ ->
            onUserEndRequest()
            true
        }
        ViewCompat.addAccessibilityAction(
            root,
            getString(R.string.in_call_action_status)
        ) { _, _ ->
            speakStatus()
            true
        }

        root.accessibilityDelegate = object : View.AccessibilityDelegate() {
            override fun onInitializeAccessibilityNodeInfo(host: View, info: AccessibilityNodeInfo) {
                super.onInitializeAccessibilityNodeInfo(host, info)
                val compat = AccessibilityNodeInfoCompat.wrap(info)
                compat.roleDescription = getString(R.string.in_call_role_description)
            }
        }
    }

    private fun updateAccessibilityPaneTitle() {
        val root = findViewById<View>(R.id.rootLayout)
        val title = if (seenOffhook) {
            getString(R.string.in_call_pane_active, displayName)
        } else {
            getString(R.string.in_call_pane_title, displayName)
        }
        ViewCompat.setAccessibilityPaneTitle(root, title)
        tvStatus.contentDescription = getString(
            R.string.in_call_status_live_desc,
            tvStatus.text
        )
    }

    companion object {
        const val EXTRA_PHONE = "call_phone"
        const val EXTRA_NAME = "call_name"
        const val EXTRA_MODE = "call_mode"
        const val MODE_OUTGOING = "outgoing"
        const val MODE_INCOMING = "incoming"
        private const val READ_PHONE_STATE_REQUEST = 3001
        private const val IDLE_GRACE_MS = 5000L
        private const val END_CALL_RETRY_MS = 700L
        private const val END_CALL_VERIFY_MS = 2200L
        private const val MAX_END_CALL_ATTEMPTS = 5
    }
}