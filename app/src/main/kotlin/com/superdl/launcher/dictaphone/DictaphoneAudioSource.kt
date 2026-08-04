package com.superdl.launcher.dictaphone

import android.content.Context
import android.media.AudioManager
import android.media.MediaRecorder
import android.os.Build

/**
 * Melyik hangforrásból vegyen fel a diktafon.
 *
 * MIÉRT KELL EZ:
 * A szoftveres zajszűrő kikapcsolása önmagában NEM ad nyers hangot. Az
 * alapértelmezett mikrofon-forráson (MIC) a legtöbb készülék HARDVERESEN is
 * feldolgozza a hangot: zajszűrés, visszhangszűrés, hangerő-kiegyenlítés. Ezt az
 * alkalmazás nem látja és nem tudja kikapcsolni — csak úgy kerülhető meg, ha
 * MÁSIK hangforrást kérünk a rendszertől.
 *
 * Sorrend nyers felvételnél:
 *   1. UNPROCESSED       — kifejezetten feldolgozatlan hang (ha a készülék tudja)
 *   2. VOICE_RECOGNITION — jóval kevesebb feldolgozás, mint a MIC
 *   3. MIC               — végső tartalék
 */
object DictaphoneAudioSource {

    data class Choice(
        val source: Int,
        /** Emberi nyelvű leírás felolvasáshoz. */
        val label: String,
        /** Igaz, ha tényleg feldolgozatlan hangot kapunk. */
        val trulyRaw: Boolean
    )

    fun resolve(context: Context, rawCapture: Boolean): Choice {
        if (!rawCapture) {
            return Choice(
                MediaRecorder.AudioSource.MIC,
                "alapértelmezett mikrofon",
                trulyRaw = false
            )
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N && supportsUnprocessed(context)) {
            return Choice(
                MediaRecorder.AudioSource.UNPROCESSED,
                "feldolgozatlan mikrofon",
                trulyRaw = true
            )
        }
        // A készülék nem ad valóban nyers forrást — a hangfelismerő forrás a
        // legkevésbé feldolgozott elérhető alternatíva.
        return Choice(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            "kevéssé feldolgozott mikrofon",
            trulyRaw = false
        )
    }

    /** Támogatja-e a készülék a valóban feldolgozatlan felvételt? */
    fun supportsUnprocessed(context: Context): Boolean = try {
        val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        am.getProperty(AudioManager.PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED) == "true"
    } catch (_: Exception) {
        false
    }

    /** Felolvasható tájékoztatás a készülék képességéről. */
    fun speakCapability(context: Context): String =
        if (supportsUnprocessed(context)) {
            "Ez a készülék támogatja a teljesen nyers felvételt."
        } else {
            "Ez a készülék nem ad teljesen nyers hangot, ezért a lehető " +
                "legkevésbé feldolgozott forrást használjuk."
        }
}
