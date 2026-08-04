package com.superdl.launcher.dictaphone

enum class DictaphoneSampleRate(val hz: Int, val label: String) {
    RATE_8K(8_000, "8 kilohertz"),
    RATE_16K(16_000, "16 kilohertz"),
    RATE_22K(22_050, "22 kilohertz"),
    RATE_32K(32_000, "32 kilohertz"),
    RATE_44K(44_100, "44.1 kilohertz C D minőség"),
    RATE_48K(48_000, "48 kilohertz stúdió minőség");

    fun speakSummary(): String = label
}