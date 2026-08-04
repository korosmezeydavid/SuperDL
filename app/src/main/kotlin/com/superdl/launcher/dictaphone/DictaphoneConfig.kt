package com.superdl.launcher.dictaphone

data class DictaphoneConfig(
    val format: DictaphoneFormat = DictaphoneFormat.WAV,
    val sampleRate: DictaphoneSampleRate = DictaphoneSampleRate.RATE_44K,
    val bitrate: DictaphoneBitrate = DictaphoneBitrate.B192,
    val channels: DictaphoneChannels = DictaphoneChannels.MONO,
    val noiseSuppressionEnabled: Boolean = false,

    /**
     * TELJESEN NYERS felvétel.
     *
     * A szoftveres zajszűrő kikapcsolása önmagában NEM elég: az alapértelmezett
     * mikrofon-forráson (MIC) a legtöbb telefon HARDVERESEN is végez
     * feldolgozást — zajszűrést, hangerő-kiegyenlítést —, amit az alkalmazás nem
     * lát és nem tud kikapcsolni.
     *
     * Bekapcsolva a felvétel a rendszer "feldolgozatlan" hangforrását használja
     * (UNPROCESSED), ami pontosan azt adja, amit a mikrofon hall. Ha a készülék
     * ezt nem támogatja, a következő legkevésbé feldolgozott forrásra esünk
     * vissza, és ezt a beállítás felolvasásakor jelezzük is.
     */
    val rawCapture: Boolean = false
) {
    fun speakSummary(): String {
        val noise = when {
            rawCapture -> "teljesen nyers felvétel, minden feldolgozás kikapcsolva"
            noiseSuppressionEnabled -> "zajszűrés be"
            else -> "zajszűrés ki"
        }
        val ratePart = if (format.isCompressed()) {
            "${format.speakSummary()}, ${sampleRate.speakSummary()}, ${bitrate.speakSummary()}, ${channels.speakSummary()}, $noise"
        } else {
            "${format.speakSummary()}, ${sampleRate.speakSummary()}, ${channels.speakSummary()}, $noise"
        }
        return ratePart
    }
}