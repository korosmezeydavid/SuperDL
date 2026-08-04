package com.superdl.launcher.security

import android.content.Context

object LockSession {

    @Volatile
    var isUnlocked: Boolean = false

    @Volatile
    var lockScreenVisible: Boolean = false

    fun unlock() {
        isUnlocked = true
        lockScreenVisible = false
    }

    fun lock() {
        isUnlocked = false
    }

    fun needsUnlock(context: Context): Boolean =
        LockPinStore.isEnabled(context) &&
            LockPinStore.hasPinSet(context) &&
            !isUnlocked
}