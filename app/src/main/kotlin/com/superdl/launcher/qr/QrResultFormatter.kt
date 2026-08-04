package com.superdl.launcher.qr

import android.net.Uri

object QrResultFormatter {

    fun formatForSpeech(raw: String): String {
        val trimmed = raw.trim()
        if (trimmed.isBlank()) return "Üres kód."

        val uri = runCatching { Uri.parse(trimmed) }.getOrNull()
        val scheme = uri?.scheme?.lowercase()

        return when {
            scheme == "http" || scheme == "https" -> {
                val host = uri?.host.orEmpty().replace(".", " pont ")
                val path = uri?.path.orEmpty().replace("/", " per ")
                "Webcím. $host$path"
            }
            scheme == "mailto" -> {
                val email = uri?.schemeSpecificPart.orEmpty()
                    .substringBefore("?")
                    .replace("@", " kukac ")
                    .replace(".", " pont ")
                "E-mail cím. $email"
            }
            scheme == "tel" -> {
                val number = uri?.schemeSpecificPart.orEmpty()
                "Telefonszám. ${number.replace("+", " plusz ")}"
            }
            scheme == "sms" || scheme == "smsto" -> {
                val number = uri?.schemeSpecificPart.orEmpty().substringBefore("?")
                "Üzenet címzett. ${number.replace("+", " plusz ")}"
            }
            scheme == "geo" -> {
                val label = uri?.getQueryParameter("q")?.trim().orEmpty()
                if (label.isNotBlank()) "Hely koordináta. $label"
                else "Hely koordináta a kódban."
            }
            trimmed.contains("@") && trimmed.contains(".") ->
                "E-mail cím. ${trimmed.replace("@", " kukac ").replace(".", " pont ")}"
            trimmed.all { it.isDigit() || it == '+' } ->
                "Szám. ${trimmed.replace("+", " plusz ")}"
            else -> trimmed
        }
    }
}