package com.superdl.launcher.catalog

import android.content.Context

/**
 * Melyik modul van letöltve, és milyen verzióban.
 *
 * Ebből tudjuk megmondani a listában, hogy egy modul "nincs letöltve",
 * "letöltve", vagy "frissítés érhető el".
 */
object CatalogStore {

    private const val PREFS = "superdl_catalog"

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun markInstalled(context: Context, moduleId: String, version: Int, type: ModuleType) {
        prefs(context).edit()
            .putInt("ver_$moduleId", version)
            .putString("type_$moduleId", type.key)
            .apply()
    }

    /** A telepített verzió, vagy null ha nincs letöltve. */
    fun installedVersion(context: Context, moduleId: String): Int? {
        val v = prefs(context).getInt("ver_$moduleId", -1)
        return if (v > 0) v else null
    }

    fun remove(context: Context, moduleId: String) {
        prefs(context).edit()
            .remove("ver_$moduleId")
            .remove("type_$moduleId")
            .apply()
        try {
            CatalogClient.moduleFile(context, moduleId).delete()
        } catch (_: Exception) {
        }
    }

    /** A letöltött modulok azonosítói, típus szerint szűrve. */
    fun installedIds(context: Context, type: ModuleType? = null): List<String> {
        val all = prefs(context).all
        return all.keys
            .filter { it.startsWith("ver_") }
            .map { it.removePrefix("ver_") }
            .filter { id ->
                type == null || all["type_$id"] == type.key
            }
    }

    fun installedCount(context: Context): Int = installedIds(context).size

    /**
     * Egy letöltött modul tartalmának beolvasása.
     * @return a JSON szöveg, vagy null ha nincs meg
     */
    fun readModule(context: Context, moduleId: String): String? = try {
        val file = CatalogClient.moduleFile(context, moduleId)
        if (file.exists()) file.readText(Charsets.UTF_8) else null
    } catch (_: Exception) {
        null
    }
}
