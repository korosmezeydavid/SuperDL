package com.superdl.launcher.gps

import android.location.Location

object GpsRadarStore {

    @Volatile
    var nearbyPois: List<GpsPoi> = emptyList()

    @Volatile
    var targetPoi: GpsPoi? = null

    @Volatile
    var lastLocation: Location? = null

    @Volatile
    var lastHeading: Float = 0f

    @Volatile
    var isGuiding: Boolean = false

    @Volatile
    var approachSavedPoi: Boolean = false

    @Volatile
    var lastApproachThreshold: Int? = null

    @Volatile
    var pendingArrivalPrompt: String? = null

    @Volatile
    var streetMonitoringEnabled: Boolean = true

    @Volatile
    var lastAnnouncedStreet: String? = null

    @Volatile
    var streetContext: StreetContext? = null

    @Volatile
    var announcedIntersectionKeys: MutableSet<String> = mutableSetOf()

    @Volatile
    var announcedIntersectionMilestones: MutableSet<String> = mutableSetOf()

    @Volatile
    var surroundingsMonitoringActive: Boolean = false

    fun clear() {
        nearbyPois = emptyList()
        targetPoi = null
        lastLocation = null
        lastHeading = 0f
        isGuiding = false
        approachSavedPoi = false
        lastApproachThreshold = null
        pendingArrivalPrompt = null
        lastAnnouncedStreet = null
        streetContext = null
        announcedIntersectionKeys = mutableSetOf()
        announcedIntersectionMilestones = mutableSetOf()
        surroundingsMonitoringActive = false
    }
}