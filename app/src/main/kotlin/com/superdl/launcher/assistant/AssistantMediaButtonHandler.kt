package com.superdl.launcher.assistant

import android.content.Context
import android.content.Intent
import android.media.session.MediaSession
import android.os.SystemClock
import android.view.KeyEvent
import com.superdl.launcher.MainActivity

class AssistantMediaButtonHandler(
    private val activity: MainActivity
) {
    private var mediaSession: MediaSession? = null
    private var keyDownAt = 0L
    private var announced = false

    fun start() {
        if (!BluetoothAssistantStore.isEnabled(activity)) return
        if (mediaSession != null) return
        mediaSession = MediaSession(activity, "SuperDLAssistant").apply {
            setCallback(object : MediaSession.Callback() {
                override fun onMediaButtonEvent(mediaButtonIntent: Intent): Boolean {
                    if (!BluetoothAssistantStore.isEnabled(activity)) return false
                    val event = if (android.os.Build.VERSION.SDK_INT >= 33) {
                        mediaButtonIntent.getParcelableExtra(Intent.EXTRA_KEY_EVENT, KeyEvent::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        mediaButtonIntent.getParcelableExtra(Intent.EXTRA_KEY_EVENT)
                    } ?: return false
                    return handleKeyEvent(event)
                }
            })
            isActive = true
        }
        if (!announced) {
            announced = true
        }
    }

    fun stop() {
        mediaSession?.isActive = false
        mediaSession?.release()
        mediaSession = null
    }

    private fun handleKeyEvent(event: KeyEvent): Boolean {
        val code = event.keyCode
        val isMediaKey = code == KeyEvent.KEYCODE_HEADSETHOOK ||
            code == KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE ||
            code == KeyEvent.KEYCODE_MEDIA_PLAY ||
            code == KeyEvent.KEYCODE_MEDIA_PAUSE
        if (!isMediaKey) return false

        when (event.action) {
            KeyEvent.ACTION_DOWN -> {
                if (event.repeatCount == 0) keyDownAt = SystemClock.uptimeMillis()
                return true
            }
            KeyEvent.ACTION_UP -> {
                val held = SystemClock.uptimeMillis() - keyDownAt
                if (held >= 550L) {
                    activity.launchVoiceAssistantFromMediaButton()
                }
                return true
            }
        }
        return false
    }

    companion object {
        fun speakStatus(context: Context, enabled: Boolean): String =
            if (enabled) {
                "Bluetooth gomb figyelve. Hosszú nyomás: Elena."
            } else {
                "Bluetooth asszisztens gomb kikapcsolva."
            }
    }
}