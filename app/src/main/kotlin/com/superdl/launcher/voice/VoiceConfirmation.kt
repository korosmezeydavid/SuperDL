package com.superdl.launcher.voice

object VoiceConfirmation {

    enum class Result { CONFIRM, CANCEL, REPEAT, UNKNOWN }

    private val confirmExact = setOf(
        "igen", "mehet", "oké", "oke", "ok", "rendben", "jó", "jo",
        "küldés", "küldd", "küld", "kuld", "küldes",
        "hívás", "hívd", "hivd", "hívj", "hivj", "telefonálj", "telefonalj",
        "lejátszás", "lejatszas", "lejátszd", "lejatszd", "indít", "indit", "indítsd", "inditsd", "nézd", "nezd",
        "megerősít", "megerősítem", "megerosít", "megerositem", "jóváhagyom", "jóváhagy"
    )

    private val cancelExact = setOf(
        "nem", "mégse", "megse", "vissza", "töröl", "torol", "állj", "allj",
        "stop", "leállít", "leallit", "mégsem", "megsem"
    )

    private val repeatExact = setOf(
        "ismételd", "ismeteld", "újra", "ujra", "ismétlés", "ismetles", "mit", "mi az"
    )

    fun parse(spoken: String): Result {
        val normalized = spoken.trim().lowercase()
            .replace("!", "")
            .replace(".", "")
            .replace(",", "")
        if (normalized.isBlank()) return Result.UNKNOWN

        if (normalized in repeatExact) return Result.REPEAT
        if (normalized in cancelExact) return Result.CANCEL
        if (normalized in confirmExact) return Result.CONFIRM

        val words = normalized.split(Regex("\\s+"))
        if (words.any { it in repeatExact }) return Result.REPEAT
        if (words.any { it in cancelExact }) return Result.CANCEL
        if (words.any { it in confirmExact }) return Result.CONFIRM
        return Result.UNKNOWN
    }
}