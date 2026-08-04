package com.superdl.launcher.gps

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.location.Location
import android.location.LocationListener
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat
import com.superdl.launcher.patrol.PatrolAnnouncer

/**
 * Voice Vista / Soundscape-szerű környezeti figyelő.
 * Folyamatos G P S-frissítéssel és háttérszálon futó utca- és kereszteződés-bemondás.
 */
class GpsSurroundingsService : Service() {

    companion object {
        private const val CHANNEL_ID = "GPS_SURROUNDINGS_CHANNEL"
        private const val NOTIFICATION_ID = 7401
        private const val LOCATION_INTERVAL_MS = 2_000L
    }

    private val mainHandler = Handler(Looper.getMainLooper())
    private var compass: CompassProvider? = null
    private var locationListener: LocationListener? = null
    private var announcedIntro = false
    private val poiProximityWatcher = SavedPoiProximityWatcher(this)

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        GpsRadarStore.surroundingsMonitoringActive = true
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        compass = CompassProvider(this).also { it.start() }
        locationListener = GpsLocationHelper.requestUpdates(this, LOCATION_INTERVAL_MS) { location ->
            GpsRadarStore.lastLocation = location
            handleLocationUpdate(location)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    override fun onDestroy() {
        mainHandler.removeCallbacksAndMessages(null)
        GpsLocationHelper.removeUpdates(this, locationListener)
        compass?.stop()
        compass = null
        locationListener = null
        poiProximityWatcher.reset()
        GpsRadarStore.surroundingsMonitoringActive = false
        super.onDestroy()
    }

    private fun handleLocationUpdate(location: Location) {
        val heading = compass?.heading() ?: GpsRadarStore.lastHeading
        GpsRadarStore.lastHeading = heading

        // Mentett helyek hangjegyzeteinek automatikus lejátszása odaéréskor.
        poiProximityWatcher.onLocation(location)

        val cached = GpsRadarStore.streetContext
        if (cached != null) {
            val refreshed = GpsStreetHelper.refreshContext(cached, location.latitude, location.longitude, heading)
            GpsRadarStore.streetContext = refreshed
            announceMessages(GpsStreetAnnouncer.evaluate(refreshed, heading))
        }

        if (!GpsStreetAnnouncer.shouldFetchContext(location)) return
        GpsStreetAnnouncer.fetchContextAsync(
            latitude = location.latitude,
            longitude = location.longitude,
            headingDegrees = heading
        ) { context ->
            mainHandler.post {
                if (!GpsRadarStore.surroundingsMonitoringActive) return@post
                if (context == null) return@post
                announceMessages(GpsStreetAnnouncer.evaluate(context, heading))
                if (!announcedIntro && GpsRadarStore.streetMonitoringEnabled) {
                    announcedIntro = true
                    PatrolAnnouncer.announce(this, GpsStreetAnnouncer.introMessage(), withBeep = false)
                }
            }
        }
    }

    private fun announceMessages(messages: List<String>) {
        // FONTOS: a hálózati lekérdezés közben a felhasználó kiléphetett. A
        // bemondás előtt ellenőrizzük, hogy még aktív-e a figyelő — különben a
        // főmenüben is "beragadva" mondaná az utcaneveket/kereszteződéseket.
        if (!GpsRadarStore.surroundingsMonitoringActive) {
            stopSelf()
            return
        }
        messages.forEach { message ->
            PatrolAnnouncer.announce(this, message, withBeep = false)
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "GPS Környezeti figyelő",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Utcanevek és kereszteződések automatikus bemondása séta közben"
            setShowBadge(false)
        }
        getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
    }

    private fun buildNotification(): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("GPS Környezeti figyelő")
            .setContentText("Utcák és kereszteződések figyelése aktív")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setOngoing(true)
            .setSilent(true)
            .build()
}