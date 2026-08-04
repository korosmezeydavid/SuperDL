package com.superdl.launcher.lock.keyguard

import android.accessibilityservice.AccessibilityService
import android.graphics.PixelFormat
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.WindowManager
import android.widget.TextView
import com.superdl.launcher.R
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.input.NumberPadHelper
import com.superdl.launcher.input.NumberPadItem
import com.superdl.launcher.input.NumberPadKey
import com.superdl.launcher.tts.TtsManager

private const val TAG_OVERLAY = "SDL_PINASSIST"

class KeyguardPinOverlayController(
    private val service: AccessibilityService,
    private val onAction: (OverlayAction, (Boolean) -> Unit) -> Unit,
    private val injectionHint: () -> String? = { null }
) {

    sealed interface OverlayAction {
        data class Digit(val value: Char) : OverlayAction
        data object Confirm : OverlayAction
        data object Delete : OverlayAction
        data object Clear : OverlayAction
    }

    private val handler = Handler(Looper.getMainLooper())
    private val windowManager = service.getSystemService(WindowManager::class.java)
    private val items: List<NumberPadItem> = NumberPadHelper.pinItems
    private var overlayView: View? = null
    private var tvItem: TextView? = null
    private var tvHint: TextView? = null
    private var tvPosition: TextView? = null
    private var padIndex = 0
    private var entryLength = 0
    private var visible = false
    private var introSpoken = false

    val isVisible: Boolean
        get() = visible

    private var tts: TtsManager? = null
    private var sounds: SoundFeedback? = null
    private var gestureListener: SwipeGestureListener? = null
    private var suspendedForInjection = false

    fun show() {
        handler.post {
            if (visible) {
                updateDisplay()
                return@post
            }
            ensureResources()
            if (overlayView == null) {
                attachOverlay()
            }
            visible = true
            padIndex = 0
            entryLength = 0
            updateDisplay()
            speakIntroIfNeeded()
        }
    }

    fun hide() {
        handler.post {
            if (!visible) return@post
            visible = false
            entryLength = 0
            padIndex = 0
            detachOverlay()
        }
    }

    fun release() {
        handler.post {
            hide()
            suspendedForInjection = false
            tts?.shutdown()
            tts = null
            sounds?.release()
            sounds = null
            gestureListener = null
        }
    }

    fun suspendForInjection() {
        if (Looper.myLooper() == handler.looper) {
            suspendForInjectionImmediate()
            return
        }
        val latch = java.util.concurrent.CountDownLatch(1)
        handler.post {
            suspendForInjectionImmediate()
            latch.countDown()
        }
        latch.await(500, java.util.concurrent.TimeUnit.MILLISECONDS)
    }

    fun restoreAfterInjection() {
        if (Looper.myLooper() == handler.looper) {
            restoreAfterInjectionImmediate()
            return
        }
        val latch = java.util.concurrent.CountDownLatch(1)
        handler.post {
            restoreAfterInjectionImmediate()
            latch.countDown()
        }
        latch.await(500, java.util.concurrent.TimeUnit.MILLISECONDS)
    }

    private fun suspendForInjectionImmediate() {
        if (!visible || suspendedForInjection) return
        suspendedForInjection = true
        detachOverlay()
    }

    private fun restoreAfterInjectionImmediate() {
        if (!suspendedForInjection) return
        suspendedForInjection = false
        if (!visible) return
        if (overlayView == null) {
            attachOverlay()
        }
        updateDisplay()
    }

    fun onUnlockSucceeded() {
        handler.post {
            entryLength = 0
            padIndex = 0
            introSpoken = false
            tts?.speak("Telefon feloldva.")
            hide()
        }
    }

    private fun ensureResources() {
        // DIRECT BOOT (első bekapcsolás, feloldás előtt):
        // a TtsManager és a SoundFeedback a beállításait a szokásos tárolóból
        // olvassa, ami ilyenkor MÉG TITKOSÍTVA van -> IllegalStateException, és
        // a teljes kisegítő szolgáltatás összeomlott (a rendszer újraindította,
        // majd 30 percre elhalasztotta). Ezért hibánál eszköz-védett környezettel
        // próbálkozunk, ami titkosítás alatt is elérhető; ha az sem megy, a
        // billentyűzet hang nélkül, de MŰKÖDVE jelenik meg.
        if (tts == null) {
            tts = try {
                TtsManager(service)
            } catch (e: Exception) {
                android.util.Log.w(TAG_OVERLAY, "TTS szokasos tarolobol nem indult: ${e.message}")
                try {
                    TtsManager(deviceProtected())
                } catch (e2: Exception) {
                    android.util.Log.w(TAG_OVERLAY, "TTS eszkoz-vedettel sem: ${e2.message}")
                    null
                }
            }
        }
        if (sounds == null) {
            sounds = try {
                SoundFeedback(service)
            } catch (e: Exception) {
                android.util.Log.w(TAG_OVERLAY, "Hangok szokasos tarolobol nem indultak: ${e.message}")
                try {
                    SoundFeedback(deviceProtected())
                } catch (_: Exception) {
                    null
                }
            }
        }
    }

    /** Titkosítás alatt is elérhető környezet (Direct Boot). */
    private fun deviceProtected(): android.content.Context = try {
        service.createDeviceProtectedStorageContext() ?: service
    } catch (_: Exception) {
        service
    }

    private fun attachOverlay() {
        val inflater = LayoutInflater.from(service)
        val root = inflater.inflate(R.layout.overlay_keyguard_pin, null)
        tvItem = root.findViewById(R.id.tvKeyguardPinItem)
        tvHint = root.findViewById(R.id.tvKeyguardPinHint)
        tvPosition = root.findViewById(R.id.tvKeyguardPinPosition)

        gestureListener = SwipeGestureListener(
            context = service,
            onSwipeUp = { feedback(SoundType.SWIPE_UP); navigate(-1) },
            onSwipeDown = { feedback(SoundType.SWIPE_DOWN); navigate(+1) },
            onSwipeRight = { feedback(SoundType.SWIPE_RIGHT); activate() },
            onSwipeLeft = { feedback(SoundType.SWIPE_LEFT); backspace() }
        )

        root.setOnTouchListener { _, event ->
            gestureListener?.detector?.onTouchEvent(event)
            true
        }

        val layoutType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP_MR1) {
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_SYSTEM_ALERT
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            layoutType,
            WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
                WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
        }

        windowManager.addView(root, params)
        overlayView = root
    }

    private fun detachOverlay() {
        overlayView?.let { view ->
            runCatching { windowManager.removeView(view) }
        }
        overlayView = null
        tvItem = null
        tvHint = null
        tvPosition = null
    }

    private fun speakIntroIfNeeded() {
        if (introSpoken) return
        introSpoken = true
        tts?.speak(
            "Rendszer zárolás. Add meg a telefon PIN kódját. " +
                "Egyestől nulláig, alul a Törlés és Megerősítés gomb. " +
                "Fel-le választás, jobbra beírás, balra egy számjegy törlése."
        )
        tts?.speakAdd(items.first().speakLabel())
    }

    private fun navigate(delta: Int) {
        padIndex = (padIndex + delta + items.size) % items.size
        updateDisplay()
        tts?.speak(items[padIndex].speakLabel())
    }

    private fun activate() {
        val item = items[padIndex]
        when (item.key) {
            NumberPadKey.DIGIT -> {
                val digit = item.value.firstOrNull() ?: return
                onAction(OverlayAction.Digit(digit)) { success ->
                    handler.post {
                        if (success) {
                            entryLength += 1
                            updateDisplay()
                            sounds?.play(SoundType.MENU_NAV)
                            tts?.speak(NumberPadHelper.speakPinDigitEntered("x".repeat(entryLength)))
                        } else {
                            feedback(SoundType.ACTION_ERROR)
                            tts?.speak(
                                injectionHint() ?: "A rendszer billentyű nem érhető el. Próbáld újra."
                            )
                        }
                    }
                }
            }
            NumberPadKey.CLEAR -> {
                onAction(OverlayAction.Clear) { success ->
                    handler.post {
                        if (success) {
                            entryLength = 0
                            updateDisplay()
                            sounds?.play(SoundType.ACTION_OK)
                            tts?.speak("Teljes bevitel törölve.")
                        } else {
                            feedback(SoundType.ACTION_ERROR)
                            tts?.speak("A törlés nem sikerült.")
                        }
                    }
                }
            }
            NumberPadKey.CONFIRM -> {
                onAction(OverlayAction.Confirm) { success ->
                    handler.post {
                        if (success) {
                            sounds?.play(SoundType.ACTION_OK)
                            tts?.speak("PIN elküldve.")
                        } else {
                            feedback(SoundType.ACTION_ERROR)
                            tts?.speak("A megerősítés nem sikerült.")
                        }
                    }
                }
            }
            else -> Unit
        }
    }

    private fun backspace() {
        if (entryLength == 0) {
            feedback(SoundType.ACTION_ERROR)
            tts?.speak("Add meg a telefon PIN kódját.")
            return
        }
        onAction(OverlayAction.Delete) { success ->
            handler.post {
                if (success) {
                    entryLength = (entryLength - 1).coerceAtLeast(0)
                    updateDisplay()
                    sounds?.play(SoundType.SWIPE_LEFT)
                    tts?.speak(NumberPadHelper.speakPinBackspace("x".repeat(entryLength)))
                } else {
                    feedback(SoundType.ACTION_ERROR)
                    tts?.speak("A törlés nem sikerült.")
                }
            }
        }
    }

    private fun updateDisplay() {
        val item = items[padIndex]
        tvItem?.text = item.label
        tvPosition?.text = "Rendszer PIN  •  ${padIndex + 1} / ${items.size}"
        val lengthHint = if (entryLength == 0) "" else "  •  $entryLength számjegy"
        tvHint?.text = "⬆⬇ ${item.label}$lengthHint  •  ➡ beír  •  ⬅ egy törlés"
    }

    private fun feedback(type: SoundType) = sounds?.play(type)
}