package com.superdl.launcher.feedback

import android.os.Handler
import android.os.Looper
import android.util.Log

/**
 * Fokozatos riasztás-indítás: először könnyű beep-beep, majd késleltetve a teljes menü.
 * Csökkenti az egyidejű terhelést (FGS + Activity + TTS), ami befagyást okozhat.
 * Hiba esetén azonnali tartalék-indítás – csendes meghibásodás tilos.
 */
object AlertLaunchHelper {

    private const val TAG = "AlertLaunchHelper"

    private val mainHandler = Handler(Looper.getMainLooper())

    fun launchStaged(
        onAfterWakeBeep: () -> Unit,
        onShowAlertUi: () -> Unit,
        onComplete: () -> Unit = {}
    ) {
        Thread(
            {
                try {
                    AlertSoundPlayer.playAlertWakeBeep()
                    sleepInterruptibly(AlertSoundPlayer.DELAY_AFTER_WAKE_BEEP_MS)
                    postToMain(onAfterWakeBeep)
                    sleepInterruptibly(AlertSoundPlayer.DELAY_BEFORE_ALERT_UI_MS)
                    postToMain(onShowAlertUi)
                } catch (e: InterruptedException) {
                    Thread.currentThread().interrupt()
                    Log.w(TAG, "Fokozatos riasztás megszakítva, tartalék-indítás", e)
                    launchImmediateFallback(onAfterWakeBeep, onShowAlertUi)
                } catch (e: Exception) {
                    Log.e(TAG, "Fokozatos riasztás meghiúsult, tartalék-indítás", e)
                    launchImmediateFallback(onAfterWakeBeep, onShowAlertUi)
                } finally {
                    postToMain(onComplete)
                }
            },
            "SuperDL-AlertLaunch"
        ).start()
    }

    private fun launchImmediateFallback(
        onAfterWakeBeep: () -> Unit,
        onShowAlertUi: () -> Unit
    ) {
        try {
            AlertSoundPlayer.playAlertWakeBeep()
        } catch (e: Exception) {
            Log.e(TAG, "Tartalék beep sem sikerült", e)
        }
        postToMain {
            try {
                onAfterWakeBeep()
            } catch (e: Exception) {
                Log.e(TAG, "Tartalék szolgáltatás-indítás sikertelen", e)
            }
            try {
                onShowAlertUi()
            } catch (e: Exception) {
                Log.e(TAG, "Tartalék UI-indítás sikertelen", e)
            }
        }
    }

    private fun postToMain(block: () -> Unit) {
        if (Looper.myLooper() == Looper.getMainLooper()) {
            block()
        } else {
            mainHandler.post(block)
        }
    }

    private fun sleepInterruptibly(delayMs: Long) {
        if (delayMs <= 0L) return
        Thread.sleep(delayMs)
    }
}