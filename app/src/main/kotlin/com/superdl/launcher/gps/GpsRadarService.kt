package com.superdl.launcher.gps

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.location.Location
import android.location.LocationListener
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat
import com.superdl.launcher.patrol.PatrolAnnouncer

class GpsRadarService : Service() {

    companion object {
        private const val CHANNEL_ID = "GPS_RADAR_CHANNEL"
        private const val NOTIFICATION_ID = 7400
        private const val DIRECTION_BEEP_MS = 2_800L
        private const val REFRESH_MS = 18_000L
        const val ACTION_GPS_ARRIVAL = "com.superdl.launcher.GPS_ARRIVAL"
        const val EXTRA_DESTINATION_NAME = "destination_name"
    }

    private val handler = Handler(Looper.getMainLooper())
    private var compass: CompassProvider? = null
    private var locationListener: LocationListener? = null
    private var lastDirectionBeepAt = 0L
    private var lastFacingState: Boolean? = null
    private var announcedStart = false
    private var directionTone: ToneGenerator? = null

    private val directionRunnable = object : Runnable {
        override fun run() {
            playDirectionFeedback()
            handler.postDelayed(this, DIRECTION_BEEP_MS)
        }
    }

    private val refreshRunnable = object : Runnable {
        override fun run() {
            refreshRadar()
            handler.postDelayed(this, REFRESH_MS)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        compass = CompassProvider(this).also { it.start() }
        val updateIntervalMs = if (GpsRadarStore.approachSavedPoi) 2_000L else 3_000L
        locationListener = GpsLocationHelper.requestUpdates(this, updateIntervalMs) { location ->
            GpsRadarStore.lastLocation = location
            updateTargetFromLocation(location)
        }
        handler.post(directionRunnable)
        handler.postDelayed(refreshRunnable, REFRESH_MS)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!GpsRadarStore.isGuiding || GpsRadarStore.targetPoi == null) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (!announcedStart) {
            announcedStart = true
            val target = GpsRadarStore.targetPoi ?: return START_NOT_STICKY
            PatrolAnnouncer.announce(
                this,
                "Célzárolva: ${target.speakRadar()} Követés elindult.",
                withBeep = true
            )
            GpsRadarStore.lastLocation?.let { location ->
                updateTargetFromLocation(location)
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        handler.removeCallbacks(directionRunnable)
        handler.removeCallbacks(refreshRunnable)
        releaseDirectionTone()
        compass?.stop()
        GpsLocationHelper.removeUpdates(this, locationListener)
        compass = null
        locationListener = null
        super.onDestroy()
    }

    private fun playDirectionFeedback() {
        val target = GpsRadarStore.targetPoi ?: return
        val location = GpsRadarStore.lastLocation ?: return
        val heading = compass?.heading() ?: GpsRadarStore.lastHeading
        GpsRadarStore.lastHeading = heading

        val bearing = GpsRadarMath.bearingDegrees(
            location.latitude,
            location.longitude,
            target.latitude,
            target.longitude
        )
        val relative = GpsRadarMath.relativeBearing(bearing, heading)
        val facing = GpsRadarMath.isFacingTarget(relative)

        if (lastFacingState != null && lastFacingState != facing) {
            val hint = GpsRadarMath.turnHint(relative)
            PatrolAnnouncer.announce(this, hint, withBeep = false)
        }
        lastFacingState = facing

        val now = System.currentTimeMillis()
        if (now - lastDirectionBeepAt < DIRECTION_BEEP_MS - 200L) return
        lastDirectionBeepAt = now
        playBeep(facing)
    }

    private fun playBeep(facing: Boolean) {
        try {
            val tone = directionTone ?: ToneGenerator(
                AudioManager.STREAM_MUSIC,
                if (facing) 95 else 70
            ).also { directionTone = it }
            val freq = if (facing) ToneGenerator.TONE_PROP_BEEP2 else ToneGenerator.TONE_PROP_BEEP
            tone.startTone(freq, if (facing) 120 else 220)
        } catch (_: Exception) {
            releaseDirectionTone()
        }
    }

    private fun releaseDirectionTone() {
        try {
            directionTone?.release()
        } catch (_: Exception) {
        }
        directionTone = null
    }

    private fun refreshRadar() {
        val location = GpsRadarStore.lastLocation ?: return
        val heading = compass?.heading() ?: GpsRadarStore.lastHeading
        GpsRadarHelper.refreshPoisWithLocation(location, heading) { pois ->
            val target = GpsRadarStore.targetPoi ?: return@refreshPoisWithLocation
            val updated = pois.firstOrNull { it.id == target.id } ?: target
            GpsRadarStore.targetPoi = updated
            val bearing = GpsRadarMath.bearingDegrees(
                location.latitude,
                location.longitude,
                updated.latitude,
                updated.longitude
            )
            val relative = GpsRadarMath.relativeBearing(bearing, heading)
            if (!GpsRadarStore.approachSavedPoi) {
                val message = updated.speakGuidance(GpsRadarMath.turnHint(relative))
                PatrolAnnouncer.announce(this, message, withBeep = true)
            }
            updateNotification(updated)
        }
    }

    private fun updateTargetFromLocation(location: Location) {
        val target = GpsRadarStore.targetPoi ?: return
        val heading = compass?.heading() ?: GpsRadarStore.lastHeading
        val updated = GpsRadarMath.enrichPoi(
            GpsPoiRaw(target.id, target.name, target.category, target.latitude, target.longitude),
            location.latitude,
            location.longitude,
            heading
        )
        GpsRadarStore.targetPoi = updated
        if (GpsRadarStore.approachSavedPoi) {
            checkApproachAnnouncements(updated)
        }
    }

    private fun checkApproachAnnouncements(target: GpsPoi) {
        val distance = target.distanceMeters
        val thresholds = listOf(50, 20, 10, 5, 2)
        val crossed = thresholds.filter { distance <= it }
        if (crossed.isEmpty()) return

        val milestone = crossed.minOrNull() ?: return
        val last = GpsRadarStore.lastApproachThreshold
        if (last != null && last <= milestone) return

        GpsRadarStore.lastApproachThreshold = milestone
        val message = when (milestone) {
            50 -> "50 méterre vagy ${target.name} helyétől."
            20 -> "20 méterre vagy."
            10 -> "10 méter, közel vagy."
            5 -> "5 méter."
            else -> "Cél elérve: ${target.name}."
        }
        PatrolAnnouncer.announce(this, message, withBeep = true)
        if (milestone <= 2) {
            GpsRadarStore.pendingArrivalPrompt = target.name
            GpsRadarManager.stopGuidance(this)
            sendBroadcast(
                Intent(ACTION_GPS_ARRIVAL).setPackage(packageName)
                    .putExtra(EXTRA_DESTINATION_NAME, target.name)
            )
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "GPS Kitekintő",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Térbeli tájékozódás és célkövetés"
            setShowBadge(false)
        }
        getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
    }

    private fun buildNotification(): Notification {
        val target = GpsRadarStore.targetPoi
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("GPS Kitekintő")
            .setContentText(target?.name ?: "Célkövetés")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }

    private fun updateNotification(target: GpsPoi) {
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("GPS Kitekintő")
            .setContentText("${target.name} • ${target.distanceMeters} m")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setOngoing(true)
            .setSilent(true)
            .build()
        startForeground(NOTIFICATION_ID, notification)
    }
}