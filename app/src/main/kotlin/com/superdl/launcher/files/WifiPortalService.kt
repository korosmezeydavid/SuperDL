package com.superdl.launcher.files

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.superdl.launcher.MainActivity
import com.superdl.launcher.patrol.PatrolAnnouncer

/**
 * A WiFi fájlportált életben tartó szolgáltatás.
 *
 * Foreground service kell hozzá, különben az Android leállítja, amint a
 * felhasználó más appra vált – a portálnak viszont akkor is mennie kell,
 * amíg a gépről tölt fel.
 *
 * WifiLock: megakadályozza, hogy a WiFi elaludjon átvitel közben.
 */
class WifiPortalService : Service() {

    companion object {
        const val ACTION_STOP = "com.superdl.launcher.files.PORTAL_STOP"
        private const val CHANNEL_ID = "WIFI_PORTAL_CHANNEL"
        private const val NOTIFICATION_ID = 8801

        @Volatile
        private var server: WifiPortalServer? = null

        val isRunning: Boolean get() = server?.isRunning == true

        /** A böngészőbe írandó cím, ha fut a portál. */
        fun currentUrl(): String? = server?.portalUrl()

        /** Felolvasható cím. */
        fun currentSpokenUrl(): String? = server?.speakUrl()

        /** A portál PIN kódja, ha fut (felolvasható alakban: "3 7 2 9"). */
        fun currentSpokenPin(): String? = server?.speakPin()

        /** A portál PIN kódja, ha fut. */
        fun currentPin(): String? = server?.pin

        fun start(context: Context) {
            val intent = Intent(context, WifiPortalService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            context.startService(
                Intent(context, WifiPortalService::class.java).apply { action = ACTION_STOP }
            )
        }
    }

    private var wifiLock: WifiManager.WifiLock? = null

    /**
     * CPU-ébrentartás. A WifiLock csak a rádiót tartja ébren, a PROCESSZORT nem:
     * hosszú (több száz MB-os) feltöltés közben — főleg lezárt képernyőnél — a
     * készülék mély alvásba mehet, az átvitel megáll, és a socket időkorlátja
     * elvágja a kapcsolatot ("Nem sikerült a kapcsolat"). Ez tartja ébren a CPU-t,
     * amíg a portál fut.
     */
    private var wakeLock: android.os.PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopPortal()
            stopSelf()
            return START_NOT_STICKY
        }

        val srv = server ?: WifiPortalServer(applicationContext).also { newServer ->
            // Feltöltéskor a telefon bemondja, mi érkezett és hova.
            newServer.onFilesUploaded = { names, destination ->
                val what = when {
                    names.size == 1 -> names.first()
                    names.size <= 3 -> names.joinToString(", ")
                    else -> "${names.size} fájl"
                }
                PatrolAnnouncer.announce(
                    applicationContext,
                    "Fájl megérkezett: $what. Helye: $destination.",
                    withBeep = false,
                    softChime = true
                )
            }
            server = newServer
        }
        if (!srv.isRunning) {
            if (!srv.start()) {
                stopSelf()
                return START_NOT_STICKY
            }
        }
        acquireWifiLock()
        acquireWakeLock()
        startForeground(NOTIFICATION_ID, buildNotification(srv.portalUrl()))
        return START_STICKY
    }

    private fun stopPortal() {
        server?.stop()
        server = null
        releaseWifiLock()
        releaseWakeLock()
    }

    private fun acquireWakeLock() {
        try {
            val pm = applicationContext.getSystemService(Context.POWER_SERVICE)
                as android.os.PowerManager
            wakeLock = pm.newWakeLock(
                android.os.PowerManager.PARTIAL_WAKE_LOCK,
                "SuperDL:PortalCpu"
            ).apply {
                setReferenceCounted(false)
                acquire()
            }
        } catch (_: Exception) {
        }
    }

    private fun releaseWakeLock() {
        try {
            wakeLock?.let { if (it.isHeld) it.release() }
        } catch (_: Exception) {
        }
        wakeLock = null
    }

    private fun acquireWifiLock() {
        try {
            val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            wifiLock = wm.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "SuperDL:Portal")
                .apply {
                    setReferenceCounted(false)
                    acquire()
                }
        } catch (_: Exception) {
        }
    }

    private fun releaseWifiLock() {
        try {
            wifiLock?.let { if (it.isHeld) it.release() }
        } catch (_: Exception) {
        }
        wifiLock = null
    }

    private fun buildNotification(url: String?): Notification {
        val openApp = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val stopIntent = PendingIntent.getService(
            this,
            1,
            Intent(this, WifiPortalService::class.java).apply { action = ACTION_STOP },
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Fájlportál bekapcsolva")
            .setContentText(url ?: "Nincs WiFi kapcsolat")
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setOngoing(true)
            .setContentIntent(openApp)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Leállítás", stopIntent)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "WiFi fájlportál",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "A fájlportál akkor fut, amíg be van kapcsolva"
            setSound(null, null)
        }
        getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
    }

    override fun onDestroy() {
        stopPortal()
        super.onDestroy()
    }
}
