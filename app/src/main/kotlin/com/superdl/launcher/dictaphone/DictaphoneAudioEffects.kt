package com.superdl.launcher.dictaphone

import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.AutomaticGainControl
import android.media.audiofx.NoiseSuppressor

class DictaphoneAudioEffects private constructor(
    private val echoCanceler: AcousticEchoCanceler?,
    private val noiseSuppressor: NoiseSuppressor?,
    private val gainControl: AutomaticGainControl?
) {

    fun release() {
        echoCanceler?.release()
        noiseSuppressor?.release()
        gainControl?.release()
    }

    companion object {
        fun apply(audioSessionId: Int, enabled: Boolean): DictaphoneAudioEffects {
            val aec = if (AcousticEchoCanceler.isAvailable()) {
                AcousticEchoCanceler.create(audioSessionId)?.apply { setEnabled(enabled) }
            } else null

            val ns = if (NoiseSuppressor.isAvailable()) {
                NoiseSuppressor.create(audioSessionId)?.apply { setEnabled(enabled) }
            } else null

            val agc = if (AutomaticGainControl.isAvailable()) {
                AutomaticGainControl.create(audioSessionId)?.apply { setEnabled(enabled) }
            } else null

            return DictaphoneAudioEffects(aec, ns, agc)
        }

        fun speakAvailability(): String {
            val parts = mutableListOf<String>()
            parts += if (AcousticEchoCanceler.isAvailable()) "visszhangszűrő elérhető" else "visszhangszűrő nem elérhető"
            parts += if (NoiseSuppressor.isAvailable()) "zajszűrő elérhető" else "zajszűrő nem elérhető"
            return parts.joinToString(", ")
        }
    }
}