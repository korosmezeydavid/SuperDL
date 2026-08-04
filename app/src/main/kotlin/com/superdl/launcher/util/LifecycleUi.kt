package com.superdl.launcher.util

import android.app.Activity
import android.os.Handler
import android.os.Looper

private val mainHandler by lazy { Handler(Looper.getMainLooper()) }

fun Activity.postWhenAlive(block: () -> Unit) {
    if (isFinishing || isDestroyed) return
    mainHandler.post {
        if (isFinishing || isDestroyed) return@post
        block()
    }
}

fun Activity.cancelUiCallbacks(handler: Handler) {
    handler.removeCallbacksAndMessages(null)
}