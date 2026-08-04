package com.superdl.launcher.callfilter

import android.telecom.Call
import android.telecom.CallScreeningService
import com.superdl.launcher.call.IncomingCallCache

class SuperCallScreeningService : CallScreeningService() {

    override fun onScreenCall(callDetails: Call.Details) {
        val number = callDetails.handle?.schemeSpecificPart
        val presentation = callDetails.handlePresentation
        if (!number.isNullOrBlank()) {
            IncomingCallCache.store(number)
        }
        val block = CallFilterEngine.shouldBlock(applicationContext, number, presentation)

        val response = if (block) {
            CallResponse.Builder()
                .setDisallowCall(true)
                .setRejectCall(true)
                .setSkipCallLog(false)
                .setSkipNotification(true)
                .build()
        } else {
            CallResponse.Builder().build()
        }
        respondToCall(callDetails, response)
    }
}