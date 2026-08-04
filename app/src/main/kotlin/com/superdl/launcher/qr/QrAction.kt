package com.superdl.launcher.qr

import android.net.Uri

enum class QrActionType {
    READ_AGAIN,
    CALL,
    SMS,
    EMAIL,
    NAVIGATE,
    FINISH
}

data class QrAction(
    val type: QrActionType,
    val label: String,
    val payload: String = ""
)

object QrActionParser {

    fun parse(raw: String): List<QrAction> {
        val trimmed = raw.trim()
        val actions = mutableListOf<QrAction>()
        actions.add(QrAction(QrActionType.READ_AGAIN, "Felolvasás ismétlése", trimmed))

        val uri = runCatching { Uri.parse(trimmed) }.getOrNull()
        val scheme = uri?.scheme?.lowercase()

        when (scheme) {
            "tel" -> {
                val number = uri?.schemeSpecificPart.orEmpty().substringBefore(";")
                if (number.isNotBlank()) {
                    actions.add(QrAction(QrActionType.CALL, "Hívás: $number", number))
                    actions.add(QrAction(QrActionType.SMS, "Üzenet: $number", number))
                }
            }
            "sms", "smsto" -> {
                val number = uri?.schemeSpecificPart.orEmpty().substringBefore("?")
                if (number.isNotBlank()) {
                    actions.add(QrAction(QrActionType.SMS, "Üzenet: $number", number))
                    actions.add(QrAction(QrActionType.CALL, "Hívás: $number", number))
                }
            }
            "mailto" -> {
                val email = uri?.schemeSpecificPart.orEmpty().substringBefore("?")
                if (email.isNotBlank()) {
                    actions.add(QrAction(QrActionType.EMAIL, "E-mail: $email", email))
                }
            }
            "geo" -> {
                parseGeoPayload(uri)?.let { payload ->
                    actions.add(QrAction(QrActionType.NAVIGATE, "Gyalogos útvonal ide", payload))
                }
            }
        }

        if (trimmed.contains("@") && trimmed.contains(".") && scheme != "mailto") {
            actions.add(QrAction(QrActionType.EMAIL, "E-mail: $trimmed", trimmed))
        }
        if (trimmed.all { it.isDigit() || it == '+' } && trimmed.length >= 6) {
            actions.add(QrAction(QrActionType.CALL, "Hívás: $trimmed", trimmed))
            actions.add(QrAction(QrActionType.SMS, "Üzenet: $trimmed", trimmed))
        }

        actions.add(QrAction(QrActionType.FINISH, "Vissza a menübe"))
        return actions
    }

    private fun parseGeoPayload(uri: Uri?): String? {
        val raw = uri?.schemeSpecificPart.orEmpty()
        if (raw.isBlank()) return null
        val coords = raw.substringBefore("?").split(",")
        if (coords.size < 2) return null
        val lat = coords[0].trim().toDoubleOrNull() ?: return null
        val lon = coords[1].trim().toDoubleOrNull() ?: return null
        val label = uri?.getQueryParameter("q")?.trim().orEmpty()
        return if (label.isNotBlank()) "$lat,$lon|$label" else "$lat,$lon"
    }
}