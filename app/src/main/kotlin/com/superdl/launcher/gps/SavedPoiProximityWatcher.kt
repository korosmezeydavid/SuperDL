package com.superdl.launcher.gps

import android.content.Context
import android.location.Location
import android.media.MediaPlayer
import android.util.Log
import com.superdl.launcher.patrol.PatrolAnnouncer

/**
 * Séta közben figyeli a mentett helyeket: amikor a felhasználó elég közel ér
 * egy olyan helyhez, aminek van saját hangjegyzete, azt AUTOMATIKUSAN
 * lejátssza ("a bejárat kicsit beljebb van, vigyázz a lépcsőre").
 *
 * Így a hely a felhasználó SAJÁT hangján szólal meg, amikor odaér – ez teszi
 * a hangos emlékhelyet igazán hasznossá vakoknak.
 */
class SavedPoiProximityWatcher(private val context: Context) {

    companion object {
        private const val TAG = "SuperDL.PoiProximity"
        // Ekkora távolságon belül szólal meg a hely hangjegyzete.
        private const val TRIGGER_RADIUS_M = 25
        // Ennyivel távolabb kell kerülni, hogy újra "élesedjen" (hiszterézis,
        // hogy a GPS-ingadozás ne játssza le újra meg újra ugyanazt).
        private const val REARM_RADIUS_M = 45
        // Ugyanaz a hely legfeljebb ennyi időnként szólalhat meg újra.
        private const val REPEAT_COOLDOWN_MS = 60_000L
    }

    // Helyek, amelyek most a közelben vannak és már lejátszottuk őket.
    private val insideNow = mutableSetOf<String>()
    private val lastPlayedAt = mutableMapOf<String, Long>()
    private var player: MediaPlayer? = null

    /** Minden GPS-frissítésnél meghívandó. */
    fun onLocation(location: Location) {
        val pois = SavedPoiStore.getAll(context).filter { it.hasVoiceNote() }
        if (pois.isEmpty()) return
        val now = System.currentTimeMillis()

        for (poi in pois) {
            val distance = distanceTo(location, poi)
            val id = poi.id
            when {
                distance <= TRIGGER_RADIUS_M && id !in insideNow -> {
                    insideNow.add(id)
                    val last = lastPlayedAt[id] ?: 0L
                    if (now - last >= REPEAT_COOLDOWN_MS) {
                        lastPlayedAt[id] = now
                        playNote(poi)
                    }
                }
                distance >= REARM_RADIUS_M && id in insideNow -> {
                    // Eltávolodtunk: újra élesítjük, hogy legközelebb megszólaljon.
                    insideNow.remove(id)
                }
            }
        }
    }

    private fun playNote(poi: SavedPoi) {
        val path = poi.voiceNotePath ?: return
        try {
            // Előbb kimondjuk a hely nevét, majd lejátsszuk a saját hangfelvételt.
            PatrolAnnouncer.announce(
                context,
                "${poi.name}. Hangjegyzeted:",
                withBeep = false,
                critical = true,
                onDone = { playAudioFile(path) }
            )
        } catch (e: Exception) {
            Log.w(TAG, "playNote failed", e)
        }
    }

    private fun playAudioFile(path: String) {
        try {
            releasePlayer()
            player = MediaPlayer().apply {
                setDataSource(path)
                setOnCompletionListener { releasePlayer() }
                prepare()
                start()
            }
        } catch (e: Exception) {
            Log.w(TAG, "playAudioFile failed", e)
            releasePlayer()
        }
    }

    private fun distanceTo(location: Location, poi: SavedPoi): Int =
        GpsRadarMath.distanceMeters(location.latitude, location.longitude, poi.latitude, poi.longitude)

    private fun releasePlayer() {
        try {
            player?.release()
        } catch (_: Exception) {
        }
        player = null
    }

    fun reset() {
        insideNow.clear()
        lastPlayedAt.clear()
        releasePlayer()
    }
}
