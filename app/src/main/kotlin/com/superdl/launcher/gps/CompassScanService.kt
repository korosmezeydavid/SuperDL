package com.superdl.launcher.gps

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.location.Location
import android.os.Build
import android.os.Handler
import android.os.Looper
import androidx.core.app.NotificationCompat
import com.superdl.launcher.patrol.PatrolAnnouncer

/**
 * Hang-iránytű "söprő mód": a felhasználó forgatja a telefont, és ahogy egy
 * környező hely a nézési irányba kerül, az app kimondja a nevét, óra-irányát
 * és távolságát. A meglévő GPS radar POI-jaira és iránytűjére épül, de nem egy
 * célt követ, hanem élő felfedezést ad a "merre van mi" kérdésre.
 */
class CompassScanService : Service() {

    companion object {
        private const val CHANNEL_ID = "COMPASS_SCAN_CHANNEL"
        private const val NOTIFICATION_ID = 7420
        private const val SCAN_INTERVAL_MS = 500L
        private const val POI_REFRESH_MS = 20_000L
    }

    private val handler = Handler(Looper.getMainLooper())
    private var compass: CompassProvider? = null
    private val scanHelper = CompassScanHelper()

    @Volatile
    private var pois: List<GpsPoi> = emptyList()

    @Volatile
    private var lastLocation: Location? = null
    private var lastPoiRefreshAt = 0L
    private var announcedStart = false

    private val scanRunnable = object : Runnable {
        override fun run() {
            performScan()
            handler.postDelayed(this, SCAN_INTERVAL_MS)
        }
    }

    override fun onBind(intent: Intent?) = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        compass = CompassProvider(this).also { it.start() }
        scanHelper.reset()
        loadPois()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!CompassScanStore.isActive) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (!announcedStart) {
            announcedStart = true
            PatrolAnnouncer.announce(
                this,
                "Hang-iránytű bekapcsolva. Forgasd a telefont, és megnevezem a helyeket amerre nézel.",
                withBeep = true,
                critical = true
            )
            handler.post(scanRunnable)
        }
        return START_STICKY
    }

    override fun onDestroy() {
        handler.removeCallbacks(scanRunnable)
        compass?.stop()
        compass = null
        super.onDestroy()
    }

    private fun loadPois() {
        lastPoiRefreshAt = System.currentTimeMillis()
        val heading = compass?.heading() ?: 0f
        GpsRadarHelper.loadNearbyPois(
            context = this,
            headingDegrees = heading,
            onResult = { list ->
                lastLocation = GpsRadarStore.lastLocation
                // Csak a valódi helyek (nem utcák/kereszteződések), a felfedezéshez.
                pois = list.filter { it.category != "utca" && it.category != "kereszteződés" }
                if (pois.isEmpty()) {
                    PatrolAnnouncer.announce(
                        this,
                        "Nincs ismert hely a közeledben.",
                        withBeep = false,
                        critical = true
                    )
                }
            },
            onError = { message ->
                PatrolAnnouncer.announce(this, message, withBeep = false, critical = true)
            }
        )
    }

    private fun performScan() {
        if (!CompassScanStore.isActive) {
            stopSelf()
            return
        }
        val now = System.currentTimeMillis()
        val heading = compass?.heading() ?: return
        val location = GpsRadarStore.lastLocation ?: lastLocation

        // A POI-k irányát/távolságát frissítjük az aktuális helyhez.
        val livePois = if (location != null) {
            GpsRadarHelper.updatePoiDirections(pois, location, heading)
        } else {
            pois
        }

        val toSpeak = scanHelper.pickAnnouncement(livePois, heading, now)
        if (toSpeak != null) {
            // FONTOS: a pickAnnouncement/hálózat közben a felhasználó kiléphetett.
            // A bemondás ELŐTT újra ellenőrizzük, hogy még aktív-e a szolgáltatás —
            // különben a főmenüben is "beragadva" mondaná a GPS-szöveget.
            if (!CompassScanStore.isActive) {
                stopSelf()
                return
            }
            val text = scanHelper.speakText(toSpeak, heading)
            PatrolAnnouncer.announce(this, text, withBeep = false, critical = true)
        }

        // Időnként frissítjük a POI-listát (ha elmozdultál).
        if (now - lastPoiRefreshAt >= POI_REFRESH_MS) {
            loadPois()
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Hang-iránytű",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Élő térbeli tájékozódás forgatással"
            setShowBadge(false)
        }
        getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
    }

    private fun buildNotification(): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Hang-iránytű")
            .setContentText("Forgasd a telefont a tájékozódáshoz")
            .setSmallIcon(android.R.drawable.ic_menu_compass)
            .setOngoing(true)
            .setSilent(true)
            .build()
}
