package com.superdl.launcher.system

import android.content.Context

/**
 * Utolsó ismert hotspot állapot – ha a rendszer API hamis pozitívat ad (pl. Ulefone, Android 13).
 */
object HotspotStateStore {

    private const val PREFS = "superdl"
    private const val KEY_ENABLED = "hotspot_last_known_enabled"
    private const val KEY_UPDATED_AT = "hotspot_last_known_updated_at"
    private const val TOGGLE_COOLDOWN_MS = 1200L

    private val toggleLock = Any()

    @Volatile
    private var toggleInProgress = false

    @Volatile
    private var lastToggleAt = 0L

    fun canToggle(): Boolean = synchronized(toggleLock) {
        !toggleInProgress && System.currentTimeMillis() - lastToggleAt >= TOGGLE_COOLDOWN_MS
    }

    fun tryBeginToggle(): Boolean = synchronized(toggleLock) {
        if (toggleInProgress) return false
        if (System.currentTimeMillis() - lastToggleAt < TOGGLE_COOLDOWN_MS) return false
        toggleInProgress = true
        lastToggleAt = System.currentTimeMillis()
        true
    }

    fun beginToggle() {
        synchronized(toggleLock) {
            toggleInProgress = true
            lastToggleAt = System.currentTimeMillis()
        }
    }

    fun endToggle() {
        synchronized(toggleLock) {
            toggleInProgress = false
        }
    }

    fun get(context: Context): Boolean? {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!prefs.contains(KEY_ENABLED)) return null
        return prefs.getBoolean(KEY_ENABLED, false)
    }

    fun set(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_ENABLED, enabled)
            .putLong(KEY_UPDATED_AT, System.currentTimeMillis())
            .apply()
    }
}