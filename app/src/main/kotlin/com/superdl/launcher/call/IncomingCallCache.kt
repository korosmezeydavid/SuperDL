package com.superdl.launcher.call

import android.os.SystemClock

/**
 * Stores the latest screened incoming call number because [TelephonyManager.EXTRA_INCOMING_NUMBER]
 * is often empty when the app is not the default dialer.
 */
object IncomingCallCache {

    private const val TTL_MS = 30_000L

    @Volatile
    private var number: String = ""

    @Volatile
    private var storedAt: Long = 0L

    fun store(number: String?) {
        val normalized = number?.trim().orEmpty()
        if (normalized.isBlank()) return
        this.number = normalized
        storedAt = SystemClock.elapsedRealtime()
    }

    fun peekNumber(): String {
        if (number.isBlank()) return ""
        if (SystemClock.elapsedRealtime() - storedAt > TTL_MS) {
            clear()
            return ""
        }
        return number
    }

    fun takeNumber(): String {
        val value = peekNumber()
        clear()
        return value
    }

    fun clear() {
        number = ""
        storedAt = 0L
    }
}