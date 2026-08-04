package com.superdl.launcher.music

import android.content.Context
import android.media.audiofx.Equalizer
import android.util.Log

/**
 * Egyszerű equalizer a zenelejátszóhoz, az Android beépített audio-effekt
 * motorjával. Néhány kész hangzás-profil (preset) között lehet váltani,
 * ami vak felhasználónak egyszerűbb, mint sávonként állítgatni.
 */
class MusicEqualizer(private val context: Context) {

    private var equalizer: Equalizer? = null
    private var presets: List<String> = emptyList()

    /** A választható profilok: az eszköz gyári presetjei + egy "Kikapcsolva". */
    fun availableProfiles(): List<String> = listOf(OFF_LABEL) + presets

    /**
     * Rákapcsolódik a lejátszó audio session-jére. A mentett profilt állítja be.
     */
    fun attach(audioSessionId: Int) {
        release()
        try {
            val eq = Equalizer(0, audioSessionId)
            val count = eq.numberOfPresets.toInt()
            presets = (0 until count).map { eq.getPresetName(it.toShort()) }
            equalizer = eq
            applyProfile(MusicPlayerPrefs.getEqProfile(context))
        } catch (e: Exception) {
            Log.w(TAG, "Equalizer attach failed", e)
            equalizer = null
        }
    }

    /** A következő profilra vált (körben), és elmenti. Visszaadja a nevét. */
    fun cycleProfile(): String {
        val profiles = availableProfiles()
        if (profiles.size <= 1) return OFF_LABEL
        val current = MusicPlayerPrefs.getEqProfile(context)
        val idx = profiles.indexOf(current).let { if (it < 0) 0 else it }
        val next = profiles[(idx + 1) % profiles.size]
        applyProfile(next)
        MusicPlayerPrefs.setEqProfile(context, next)
        return next
    }

    private fun applyProfile(name: String) {
        val eq = equalizer ?: return
        try {
            if (name == OFF_LABEL) {
                eq.enabled = false
                return
            }
            val idx = presets.indexOf(name)
            if (idx >= 0) {
                eq.enabled = true
                eq.usePreset(idx.toShort())
            }
        } catch (e: Exception) {
            Log.w(TAG, "Equalizer applyProfile failed", e)
        }
    }

    fun release() {
        try {
            equalizer?.release()
        } catch (_: Exception) {
        }
        equalizer = null
    }

    companion object {
        private const val TAG = "SuperDL.MusicEq"
        const val OFF_LABEL = "Kikapcsolva"
    }
}
