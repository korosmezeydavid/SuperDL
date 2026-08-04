package com.superdl.launcher.assistant

import android.app.role.RoleManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.Settings
import android.service.voice.VoiceInteractionService
import com.superdl.launcher.settings.PermissionGuideSection

object AssistantRoleHelper {

    private const val VOICE_INTERACTION_SETTING = "voice_interaction_service"
    private const val ASSISTANT_SETTING = "assistant"

    private fun voiceInteractionComponent(context: Context): ComponentName =
        ComponentName(context, SuperVoiceInteractionService::class.java)

    fun isAssistantRoleHeld(context: Context): Boolean {
        if (isRoleAssistantHeld(context)) return true
        if (isVoiceInteractionServiceEnabled(context)) return true
        if (isAssistantPackageSet(context)) return true
        return false
    }

    fun isVoiceInteractionActive(context: Context): Boolean {
        return try {
            VoiceInteractionService.isActiveService(context, voiceInteractionComponent(context))
        } catch (_: Exception) {
            false
        }
    }

    fun needsActivation(context: Context): Boolean =
        isRoleAssistantHeld(context) && !isVoiceInteractionActive(context)

    fun createRoleRequestIntent(context: Context): Intent? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return null
        val roleManager = context.getSystemService(RoleManager::class.java) ?: return null
        if (!roleManager.isRoleAvailable(RoleManager.ROLE_ASSISTANT)) return null
        if (roleManager.isRoleHeld(RoleManager.ROLE_ASSISTANT)) return null
        return roleManager.createRequestRoleIntent(RoleManager.ROLE_ASSISTANT)
    }

    fun createActivationIntent(context: Context): Intent? {
        val candidates = listOf(
            Intent(Settings.ACTION_VOICE_INPUT_SETTINGS),
            Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS),
            Intent(Settings.ACTION_SETTINGS)
        )
        return candidates.firstOrNull { intent ->
            intent.resolveActivity(context.packageManager) != null
        }
    }

    fun isVoiceInteractionServiceEnabled(context: Context): Boolean {
        val current = Settings.Secure.getString(
            context.contentResolver,
            VOICE_INTERACTION_SETTING
        ).orEmpty()
        if (current.isBlank()) return false
        val component = ComponentName.unflattenFromString(current)
        if (component != null) {
            return component.packageName == context.packageName
        }
        return current.contains(context.packageName)
    }

    fun speakStatus(context: Context): String = when {
        isVoiceInteractionActive(context) ->
            "A Super DL be van állítva és aktív alapértelmezett digitális asszisztensként. " +
                "Az oldalsó gomb hosszú nyomására Elena indul."

        needsActivation(context) ->
            "A Super DL ki van választva asszisztensnek, de a rendszer még nem aktiválta. " +
                "Válaszd újra a Super DL-t az alapértelmezett asszisztens beállításban."

        isAssistantRoleHeld(context) ->
            "A Super DL be van állítva alapértelmezett digitális asszisztensként. " +
                "Az oldalsó gomb hosszú nyomására Elena indul."

        else ->
            "A Super DL még nincs beállítva alapértelmezett asszisztensként. " +
                "Válaszd ki a rendszer beállításokban, hogy az oldalsó gomb a Super DL-t indítsa."
    }

    fun assistantGuideSections(): List<PermissionGuideSection> = listOf(
        PermissionGuideSection(
            "Alapértelmezett asszisztens – Android 10 vagy újabb",
            "A Super DL megjelenik a Digitális asszisztens alkalmazások listájában. " +
                "A menüben válaszd: Asszisztens, Alapértelmezett asszisztens beállítása. " +
                "A rendszer kérése után válaszd a Super DL-t. " +
                "Ezután az oldalsó bekapcsoló gomb hosszú nyomására, " +
                "vagy a rendszer asszisztens gombjára Elena indul."
        ),
        PermissionGuideSection(
            "Alapértelmezett asszisztens – kézi beállítás",
            "Ha a rendszer nem kérdez rá automatikusan: Beállítások, Alkalmazások, " +
                "Alapértelmezett alkalmazások, Digitális asszisztens alkalmazás, " +
                "és válaszd a Super DL-t. Egyes telefonokon: Beállítások, Gombok és gesztusok, " +
                "Digitális asszisztens gomb, és ott is kiválasztható a Super DL."
        ),
        PermissionGuideSection(
            "Asszisztens aktiválás",
            "Ha a Super DL ki van választva, de a gomb nem reagál: nyisd meg újra " +
                "az Alapértelmezett asszisztens beállítását, és válaszd ismét a Super DL-t. " +
                "Ezután ellenőrizd az Asszisztens állapota menüpontot."
        ),
        PermissionGuideSection(
            "Elena engedély",
            "Az asszisztens mikrofont használ. Engedélyezd a mikrofon hozzáférést a Super DL-nek: " +
                "Beállítások, Alkalmazások, Super DL, Engedélyek, Mikrofon."
        )
    )

    private fun isRoleAssistantHeld(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return false
        val roleManager = context.getSystemService(RoleManager::class.java) ?: return false
        return roleManager.isRoleAvailable(RoleManager.ROLE_ASSISTANT) &&
            roleManager.isRoleHeld(RoleManager.ROLE_ASSISTANT)
    }

    private fun isAssistantPackageSet(context: Context): Boolean {
        val assistant = Settings.Secure.getString(context.contentResolver, ASSISTANT_SETTING).orEmpty()
        return assistant == context.packageName
    }
}