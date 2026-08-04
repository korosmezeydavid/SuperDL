package com.superdl.launcher.call

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.telephony.TelephonyManager
import android.view.View
import android.view.WindowManager
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.superdl.launcher.R
import com.superdl.launcher.contacts.ContactHelper
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.system.QuietModeHelper
import com.superdl.launcher.tts.TtsManager

class IncomingCallActivity : AppCompatActivity() {

    private lateinit var tvName: TextView
    private lateinit var tvNumber: TextView
    private lateinit var tvStatus: TextView
    private lateinit var tvHint: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gestureListener: SwipeGestureListener
    private var callState = TelephonyManager.CALL_STATE_IDLE
    private var handled = false
    private var dismissReceiver: BroadcastReceiver? = null
    private var callStateWatcher: CallStateWatcher? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (QuietModeHelper.shouldSuppressIncomingCalls(this)) {
            finish()
            return
        }
        applyLockScreenFlags()
        setContentView(R.layout.activity_in_call)
        applyImmersive()
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvName = findViewById(R.id.tvCallName)
        tvNumber = findViewById(R.id.tvCallNumber)
        tvStatus = findViewById(R.id.tvCallStatus)
        tvHint = findViewById(R.id.tvCallHint)

        val phone = intent.getStringExtra(EXTRA_PHONE).orEmpty()
        val name = intent.getStringExtra(EXTRA_NAME)
            .orEmpty()
            .ifBlank { ContactHelper.findNameByPhone(this, phone).orEmpty() }
            .ifBlank { if (phone.isNotBlank()) "Ismeretlen szám" else "Ismeretlen" }

        tvName.text = name
        tvNumber.text = ContactHelper.maskPhone(phone)
        tvStatus.text = getString(R.string.call_status_ringing)
        tvHint.text = getString(R.string.incoming_call_hint)

        tts = TtsManager(this)
        sounds = SoundFeedback(this)

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                speakCallerInfo(name, phone)
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                tts.speak("Bejövő hívás. $name. ${ContactHelper.maskPhone(phone)}")
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                acceptCall()
            },
            onSwipeLeft = {
                sounds.play(SoundType.SWIPE_LEFT)
                rejectCall()
            }
        )

        findViewById<View>(R.id.rootLayout).setOnTouchListener { _, event ->
            gestureListener.detector.onTouchEvent(event)
            true
        }

        registerPhoneListener()
        registerDismissReceiver()
        IncomingCallState.isShowing = true
        tts.speakThen("Bejövő hívás. $name.") {
            tts.speakAdd("Söpörj jobbra a fogadáshoz, söprés balra az elutasításhoz.")
        }
    }

    private fun acceptCall() {
        if (handled) return
        handled = true
        IncomingCallRinger.stop(applicationContext)
        if (CallHelper.acceptIncomingCall(this)) {
            sounds.play(SoundType.ACTION_OK)
            val phone = intent.getStringExtra(EXTRA_PHONE).orEmpty()
            val name = intent.getStringExtra(EXTRA_NAME).orEmpty().ifBlank { "Ismeretlen" }
            IncomingCallState.isShowing = false
            CallHelper.launchInCall(this, phone, name, InCallActivity.MODE_INCOMING)
            finish()
        } else {
            handled = false
            tts.speak(
                "A hívás fogadása nem sikerült. Engedélyezd a híváskezelés engedélyt, " +
                    "vagy fogadd a telefon képernyőjén."
            )
        }
    }

    private fun rejectCall() {
        if (handled) return
        handled = true
        IncomingCallRinger.stop(applicationContext)
        if (CallHelper.rejectIncomingCall(this)) {
            tts.speakThen("Hívás elutasítva.") { finish() }
        } else {
            handled = false
            tts.speakThen("Hívás elutasítva.") { finish() }
        }
    }

    private fun speakCallerInfo(name: String, phone: String) {
        tts.speak("$name. Szám: ${CallHelper.speakPhoneNumber(phone)}")
    }

    private fun registerPhoneListener() {
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
            TelephonyManager.CALL_STATE_IDLE -> {
                if (!handled) {
                    handled = true
                    tts.speakThen("A hívás véget ért.") { finish() }
                }
            }
            TelephonyManager.CALL_STATE_OFFHOOK -> {
                if (!handled) {
                    handled = true
                    val phone = intent.getStringExtra(EXTRA_PHONE).orEmpty()
                    val name = intent.getStringExtra(EXTRA_NAME).orEmpty().ifBlank { "Ismeretlen" }
                    IncomingCallState.isShowing = false
                    CallHelper.launchInCall(this, phone, name, InCallActivity.MODE_INCOMING)
                    finish()
                }
            }
        }
    }

    private fun applyLockScreenFlags() {
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

    private fun registerDismissReceiver() {
        dismissReceiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                if (!handled) finish()
            }
        }
        val filter = IntentFilter(IncomingCallState.ACTION_DISMISS_INCOMING_CALL)
        ContextCompat.registerReceiver(
            this,
            dismissReceiver,
            filter,
            ContextCompat.RECEIVER_NOT_EXPORTED
        )
    }

    override fun onDestroy() {
        IncomingCallState.isShowing = false
        IncomingCallRinger.stop(applicationContext)
        dismissReceiver?.let { unregisterReceiver(it) }
        dismissReceiver = null
        unregisterPhoneListener()
        tts.shutdown()
        if (::sounds.isInitialized) sounds.release()
        super.onDestroy()
    }

    companion object {
        const val EXTRA_PHONE = "incoming_phone"
        const val EXTRA_NAME = "incoming_name"
    }
}