package com.superdl.launcher.sound

import android.content.Context
import android.media.AudioAttributes
import android.media.Ringtone
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build

/**
 * Egyetlen gyári hang rövid előnézetét játssza le választás közben
 * ("belehallgatás"). Mindig csak egy hang szól: új előnézet indítása
 * leállítja az előzőt. Gondos életciklus – a korábbi instabilitás elkerülésére.
 */
class RingtonePreviewPlayer(private val context: Context) {

    private var current: Ringtone? = null

    /** Belehallgatás a megadott hangba (az adott csatorna-típussal). */
    fun preview(uri: Uri, streamType: Int) {
        stop()
        try {
            val ringtone = RingtoneManager.getRingtone(context, uri) ?: return
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                ringtone.audioAttributes = AudioAttributes.Builder()
                    .setUsage(usageForStream(streamType))
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build()
            }
            current = ringtone
            ringtone.play()
        } catch (_: Exception) {
            current = null
        }
    }

    fun stop() {
        current?.let {
            try {
                if (it.isPlaying) it.stop()
            } catch (_: Exception) {
            }
        }
        current = null
    }

    private fun usageForStream(streamType: Int): Int = when (streamType) {
        android.media.AudioManager.STREAM_ALARM -> AudioAttributes.USAGE_ALARM
        android.media.AudioManager.STREAM_RING -> AudioAttributes.USAGE_NOTIFICATION_RINGTONE
        else -> AudioAttributes.USAGE_NOTIFICATION
    }
}
