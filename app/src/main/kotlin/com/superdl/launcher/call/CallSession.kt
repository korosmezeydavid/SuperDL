package com.superdl.launcher.call

import android.os.SystemClock

/**
 * Coordinates in-call UI lifecycle across [InCallActivity], [IncomingCallActivity],
 * and [IncomingCallNotifier] so transient IDLE broadcasts during accept handoff
 * do not tear down the active call screen.
 */
object CallSession {

    @Volatile
    var isInCallUiActive: Boolean = false
        private set

    @Volatile
    var isOffhookConfirmed: Boolean = false
        private set

    private var handoffStartedAt: Long = 0L

    fun markInCallUiStarted(incomingHandoff: Boolean = false) {
        isInCallUiActive = true
        isOffhookConfirmed = false
        handoffStartedAt = if (incomingHandoff) SystemClock.elapsedRealtime() else 0L
    }

    fun markOffhookConfirmed() {
        isOffhookConfirmed = true
        handoffStartedAt = 0L
    }

    fun markInCallUiEnded() {
        isInCallUiActive = false
        isOffhookConfirmed = false
        handoffStartedAt = 0L
    }

    fun isInHandoffGrace(): Boolean {
        if (handoffStartedAt <= 0L) return false
        return SystemClock.elapsedRealtime() - handoffStartedAt < HANDOFF_GRACE_MS
    }

    fun shouldSuppressIdleDismissal(): Boolean {
        return isInCallUiActive && (isInHandoffGrace() || !isOffhookConfirmed)
    }

    const val HANDOFF_GRACE_MS = 5000L
}