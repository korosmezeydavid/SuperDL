package com.superdl.launcher.dictaphone

import android.content.Context
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build

/**
 * Megmondja, mire képes a KÉSZÜLÉK mikrofon-oldalon.
 *
 * Miért hasznos: a diktafon beállításai (sztereó, nyers felvétel, mintavétel)
 * csak akkor érnek valamit, ha a hardver támogatja őket. Ez a vizsgálat
 * felolvasható formában elmondja, mi érhető el ezen a telefonon — és a nyilvános
 * teszt során is sokat segít majd, mert készülékenként eltérő lehet.
 */
object DictaphoneCapabilities {

    data class Report(
        val micCount: Int,
        val micDescriptions: List<String>,
        val supportsUnprocessed: Boolean,
        val supportsStereo: Boolean,
        val maxSampleRate: Int
    )

    fun inspect(context: Context): Report {
        val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

        // 1. Hány mikrofon van, és hol
        var count = 0
        val descriptions = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            try {
                val mics = am.microphones
                count = mics.size
                mics.forEach { mic ->
                    val place = when (mic.location) {
                        android.media.MicrophoneInfo.LOCATION_MAINBODY -> "készülékházban"
                        android.media.MicrophoneInfo.LOCATION_MAINBODY_MOVABLE -> "mozgatható részen"
                        android.media.MicrophoneInfo.LOCATION_PERIPHERAL -> "külső eszközön"
                        else -> "ismeretlen helyen"
                    }
                    val dir = when (mic.directionality) {
                        android.media.MicrophoneInfo.DIRECTIONALITY_OMNI -> "körkörös"
                        android.media.MicrophoneInfo.DIRECTIONALITY_CARDIOID -> "irányított"
                        android.media.MicrophoneInfo.DIRECTIONALITY_HYPER_CARDIOID -> "erősen irányított"
                        android.media.MicrophoneInfo.DIRECTIONALITY_BI_DIRECTIONAL -> "kétirányú"
                        else -> "ismeretlen jellegű"
                    }
                    descriptions.add("$place, $dir")
                }
            } catch (_: Exception) {
            }
        }

        // 2. Nyers (feldolgozatlan) felvétel
        val unprocessed = DictaphoneAudioSource.supportsUnprocessed(context)

        // 3. Sztereó bemenet: valódi próbával, nem feltételezéssel
        val stereo = canOpen(AudioFormat.CHANNEL_IN_STEREO, 44100)

        // 4. Legnagyobb működő mintavétel
        val maxRate = listOf(48000, 44100, 32000, 22050, 16000, 8000)
            .firstOrNull { canOpen(AudioFormat.CHANNEL_IN_MONO, it) } ?: 0

        return Report(count, descriptions, unprocessed, stereo, maxRate)
    }

    /** Megpróbál megnyitni egy felvevőt — ebből derül ki, mit bír a hardver. */
    private fun canOpen(channelConfig: Int, sampleRate: Int): Boolean {
        return try {
            val min = AudioRecord.getMinBufferSize(
                sampleRate, channelConfig, AudioFormat.ENCODING_PCM_16BIT
            )
            if (min <= 0) return false
            val rec = AudioRecord(
                MediaRecorder.AudioSource.MIC, sampleRate, channelConfig,
                AudioFormat.ENCODING_PCM_16BIT, min * 2
            )
            val ok = rec.state == AudioRecord.STATE_INITIALIZED
            rec.release()
            ok
        } catch (_: Exception) {
            false
        }
    }

    /** Felolvasható összefoglaló. */
    fun speak(context: Context): String {
        val r = inspect(context)
        val parts = mutableListOf<String>()

        parts += when {
            r.micCount <= 0 -> "A mikrofonok száma nem állapítható meg."
            r.micCount == 1 -> "Egy mikrofon található a készülékben."
            else -> "${r.micCount} mikrofon található a készülékben."
        }
        if (r.micDescriptions.isNotEmpty()) {
            parts += r.micDescriptions.mapIndexed { i, d -> "${i + 1}. $d" }.joinToString(", ")
        }
        parts += if (r.supportsStereo) {
            "A sztereó felvétel támogatott."
        } else {
            "A sztereó felvétel nem támogatott, csak mono."
        }
        parts += if (r.supportsUnprocessed) {
            "A teljesen nyers, feldolgozatlan felvétel támogatott."
        } else {
            "A teljesen nyers felvétel nem támogatott; a legkevésbé feldolgozott forrást használjuk helyette."
        }
        if (r.maxSampleRate > 0) {
            parts += "A legnagyobb működő mintavétel ${r.maxSampleRate / 1000} kilohertz."
        }
        return parts.joinToString(" ")
    }
}
