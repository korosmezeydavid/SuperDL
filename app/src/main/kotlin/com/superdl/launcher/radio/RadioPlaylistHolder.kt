package com.superdl.launcher.radio

/**
 * Átadja a RadioPlayerActivity-nek a lejátszandó állomás-listát és a kezdő
 * indexet (a MusicPlaylistHolder / PodcastEpisodeHolder mintájára — így nem kell
 * nagy adatot Intent-extraként cipelni).
 */
object RadioPlaylistHolder {
    var stations: List<RadioStation> = emptyList()
    var startIndex: Int = 0
}
