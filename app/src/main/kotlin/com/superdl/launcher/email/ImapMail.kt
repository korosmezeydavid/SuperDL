package com.superdl.launcher.email

data class ImapMail(
    val uid: Long,
    val from: String,
    val subject: String,
    val date: String,
    val body: String
) {
    /**
     * A feladó EMBERI neve, ha van. A fejlécben általában
     * `Géza <mezeig79@gmail.com>` alakban érkezik — a nevet felolvasni sokkal
     * barátságosabb, mint a "kukac ... pont ..." formában betűzött címet.
     * Ha csak cím van, azt mondjuk ki.
     */
    fun speakFrom(): String {
        val raw = from.trim()
        if (raw.isBlank()) return "Ismeretlen feladó"
        val name = raw.substringBefore("<").trim().trim('"').trim()
        return if (name.isNotBlank()) name
        else EmailHelper.speakAddress(raw.substringAfter("<").substringBefore(">").trim())
    }

    fun speakHeader(index: Int, total: Int): String =
        "Levél $index a $total közül. Feladó: ${speakFrom()}. " +
            "Tárgy: $subject. Dátum: $date."

    fun speakBodyPreview(maxChars: Int = 1200): String {
        // A levél megnyitásakor a FELADÓ és a TÁRGY is hangozzon el, utána a
        // tartalom — enélkül a felolvasás csonka volt.
        val head = "Feladó: ${speakFrom()}. Tárgy: $subject."
        val text = body.take(maxChars).trim()
        return if (text.isBlank()) "$head A levél tartalma üres."
        else "$head $text"
    }
}