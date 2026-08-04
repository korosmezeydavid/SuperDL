package com.superdl.launcher.dictaphone

enum class DictaphoneSettingsOption(val label: String) {
    FORMAT("Formátum"),
    SAMPLE_RATE("Mintavételi frekvencia"),
    BITRATE("Bitráta"),
    CHANNELS("Csatornák"),
    NOISE_SUPPRESSION("Zajszűrés ki-be");

    fun speakCurrent(config: DictaphoneConfig): String = when (this) {
        FORMAT -> config.format.speakSummary()
        SAMPLE_RATE -> config.sampleRate.speakSummary()
        BITRATE -> if (config.format.isCompressed()) config.bitrate.speakSummary() else "Nem alkalmazható"
        CHANNELS -> config.channels.speakSummary()
        NOISE_SUPPRESSION -> if (config.noiseSuppressionEnabled) "Be, rendszer zajszűrés aktív" else "Ki, nyers organikus hang"
    }
}