package com.superdl.launcher.lock.keyguard

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.util.Log

import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.superdl.launcher.lock.keyguard.KeyguardPinDetector.CredentialState
import com.superdl.launcher.lock.keyguard.KeyguardPinOverlayController.OverlayAction
import com.superdl.launcher.system.ConnectivityHelper
import com.superdl.launcher.system.HotspotStateStore

class KeyguardPinAccessibilityService : AccessibilityService() {

    companion object {
        private const val TAG = "SuperDL-A11y"
        private const val POLL_INTERVAL_MS = 350L
    }

    private val handler = Handler(Looper.getMainLooper())
    private var lastLoggedKeyguardState: String? = null
    private val workerThread = HandlerThread("SuperDL-A11yWorker").apply { start() }
    private val workerHandler = Handler(workerThread.looper)

    private var overlay: KeyguardPinOverlayController? = null
    private var credentialState = CredentialState.NONE
    private var evaluateRunnable: Runnable? = null
    private var pollRunnable: Runnable? = null
    private var unlockReceiver: BroadcastReceiver? = null
    private var pollingActive = false
    private var pinAssistLocked = false
    @Volatile
    var lastInjectionHint: String? = null

    override fun onCreate() {
        super.onCreate()
        overlay = KeyguardPinOverlayController(
            service = this,
            onAction = ::handleOverlayAction,
            injectionHint = { lastInjectionHint }
        )
        registerUnlockReceiver()
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        // Napló: ebből derül ki, hogy a szolgáltatás elindul-e az ELSŐ FELOLDÁS
        // ELŐTT (Direct Boot) is, vagy csak feloldás után. A userUnlocked=false
        // azt jelenti, hogy még a titkosított, korlátozott fázisban vagyunk.
        val unlocked = try {
            val um = getSystemService(android.content.Context.USER_SERVICE) as android.os.UserManager
            um.isUserUnlocked
        } catch (_: Exception) {
            null
        }
        android.util.Log.i(
            "SDL_PINASSIST",
            "onServiceConnected: felhasznalo feloldva=$unlocked, funkcio=${KeyguardPinSettings.isFeatureEnabled(this)}"
        )
        AccessibilityAssistBridge.activeService = this
        configureServiceInfo()
        evaluateKeyguardState(force = true)
        updateKeyguardPolling()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return
        if (event.packageName?.toString() == packageName) return

        if (KeyguardPinSettings.isFeatureEnabled(this) && KeyguardPinDetector.isRelevantEvent(event)) {
            scheduleKeyguardEvaluation {
                val state = if (KeyguardPinDetector.isKeyguardLocked(this)) {
                    KeyguardPinDetector.analyzeEvent(event, this)
                } else {
                    CredentialState.NONE
                }
                applyCredentialState(state)
            }
        }
    }

    override fun onInterrupt() {
        handler.post { overlay?.hide() }
    }

    override fun onDestroy() {
        if (AccessibilityAssistBridge.activeService === this) {
            AccessibilityAssistBridge.activeService = null
        }
        unregisterUnlockReceiver()
        stopKeyguardPolling()
        evaluateRunnable?.let { handler.removeCallbacks(it) }
        overlay?.release()
        overlay = null
        workerThread.quitSafely()
        super.onDestroy()
    }

    fun requestHotspotToggle(targetEnabled: Boolean, callback: (Boolean) -> Unit) {
        workerHandler.post {
            val ok = performHotspotToggle(targetEnabled)
            handler.post { callback(ok) }
        }
    }

    private fun performHotspotToggle(targetEnabled: Boolean): Boolean {
        val current = ConnectivityHelper.isHotspotEnabled(this)
        if (current == targetEnabled) {
            HotspotStateStore.set(this, targetEnabled)
            return true
        }
        val viaQuickSettings = HotspotAccessibilityHelper.toggleViaQuickSettings(this, targetEnabled)
        if (viaQuickSettings) {
            Thread.sleep(900)
            val detected = ConnectivityHelper.isHotspotEnabled(this)
            if (detected == targetEnabled) {
                HotspotStateStore.set(this, targetEnabled)
                return true
            }
        }
        Log.w(TAG, "Hotspot a11y toggle failed target=$targetEnabled current=$current")
        return false
    }

    private fun configureServiceInfo() {
        val info = serviceInfo ?: AccessibilityServiceInfo()
        info.eventTypes = AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED or
            AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED or
            AccessibilityEvent.TYPE_WINDOWS_CHANGED or
            AccessibilityEvent.TYPE_VIEW_FOCUSED or
            AccessibilityEvent.TYPE_VIEW_CLICKED or
            AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED
        info.feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
        info.flags = info.flags or
            AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS or
            AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS or
            AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS
        info.notificationTimeout = 50L
        serviceInfo = info
    }

    private fun scheduleKeyguardEvaluation(block: () -> Unit) {
        evaluateRunnable?.let { handler.removeCallbacks(it) }
        evaluateRunnable = Runnable {
            if (!KeyguardPinSettings.isFeatureEnabled(this)) {
                overlay?.hide()
                credentialState = CredentialState.NONE
                return@Runnable
            }
            block()
        }
        handler.postDelayed(evaluateRunnable!!, 60L)
    }

    private fun evaluateKeyguardState(force: Boolean = false) {
        val featureOn = KeyguardPinSettings.isFeatureEnabled(this)
        // Diagnosztika CSAK állapotváltozáskor — a vizsgálat 350 ms-onként fut,
        // minden körben naplózni fölösleges terhelés lenne.
        val locked = try { KeyguardPinDetector.isKeyguardLocked(this) } catch (_: Exception) { null }
        val stateKey = "$featureOn/$locked"
        if (stateKey != lastLoggedKeyguardState) {
            lastLoggedKeyguardState = stateKey
            android.util.Log.i(
                "SDL_PINASSIST",
                "allapot valtozas: funkcio=$featureOn zarolva=$locked"
            )
        }
        if (!featureOn) {
            overlay?.hide()
            credentialState = CredentialState.NONE
            pinAssistLocked = false
            stopKeyguardPolling()
            return
        }

        if (!KeyguardPinDetector.isKeyguardLocked(this)) {
            applyCredentialState(CredentialState.NONE)
            stopKeyguardPolling()
            return
        }

        if (pinAssistLocked && overlay?.isVisible == true) {
            val root = KeyguardPinInjector.findKeyguardRoot(this)
            if (root != null) {
                val analyzed = KeyguardPinDetector.analyzeRoot(root, this)
                @Suppress("DEPRECATION")
                root.recycle()
                if (analyzed == CredentialState.PATTERN ||
                    analyzed == CredentialState.BIOMETRIC_PROMPT
                ) {
                    applyCredentialState(analyzed)
                }
            }
            return
        }

        startKeyguardPolling()
        val root = KeyguardPinInjector.findKeyguardRoot(this)
        // DIAGNOSZTIKA: megtaláltuk-e a zárolási képernyő ablakát, és minek
        // ismertük fel? Ha a root null, a rendszer nem engedi látni a keyguardot;
        // ha a felismert állapot nem PIN, akkor a képernyő szerkezete más.
        android.util.Log.i(
            "SDL_PINASSIST",
            "kereses: keyguard ablak=${if (root != null) "megvan" else "NINCS"}"
        )
        val state = if (root != null) {
            val analyzed = KeyguardPinDetector.analyzeRoot(root, this)
            val pinField = KeyguardPinDetector.findPinInputField(root)
            android.util.Log.i(
                "SDL_PINASSIST",
                "felismeres: allapot=$analyzed, PIN-mezo=${if (pinField != null) "megvan" else "nincs"}, " +
                    "vedett=${KeyguardPinDetector.isDeviceSecure(this)}"
            )
            val resolved = if (analyzed == CredentialState.KEYGUARD_IDLE &&
                KeyguardPinDetector.isDeviceSecure(this) &&
                pinField != null
            ) {
                CredentialState.PIN_OR_PASSWORD
            } else {
                analyzed
            }
            pinField?.let {
                @Suppress("DEPRECATION")
                it.recycle()
            }
            resolved.also {
                @Suppress("DEPRECATION")
                root.recycle()
            }
        } else if (force && KeyguardPinDetector.isDeviceSecure(this)) {
            CredentialState.KEYGUARD_IDLE
        } else if (force) {
            credentialState
        } else {
            credentialState
        }
        applyCredentialState(state)
    }

    private fun applyCredentialState(state: CredentialState) {
        if (!KeyguardPinDetector.isKeyguardLocked(this)) {
            credentialState = CredentialState.NONE
            pinAssistLocked = false
            overlay?.hide()
            stopKeyguardPolling()
            return
        }

        val effectiveState = resolveCredentialState(state)
        credentialState = effectiveState
        when (effectiveState) {
            CredentialState.PIN_OR_PASSWORD -> overlay?.show()
            CredentialState.NONE,
            CredentialState.KEYGUARD_IDLE,
            CredentialState.BIOMETRIC_PROMPT,
            CredentialState.PATTERN,
            CredentialState.OTHER_CREDENTIAL -> overlay?.hide()
        }
    }

    private fun resolveCredentialState(state: CredentialState): CredentialState {
        if (pinAssistLocked && state == CredentialState.KEYGUARD_IDLE) {
            return CredentialState.PIN_OR_PASSWORD
        }
        when (state) {
            CredentialState.PIN_OR_PASSWORD -> pinAssistLocked = true
            CredentialState.BIOMETRIC_PROMPT,
            CredentialState.PATTERN,
            CredentialState.OTHER_CREDENTIAL -> pinAssistLocked = false
            else -> Unit
        }
        return state
    }

    private fun handleOverlayAction(action: OverlayAction, callback: (Boolean) -> Unit) {
        workerHandler.post {
            val result = performOverlayAction(action)
            callback(result)
        }
    }

    private fun performOverlayAction(action: OverlayAction): Boolean {
        lastInjectionHint = null
        overlay?.suspendForInjection()
        sleepInterruptibly(200L)
        return try {
            var root = KeyguardPinInjector.findKeyguardRoot(this)
            if (root == null) {
                lastInjectionHint = "Nem találom a zárolási képernyőt."
                Log.w(TAG, "Keyguard root not found for overlay action=$action")
                return false
            }

            if (action is OverlayAction.Digit &&
                !KeyguardPinInjector.hasPinBouncerPublic(root) &&
                KeyguardPinInjector.countAvailableDigits(root) < 4
            ) {
                KeyguardPinInjector.revealPinBouncer(this, root)
                sleepInterruptibly(350L)
                @Suppress("DEPRECATION")
                root.recycle()
                root = KeyguardPinInjector.findKeyguardRoot(this)
                if (root == null) {
                    lastInjectionHint =
                        "Először koppints az ujjlenyomat ikonra, hogy megjelenjen a rendszer PIN billentyűzet."
                    return false
                }
            }

            val visibleDigits = KeyguardPinInjector.countAvailableDigits(root)
            val result = when (action) {
                is OverlayAction.Digit -> {
                    val clicked = KeyguardPinInjector.clickDigit(this, root, action.value)
                    clicked || KeyguardPinInjector.appendDigitToPasswordField(root, action.value)
                }
                OverlayAction.Confirm -> KeyguardPinInjector.clickConfirm(this, root)
                OverlayAction.Delete -> KeyguardPinInjector.clickDelete(this, root)
                OverlayAction.Clear -> {
                    var cleared = false
                    repeat(16) {
                        if (KeyguardPinInjector.clickDelete(this, root)) cleared = true
                    }
                    cleared
                }
            }
            if (!result) {
                lastInjectionHint = if (visibleDigits < 4) {
                    "Először koppints az ujjlenyomat ikonra, hogy megjelenjen a rendszer PIN billentyűzet."
                } else {
                    "A rendszer billentyű nem érhető el. Próbáld újra."
                }
            }
            @Suppress("DEPRECATION")
            root.recycle()
            handler.postDelayed({ checkUnlockAfterInput() }, 250L)
            result
        } finally {
            overlay?.restoreAfterInjection()
        }
    }

    private fun sleepInterruptibly(delayMs: Long) {
        if (delayMs <= 0L || Thread.currentThread().isInterrupted) return
        try {
            Thread.sleep(delayMs)
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        }
    }

    private fun checkUnlockAfterInput() {
        if (!KeyguardPinDetector.isKeyguardLocked(this)) {
            pinAssistLocked = false
            overlay?.onUnlockSucceeded()
            credentialState = CredentialState.NONE
            stopKeyguardPolling()
        }
    }

    private fun updateKeyguardPolling() {
        if (KeyguardPinSettings.isFeatureEnabled(this) &&
            KeyguardPinDetector.isKeyguardLocked(this)
        ) {
            startKeyguardPolling()
        } else {
            stopKeyguardPolling()
        }
    }

    private fun startKeyguardPolling() {
        if (pollingActive) return
        pollingActive = true
        pollRunnable = object : Runnable {
            override fun run() {
                if (!pollingActive || !KeyguardPinSettings.isFeatureEnabled(this@KeyguardPinAccessibilityService)) {
                    stopKeyguardPolling()
                    return
                }
                if (!KeyguardPinDetector.isKeyguardLocked(this@KeyguardPinAccessibilityService)) {
                    applyCredentialState(CredentialState.NONE)
                    stopKeyguardPolling()
                    return
                }
                evaluateKeyguardState(force = true)
                handler.postDelayed(this, POLL_INTERVAL_MS)
            }
        }
        handler.post(pollRunnable!!)
    }

    private fun stopKeyguardPolling() {
        pollingActive = false
        pollRunnable?.let { handler.removeCallbacks(it) }
        pollRunnable = null
    }

    private fun registerUnlockReceiver() {
        if (unlockReceiver != null) return
        val filter = IntentFilter().apply {
            addAction(Intent.ACTION_USER_PRESENT)
            addAction(Intent.ACTION_SCREEN_OFF)
            addAction(Intent.ACTION_SCREEN_ON)
            addAction(Intent.ACTION_BOOT_COMPLETED)
        }
        unlockReceiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                when (intent.action) {
                    Intent.ACTION_USER_PRESENT -> {
                        pinAssistLocked = false
                        overlay?.onUnlockSucceeded()
                        credentialState = CredentialState.NONE
                        stopKeyguardPolling()
                    }
                    Intent.ACTION_SCREEN_OFF -> overlay?.hide()
                    Intent.ACTION_SCREEN_ON,
                    Intent.ACTION_BOOT_COMPLETED -> {
                        handler.postDelayed({
                            evaluateKeyguardState(force = true)
                            updateKeyguardPolling()
                        }, 300L)
                    }
                }
            }
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(unlockReceiver, filter, RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(unlockReceiver, filter)
        }
    }

    private fun unregisterUnlockReceiver() {
        unlockReceiver?.let { unregisterReceiver(it) }
        unlockReceiver = null
    }
}