package com.superdl.launcher.sms

import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.Telephony
import com.superdl.launcher.settings.PermissionGuideSection

object SmsRoleHelper {

    fun isDefaultSmsApp(context: Context): Boolean {
        val defaultPackage = Telephony.Sms.getDefaultSmsPackage(context)
        return defaultPackage == context.packageName
    }

    fun isSmsRoleHeld(context: Context): Boolean = isDefaultSmsApp(context)

    fun createRoleRequestIntent(context: Context): Intent? {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val roleManager = context.getSystemService(RoleManager::class.java) ?: return null
            if (roleManager.isRoleAvailable(RoleManager.ROLE_SMS) &&
                !roleManager.isRoleHeld(RoleManager.ROLE_SMS)
            ) {
                return roleManager.createRequestRoleIntent(RoleManager.ROLE_SMS)
            }
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            if (isDefaultSmsApp(context)) return null
            return Intent(Telephony.Sms.Intents.ACTION_CHANGE_DEFAULT).apply {
                putExtra(Telephony.Sms.Intents.EXTRA_PACKAGE_NAME, context.packageName)
            }
        }
        return null
    }

    fun speakStatus(context: Context): String =
        if (isDefaultSmsApp(context)) {
            "A Super DL be van állítva alapértelmezett üzenet alkalmazásként. " +
                "Az üzenetek küldése és fogadása a Super DL-ből működik."
        } else {
            "A Super DL még nincs beállítva alapértelmezett üzenet alkalmazásként. " +
                "Beállítás nélkül az üzenetek olvasása és fogadása korlátozott lehet."
        }

    fun smsGuideSections(): List<PermissionGuideSection> = listOf(
        PermissionGuideSection(
            "Alapértelmezett üzenet app – Android 10 vagy újabb",
            "A Super DL megjelenik az SMS és üzenet alkalmazások listájában. " +
                "A menüben válaszd: Üzenetek és E-mail, Alapértelmezett üzenet app beállítása. " +
                "A rendszer kérése után válaszd a Super DL-t."
        ),
        PermissionGuideSection(
            "Alapértelmezett üzenet app – kézi beállítás",
            "Ha a rendszer nem kérdez rá automatikusan: Beállítások, Alkalmazások, " +
                "Alapértelmezett alkalmazások, SMS alkalmazás vagy Üzenet alkalmazás, " +
                "és válaszd a Super DL-t."
        )
    )
}