package com.superdl.launcher.hearingaid

data class HearingAidSettings(
    val masterGain: Float = 1.5f,
    val micGain: Float = 1.2f,
    val bassGain: Float = 1.0f,
    val midGain: Float = 1.0f,
    val trebleGain: Float = 1.0f,
    val balance: BalanceMode = BalanceMode.BOTH,
    val micSource: MicSource = MicSource.AUTO
) {
    enum class BalanceMode { LEFT, BOTH, RIGHT }

    /**
     * Melyik fizikai mikrofon fogja a hangot:
     * - AUTO: a rendszer dönt (általában a headset mikrofonja, ha van)
     * - PHONE: a telefon beépített mikrofonja (tisztább, de a telefont oda kell tartani)
     * - HEADSET: a Bluetooth vagy vezetékes fülhallgató mikrofonja
     * A kimenet (amin hallasz) ettől függetlenül a headset marad, ha csatlakoztatva van.
     */
    enum class MicSource { AUTO, PHONE, HEADSET }

    fun speakSummary(): String = buildString {
        append("Hallás erősítő. ")
        append("Fő erősítés: ${percent(masterGain)}. ")
        append("Mikrofon: ${percent(micGain)}. ")
        append("Mély: ${percent(bassGain)}. ")
        append("Közép: ${percent(midGain)}. ")
        append("Magas: ${percent(trebleGain)}. ")
        append("Balansz: ${balance.speakHu()}. ")
        append("Mikrofon forrás: ${micSource.speakHu()}.")
    }

    private fun percent(value: Float): String = "${(value * 100).toInt()} százalék"

    companion object {
        const val GAIN_MIN = 0.5f
        const val GAIN_MAX = 3.0f
        const val GAIN_STEP = 0.25f
    }
}

fun HearingAidSettings.BalanceMode.speakHu(): String = when (this) {
    HearingAidSettings.BalanceMode.LEFT -> "bal fül"
    HearingAidSettings.BalanceMode.BOTH -> "mindkét fül"
    HearingAidSettings.BalanceMode.RIGHT -> "jobb fül"
}

fun HearingAidSettings.MicSource.speakHu(): String = when (this) {
    HearingAidSettings.MicSource.AUTO -> "automatikus"
    HearingAidSettings.MicSource.PHONE -> "telefon mikrofon"
    HearingAidSettings.MicSource.HEADSET -> "fülhallgató mikrofon"
}