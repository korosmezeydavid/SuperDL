package com.superdl.launcher.apps

import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.os.Build

data class ExternalApp(
    val packageName: String,
    val label: String
) {
    fun speakPreview(): String = label
}

object ExternalAppHelper {

    fun warningMessage(): String =
        "Itt a telefonra telepített többi alkalmazás található. " +
            "Ha a Super DL képernyőolvasó be van kapcsolva, ezeket is kezelheted vele. " +
            "Söpörj fel-le választás, jobbra megnyitás, balra vissza."

    /**
     * Mit mondjunk külső alkalmazás indításakor.
     *
     * A régi szöveg ("a Super DL nem olvassa fel a tartalmát") MÁR NEM IGAZ,
     * mióta van saját képernyőolvasó. Most az állapottól függően tájékoztatunk:
     * ha az olvasó készen áll, bekapcsoljuk; ha nincs engedélyezve, elmondjuk,
     * hol lehet. Aki a megszokott képernyőolvasóját használná, bármikor
     * kikapcsolhatja a beállításokban.
     */
    fun assistantLaunchWarning(context: Context): String {
        val enabledInSystem = isScreenReaderEnabledInSystem(context)
        val enabledInApp = com.superdl.launcher.screenreader.ScreenReaderPrefs.isEnabled(context)
        return when {
            enabledInSystem && enabledInApp ->
                "Külső alkalmazás. A Super DL képernyőolvasó bekapcsol, hogy kezelni tudd."
            enabledInSystem ->
                "Külső alkalmazás. Bekapcsolom neked a Super DL képernyőolvasót. " +
                    "A beállításokban bármikor kikapcsolhatod, ha a megszokott programodat használnád."
            else ->
                "Külső alkalmazás. A Super DL képernyőolvasót előbb engedélyezned kell " +
                    "a beállításokban, a Haladó és technikai menüben."
        }
    }

    /** Engedélyezve van-e a Super DL képernyőolvasó a rendszer kisegítő beállításaiban? */
    fun isScreenReaderEnabledInSystem(context: Context): Boolean {
        val expected = com.superdl.launcher.screenreader.ScreenReaderService::class.java.name
        return try {
            val enabled = android.provider.Settings.Secure.getString(
                context.contentResolver,
                android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            ).orEmpty()
            enabled.split(':').any { it.substringAfter('/', it).trim() == expected }
        } catch (_: Exception) {
            false
        }
    }

    fun findByName(context: Context, query: String): ExternalApp? {
        val normalized = normalizeName(query)
        if (normalized.isBlank()) return null
        val apps = getLaunchableApps(context)
        apps.firstOrNull { normalizeName(it.label) == normalized }?.let { return it }
        apps.firstOrNull { normalizeName(it.label).contains(normalized) }?.let { return it }
        apps.firstOrNull { normalized.contains(normalizeName(it.label)) }?.let { return it }
        return apps.firstOrNull { app ->
            val label = normalizeName(app.label)
            normalized.split(" ").any { word -> word.length >= 4 && label.contains(word) }
        }
    }

    private fun normalizeName(raw: String): String =
        raw.trim().lowercase()
            .replace(Regex("[^a-záéíóöőúüű0-9\\s]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()

    fun getLaunchableApps(context: Context): List<ExternalApp> {
        val pm = context.packageManager
        val ownPackage = context.packageName
        val found = linkedMapOf<String, ExternalApp>()

        fun addApp(packageName: String, label: String) {
            if (packageName.isBlank()) return
            if (packageName == ownPackage || packageName.startsWith("com.superdl.launcher")) return
            found.putIfAbsent(
                packageName,
                ExternalApp(packageName, label.ifBlank { packageName })
            )
        }

        fun collectFromIntent(intent: Intent) {
            queryLaunchableActivities(pm, intent).forEach { resolve ->
                val pkg = resolve.activityInfo?.packageName ?: return@forEach
                val label = resolve.loadLabel(pm).toString()
                addApp(pkg, label)
            }
        }

        collectFromIntent(
            Intent(Intent.ACTION_MAIN, null).apply {
                addCategory(Intent.CATEGORY_LAUNCHER)
            }
        )
        collectFromIntent(
            Intent(Intent.ACTION_MAIN, null).apply {
                addCategory(Intent.CATEGORY_LEANBACK_LAUNCHER)
            }
        )

        val packageFlags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            PackageManager.MATCH_DISABLED_COMPONENTS or PackageManager.GET_META_DATA
        } else {
            @Suppress("DEPRECATION")
            PackageManager.GET_META_DATA
        }
        pm.getInstalledPackages(packageFlags).forEach { pkgInfo ->
            val pkg = pkgInfo.packageName
            if (found.containsKey(pkg)) return@forEach
            val launch = pm.getLaunchIntentForPackage(pkg) ?: return@forEach
            if (launch.resolveActivity(pm) == null) return@forEach
            val label = pm.getApplicationLabel(pkgInfo.applicationInfo).toString()
            addApp(pkg, label)
        }

        return found.values.sortedBy { it.label.lowercase() }
    }

    private fun queryLaunchableActivities(
        pm: PackageManager,
        intent: Intent
    ): List<android.content.pm.ResolveInfo> {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            pm.queryIntentActivities(
                intent,
                PackageManager.ResolveInfoFlags.of(PackageManager.MATCH_ALL.toLong())
            )
        } else {
            @Suppress("DEPRECATION")
            pm.queryIntentActivities(intent, PackageManager.MATCH_ALL)
        }
    }

    fun launch(context: Context, app: ExternalApp): Boolean {
        val pm = context.packageManager
        val intent = pm.getLaunchIntentForPackage(app.packageName) ?: return false
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
        return true
    }

    fun isInstalled(context: Context, packageName: String): Boolean {
        return try {
            context.packageManager.getPackageInfo(packageName, 0)
            true
        } catch (_: Exception) {
            false
        }
    }

    fun isSystemApp(context: Context, packageName: String): Boolean {
        return try {
            val info = context.packageManager.getApplicationInfo(packageName, 0)
            (info.flags and ApplicationInfo.FLAG_SYSTEM) != 0
        } catch (_: Exception) {
            false
        }
    }
}