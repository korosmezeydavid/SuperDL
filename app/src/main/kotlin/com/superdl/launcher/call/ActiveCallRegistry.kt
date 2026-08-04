package com.superdl.launcher.call

import android.telecom.Call

object ActiveCallRegistry {

    @Volatile
    var ringingCall: Call? = null
        private set

    @Volatile
    var activeCall: Call? = null
        private set

    val hasManagedCall: Boolean
        get() = ringingCall != null || activeCall != null

    fun onCallAdded(call: Call) {
        when (call.state) {
            Call.STATE_RINGING -> ringingCall = call
            Call.STATE_ACTIVE, Call.STATE_DIALING, Call.STATE_CONNECTING -> activeCall = call
        }
    }

    fun onStateChanged(call: Call, state: Int) {
        when (state) {
            Call.STATE_RINGING -> {
                ringingCall = call
                if (activeCall == call) activeCall = null
            }
            Call.STATE_ACTIVE, Call.STATE_DIALING, Call.STATE_CONNECTING -> {
                activeCall = call
                if (ringingCall == call) ringingCall = null
            }
            Call.STATE_DISCONNECTED, Call.STATE_DISCONNECTING -> clearCall(call)
        }
    }

    fun onCallRemoved(call: Call) {
        clearCall(call)
    }

    private fun clearCall(call: Call) {
        if (ringingCall == call) ringingCall = null
        if (activeCall == call) activeCall = null
    }

    fun clearAll() {
        ringingCall = null
        activeCall = null
    }
}