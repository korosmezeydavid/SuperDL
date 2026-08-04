package com.superdl.launcher.navigation

import com.superdl.launcher.transit.TransitPlace

data class NavPlace(
    val shortName: String,
    val fullName: String,
    val distanceMeters: Int?,
    val latitude: Double? = null,
    val longitude: Double? = null
) {
    fun speakPreview(): String = buildString {
        append(shortName)
        if (fullName.isNotBlank() && fullName != shortName) append(". $fullName")
        distanceMeters?.let { append(". ${TransitPlace.formatDistance(it)}") }
    }

    fun speakFull(): String = speakPreview()

    fun hasCoordinates(): Boolean = latitude != null && longitude != null
}