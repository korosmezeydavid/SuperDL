package com.superdl.launcher.alarm

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.core.app.NotificationCompat

/**
 * Egy megszólaló ébresztő valódi hangját kezeli: a kiválasztott (vagy alap)
 * gyári ébresztőhangot ismétlődően, ébresztő-hangcsatornán, FOKOZATOSAN
 * hangosodva játssza – kíméletes ébredés. Mellette rezgés.
 *
 * Foreground service, hogy zárolt képernyőnél és háttérben is megbízhatóan
 * szóljon. A hangot a felhasználó a szundival vagy leállítással némítja
 * (AlarmAlertActivity), vagy egy biztonsági időkorlát után magától elhallgat.
 */
class AlarmService : Service() {

    companion object {
        const val EXTRA_ALARM_ID = "alarm_id"
        const val EXTRA_LABEL = "label"
        const val EXTRA_TONE_URI = "tone_uri"
        const val ACTION_STOP = "com.superdl.launcher.alarm.STOP"

        private const val CHANNEL_ID = "ALARM_SERVICE_CHANNEL"
        private const val NOTIFICATION_ID = 8420
        // Fokozatos hangosodás: ennyi idő alatt éri el a teljes hangerőt.
        private const val FADE_DURATION_MS = 30_000L
        private const val FADE_STEP_MS = 1_500L
        // Biztonsági időkorlát: ennyi után magától leáll, ha senki nem reagál.
        private const val AUTO_STOP_MS = 10 * 60 * 1000L
    }

    private val handler = Handler(Looper.getMainLooper())
    private var player: MediaPlayer? = null
    private var vibrator: Vibrator? = null
    private var currentVolume = 0f

    private val fadeRunnable = object : Runnable {
        override fun run() {
            currentVolume = (currentVolume + (FADE_STEP_MS.toFloat() / FADE_DURATION_MS)).coerceAtMost(1f)
            player?.setVolume(currentVolume, currentVolume)
            if (currentVolume < 1f) {
                handler.postDelayed(this, FADE_STEP_MS)
            }
        }
    }

    private val autoStopRunnable = Runnable { stopSelf() }

    override fun onBind(intent: Intent?) = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        val label = intent?.getStringExtra(EXTRA_LABEL)?.takeIf { it.isNotBlank() } ?: "Ébresztő"
        val toneUri = intent?.getStringExtra(EXTRA_TONE_URI)?.let(Uri::parse)
            ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)

        startForeground(NOTIFICATION_ID, buildNotification(label))
        startVibration()
        startTone(toneUri)

        handler.postDelayed(autoStopRunnable, AUTO_STOP_MS)
        return START_STICKY
    }

    private fun startTone(uri: Uri?) {
        if (uri == null) return
        try {
            player = MediaPlayer().apply {
                setDataSource(this@AlarmService, uri)
                setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ALARM)
                        .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                        .build()
                )
                isLooping = true
                prepare()
                // Halkan indulunk, majd a fadeRunnable felhúzza.
                currentVolume = 0.1f
                setVolume(currentVolume, currentVolume)
                start()
            }
            // A rendszer ébresztő-hangerejét felvisszük, hogy tényleg hallható legyen.
            raiseAlarmStreamVolume()
            handler.postDelayed(fadeRunnable, FADE_STEP_MS)
        } catch (_: Exception) {
            // Ha a hang nem indul, a rezgés akkor is figyelmeztet.
        }
    }

    private fun raiseAlarmStreamVolume() {
        try {
            val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            val max = am.getStreamMaxVolume(AudioManager.STREAM_ALARM)
            am.setStreamVolume(AudioManager.STREAM_ALARM, max, 0)
        } catch (_: Exception) {
        }
    }

    private fun startVibration() {
        val pattern = longArrayOf(0, 600, 400, 600, 400)
        try {
            vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                (getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator?.vibrate(VibrationEffect.createWaveform(pattern, 0))
            } else {
                @Suppress("DEPRECATION")
                vibrator?.vibrate(pattern, 0)
            }
        } catch (_: Exception) {
        }
    }

    private fun buildNotification(label: String): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Ébresztő")
            .setContentText(label)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .build()

    private fun createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Ébresztő szolgáltatás",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "Aktív ébresztő hangja"
            setSound(null, null) // a hangot a service kezeli, ne a csatorna
            enableVibration(false)
        }
        getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
    }

    override fun onDestroy() {
        handler.removeCallbacks(fadeRunnable)
        handler.removeCallbacks(autoStopRunnable)
        player?.runCatching {
            if (isPlaying) stop()
            release()
        }
        player = null
        vibrator?.cancel()
        vibrator = null
        super.onDestroy()
    }
}
