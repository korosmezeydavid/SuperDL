package com.superdl.launcher.feedback

import android.content.Context
import android.media.SoundPool
import android.os.Handler
import android.os.Looper
import java.util.EnumMap

class GameSoundFeedback(context: Context) {

    private val appContext = context.applicationContext
    private val mainHandler = Handler(Looper.getMainLooper())
    private val loaded = EnumMap<GameSoundType, Boolean>(GameSoundType::class.java)
    private val soundPool: SoundPool
    private val soundIds = EnumMap<GameSoundType, Int>(GameSoundType::class.java)

    init {
        soundPool = SoundPool.Builder()
            .setMaxStreams(8)
            .setAudioAttributes(GestureSoundHelper.gestureAudioAttributes())
            .build()
        soundPool.setOnLoadCompleteListener { _, sampleId, status ->
            if (status == 0) {
                soundIds.entries.firstOrNull { it.value == sampleId }?.key?.let {
                    loaded[it] = true
                }
            }
        }
        GameSoundType.entries.forEach { type ->
            loaded[type] = false
            soundIds[type] = soundPool.load(appContext, type.resId, 1)
        }
    }

    fun play(type: GameSoundType, volume: Float = 1f) {
        if (AlertSoundSettingsStore.isSilentMode(appContext)) return
        GestureSoundHelper.ensureGestureStreamAudible(appContext)
        val id = soundIds[type] ?: return
        if (loaded[type] != true) return
        soundPool.play(id, volume, volume, 1, 0, 1f)
    }

    fun playDelayed(type: GameSoundType, delayMs: Long, volume: Float = 1f) {
        mainHandler.postDelayed({ play(type, volume) }, delayMs)
    }

    fun playSequence(types: List<GameSoundType>, gapMs: Long = 180L, volume: Float = 1f) {
        types.forEachIndexed { index, type ->
            if (index == 0) play(type, volume) else playDelayed(type, gapMs * index, volume)
        }
    }

    fun release() {
        mainHandler.removeCallbacksAndMessages(null)
        soundPool.release()
    }
}