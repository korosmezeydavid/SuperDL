package com.superdl.launcher.screenreader

import android.content.Context
import android.view.accessibility.AccessibilityNodeInfo

/**
 * SAJÁT ELNEVEZÉSEK — a rosszul címkézett alkalmazások megszelídítése.
 *
 * A PROBLÉMA: rengeteg alkalmazásban vannak felirat nélküli gombok. A
 * képernyőolvasó ilyenkor legfeljebb annyit tud mondani, hogy "gomb" — a
 * felhasználó pedig találgathat, melyik mit csinál. Ezen semmilyen okos
 * felismerés nem segít, mert az információ EGYSZERŰEN NINCS OTT.
 *
 * A MEGOLDÁS: ha egyszer kiderítetted, mit csinál az a gomb, ELNEVEZHETED.
 * A név megjegyződik, és onnantól a képernyőolvasó azt mondja.
 *
 * AZONOSÍTÁS: elsősorban az elem belső azonosítója alapján (ez frissítés után
 * is ugyanaz marad), ha az nincs, akkor a képernyőn elfoglalt helye alapján.
 * A nevek alkalmazásonként külön tárolódnak.
 */
object ScreenReaderLabels {

    private const val PREFS = "superdl_screenreader_labels"

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /**
     * Az elem azonosító kulcsa.
     * @return null, ha az elem nem azonosítható megbízhatóan
     */
    fun keyOf(node: AccessibilityNodeInfo, packageName: String): String? {
        // 1. A legjobb: a fejlesztő által adott belső azonosító — ez az
        //    alkalmazás frissítése után is jellemzően ugyanaz marad.
        val viewId = try {
            node.viewIdResourceName
        } catch (_: Exception) {
            null
        }
        if (!viewId.isNullOrBlank()) return "$packageName|id|$viewId"

        // 2. Tartalék: a képernyőn elfoglalt hely. Ez törékenyebb (elmozdulhat),
        //    de jobb a semminél. Rácsra kerekítünk, hogy pár képpontnyi
        //    eltolódás ne rontsa el.
        return try {
            val r = android.graphics.Rect()
            node.getBoundsInScreen(r)
            if (r.width() <= 0 || r.height() <= 0) return null
            val gx = r.centerX() / 24
            val gy = r.centerY() / 24
            "$packageName|pos|$gx:$gy"
        } catch (_: Exception) {
            null
        }
    }

    /** A mentett név, vagy null. */
    fun labelFor(context: Context, node: AccessibilityNodeInfo, packageName: String): String? {
        val key = keyOf(node, packageName) ?: return null
        return prefs(context).getString(key, null)?.takeIf { it.isNotBlank() }
    }

    fun setLabel(context: Context, node: AccessibilityNodeInfo, packageName: String, label: String): Boolean {
        val key = keyOf(node, packageName) ?: return false
        prefs(context).edit().putString(key, label.trim()).apply()
        return true
    }

    fun removeLabel(context: Context, node: AccessibilityNodeInfo, packageName: String): Boolean {
        val key = keyOf(node, packageName) ?: return false
        prefs(context).edit().remove(key).apply()
        return true
    }

    /** Hány saját elnevezés van mentve. */
    fun count(context: Context): Int = prefs(context).all.size

    fun clearAll(context: Context) {
        prefs(context).edit().clear().apply()
    }
}
