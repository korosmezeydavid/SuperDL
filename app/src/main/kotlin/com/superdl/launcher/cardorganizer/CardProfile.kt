package com.superdl.launcher.cardorganizer

data class CardProfile(
    val id: String,
    val name: String,
    val createdAt: Long,
    val frontVisualHash: String,
    val backVisualHash: String,
    val frontThumbnailPath: String? = null,
    val backThumbnailPath: String? = null
) {
    val visualHashes: List<String> = listOf(frontVisualHash, backVisualHash).filter { it.isNotBlank() }

    fun speakPreview(): String = name
}