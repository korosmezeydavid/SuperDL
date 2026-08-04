package com.superdl.launcher.call

import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.telecom.TelecomManager
import com.superdl.launcher.settings.PermissionGuideSection

object DialerRoleHelper {

    fun isDefaultDialer(context: Context): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val telecom = context.getSystemService(TelecomManager::class.java) ?: return false
            return telecom.defaultDialerPackage == context.packageName
        }
        return false
    }

    fun isDialerRoleHeld(context: Context): Boolean = isDefaultDialer(context)

    fun createRoleRequestIntent(context: Context): Intent? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            return createLegacyDialerIntent(context)
        }
        val roleManager = context.getSystemService(RoleManager::class.java) ?: return null
        if (!roleManager.isRoleAvailable(RoleManager.ROLE_DIALER)) return createLegacyDialerIntent(context)
        if (roleManager.isRoleHeld(RoleManager.ROLE_DIALER)) return null
        return roleManager.createRequestRoleIntent(RoleManager.ROLE_DIALER)
    }

    private fun createLegacyDialerIntent(context: Context): Intent? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return null
        val telecom = context.getSystemService(TelecomManager::class.java) ?: return null
        if (telecom.defaultDialerPackage == context.packageName) return null
        return Intent(TelecomManager.ACTION_CHANGE_DEFAULT_DIALER).apply {
            putExtra(TelecomManager.EXTRA_CHANGE_DEFAULT_DIALER_PACKAGE_NAME, context.packageName)
        }
    }

    fun speakStatus(context: Context): String =
        if (isDefaultDialer(context)) {
            "A Super DL be van állítva alapértelmezett telefon alkalmazásként. " +
                "A bejövő hívások száma és a hívó neve megjelenik."
        } else {
            "A Super DL még nincs beállítva alapértelmezett telefon alkalmazásként. " +
                "Beállítás nélkül a bejövő hívó száma gyakran ismeretlen marad."
        }

    fun dialerGuideSections(): List<PermissionGuideSection> = listOf(
        PermissionGuideSection(
            "Alapértelmezett telefon – Android 10 vagy újabb",
            "A Super DL megjelenik a telefon alkalmazások listájában. " +
                "A menüben válaszd: Beállítások, Biztonság, Alapértelmezett telefon beállítása. " +
                "A rendszer kérése után válaszd a Super DL-t. " +
                "Ez szükséges ahhoz, hogy a bejövő hívásoknál lásd a hívó számát és nevét."
        ),
        PermissionGuideSection(
            "Alapértelmezett telefon – kézi beállítás",
            "Ha a rendszer nem kérdez rá automatikusan: Beállítások, Alkalmazások, " +
                "Alapértelmezett alkalmazások, Telefon alkalmazás, és válaszd a Super DL-t. " +
                "Egyes telefonokon: Beállítások, Alkalmazások, Speciális hozzáférés, " +
                "Alapértelmezett alkalmazások, Telefon."
        )
    )
}