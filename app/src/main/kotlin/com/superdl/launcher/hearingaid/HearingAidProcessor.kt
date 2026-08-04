package com.superdl.launcher.hearingaid

import kotlin.math.abs

/**
 * Valós idejű mono PCM feldolgozás: EQ (mély/közép/magas), erősítés, sztereó pan.
 */
class HearingAidProcessor {

    @Volatile
    private var settings = HearingAidSettings()

    private var bassState = 0f
    private val bassAlpha = 0.04f

    fun updateSettings(newSettings: HearingAidSettings) {
        settings = newSettings
    }

    fun processMonoToStereo(input: ShortArray, output: ShortArray) {
        val s = settings
        val leftMul = when (s.balance) {
            HearingAidSettings.BalanceMode.LEFT -> 1f
            HearingAidSettings.BalanceMode.BOTH -> 0.85f
            HearingAidSettings.BalanceMode.RIGHT -> 0.2f
        }
        val rightMul = when (s.balance) {
            HearingAidSettings.BalanceMode.LEFT -> 0.2f
            HearingAidSettings.BalanceMode.BOTH -> 0.85f
            HearingAidSettings.BalanceMode.RIGHT -> 1f
        }
        val totalGain = s.masterGain * s.micGain

        for (i in input.indices) {
            val sample = input[i] / 32768f
            bassState += bassAlpha * (sample - bassState)
            val bass = bassState
            val treble = sample - bassState
            val mid = sample - bass * 0.65f - treble * 0.35f

            var mixed = bass * s.bassGain + mid * s.midGain + treble * s.trebleGain
            mixed *= totalGain
            mixed = softClip(mixed)

            val left = (mixed * leftMul * 32767f).toInt().coerceIn(-32768, 32767).toShort()
            val right = (mixed * rightMul * 32767f).toInt().coerceIn(-32768, 32767).toShort()
            val outIndex = i * 2
            if (outIndex + 1 < output.size) {
                output[outIndex] = left
                output[outIndex + 1] = right
            }
        }
    }

    private fun softClip(value: Float): Float {
        val absVal = abs(value)
        return when {
            absVal <= 0.9f -> value
            absVal >= 1.4f -> if (value >= 0f) 1f else -1f
            else -> {
                val sign = if (value >= 0f) 1f else -1f
                sign * (0.9f + (absVal - 0.9f) * 0.25f)
            }
        }
    }
}