package com.superdl.launcher.camera

enum class CameraQualityProfile(
    val label: String,
    val photoWidth: Int,
    val photoHeight: Int,
    val videoWidth: Int,
    val videoHeight: Int,
    val videoBitrate: Int
) {
    LOW(
        label = "Alacsony",
        photoWidth = 1280,
        photoHeight = 720,
        videoWidth = 1280,
        videoHeight = 720,
        videoBitrate = 2_000_000
    ),
    MEDIUM(
        label = "Közepes",
        photoWidth = 1920,
        photoHeight = 1080,
        videoWidth = 1920,
        videoHeight = 1080,
        videoBitrate = 5_000_000
    ),
    HIGH(
        label = "Magas",
        photoWidth = 3264,
        photoHeight = 2448,
        videoWidth = 1920,
        videoHeight = 1080,
        videoBitrate = 10_000_000
    );

    fun speakSummary(): String =
        "$label minőség, fénykép ${photoWidth}×${photoHeight}, videó ${videoWidth}×${videoHeight}"
}