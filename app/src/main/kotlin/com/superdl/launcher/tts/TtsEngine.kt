package com.superdl.launcher.tts

data class TtsEngine(
    val packageName: String?,
    val label: String
) {
    val isSystemDefault: Boolean get() = packageName.isNullOrBlank()

    fun speakLabel(): String = label

    fun speakFull(): String =
        if (isSystemDefault) "$label, rendszer alapértelmezett" else label
}