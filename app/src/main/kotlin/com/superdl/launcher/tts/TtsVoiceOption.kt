package com.superdl.launcher.tts

data class TtsVoiceOption(
    val enginePackage: String?,
    val engineLabel: String,
    val voiceName: String?,
    val displayLabel: String
) {
    val isSystemDefault: Boolean get() = enginePackage.isNullOrBlank()

    fun speakFull(): String = displayLabel
}