package com.superdl.launcher.screenreader

import android.view.accessibility.AccessibilityNodeInfo

/**
 * A képernyő elemeinek összegyűjtése és leírása.
 *
 * Ez a képernyőolvasó "agya": bejárja a megnyitott alkalmazás elemfáját,
 * kiválogatja azt, ami a felhasználó számára értelmes, és emberi nyelvű
 * leírást készít róla.
 *
 * SZÁNDÉKOSAN EGYSZERŰ: nem célunk a TalkBack teljes tudása. A cél, hogy a
 * gyakori alkalmazások gombjai, szövegei és beviteli mezői elérhetők legyenek a
 * megszokott négy gesztussal.
 */
object ScreenReaderNavigator {

    /** Ennyi elemnél többet nem gyűjtünk (védelem a végtelen listák ellen). */
    private const val MAX_NODES = 300

    /**
     * A képernyő felolvasható elemei, a fa bejárási sorrendjében
     * (ez a legtöbb alkalmazásnál megegyezik a vizuális sorrenddel).
     */
    fun collectNodes(root: AccessibilityNodeInfo?): List<AccessibilityNodeInfo> {
        if (root == null) return emptyList()
        val out = mutableListOf<AccessibilityNodeInfo>()
        try {
            walk(root, out)
        } catch (_: Exception) {
        }
        return out
    }

    private fun walk(node: AccessibilityNodeInfo, out: MutableList<AccessibilityNodeInfo>) {
        if (out.size >= MAX_NODES) return
        if (!node.isVisibleToUser) return

        if (isMeaningful(node)) {
            out.add(node)
        }
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            walk(child, out)
        }
    }

    /**
     * Érdemes-e megállni ezen az elemen?
     *
     * SZIGORÚ SZŰRÉS: korábban minden megnyomható elem bekerült, akkor is, ha
     * semmit nem lehetett mondani róla — ezért hallott a felhasználó rengeteg
     * "névtelen elem"-et, ami elrejtette a lényeget.
     *
     * Most csak akkor állunk meg, ha VAN MIT MONDANI (saját szöveg, leírás,
     * gyerekek szövege vagy értelmes azonosító), VAGY ha az elem beírható /
     * kapcsolható — azok ugyanis akkor is fontosak, ha névtelenek.
     */
    private fun isMeaningful(node: AccessibilityNodeInfo): Boolean {
        // A beviteli mezők és kapcsolók MINDIG fontosak.
        if (node.isEditable || node.isCheckable) return true

        val ownText = !node.text.isNullOrBlank() || !node.contentDescription.isNullOrBlank()
        if (ownText) return true

        // Nincs saját szövege: csak akkor érdekes, ha MEGNYOMHATÓ és van róla
        // mondanivalónk (a gyerekeiből vagy az azonosítójából).
        if (!node.isClickable) return false

        // Ha megnyomható, de a gyerekei közt van olyan, ami MAGA IS megnyomható
        // és van szövege, akkor inkább azon állunk meg — ne duplázzunk.
        if (hasLabelledClickableChild(node)) return false

        return labelOf(node) != null
    }

    /** Van-e olyan gyereke, ami maga is megnyomható ÉS van szövege? */
    private fun hasLabelledClickableChild(node: AccessibilityNodeInfo): Boolean {
        for (i in 0 until node.childCount) {
            val child = try { node.getChild(i) } catch (_: Exception) { null } ?: continue
            if (!child.isVisibleToUser) continue
            val childText = !child.text.isNullOrBlank() || !child.contentDescription.isNullOrBlank()
            if (child.isClickable && childText) return true
        }
        return false
    }

    /**
     * Az elem CÍMKÉJE — több forrásból, ebben a sorrendben.
     *
     * MIÉRT ÍGY: sok alkalmazásban (különösen a rendszerbeállításokban) az a
     * doboz, amit meg lehet nyomni, MAGA NÉVTELEN — a felirat a benne lévő
     * szövegen ül. Ha csak a saját szövegét néznénk, a felhasználó végig
     * "névtelen elem"-eket hallana, ami használhatatlan.
     *
     * Ezért sorban megnézzük: saját szöveg, leírás, súgó, buboréksúgó, majd a
     * GYEREKEK szövegét, végül az azonosítóból és a típusból következtetünk.
     */
    fun labelOf(node: AccessibilityNodeInfo): String? {
        node.text?.toString()?.trim()?.takeIf { it.isNotBlank() }?.let { return it }
        node.contentDescription?.toString()?.trim()?.takeIf { it.isNotBlank() }?.let { return it }
        node.hintText?.toString()?.trim()?.takeIf { it.isNotBlank() }?.let { return it }
        try {
            node.tooltipText?.toString()?.trim()?.takeIf { it.isNotBlank() }?.let { return it }
        } catch (_: Exception) {
        }

        // A gyerekek szövege: ez menti meg a "névtelen" sorokat és dobozokat.
        childText(node, depth = 0)?.let { return it }

        // Végső esetben az azonosítóból következtetünk (pl. "switch_widget").
        return labelFromId(node)
    }

    /** A gyerekek látható szövegének összefűzése (legfeljebb 3 szint mélyen). */
    private fun childText(node: AccessibilityNodeInfo, depth: Int): String? {
        if (depth > 3) return null
        val parts = mutableListOf<String>()
        for (i in 0 until node.childCount) {
            val child = try { node.getChild(i) } catch (_: Exception) { null } ?: continue
            if (!child.isVisibleToUser) continue
            val own = child.text?.toString()?.trim()?.takeIf { it.isNotBlank() }
                ?: child.contentDescription?.toString()?.trim()?.takeIf { it.isNotBlank() }
            if (own != null) {
                parts.add(own)
            } else {
                childText(child, depth + 1)?.let { parts.add(it) }
            }
            // Kettőnél többet nem fűzünk össze: a hosszú felolvasás fárasztó.
            if (parts.size >= 2) break
        }
        return parts.takeIf { it.isNotEmpty() }?.joinToString(", ")
    }

    /**
     * Következtetés az elem azonosítójából. A fejlesztők általában beszédes
     * neveket adnak ("switch_widget", "back_button"), ezek jobbak a semminél.
     */
    private fun labelFromId(node: AccessibilityNodeInfo): String? {
        val id = try {
            node.viewIdResourceName?.substringAfterLast('/')
        } catch (_: Exception) {
            null
        } ?: return null
        if (id.isBlank()) return null
        val words = id.replace('_', ' ').replace(Regex("([a-z])([A-Z])"), "$1 $2").lowercase()
        return when {
            words.contains("switch") || words.contains("toggle") -> "kapcsoló"
            words.contains("back") -> "vissza"
            words.contains("search") -> "keresés"
            words.contains("menu") -> "menü"
            words.contains("settings") -> "beállítások"
            words.contains("icon") || words.contains("image") -> null   // ikon: nem mondunk semmit
            words.contains("title") -> "cím"
            words.contains("summary") -> "leírás"
            words.contains("close") -> "bezárás"
            words.contains("delete") || words.contains("remove") -> "törlés"
            words.contains("add") -> "hozzáadás"
            words.contains("edit") -> "szerkesztés"
            words.contains("play") -> "lejátszás"
            words.contains("pause") -> "szünet"
            words.contains("next") -> "következő"
            words.contains("prev") -> "előző"
            words.contains("send") -> "küldés"
            words.contains("ok") || words.contains("confirm") -> "rendben"
            words.contains("cancel") -> "mégse"
            else -> null
        }
    }

    /**
     * Emberi nyelvű leírás: mit lát a felhasználó, milyen típusú, milyen
     * állapotban van.
     *
     * FONTOS: használat előtt FRISSÍTJÜK az elemet. Az alkalmazások menet közben
     * átrajzolják a képernyőt, és az elavult elemből hibás adat jönne (vagy
     * kivétel). A frissítés megmondja azt is, ha az elem már nem létezik.
     */
    fun describe(node: AccessibilityNodeInfo): String {
        if (!refresh(node)) return "ez az elem eltűnt"
        val parts = mutableListOf<String>()

        val label = labelOf(node)
        // Ha tényleg semmit nem tudunk mondani róla, legalább a TÍPUSÁT
        // mondjuk ki — az "ismeretlen gomb" is többet ér a "névtelen elem"-nél.
        parts += label ?: (typeOf(node) ?: "ismeretlen elem")

        // Típus — csak ha nem ez lett maga a címke.
        val kind = typeOf(node)
        if (kind != null && kind != label) parts += kind

        // Állapot
        if (node.isCheckable) parts += if (node.isChecked) "bekapcsolva" else "kikapcsolva"
        if (!node.isEnabled) parts += "letiltva"
        if (node.isSelected) parts += "kiválasztva"

        return parts.joinToString(", ")
    }

    /** Az elem típusa emberi nyelven, vagy null, ha nem árulkodó. */
    private fun typeOf(node: AccessibilityNodeInfo): String? {
        val cls = node.className?.toString().orEmpty()
        return when {
            node.isEditable -> "szövegmező"
            node.isCheckable -> "kapcsoló"
            cls.contains("Button", true) -> "gomb"
            cls.contains("CheckBox", true) -> "jelölőnégyzet"
            cls.contains("RadioButton", true) -> "választógomb"
            cls.contains("SeekBar", true) -> "csúszka"
            cls.contains("ImageView", true) && node.isClickable -> "kép gomb"
            node.isClickable -> "megnyomható"
            else -> null
        }
    }

    /**
     * Az elem adatainak frissítése a rendszerből.
     * @return hamis, ha az elem már nem létezik (a képernyő közben megváltozott)
     */
    fun refresh(node: AccessibilityNodeInfo): Boolean = try {
        node.refresh()
    } catch (_: Exception) {
        false
    }

    private fun hintOf(node: AccessibilityNodeInfo): String? =
        node.hintText?.toString()?.takeIf { it.isNotBlank() }

    /**
     * Elem aktiválása. Ha maga nem megnyomható, felfelé keresünk egy szülőt,
     * ami az — sok alkalmazásban ugyanis a szöveg egy megnyomható sor belsejében
     * van, és a szövegre kattintás nem működne.
     */
    fun activate(node: AccessibilityNodeInfo): Boolean {
        // Az elavult elemre küldött kattintás vagy nem hatna, vagy rossz helyre
        // menne — ezért előbb frissítünk.
        if (!refresh(node)) return false
        var current: AccessibilityNodeInfo? = node
        var depth = 0
        while (current != null && depth < 6) {
            if (current.isClickable && current.isEnabled) {
                return try {
                    current.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                } catch (_: Exception) {
                    false
                }
            }
            current = current.parent
            depth++
        }
        return false
    }

    /**
     * HOSSZAN NYOMÁS megfelelője. Sok alkalmazásban itt rejtőznek a további
     * lehetőségek (törlés, megosztás, átnevezés).
     */
    fun longPress(node: AccessibilityNodeInfo): Boolean {
        var current: AccessibilityNodeInfo? = node
        var depth = 0
        while (current != null && depth < 6) {
            if (current.isLongClickable && current.isEnabled) {
                return try {
                    current.performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK)
                } catch (_: Exception) {
                    false
                }
            }
            current = current.parent
            depth++
        }
        return false
    }

    // ── GÖRGETÉS ────────────────────────────────────────────────────────────

    /**
     * Megkeresi a legközelebbi GÖRGETHETŐ szülőt, és görget rajta.
     *
     * Enélkül a hosszú listák alja elérhetetlen lenne: az elemfa csak azt
     * tartalmazza, ami éppen látszik a képernyőn.
     *
     * @param forward igaz = lefelé/előre, hamis = felfelé/vissza
     * @return sikerült-e görgetni (hamis, ha nincs több)
     */
    fun scroll(from: AccessibilityNodeInfo?, forward: Boolean): Boolean {
        val action = if (forward) {
            AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
        } else {
            AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
        }
        // Először az elem szülői közt keresünk görgethetőt...
        var current: AccessibilityNodeInfo? = from
        var depth = 0
        while (current != null && depth < 8) {
            if (current.isScrollable) {
                return try {
                    current.performAction(action)
                } catch (_: Exception) {
                    false
                }
            }
            current = current.parent
            depth++
        }
        return false
    }

    /** Görgethető elem keresése a teljes fában (ha az aktuális elemtől nem találunk). */
    fun findScrollable(root: AccessibilityNodeInfo?): AccessibilityNodeInfo? {
        if (root == null) return null
        if (root.isScrollable && root.isVisibleToUser) return root
        for (i in 0 until root.childCount) {
            val child = root.getChild(i) ?: continue
            val found = findScrollable(child)
            if (found != null) return found
        }
        return null
    }

    // ── SZÖVEGBEVITEL ───────────────────────────────────────────────────────

    /**
     * Szöveg beírása egy beviteli mezőbe. A meglévő tartalmat lecseréli.
     * Ezt használjuk a diktálás eredményének beírásához.
     */
    fun setText(node: AccessibilityNodeInfo, text: String): Boolean = try {
        val args = android.os.Bundle().apply {
            putCharSequence(
                AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text
            )
        }
        node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    } catch (_: Exception) {
        false
    }

    /** A mező tartalmának felolvasható leírása. */
    fun describeFieldContent(node: AccessibilityNodeInfo): String {
        val current = node.text?.toString()?.trim()
        return if (current.isNullOrBlank()) "A mező üres." else "Jelenlegi tartalom: $current"
    }

    /** A begyűjtött elemek elengedése (memória-felszabadítás). */
    fun recycleAll(nodes: List<AccessibilityNodeInfo>) {
        nodes.forEach {
            try {
                @Suppress("DEPRECATION")
                it.recycle()
            } catch (_: Exception) {
            }
        }
    }
}
