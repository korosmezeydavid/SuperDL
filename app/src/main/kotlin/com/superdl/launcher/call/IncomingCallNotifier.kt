package com.superdl.launcher.call

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.telecom.TelecomManager
import android.telephony.TelephonyManager
import com.superdl.launcher.callfilter.CallFilterEngine
import com.superdl.launcher.contacts.ContactHelper
import com.superdl.launcher.system.QuietModeHelper

object IncomingCallNotifier {

    fun handlePhoneStateChanged(context: Context, intent: Intent) {
        if (intent.action != TelephonyManager.ACTION_PHONE_STATE_CHANGED) return
        val state = intent.getStringExtra(TelephonyManager.EXTRA_STATE) ?: return

        when (state) {
            TelephonyManager.EXTRA_STATE_RINGING -> onRinging(context, intent)
            TelephonyManager.EXTRA_STATE_OFFHOOK -> onOffhook()
            TelephonyManager.EXTRA_STATE_IDLE -> onIdle(context)
        }
    }

    private fun onRinging(context: Context, intent: Intent) {
        if (QuietModeHelper.shouldSuppressIncomingCalls(context)) return
        if (DialerRoleHelper.isDefaultDialer(context) || ActiveCallRegistry.hasManagedCall) return

        @Suppress("DEPRECATION")
        var number = intent.getStringExtra(TelephonyManager.EXTRA_INCOMING_NUMBER).orEmpty()
        if (number.isBlank()) {
            number = IncomingCallCache.takeNumber()
        }
        if (CallFilterEngine.shouldBlock(context, number, TelecomManager.PRESENTATION_ALLOWED)) {
            CallHelper.rejectIncomingCall(context)
            IncomingCallCache.clear()
            return
        }
        if (IncomingCallState.isShowing) return
        val name = resolveCallerName(context, number)
        IncomingCallRinger.start(context, number, name)
        IncomingCallState.show(context, number, name)
    }

    private fun resolveCallerName(context: Context, number: String): String {
        val fromContacts = ContactHelper.findNameByPhone(context, number).orEmpty()
        if (fromContacts.isNotBlank()) return fromContacts
        return if (number.isNotBlank()) "Ismeretlen szám" else "Ismeretlen"
    }

    private fun onOffhook() {
        if (CallSession.isInCallUiActive) {
            CallSession.markOffhookConfirmed()
        }
    }

    private fun onIdle(context: Context) {
        IncomingCallCache.clear()
        if (CallSession.shouldSuppressIdleDismissal()) return
        IncomingCallState.dismissIfShowing(context)
    }
}

object IncomingCallState {
    @Volatile
    var isShowing: Boolean = false

    fun show(context: Context, phone: String, name: String) {
        if (QuietModeHelper.shouldSuppressIncomingCalls(context)) return
        isShowing = true
        val launch = Intent(context, IncomingCallActivity::class.java).apply {
            putExtra(IncomingCallActivity.EXTRA_PHONE, phone)
            putExtra(IncomingCallActivity.EXTRA_NAME, name)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or
                Intent.FLAG_ACTIVITY_CLEAR_TOP or
                Intent.FLAG_ACTIVITY_SINGLE_TOP or
                Intent.FLAG_ACTIVITY_REORDER_TO_FRONT
        }
        context.startActivity(launch)
    }

    fun dismissUiOnly(context: Context) {
        if (!isShowing) return
        isShowing = false
        context.sendBroadcast(
            Intent(ACTION_DISMISS_INCOMING_CALL).setPackage(context.packageName)
        )
    }

    fun dismissIfShowing(context: Context) {
        isShowing = false
        IncomingCallRinger.stop(context)
        context.sendBroadcast(
            Intent(ACTION_DISMISS_INCOMING_CALL).setPackage(context.packageName)
        )
    }

    const val ACTION_DISMISS_INCOMING_CALL = "com.superdl.launcher.action.DISMISS_INCOMING_CALL"
}