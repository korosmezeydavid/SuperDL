package com.superdl.launcher.radio

/**
 * Egy internetes rádióállomás.
 *
 * A streamUrl lehet közvetlen hangfolyam (pl. .mp3/.aac stream), vagy egy
 * lejátszási lista (.pls / .m3u), amit a RadioPlaylistResolver old fel a
 * tényleges hangfolyam-címre.
 */
data class RadioStation(
    val id: String,
    val name: String,
    val streamUrl: String,
    val builtin: Boolean = false
)
