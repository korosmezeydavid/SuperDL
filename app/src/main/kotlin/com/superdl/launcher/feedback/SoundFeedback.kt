package com.superdl.launcher.feedback

import android.content.Context
import android.media.SoundPool
import java.util.EnumMap

class SoundFeedback(context: Context) {

    private val appContext = context.applicationContext
    private var theme: SoundTheme = SoundThemeStore.get(appContext)
    private val loaded = EnumMap<SoundType, Boolean>(SoundType::class.java)
    private val pendingVolume = EnumMap<SoundType, Float>(SoundType::class.java)
    private var soundPool: SoundPool = createSoundPool()
    private val soundIds = EnumMap<SoundType, Int>(SoundType::class.java)

    init {
        loadCurrentTheme()
    }

    fun reloadTheme() {
        val next = SoundThemeStore.get(appContext)
        if (next == theme) return
        theme = next
        pendingVolume.clear()
        soundPool.release()
        soundPool = createSoundPool()
        loadCurrentTheme()
    }

    fun play(type: SoundType, volume: Float = 1f) {
        GestureSoundHelper.ensureGestureStreamAudible(appContext)
        val id = soundIds[type] ?: return
        if (loaded[type] != true) {
            pendingVolume[type] = volume
            return
        }
        playLoaded(type, id, volume)
    }

    fun release() {
        pendingVolume.clear()
        soundPool.release()
    }

    private fun playLoaded(type: SoundType, id: Int, volume: Float) {
        val scale = AlertSoundSettingsStore.volumeScale(appContext).coerceAtLeast(0.25f)
        val effectiveVolume = (volume * scale).coerceIn(0.1f, 1f)
        soundPool.play(id, effectiveVolume, effectiveVolume, 1, 0, 1f)
    }

    private fun createSoundPool(): SoundPool =
        SoundPool.Builder()
            .setMaxStreams(8)
            .setAudioAttributes(GestureSoundHelper.gestureAudioAttributes())
            .build()
            .also { pool ->
                pool.setOnLoadCompleteListener { _, sampleId, status ->
                    if (status != 0) return@setOnLoadCompleteListener
                    val type = soundIds.entries.firstOrNull { it.value == sampleId }?.key ?: return@setOnLoadCompleteListener
                    loaded[type] = true
                    val pending = pendingVolume.remove(type) ?: return@setOnLoadCompleteListener
                    playLoaded(type, sampleId, pending)
                }
            }

    private fun loadCurrentTheme() {
        SoundType.entries.forEach { type ->
            loaded[type] = false
            pendingVolume.remove(type)
            soundIds[type] = soundPool.load(appContext, theme.resIdFor(type), 1)
        }
    }
}