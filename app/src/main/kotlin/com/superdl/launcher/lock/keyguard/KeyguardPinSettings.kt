package com.superdl.launcher.lock.keyguard

import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.view.accessibility.AccessibilityManager

object KeyguardPinSettings {

    private const val PREFS = "keyguard_pin_assist"
    private const val KEY_ENABLED = "feature_enabled"
    private const val TAG = "SDL_PINASSIST"

    /**
     * A szolgáltatás TELJES osztályneve. Korábban egy rövidített
     * "/.lock.keyguard.…" utótagot fűztünk a csomagnévhez, és azt hasonlítottuk
     * az azonosítóhoz — ez SOHA nem egyezett, két okból is:
     *  1) a rendszer a teljes osztálynévvel adja vissza az azonosítót
     *     (pkg/com.superdl.launcher.lock.keyguard.KeyguardPinAccessibilityService),
     *  2) debug változatban a csomagnév "…launcher.debug", miközben az osztály a
     *     "…launcher" csomagban van, így a rövid forma nem létező névre mutatott.
     * Emiatt a segéd bekapcsolva is "nincs engedélyezve" állapotot mutatott.
     */
    private val SERVICE_CLASS_NAME: String
        get() = KeyguardPinAccessibilityService::class.java.name

    /**
     * Az első feloldás előtti (Direct Boot) fázisban a szokásos beállítás-tároló
     * MÉG TITKOSÍTVA van, tehát nem olvasható. Ilyenkor csak az ún. eszköz-védett
     * tároló érhető el. Ezért a kapcsolót MINDKETTŐBE írjuk, olvasni pedig
     * elsőként az eszköz-védettből próbáljuk.
     */
    private fun deviceContext(context: Context): Context = try {
        context.createDeviceProtectedStorageContext() ?: context
    } catch (_: Exception) {
        context
    }

    private fun prefsOf(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun isFeatureEnabled(context: Context): Boolean {
        // 1) Eszköz-védett tároló (Direct Boot alatt is elérhető).
        try {
            val dePrefs = prefsOf(deviceContext(context))
            if (dePrefs.contains(KEY_ENABLED)) return dePrefs.getBoolean(KEY_ENABLED, true)
        } catch (_: Exception) {
        }
        // 2) Hagyományos tároló (feloldás után).
        return try {
            prefsOf(context).getBoolean(KEY_ENABLED, true)
        } catch (_: Exception) {
            true
        }
    }

    fun setFeatureEnabled(context: Context, enabled: Boolean) {
        // Mindkét tárolóba írjuk, hogy Direct Boot alatt is helyes legyen.
        try {
            prefsOf(deviceContext(context)).edit().putBoolean(KEY_ENABLED, enabled).apply()
        } catch (_: Exception) {
        }
        try {
            prefsOf(context).edit().putBoolean(KEY_ENABLED, enabled).apply()
        } catch (_: Exception) {
        }
    }

    fun isServiceEnabled(context: Context): Boolean {
        val expected = SERVICE_CLASS_NAME
        // 1) A rendszer által jelentett futó szolgáltatások.
        try {
            val manager = context.getSystemService(Context.ACCESSIBILITY_SERVICE) as AccessibilityManager
            val running = manager.getEnabledAccessibilityServiceList(
                AccessibilityServiceInfo.FEEDBACK_ALL_MASK
            )
            val found = running.any { info ->
                val serviceName = info.resolveInfo?.serviceInfo?.name
                serviceName == expected || info.id.orEmpty().endsWith("/$expected")
            }
            if (found) return true
        } catch (e: Exception) {
            android.util.Log.w(TAG, "getEnabledAccessibilityServiceList hiba: ${e.message}")
        }
        // 2) Tartalék: a rendszerbeállítás közvetlen olvasása. Ez akkor is helyes
        //    választ ad, ha a fenti lista (gyártói ROM-okon előfordul) késve
        //    frissül vagy üresen tér vissza.
        return try {
            val enabled = Settings.Secure.getString(
                context.contentResolver,
                Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            ).orEmpty()
            enabled.split(':').any { entry ->
                entry.substringAfter('/', entry).trim() == expected
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "Settings.Secure olvasas hiba: ${e.message}")
            false
        }
    }

    fun isFullyActive(context: Context): Boolean =
        isFeatureEnabled(context) && isServiceEnabled(context)

    fun openAccessibilitySettings(context: Context) {
        val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS).apply {
            if (context !is android.app.Activity) {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
        }
        context.startActivity(intent)
    }

    fun speakStatus(context: Context): String {
        val feature = if (isFeatureEnabled(context)) "bekapcsolva" else "kikapcsolva"
        val service = if (isServiceEnabled(context)) {
            "aktív a Kisegítő lehetőségekben"
        } else {
            "nincs engedélyezve a Kisegítő lehetőségekben"
        }
        return "Rendszer PIN segéd: $feature, szolgáltatás $service. " +
            "A rendszer zárolási PIN képernyőjén függőleges számbillentyűzettel oldhatod fel a telefont."
    }
}