package com.superdl.launcher.dictaphone

enum class DictaphoneBitrate(val kbps: Int, val label: String) {
    B64(64, "64 kilobit"),
    B96(96, "96 kilobit"),
    B128(128, "128 kilobit"),
    B160(160, "160 kilobit"),
    B192(192, "192 kilobit"),
    B256(256, "256 kilobit"),
    B320(320, "320 kilobit");

    val bps: Int get() = kbps * 1000

    fun speakSummary(): String = label
}