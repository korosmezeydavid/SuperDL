package com.superdl.launcher.screenreader

import android.view.accessibility.AccessibilityNodeInfo

/**
 * NAVIGÁCIÓS MÓD — MIT lépkedünk végig a képernyőn.
 *
 * A mód csak SZŰRŐ a már összegyűjtött elemlistán: a fel-le söprés ugyanúgy
 * lépked, csak a szűrt halmazon. Így egy weboldalon végig lehet menni "csak a
 * gombokon" vagy "csak a címsorokon", ahelyett hogy 50-100 elemen kellene
 * átrágni magad.
 */
enum class NavigationMode(val label: String) {
    ALL("minden elem"),
    HEADINGS("címsorok"),
    LINKS("hivatkozások"),
    BUTTONS("gombok"),
    FIELDS("beviteli mezők"),
    TEXT("szöveg");

    companion object {
        fun next(current: NavigationMode): NavigationMode =
            entries[(current.ordinal + 1) % entries.size]

        fun previous(current: NavigationMode): NavigationMode =
            entries[(current.ordinal - 1 + entries.size) % entries.size]
    }
}

/**
 * OLVASÁSI RÉSZLETESSÉG — MEKKORA egységekben olvassunk.
 *
 * Nem az elemek közti lépkedést változtatja meg, hanem a fókuszban lévő elem
 * szövegén belüli mozgást. Ugyanaz a fel-le söprés navigál, csak más a
 * "nagyítás" — nem kell új mozdulatot tanulni.
 */
enum class ReadingGranularity(val label: String) {
    ELEMENT("elem"),
    SENTENCE("mondat"),
    WORD("szó"),
    CHARACTER("betű");

    companion object {
        fun finer(current: ReadingGranularity): ReadingGranularity =
            entries[(current.ordinal + 1).coerceAtMost(entries.lastIndex)]

        fun coarser(current: ReadingGranularity): ReadingGranularity =
            entries[(current.ordinal - 1).coerceAtLeast(0)]
    }
}

/**
 * A módokhoz tartozó felismerés és a szöveg darabolása.
 */
object ScreenReaderFilter {

    /** Megfelel-e az elem a kiválasztott módnak? */
    fun matches(node: AccessibilityNodeInfo, mode: NavigationMode): Boolean = when (mode) {
        NavigationMode.ALL -> true
        NavigationMode.HEADINGS -> isHeading(node)
        NavigationMode.LINKS -> isLink(node)
        NavigationMode.BUTTONS -> isButton(node)
        NavigationMode.FIELDS -> node.isEditable || node.isCheckable || isSlider(node)
        NavigationMode.TEXT -> hasRealText(node) && !isButton(node) && !node.isEditable
    }

    /**
     * CÍMSOR felismerése. Három forrásból próbáljuk, mert az alkalmazások
     * eltérően jelölik: a hivatalos jelölés, a böngésző szerepleírása
     * ("heading"), és a listaelem-jelölés.
     */
    private fun isHeading(node: AccessibilityNodeInfo): Boolean {
        try {
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P &&
                node.isHeading
            ) return true
        } catch (_: Exception) {
        }
        if (roleOf(node)?.contains("heading", true) == true) return true
        try {
            if (node.collectionItemInfo?.isHeading == true) return true
        } catch (_: Exception) {
        }
        return false
    }

    /**
     * HIVATKOZÁS felismerése. Böngészőben a Chrome kitölti a szerepleírást
     * ("link"), natív alkalmazásokban viszont ez a fogalom gyakran NEM létezik —
     * ilyenkor a mód üres lesz, és ezt meg is mondjuk a felhasználónak.
     */
    private fun isLink(node: AccessibilityNodeInfo): Boolean {
        val role = roleOf(node)
        if (role?.contains("link", true) == true) return true
        // Böngészőn belüli, kattintható szöveg: valószínűleg link.
        val cls = node.className?.toString().orEmpty()
        return node.isClickable && cls.contains("TextView", true) && isInsideWebView(node)
    }

    private fun isButton(node: AccessibilityNodeInfo): Boolean {
        val cls = node.className?.toString().orEmpty()
        if (cls.contains("Button", true)) return true
        if (roleOf(node)?.contains("button", true) == true) return true
        return node.isClickable && !node.isEditable && !hasRealText(node).not()
    }

    private fun isSlider(node: AccessibilityNodeInfo): Boolean =
        node.className?.toString()?.contains("SeekBar", true) == true

    private fun hasRealText(node: AccessibilityNodeInfo): Boolean =
        !node.text.isNullOrBlank() || !node.contentDescription.isNullOrBlank()

    /** A böngészők által kitöltött szerepleírás ("link", "heading", "button"). */
    private fun roleOf(node: AccessibilityNodeInfo): String? = try {
        node.extras?.getCharSequence("AccessibilityNodeInfo.roleDescription")?.toString()
    } catch (_: Exception) {
        null
    }

    private fun isInsideWebView(node: AccessibilityNodeInfo): Boolean {
        var current: AccessibilityNodeInfo? = node.parent
        var depth = 0
        while (current != null && depth < 8) {
            if (current.className?.toString()?.contains("WebView", true) == true) return true
            current = current.parent
            depth++
        }
        return false
    }

    // ── SZÖVEG DARABOLÁSA a részletességhez ─────────────────────────────────

    /**
     * A szöveg felbontása a kért egységekre.
     * Üres lista helyett mindig legalább az egész szöveget adjuk vissza.
     */
    fun segments(text: String, granularity: ReadingGranularity): List<String> {
        val clean = text.trim()
        if (clean.isEmpty()) return emptyList()
        return when (granularity) {
            ReadingGranularity.ELEMENT -> listOf(clean)
            ReadingGranularity.SENTENCE ->
                Regex("(?<=[.!?…])\\s+").split(clean)
                    .map { it.trim() }.filter { it.isNotEmpty() }
                    .ifEmpty { listOf(clean) }
            ReadingGranularity.WORD ->
                clean.split(Regex("\\s+")).filter { it.isNotEmpty() }
                    .ifEmpty { listOf(clean) }
            ReadingGranularity.CHARACTER ->
                clean.map { it.toString() }
        }
    }

    /**
     * Egy karakter FELOLVASHATÓ alakja. A beszélő elnyelné a magányos
     * írásjeleket, ezért azokat néven mondjuk.
     */
    fun speakCharacter(ch: String, phonetic: Boolean): String {
        val c = ch.firstOrNull() ?: return ch
        val named = when (c) {
            ' ' -> "szóköz"
            '.' -> "pont"
            ',' -> "vessző"
            '?' -> "kérdőjel"
            '!' -> "felkiáltójel"
            '-' -> "kötőjel"
            ':' -> "kettőspont"
            ';' -> "pontosvessző"
            '(' -> "nyitó zárójel"
            ')' -> "csukó zárójel"
            '"' -> "idézőjel"
            '\'' -> "aposztróf"
            '@' -> "kukac"
            '/' -> "perjel"
            else -> null
        }
        if (named != null) return named
        val prefix = if (c.isUpperCase()) "nagy " else ""
        val body = if (phonetic && c.isLetter()) phoneticOf(c.lowercaseChar()) else c.toString()
        return "$prefix$body"
    }

    /** Betűző ábécé — kódoknál, rendszámoknál életmentő. */
    private fun phoneticOf(c: Char): String = when (c) {
        'a' -> "Aladár"; 'á' -> "Ágnes"; 'b' -> "Béla"; 'c' -> "Cecil"
        'd' -> "Dénes"; 'e' -> "Elemér"; 'é' -> "Éva"; 'f' -> "Ferenc"
        'g' -> "Gábor"; 'h' -> "Helén"; 'i' -> "Ilona"; 'í' -> "Írisz"
        'j' -> "József"; 'k' -> "Károly"; 'l' -> "László"; 'm' -> "Mihály"
        'n' -> "Nándor"; 'o' -> "Olga"; 'ó' -> "Óra"; 'ö' -> "Ödön"
        'ő' -> "Őrszem"; 'p' -> "Péter"; 'q' -> "Kvelle"; 'r' -> "Róbert"
        's' -> "Sándor"; 't' -> "Tamás"; 'u' -> "Ubul"; 'ú' -> "Úrfi"
        'ü' -> "Üröm"; 'ű' -> "Űrhajó"; 'v' -> "Vilmos"; 'w' -> "dupla vé"
        'x' -> "Xénia"; 'y' -> "Ipszilon"; 'z' -> "Zoltán"
        else -> c.toString()
    }
}
