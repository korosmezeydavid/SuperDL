package com.superdl.launcher.assistant

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.speech.SpeechRecognizer
import androidx.core.app.NotificationCompat
import com.superdl.launcher.MainActivity
import com.superdl.launcher.voice.VoiceInput

class ElenaWakeListenService : Service() {

    companion object {
        private const val CHANNEL_ID = "ELENA_WAKE_CHANNEL"
        private const val NOTIFICATION_ID = 7600
        const val ACTION_STOP = "com.superdl.launcher.action.ELENA_WAKE_STOP"
        const val ACTION_PAUSE = "com.superdl.launcher.action.ELENA_WAKE_PAUSE"
        const val ACTION_RESUME = "com.superdl.launcher.action.ELENA_WAKE_RESUME"
        private const val LISTEN_CYCLE_MS = 450L
        private const val ERROR_BACKOFF_MS = 2_200L
    }

    private val handler = Handler(Looper.getMainLooper())
    private var voiceInput: VoiceInput? = null
    private var listeningGeneration = 0
    private var activeListenGeneration = 0

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        voiceInput = VoiceInput(applicationContext)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                ElenaWakeStore.setListenEnabled(this, false)
                shutdown()
                return START_NOT_STICKY
            }
            ACTION_PAUSE -> {
                ElenaWakeStore.listeningPaused = true
                stopActiveListening()
                return START_STICKY
            }
            ACTION_RESUME -> {
                ElenaWakeStore.listeningPaused = false
                if (ElenaWakeStore.isListenEnabled(this)) {
                    scheduleListen(LISTEN_CYCLE_MS)
                }
                return START_STICKY
            }
        }

        if (!ElenaWakeStore.isListenEnabled(this)) {
            shutdown()
            return START_NOT_STICKY
        }

        startForeground(NOTIFICATION_ID, buildNotification())
        if (!ElenaWakeStore.listeningPaused) {
            scheduleListen(LISTEN_CYCLE_MS)
        }
        return START_STICKY
    }

    override fun onDestroy() {
        listeningGeneration++
        handler.removeCallbacksAndMessages(null)
        stopActiveListening()
        voiceInput?.destroy()
        voiceInput = null
        super.onDestroy()
    }

    private fun scheduleListen(delayMs: Long = LISTEN_CYCLE_MS) {
        val generation = ++listeningGeneration
        handler.postDelayed({
            if (generation != listeningGeneration) return@postDelayed
            if (!ElenaWakeStore.isListenEnabled(this)) {
                shutdown()
                return@postDelayed
            }
            if (ElenaWakeStore.listeningPaused) {
                stopActiveListening()
                return@postDelayed
            }
            listenOnce(generation)
        }, delayMs)
    }

    private fun listenOnce(generation: Int) {
        val input = voiceInput ?: return
        if (!input.isAvailable()) {
            scheduleListen(3000L)
            return
        }
        activeListenGeneration = generation
        input.listenPromptWakeWord(
            hints = ArrayList(ElenaWakeHelper.wakeHints(this)),
            onResult = { result ->
                if (!isListenCycleActive(generation)) return@listenPromptWakeWord
                handleRecognition(result.hypotheses.firstOrNull().orEmpty())
                scheduleListen(LISTEN_CYCLE_MS)
            },
            onError = { errorCode ->
                if (!isListenCycleActive(generation)) return@listenPromptWakeWord
                val backoff = if (errorCode == SpeechRecognizer.ERROR_RECOGNIZER_BUSY) {
                    3200L
                } else {
                    ERROR_BACKOFF_MS
                }
                scheduleListen(backoff)
            }
        )
    }

    private fun isListenCycleActive(generation: Int): Boolean {
        if (generation != listeningGeneration || generation != activeListenGeneration) return false
        if (!ElenaWakeStore.isListenEnabled(this)) return false
        if (ElenaWakeStore.listeningPaused) {
            stopActiveListening()
            return false
        }
        return true
    }

    private fun handleRecognition(raw: String) {
        if (raw.isBlank()) return
        val corrected = com.superdl.launcher.voice.SpeechCorrections.apply(raw)
        if (!ElenaWakeHelper.containsWakePhrase(corrected, this)) return

        val command = ElenaWakeHelper.stripWakePrefix(corrected, this).orEmpty()
        ElenaWakeStore.listeningPaused = true
        stopActiveListening()

        val launch = Intent(this, MainActivity::class.java).apply {
            action = MainActivity.ACTION_LAUNCH_VOICE_ASSISTANT
            addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP or
                    Intent.FLAG_ACTIVITY_REORDER_TO_FRONT
            )
            putExtra(MainActivity.EXTRA_LAUNCH_VOICE_ASSISTANT, true)
            if (command.isNotBlank()) {
                putExtra(MainActivity.EXTRA_WAKE_COMMAND, command)
            } else {
                putExtra(MainActivity.EXTRA_WAKE_GREETING_ONLY, true)
            }
        }
        try {
            startActivity(launch)
        } catch (_: Exception) {
            ElenaWakeStore.listeningPaused = false
            scheduleListen(2000L)
        }
    }

    private fun stopActiveListening() {
        activeListenGeneration = 0
        voiceInput?.cancel()
    }

    private fun shutdown() {
        listeningGeneration++
        ElenaWakeStore.listeningPaused = false
        handler.removeCallbacksAndMessages(null)
        stopActiveListening()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Elena figyelő",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Elena felébresztő figyelés a háttérben"
            setShowBadge(false)
        }
        getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
    }

    private fun buildNotification(): Notification {
        val stopIntent = Intent(this, ElenaWakeListenService::class.java).apply {
            action = ACTION_STOP
        }
        val stopPending = PendingIntent.getService(
            this,
            0,
            stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Elena figyelő")
            .setContentText("Csendben figyel. Mondd: Szia Elena vagy Kérlek Elena.")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .setSilent(true)
            .addAction(
                android.R.drawable.ic_menu_close_clear_cancel,
                "Kikapcsolás",
                stopPending
            )
            .build()
    }
}