package com.superdl.launcher.locationwatch

data class LocationProfile(
    val id: String,
    val name: String,
    val createdAt: Long,
    val ocrTokens: Set<String>,
    val ocrFingerprint: String,
    val thumbnailPath: String? = null,
    val visualHashes: List<String> = emptyList(),
    val referenceImagePaths: List<String> = emptyList()
) {
    fun speakPreview(): String = name
}