package com.superdl.launcher.route

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.location.Location
import android.location.LocationListener
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat
import com.superdl.launcher.gps.GpsLocationHelper
import com.superdl.launcher.patrol.PatrolAnnouncer

class GpsRouteGuideService : Service() {

    companion object {
        private const val CHANNEL_ID = "GPS_ROUTE_GUIDE_CHANNEL"
        private const val NOTIFICATION_ID = 7411
        private const val UPDATE_INTERVAL_MS = 2_000L
    }

    private val mainHandler = Handler(Looper.getMainLooper())
    private val workerThread = HandlerThread("SuperDL-RouteGuide").apply { start() }
    private val workerHandler = Handler(workerThread.looper)

    private var locationListener: LocationListener? = null
    private var announcedStart = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        locationListener = GpsLocationHelper.requestUpdates(this, UPDATE_INTERVAL_MS) { location ->
            workerHandler.post { onLocationUpdate(location) }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!GpsRouteSession.isGuiding || GpsRouteSession.activeRoute == null) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (!announcedStart) {
            announcedStart = true
            val routeName = GpsRouteSession.activeRoute?.name ?: "Útvonal"
            PatrolAnnouncer.announce(
                this,
                "Útvonal követés elindult: $routeName.",
                withBeep = true,
                critical = true
            )
        }
        return START_STICKY
    }

    override fun onDestroy() {
        mainHandler.removeCallbacksAndMessages(null)
        workerHandler.removeCallbacksAndMessages(null)
        GpsLocationHelper.removeUpdates(this, locationListener)
        locationListener = null
        workerThread.quitSafely()
        super.onDestroy()
    }

    private fun onLocationUpdate(location: Location) {
        val route = GpsRouteSession.activeRoute ?: return
        GpsRouteSession.lastLocation = location

        updateGuidanceDirection(route, location.latitude, location.longitude)
        val reversed = GpsRouteSession.guidanceReversed
        val match = GpsRouteMatcher.match(route, location.latitude, location.longitude, reversed)
        val nextEvent = match.nextEvent ?: run {
            checkRouteCompletion(route, match)
            return
        }

        if (match.nextEventIndex <= GpsRouteSession.lastAnnouncedEventIndex) return
        val distance = match.distanceToNextEventM ?: return
        val thresholds = listOf(50, 20, 10)
        for (threshold in thresholds) {
            if (distance <= threshold) {
                val last = GpsRouteSession.lastApproachThreshold
                if (last == null || last > threshold) {
                    GpsRouteSession.lastApproachThreshold = threshold
                    val message = buildApproachMessage(nextEvent, threshold, reversed)
                    PatrolAnnouncer.announce(this, message, withBeep = threshold <= 20, critical = true)
                    if (threshold <= 10) {
                        GpsRouteSession.lastAnnouncedEventIndex = match.nextEventIndex
                        GpsRouteSession.lastApproachThreshold = null
                    }
                }
                break
            }
        }

        mainHandler.post {
            updateNotification(route.name, nextEvent, distance, reversed)
        }
    }

    private fun updateGuidanceDirection(route: GpsRouteRecording, latitude: Double, longitude: Double) {
        val forwardMatch = GpsRouteMatcher.match(route, latitude, longitude, reversed = false)
        val previousIndex = GpsRouteSession.lastPointIndex
        val currentIndex = forwardMatch.pointIndex
        if (previousIndex >= 0 && currentIndex >= 0) {
            val delta = currentIndex - previousIndex
            when {
                delta <= -2 -> {
                    if (!GpsRouteSession.guidanceReversed) {
                        GpsRouteSession.guidanceReversed = true
                        GpsRouteSession.lastAnnouncedEventIndex = -1
                        GpsRouteSession.lastApproachThreshold = null
                        if (!GpsRouteSession.announcedReverseDirection) {
                            GpsRouteSession.announcedReverseDirection = true
                            PatrolAnnouncer.announce(
                                this,
                                "Visszafelé haladsz az útvonalon.",
                                withBeep = true,
                                critical = true
                            )
                        }
                    }
                }
                delta >= 2 -> {
                    if (GpsRouteSession.guidanceReversed) {
                        GpsRouteSession.guidanceReversed = false
                        GpsRouteSession.lastAnnouncedEventIndex = -1
                        GpsRouteSession.lastApproachThreshold = null
                        GpsRouteSession.announcedReverseDirection = false
                        PatrolAnnouncer.announce(
                            this,
                            "Előrefelé haladsz az útvonalon.",
                            withBeep = false,
                            critical = true
                        )
                    }
                }
            }
        }
        GpsRouteSession.lastPointIndex = currentIndex
    }

    private fun checkRouteCompletion(route: GpsRouteRecording, match: RouteMatch) {
        if (route.points.isEmpty()) return
        val distanceToEnd = match.distanceToRouteM
        val reachedEnd = if (match.reversed) {
            match.pointIndex <= 1 && distanceToEnd <= 15
        } else {
            match.pointIndex >= route.points.lastIndex - 1 && distanceToEnd <= 15
        }
        if (reachedEnd) {
            val message = if (match.reversed) {
                "Az útvonal kezdete elérve."
            } else {
                "Útvonal vége elérve."
            }
            PatrolAnnouncer.announce(this, message, withBeep = true, critical = true)
            GpsRouteStore.stopGuidance(this)
            mainHandler.post { stopSelf() }
        }
    }

    private fun buildApproachMessage(event: RouteEvent, thresholdM: Int, reversed: Boolean): String {
        val action = when (event.type) {
            RouteEventType.TURN_LEFT -> if (reversed) "fordulj jobbra" else "fordulj balra"
            RouteEventType.TURN_RIGHT -> if (reversed) "fordulj balra" else "fordulj jobbra"
            RouteEventType.TURN_SLIGHT -> "enyhe kanyar"
            RouteEventType.U_TURN -> "fordulj vissza"
            RouteEventType.CROSSING -> "kereszteződés"
            RouteEventType.WAYPOINT -> event.label ?: "út pont"
            RouteEventType.START -> if (reversed) "megállás" else "indulás"
            RouteEventType.STOP -> if (reversed) "indulás" else "megállás"
        }
        val prefix = if (reversed) "Visszafelé: " else ""
        return when (thresholdM) {
            50 -> "${prefix}50 méter múlva $action."
            20 -> "${prefix}20 méter múlva $action."
            else -> "${prefix}Most $action."
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "GPS Útvonal követés",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Mentett útvonal hangos követése"
            setShowBadge(false)
        }
        getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
    }

    private fun buildNotification(): Notification {
        val routeName = GpsRouteSession.activeRoute?.name ?: "Útvonal követés"
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("GPS Útvonal követés")
            .setContentText(routeName)
            .setSmallIcon(android.R.drawable.ic_menu_directions)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }

    private fun updateNotification(
        routeName: String,
        nextEvent: RouteEvent,
        distanceM: Int,
        reversed: Boolean
    ) {
        val label = when (nextEvent.type) {
            RouteEventType.TURN_LEFT -> if (reversed) "jobbra" else "balra"
            RouteEventType.TURN_RIGHT -> if (reversed) "balra" else "jobbra"
            RouteEventType.TURN_SLIGHT -> "enyhe kanyar"
            RouteEventType.U_TURN -> "visszafordulás"
            RouteEventType.CROSSING -> "kereszteződés"
            RouteEventType.WAYPOINT -> nextEvent.label ?: "út pont"
            RouteEventType.START -> if (reversed) "megállás" else "indulás"
            RouteEventType.STOP -> if (reversed) "indulás" else "megállás"
        }
        val direction = if (reversed) "vissza • " else ""
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("GPS Útvonal követés")
            .setContentText("$routeName • $direction$distanceM m • $label")
            .setSmallIcon(android.R.drawable.ic_menu_directions)
            .setOngoing(true)
            .setSilent(true)
            .build()
        startForeground(NOTIFICATION_ID, notification)
    }
}