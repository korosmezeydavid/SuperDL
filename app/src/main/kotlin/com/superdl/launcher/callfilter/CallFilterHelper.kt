package com.superdl.launcher.callfilter

import android.content.Context
import android.content.Intent
import android.os.Build
import android.app.role.RoleManager
import com.superdl.launcher.settings.PermissionGuideSection

object CallFilterHelper {

    fun isScreeningRoleHeld(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return true
        val roleManager = context.getSystemService(RoleManager::class.java) ?: return false
        return !roleManager.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING) ||
            roleManager.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)
    }

    fun createRoleRequestIntent(context: Context): Intent? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return null
        val roleManager = context.getSystemService(RoleManager::class.java) ?: return null
        if (!roleManager.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)) return null
        if (roleManager.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)) return null
        return roleManager.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING)
    }

    fun screeningGuideSections(): List<PermissionGuideSection> = listOf(
        PermissionGuideSection(
            "Hívás szűrő engedély",
            "A Super DL saját hívás-szűrőt használ, külső alkalmazás nélkül. " +
                "Engedélyezés: a rendszer kérése után válaszd a Super DL-t hívás szűrőként, " +
                "vagy menj a Beállítások, Alkalmazások, Speciális hozzáférés, " +
                "Hívás szűrés és azonosítás menübe, és kapcsold be a Super DL-t. " +
                "Ez szükséges a letiltott és rejtett számok automatikus elutasításához."
        )
    )
}