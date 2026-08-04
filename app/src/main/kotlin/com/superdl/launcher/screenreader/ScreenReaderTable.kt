package com.superdl.launcher.screenreader

import android.view.accessibility.AccessibilityNodeInfo

/**
 * TÁBLÁZAT- ÉS RÁCS-NAVIGÁCIÓ.
 *
 * MIÉRT KELL: ha egy alkalmazás táblázatot vagy rácsot használ (menetrend,
 * naptár-hónap, számlázási sorok, alkalmazás-rács), a soronkénti végiglépkedés
 * használhatatlan — egy tíz oszlopos táblázatban a második sor harmadik
 * cellájához negyven söprés vezetne.
 *
 * MEGOLDÁS: az Android jelöli a rács-szerkezetet (hányadik sor, hányadik
 * oszlop). Ha ez megvan, SOR és OSZLOP szerint is lehet ugrálni.
 *
 * KORLÁT: csak ott működik, ahol a fejlesztő tényleg rácsként jelölte a
 * tartalmat. Ha nincs jelölés, ezt megmondjuk, és nem tettetjük, hogy megy.
 */
object ScreenReaderTable {

    /** Egy cella helye a rácsban. */
    data class CellPosition(val row: Int, val column: Int, val rowSpan: Int, val colSpan: Int)

    /** Az elem rács-pozíciója, vagy null, ha nem rács-elem. */
    fun positionOf(node: AccessibilityNodeInfo): CellPosition? = try {
        node.collectionItemInfo?.let {
            CellPosition(it.rowIndex, it.columnIndex, it.rowSpan, it.columnSpan)
        }
    } catch (_: Exception) {
        null
    }

    /** A tartalmazó rács mérete (sorok, oszlopok), vagy null. */
    fun gridSizeOf(node: AccessibilityNodeInfo): Pair<Int, Int>? {
        var current: AccessibilityNodeInfo? = node
        var depth = 0
        while (current != null && depth < 8) {
            try {
                current.collectionInfo?.let { return it.rowCount to it.columnCount }
            } catch (_: Exception) {
            }
            current = current.parent
            depth++
        }
        return null
    }

    /** Rács-elem-e egyáltalán? */
    fun isInGrid(node: AccessibilityNodeInfo): Boolean = positionOf(node) != null

    /**
     * A következő cella keresése SOR vagy OSZLOP irányban.
     *
     * @param nodes az összegyűjtött elemek
     * @param from a jelenlegi elem
     * @param byRow igaz = sorváltás (fel-le), hamis = oszlopváltás (balra-jobbra)
     * @param forward előre vagy vissza
     * @return a talált elem indexe a listában, vagy -1
     */
    fun findNeighbour(
        nodes: List<AccessibilityNodeInfo>,
        from: AccessibilityNodeInfo,
        byRow: Boolean,
        forward: Boolean
    ): Int {
        val here = positionOf(from) ?: return -1
        var bestIndex = -1
        var bestDistance = Int.MAX_VALUE

        nodes.forEachIndexed { i, candidate ->
            val pos = positionOf(candidate) ?: return@forEachIndexed
            if (byRow) {
                // Ugyanaz az oszlop, másik sor.
                if (pos.column != here.column) return@forEachIndexed
                val delta = pos.row - here.row
                if ((forward && delta <= 0) || (!forward && delta >= 0)) return@forEachIndexed
                val dist = kotlin.math.abs(delta)
                if (dist < bestDistance) {
                    bestDistance = dist
                    bestIndex = i
                }
            } else {
                // Ugyanaz a sor, másik oszlop.
                if (pos.row != here.row) return@forEachIndexed
                val delta = pos.column - here.column
                if ((forward && delta <= 0) || (!forward && delta >= 0)) return@forEachIndexed
                val dist = kotlin.math.abs(delta)
                if (dist < bestDistance) {
                    bestDistance = dist
                    bestIndex = i
                }
            }
        }
        return bestIndex
    }

    /** A cella helyének felolvasható leírása ("2. sor, 3. oszlop"). */
    fun speakPosition(node: AccessibilityNodeInfo): String {
        val pos = positionOf(node) ?: return ""
        val size = gridSizeOf(node)
        return if (size != null && size.first > 0 && size.second > 0) {
            "${pos.row + 1}. sor a ${size.first}-ből, ${pos.column + 1}. oszlop a ${size.second}-ből"
        } else {
            "${pos.row + 1}. sor, ${pos.column + 1}. oszlop"
        }
    }
}
