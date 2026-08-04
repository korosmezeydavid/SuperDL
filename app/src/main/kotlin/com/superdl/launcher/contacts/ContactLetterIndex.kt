package com.superdl.launcher.contacts

import java.text.Normalizer
import java.util.Locale

/**
 * Betű-index a névjegyzékhez: a nagy névjegylistát kezdőbetűk szerint
 * csoportosítja, hogy vak felhasználó gyorsan a kívánt betűhöz ugorhasson
 * ahelyett, hogy mind a több száz néven végig kellene lépkednie.
 */
object ContactLetterIndex {

    data class LetterGroup(
        val letter: String,          // pl. "O" vagy "#" (szám/egyéb)
        val contacts: List<ContactMatch>
    ) {
        fun speakLabel(): String {
            val count = contacts.size
            val name = if (letter == "#") "szám vagy egyéb" else letter
            return if (count == 1) "$name betű, 1 névjegy" else "$name betű, $count névjegy"
        }
    }

    /**
     * Csoportosítja a névjegyeket kezdőbetű szerint, magyar ábécé-rendben.
     * Az ékezetes betűk az alap-betűhöz sorolódnak (Á → A, Ö → O, stb.),
     * hogy ne legyen túl sok apró csoport.
     */
    fun buildGroups(contacts: List<ContactMatch>): List<LetterGroup> {
        val grouped = linkedMapOf<String, MutableList<ContactMatch>>()
        val sorted = contacts.sortedBy { it.name.lowercase(Locale("hu", "HU")) }
        for (contact in sorted) {
            val letter = firstLetter(contact.name)
            grouped.getOrPut(letter) { mutableListOf() }.add(contact)
        }
        // A betűk ábécé-rendben, a "#" (szám/egyéb) a végére
        return grouped.entries
            .sortedWith(compareBy({ it.key == "#" }, { it.key }))
            .map { LetterGroup(it.key, it.value) }
    }

    private fun firstLetter(name: String): String {
        val trimmed = name.trimStart()
        if (trimmed.isEmpty()) return "#"
        val firstChar = trimmed.first()
        if (!firstChar.isLetter()) return "#"
        // Ékezet eltávolítása: Á→A, Ö→O, Ü→U, stb.
        val base = Normalizer.normalize(firstChar.toString(), Normalizer.Form.NFD)
            .firstOrNull { it.isLetter() }
            ?: firstChar
        return base.uppercaseChar().toString()
    }
}
