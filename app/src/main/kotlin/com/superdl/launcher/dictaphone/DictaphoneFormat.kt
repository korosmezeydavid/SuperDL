package com.superdl.launcher.dictaphone

enum class DictaphoneFormat(val label: String, val extension: String, val mimeType: String) {
    WAV("W A V nyers P C M", "wav", "audio/wav"),
    MP3("M P 3 tömörített", "mp3", "audio/mpeg"),
    FLAC("F L A C veszteségmentes", "flac", "audio/flac"),
    AAC("A A C M 4 A", "m4a", "audio/mp4");

    fun isCompressed(): Boolean = this != WAV && this != FLAC

    fun speakSummary(): String = label
}