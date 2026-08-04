package com.superdl.launcher.email

data class EmailRecipient(
    val email: String,
    val label: String
) {
    fun speakPreview(): String = "$label. ${EmailHelper.speakAddress(email)}"

    fun speakFull(): String = speakPreview()
}