package com.superdl.launcher.lock.keyguard

import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

object AccessibilityAssistBridge {

    @Volatile
    var activeService: KeyguardPinAccessibilityService? = null

    fun isServiceRunning(): Boolean = activeService != null

    fun toggleHotspot(targetEnabled: Boolean, timeoutMs: Long = 8000L): Boolean {
        val service = activeService ?: return false
        val latch = CountDownLatch(1)
        val success = AtomicBoolean(false)
        service.requestHotspotToggle(targetEnabled) { ok ->
            success.set(ok)
            latch.countDown()
        }
        latch.await(timeoutMs, TimeUnit.MILLISECONDS)
        return success.get()
    }
}