package com.superdl.launcher.call

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.Ringtone
import android.media.RingtoneManager
import android.media.ToneGenerator
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.core.app.NotificationCompat
import com.superdl.launcher.R
import com.superdl.launcher.contacts.ContactHelper
import com.superdl.launcher.feedback.GestureSoundHelper
import com.superdl.launcher.system.QuietModeHelper

/**
 * Plays the incoming-call ringtone and vibration when this app is the default dialer.
 * Required because [android.telecom.IN_CALL_SERVICE_RINGING] delegates ringing to us.
 */
object IncomingCallRinger {

    private const val CHANNEL_ID = "superdl_incoming_calls"
    private const val NOTIFICATION_ID = 7401

    private val mainHandler = Handler(Looper.getMainLooper())

    @Volatile
    private var ringing = false

    private var mediaPlayer: MediaPlayer? = null
    private var ringtone: Ringtone? = null
    private var fallbackTone: ToneGenerator? = null
    private var vibrator: Vibrator? = null
    private var audioManager: AudioManager? = null
    private var audioFocusRequest: AudioFocusRequest? = null
    private var savedAudioMode = AudioManager.MODE_NORMAL

    fun start(context: Context, phone: String, name: String) {
        val appContext = context.applicationContext
        mainHandler.post {
            if (QuietModeHelper.shouldSuppressIncomingCalls(appContext)) return@post
            if (!ringing) {
                ringing = true
                ensureNotificationChannel(appContext)
            }
            postIncomingNotification(appContext, phone, name)
            startRingtone(appContext, phone)
            startVibration(appContext)
        }
    }

    fun stop(context: Context) {
        val appContext = context.applicationContext
        mainHandler.post {
            ringing = false
            stopRingtone()
            stopVibration()
            abandonAudioFocus()
            restoreAudioMode()
            cancelNotification(appContext)
        }
    }

    private fun startRingtone(context: Context, phone: String = "") {
        if (mediaPlayer?.isPlaying == true) return

        val manager = context.getSystemService(AudioManager::class.java) ?: return
        audioManager = manager
        savedAudioMode = manager.mode

        // Először a névjegyhez rendelt EGYÉNI csengőhangot keressük.
        // Vakon ez a leggyorsabb azonosítás: a hangból tudod, ki keres,
        // meg sem kell érintened a telefont.
        val customUri = if (phone.isNotBlank()) {
            com.superdl.launcher.contacts.ContactRingtoneStore
                .getForPhone(context, phone)
                ?.uri
                ?.let { android.net.Uri.parse(it) }
        } else {
            null
        }

        val uri = customUri
            ?: com.superdl.launcher.sound.RingtonePreferenceStore.getRingtoneUri(context)
            ?: RingtoneManager.getActualDefaultRingtoneUri(context, RingtoneManager.TYPE_RINGTONE)
            ?: return

        val useAlarmStream = manager.ringerMode != AudioManager.RINGER_MODE_NORMAL
        if (useAlarmStream) {
            GestureSoundHelper.ensureAlarmStreamAudible(context)
        } else {
            GestureSoundHelper.ensureRingStreamAudible(context)
        }

        try {
            manager.mode = AudioManager.MODE_RINGTONE
        } catch (_: Exception) {
        }

        requestRingtoneAudioFocus(manager, useAlarmStream)

        val audioAttributes = if (useAlarmStream) {
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ALARM)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .setLegacyStreamType(AudioManager.STREAM_ALARM)
                .build()
        } else {
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .setLegacyStreamType(AudioManager.STREAM_RING)
                .build()
        }

        try {
            mediaPlayer?.release()
            mediaPlayer = MediaPlayer().apply {
                setDataSource(context, uri)
                setAudioAttributes(audioAttributes)
                setVolume(1f, 1f)
                isLooping = true
                setOnErrorListener { mp, _, _ ->
                    try {
                        mp.release()
                    } catch (_: Exception) {
                    }
                    if (mediaPlayer === mp) mediaPlayer = null
                    startFallbackRingtone(context, useAlarmStream)
                    true
                }
                prepare()
                start()
            }
            if (mediaPlayer?.isPlaying != true) {
                stopRingtone()
                startFallbackRingtone(context, useAlarmStream)
            }
        } catch (_: Exception) {
            mediaPlayer?.release()
            mediaPlayer = null
            startFallbackRingtone(context, useAlarmStream)
        }
    }

    private fun startFallbackRingtone(context: Context, useAlarmStream: Boolean) {
        val uri = com.superdl.launcher.sound.RingtonePreferenceStore.getRingtoneUri(context)
            ?: RingtoneManager.getActualDefaultRingtoneUri(context, RingtoneManager.TYPE_RINGTONE)
        val attributes = if (useAlarmStream) {
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ALARM)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .setLegacyStreamType(AudioManager.STREAM_ALARM)
                .build()
        } else {
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .setLegacyStreamType(AudioManager.STREAM_RING)
                .build()
        }

        if (uri != null) {
            try {
                ringtone = RingtoneManager.getRingtone(context, uri)?.also { active ->
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                        active.audioAttributes = attributes
                    } else {
                        @Suppress("DEPRECATION")
                        active.streamType = if (useAlarmStream) {
                            AudioManager.STREAM_ALARM
                        } else {
                            AudioManager.STREAM_RING
                        }
                    }
                    active.play()
                }
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P && ringtone?.isPlaying == true) return
            } catch (_: Exception) {
                ringtone = null
            }
        }

        try {
            val stream = if (useAlarmStream) AudioManager.STREAM_ALARM else AudioManager.STREAM_RING
            fallbackTone = ToneGenerator(stream, 90).also { tone ->
                tone.startTone(ToneGenerator.TONE_CDMA_ALERT_CALL_GUARD, 1500)
            }
        } catch (_: Exception) {
            fallbackTone = null
        }
    }

    private fun requestRingtoneAudioFocus(manager: AudioManager, useAlarmStream: Boolean) {
        val attributes = if (useAlarmStream) {
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ALARM)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build()
        } else {
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build()
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
                .setAudioAttributes(attributes)
                .setAcceptsDelayedFocusGain(false)
                .setWillPauseWhenDucked(false)
                .build()
            audioFocusRequest = request
            manager.requestAudioFocus(request)
        } else {
            @Suppress("DEPRECATION")
            manager.requestAudioFocus(
                null,
                if (useAlarmStream) AudioManager.STREAM_ALARM else AudioManager.STREAM_RING,
                AudioManager.AUDIOFOCUS_GAIN_TRANSIENT
            )
        }
    }

    private fun startVibration(context: Context) {
        val manager = context.getSystemService(AudioManager::class.java) ?: return
        if (manager.ringerMode == AudioManager.RINGER_MODE_SILENT) return

        val activeVibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            context.getSystemService(VibratorManager::class.java)?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Vibrator::class.java)
        } ?: return

        vibrator = activeVibrator
        val pattern = longArrayOf(0, 1000, 1000)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                activeVibrator.vibrate(VibrationEffect.createWaveform(pattern, 0))
            } else {
                @Suppress("DEPRECATION")
                activeVibrator.vibrate(pattern, 0)
            }
        } catch (_: Exception) {
        }
    }

    private fun stopRingtone() {
        try {
            mediaPlayer?.stop()
        } catch (_: Exception) {
        }
        try {
            mediaPlayer?.release()
        } catch (_: Exception) {
        }
        mediaPlayer = null
        try {
            ringtone?.stop()
        } catch (_: Exception) {
        }
        ringtone = null
        try {
            fallbackTone?.release()
        } catch (_: Exception) {
        }
        fallbackTone = null
    }

    private fun stopVibration() {
        try {
            vibrator?.cancel()
        } catch (_: Exception) {
        }
        vibrator = null
    }

    private fun abandonAudioFocus() {
        val manager = audioManager ?: return
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                audioFocusRequest?.let { manager.abandonAudioFocusRequest(it) }
            } else {
                @Suppress("DEPRECATION")
                manager.abandonAudioFocus(null)
            }
        } catch (_: Exception) {
        }
        audioFocusRequest = null
    }

    private fun restoreAudioMode() {
        val manager = audioManager ?: return
        try {
            if (manager.mode == AudioManager.MODE_RINGTONE ||
                manager.mode == AudioManager.MODE_IN_COMMUNICATION
            ) {
                manager.mode = savedAudioMode.takeIf { it != AudioManager.MODE_RINGTONE }
                    ?: AudioManager.MODE_NORMAL
            }
        } catch (_: Exception) {
        }
        audioManager = null
    }

    private fun ensureNotificationChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            context.getString(R.string.incoming_call_channel_name),
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = context.getString(R.string.incoming_call_channel_desc)
            setBypassDnd(true)
            lockscreenVisibility = NotificationCompat.VISIBILITY_PUBLIC
        }
        context.getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
    }

    private fun postIncomingNotification(context: Context, phone: String, name: String) {
        val launchIntent = Intent(context, IncomingCallActivity::class.java).apply {
            putExtra(IncomingCallActivity.EXTRA_PHONE, phone)
            putExtra(IncomingCallActivity.EXTRA_NAME, name)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or
                Intent.FLAG_ACTIVITY_CLEAR_TOP or
                Intent.FLAG_ACTIVITY_SINGLE_TOP or
                Intent.FLAG_ACTIVITY_REORDER_TO_FRONT
        }
        val pendingIntent = PendingIntent.getActivity(
            context,
            NOTIFICATION_ID,
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val masked = ContactHelper.maskPhone(phone)
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.sym_call_incoming)
            .setContentTitle(context.getString(R.string.incoming_call_notification_title, name))
            .setContentText(masked)
            .setCategory(NotificationCompat.CATEGORY_CALL)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setOngoing(true)
            .setAutoCancel(false)
            .setContentIntent(pendingIntent)
            .setFullScreenIntent(pendingIntent, true)
            .build()
        context.getSystemService(NotificationManager::class.java)
            ?.notify(NOTIFICATION_ID, notification)
    }

    private fun cancelNotification(context: Context) {
        context.getSystemService(NotificationManager::class.java)?.cancel(NOTIFICATION_ID)
    }
}