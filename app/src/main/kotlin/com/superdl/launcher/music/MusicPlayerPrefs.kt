package com.superdl.launcher.music

import android.content.Context

/**
 * A zenelejátszó beállításai: tekerés egysége (mp) és lejátszási mód.
 */
object MusicPlayerPrefs {

    private const val PREFS = "superdl"
    private const val KEY_SEEK_STEP = "music_seek_step"
    private const val KEY_PLAY_MODE = "music_play_mode"
    private const val KEY_EQ_PROFILE = "music_eq_profile"

    // Utoljára hallgatott szám és pozíció — hogy egy hosszú hanganyag (film,
    // hangoskönyv) ne induljon elölről kilépés után.
    private const val KEY_LAST_TRACK_ID = "music_last_track_id"
    private const val KEY_LAST_POSITION_MS = "music_last_position_ms"

    // Beszéd-visszajelzés kapcsolók: mit mondjon a beszélő az egyes műveleteknél.
    private const val KEY_SPEAK_ON_SKIP = "music_speak_on_skip"
    private const val KEY_SPEAK_ON_STOP = "music_speak_on_stop"
    private const val KEY_SPEAK_ON_SEEK = "music_speak_on_seek"

    /**
     * FŐKAPCSOLÓ: ha ki van kapcsolva, a lejátszó SEMMIT nem mond zene közben —
     * se a következő szám címét, se a leállítást, se a tekerést. Hadd szóljon a
     * zene zavartalanul. A többi (részletes) kapcsoló ilyenkor nem számít.
     */
    private const val KEY_SPEECH_ENABLED = "music_speech_enabled"

    const val DEFAULT_SEEK_STEP = 10
    val SEEK_STEPS = listOf(5, 10, 30, 60)

    // ── Pozíció-mentés (folytatás) ──────────────────────────────────────────

    /** Elmenti, melyik szám hol tartott. positionMs < 3000 esetén törli (nem érdemes onnan folytatni). */
    fun savePosition(context: Context, trackId: Long, positionMs: Long) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
        if (positionMs < 3000L) {
            prefs.remove(KEY_LAST_TRACK_ID).remove(KEY_LAST_POSITION_MS)
        } else {
            prefs.putLong(KEY_LAST_TRACK_ID, trackId).putLong(KEY_LAST_POSITION_MS, positionMs)
        }
        prefs.apply()
    }

    /** A mentett pozíció ehhez a számhoz (ms), vagy 0 ha nincs mentés erre a számra. */
    fun getSavedPosition(context: Context, trackId: Long): Long {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val savedId = prefs.getLong(KEY_LAST_TRACK_ID, -1L)
        return if (savedId == trackId) prefs.getLong(KEY_LAST_POSITION_MS, 0L) else 0L
    }

    /** Az utoljára hallgatott szám azonosítója, vagy -1 ha nincs mentve. */
    fun getLastTrackId(context: Context): Long =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getLong(KEY_LAST_TRACK_ID, -1L)

    fun clearPosition(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().remove(KEY_LAST_TRACK_ID).remove(KEY_LAST_POSITION_MS).apply()
    }

    // ── Beszéd-visszajelzés kapcsolók (alapból mind BE) ─────────────────────

    /**
     * A lejátszó beszélhet-e egyáltalán. Ha ez KI van kapcsolva, a lejátszó
     * teljesen néma marad — a zene zavartalanul szól.
     */
    fun isSpeechEnabled(context: Context): Boolean = getBool(context, KEY_SPEECH_ENABLED)

    fun setSpeechEnabled(context: Context, on: Boolean) = setBool(context, KEY_SPEECH_ENABLED, on)

    // A részletes kapcsolók MIND hamisat adnak, ha a főkapcsoló ki van kapcsolva —
    // így a lejátszó meglévő hívási helyeit nem kell egyenként ellenőrizni.
    fun getSpeakOnSkip(context: Context): Boolean =
        isSpeechEnabled(context) && getBool(context, KEY_SPEAK_ON_SKIP)
    fun setSpeakOnSkip(context: Context, on: Boolean) = setBool(context, KEY_SPEAK_ON_SKIP, on)

    fun getSpeakOnStop(context: Context): Boolean =
        isSpeechEnabled(context) && getBool(context, KEY_SPEAK_ON_STOP)
    fun setSpeakOnStop(context: Context, on: Boolean) = setBool(context, KEY_SPEAK_ON_STOP, on)

    fun getSpeakOnSeek(context: Context): Boolean =
        isSpeechEnabled(context) && getBool(context, KEY_SPEAK_ON_SEEK)
    fun setSpeakOnSeek(context: Context, on: Boolean) = setBool(context, KEY_SPEAK_ON_SEEK, on)

    private fun getBool(context: Context, key: String): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(key, true)

    // Nyers (a főkapcsolótól független) állapotok — a beállítás-menü ezeket
    // mutatja, hogy a kapcsolgatás visszajelzése ne legyen félrevezető.
    fun getSpeakOnSkipRaw(context: Context): Boolean = getBool(context, KEY_SPEAK_ON_SKIP)
    fun getSpeakOnStopRaw(context: Context): Boolean = getBool(context, KEY_SPEAK_ON_STOP)
    fun getSpeakOnSeekRaw(context: Context): Boolean = getBool(context, KEY_SPEAK_ON_SEEK)

    private fun setBool(context: Context, key: String, on: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(key, on).apply()
    }

    fun getEqProfile(context: Context): String =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_EQ_PROFILE, MusicEqualizer.OFF_LABEL) ?: MusicEqualizer.OFF_LABEL

    fun setEqProfile(context: Context, profile: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY_EQ_PROFILE, profile).apply()
    }

    fun getSeekStep(context: Context): Int =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getInt(KEY_SEEK_STEP, DEFAULT_SEEK_STEP)

    fun setSeekStep(context: Context, seconds: Int) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putInt(KEY_SEEK_STEP, seconds).apply()
    }

    fun getPlayMode(context: Context): MusicPlayerActivity.PlayMode {
        val name = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_PLAY_MODE, MusicPlayerActivity.PlayMode.SEQUENTIAL.name)
        return try {
            MusicPlayerActivity.PlayMode.valueOf(name ?: MusicPlayerActivity.PlayMode.SEQUENTIAL.name)
        } catch (_: Exception) {
            MusicPlayerActivity.PlayMode.SEQUENTIAL
        }
    }

    fun setPlayMode(context: Context, mode: MusicPlayerActivity.PlayMode) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY_PLAY_MODE, mode.name).apply()
    }
}

/**
 * A lejátszási listát adja át a lejátszónak intent helyett (nagy lista nem fér
 * az intentbe). A MainActivity feltölti indítás előtt.
 */
object MusicPlaylistHolder {
    @Volatile
    var tracks: List<MusicTrack> = emptyList()
}
