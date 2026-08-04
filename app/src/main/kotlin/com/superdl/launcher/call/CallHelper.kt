package com.superdl.launcher.call

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.telecom.Call
import android.telecom.TelecomManager
import android.telecom.VideoProfile
import android.telephony.TelephonyManager
import android.view.KeyEvent
import androidx.core.content.ContextCompat

object CallHelper {

    private val dtmfHandler = Handler(Looper.getMainLooper())
    private var pendingDtmfStop: Runnable? = null

    fun launchInCall(
        context: Context,
        phone: String,
        displayName: String,
        mode: String = InCallActivity.MODE_OUTGOING
    ) {
        CallSession.markInCallUiStarted(incomingHandoff = mode == InCallActivity.MODE_INCOMING)
        val intent = inCallIntent(context, phone, displayName, mode).apply {
            // Dedicated call task — isolated from the HOME/singleTask MainActivity stack.
            addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_CLEAR_TASK or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP
            )
        }
        context.startActivity(intent)
    }

    fun bringInCallToFront(context: Context) {
        if (!CallSession.isInCallUiActive) return
        val intent = Intent(context, InCallActivity::class.java).apply {
            addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP
            )
        }
        context.startActivity(intent)
    }

    private fun inCallIntent(
        context: Context,
        phone: String,
        displayName: String,
        mode: String
    ): Intent {
        return Intent(context, InCallActivity::class.java).apply {
            putExtra(InCallActivity.EXTRA_PHONE, phone)
            putExtra(InCallActivity.EXTRA_NAME, displayName)
            putExtra(InCallActivity.EXTRA_MODE, mode)
        }
    }

    fun placeCall(context: Context, phone: String): Boolean {
        if (DialerRoleHelper.isDefaultDialer(context)) {
            return placeCallViaTelecom(context, phone)
        }
        return placeCallViaIntent(context, phone)
    }

    private fun placeCallViaIntent(context: Context, phone: String): Boolean {
        return try {
            val intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:$phone")).apply {
                if (context !is Activity) {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
            }
            context.startActivity(intent)
            true
        } catch (_: Exception) {
            false
        }
    }

    private fun placeCallViaTelecom(context: Context, phone: String): Boolean {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CALL_PHONE)
            != PackageManager.PERMISSION_GRANTED
        ) {
            return false
        }
        return try {
            val telecom = context.getSystemService(TelecomManager::class.java) ?: return false
            val uri = Uri.fromParts("tel", phone, null)
            telecom.placeCall(uri, Bundle())
            true
        } catch (_: Exception) {
            placeCallViaIntent(context, phone)
        }
    }

    fun acceptIncomingCall(context: Context): Boolean {
        ActiveCallRegistry.ringingCall?.let { call ->
            return try {
                call.answer(VideoProfile.STATE_AUDIO_ONLY)
                true
            } catch (_: Exception) {
                false
            }
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return false
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.ANSWER_PHONE_CALLS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            return false
        }
        return try {
            val telecom = context.getSystemService(TelecomManager::class.java) ?: return false
            telecom.acceptRingingCall()
            true
        } catch (_: Exception) {
            false
        }
    }

    fun rejectIncomingCall(context: Context): Boolean = endCallAggressive(context)

    fun tryEndCall(context: Context): Boolean = endCallAggressive(context)

    fun endCallAggressive(context: Context): Boolean {
        var attempted = false
        if (disconnectManagedCalls()) attempted = true
        if (endCallViaTelecomApi(context)) attempted = true
        if (endCallViaReflection(context)) attempted = true
        if (context is Activity) {
            dispatchEndCallKey(context)
            if (disconnectManagedCalls()) attempted = true
            if (endCallViaTelecomApi(context)) attempted = true
            if (endCallViaReflection(context)) attempted = true
        }
        return attempted
    }

    private fun disconnectManagedCalls(): Boolean {
        val calls = listOfNotNull(ActiveCallRegistry.activeCall, ActiveCallRegistry.ringingCall).distinct()
        if (calls.isEmpty()) return false
        var attempted = false
        calls.forEach { call ->
            try {
                when (call.state) {
                    Call.STATE_RINGING -> call.reject(false, null)
                    Call.STATE_DISCONNECTED, Call.STATE_DISCONNECTING -> Unit
                    else -> call.disconnect()
                }
                attempted = true
            } catch (_: Exception) {
            }
        }
        return attempted
    }

    private fun endCallViaTelecomApi(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.P) return false
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.ANSWER_PHONE_CALLS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            return false
        }
        return try {
            val telecom = context.getSystemService(TelecomManager::class.java) ?: return false
            @Suppress("DEPRECATION")
            telecom.endCall()
        } catch (_: Exception) {
            false
        }
    }

    @Suppress("DEPRECATION")
    private fun endCallViaReflection(context: Context): Boolean {
        return try {
            val telephony = context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
            val telephonyClass = Class.forName(telephony.javaClass.name)
            val getITelephony = telephonyClass.getDeclaredMethod("getITelephony")
            getITelephony.isAccessible = true
            val iTelephony = getITelephony.invoke(telephony) ?: return false
            val endCall = iTelephony.javaClass.getDeclaredMethod("endCall")
            endCall.isAccessible = true
            endCall.invoke(iTelephony) as Boolean
        } catch (_: Exception) {
            try {
                val telephony = context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
                val endCall = telephony.javaClass.getDeclaredMethod("endCall")
                endCall.isAccessible = true
                endCall.invoke(telephony) as Boolean
            } catch (_: Exception) {
                false
            }
        }
    }

    fun dispatchEndCallKey(activity: Activity): Boolean {
        return try {
            val down = KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_ENDCALL)
            val up = KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_ENDCALL)
            activity.dispatchKeyEvent(down)
            activity.dispatchKeyEvent(up)
        } catch (_: Exception) {
            false
        }
    }

    fun sendDtmfTone(context: Context, digit: Char): Boolean {
        if (!isValidDtmfDigit(digit)) return false
        ActiveCallRegistry.activeCall?.let { call ->
            if (sendDtmfOverCall(call, digit)) return true
        }
        return sendDtmfViaITelephony(context, digit)
    }

    private fun sendDtmfOverCall(call: Call, digit: Char): Boolean {
        return try {
            call.playDtmfTone(digit)
            scheduleStopDtmf(call)
            true
        } catch (_: Exception) {
            false
        }
    }

    private fun scheduleStopDtmf(call: Call) {
        pendingDtmfStop?.let { dtmfHandler.removeCallbacks(it) }
        val stopRunnable = Runnable {
            try {
                call.stopDtmfTone()
            } catch (_: Exception) {
            }
            pendingDtmfStop = null
        }
        pendingDtmfStop = stopRunnable
        dtmfHandler.postDelayed(stopRunnable, 200L)
    }

    @Suppress("DEPRECATION")
    private fun sendDtmfViaITelephony(context: Context, digit: Char): Boolean {
        return try {
            val telephony = context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
            val telephonyClass = Class.forName(telephony.javaClass.name)
            val getITelephony = telephonyClass.getDeclaredMethod("getITelephony")
            getITelephony.isAccessible = true
            val iTelephony = getITelephony.invoke(telephony) ?: return false
            val sendDtmf = iTelephony.javaClass.getDeclaredMethod(
                "sendDtmf",
                Char::class.javaPrimitiveType
            )
            sendDtmf.isAccessible = true
            sendDtmf.invoke(iTelephony, digit)
            true
        } catch (_: Exception) {
            false
        }
    }

    fun setSpeakerphone(context: Context, enabled: Boolean): Boolean {
        return try {
            val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            @Suppress("DEPRECATION")
            audio.isSpeakerphoneOn = enabled
            true
        } catch (_: Exception) {
            false
        }
    }

    fun isSpeakerphoneOn(context: Context): Boolean {
        return try {
            val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            @Suppress("DEPRECATION")
            audio.isSpeakerphoneOn
        } catch (_: Exception) {
            false
        }
    }

    fun setMicrophoneMute(context: Context, muted: Boolean): Boolean {
        return try {
            val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            audio.isMicrophoneMute = muted
            true
        } catch (_: Exception) {
            false
        }
    }

    fun isMicrophoneMuted(context: Context): Boolean {
        return try {
            val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            audio.isMicrophoneMute
        } catch (_: Exception) {
            false
        }
    }

    fun restoreDefaultAudioRoute(context: Context) {
        IncomingCallRinger.stop(context)
        if (ActiveCallRegistry.hasManagedCall) return
        try {
            val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                audio.clearCommunicationDevice()
            }
            @Suppress("DEPRECATION")
            audio.isSpeakerphoneOn = false
            audio.isMicrophoneMute = false
            if (audio.mode != AudioManager.MODE_NORMAL) {
                audio.mode = AudioManager.MODE_NORMAL
            }
        } catch (_: Exception) {
        }
    }

    fun speakPhoneNumber(phone: String): String {
        val words = mapOf(
            '0' to "nulla", '1' to "egy", '2' to "kettő", '3' to "három", '4' to "négy",
            '5' to "öt", '6' to "hat", '7' to "hét", '8' to "nyolc", '9' to "kilenc"
        )
        return phone.map { char ->
            when {
                char == '+' -> "plusz"
                words.containsKey(char) -> words.getValue(char)
                else -> ""
            }
        }.filter { it.isNotBlank() }.joinToString(" ")
    }

    private fun isValidDtmfDigit(digit: Char): Boolean =
        digit in '0'..'9' || digit == '*' || digit == '#'
}