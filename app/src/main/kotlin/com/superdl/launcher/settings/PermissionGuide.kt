package com.superdl.launcher.settings

import com.superdl.launcher.assistant.AssistantRoleHelper
import com.superdl.launcher.call.DialerRoleHelper
import com.superdl.launcher.callfilter.CallFilterHelper
import com.superdl.launcher.sms.SmsRoleHelper

enum class PermissionGuideType {
    NOTIFICATION_LISTENER,
    CALL_SCREENING,
    DIALER_ROLE,
    EXACT_ALARM,
    LAUNCHER_EXIT,
    WIFI_MANUAL,
    BLUETOOTH_MANUAL,
    CALENDAR_WRITE,
    ASSISTANT_ROLE,
    SMS_ROLE
}

data class PermissionGuideSection(
    val title: String,
    val body: String
) {
    fun speakPreview(): String = "$title. ${body.take(100)}…"
    fun speakFull(): String = "$title. $body"
}

object PermissionGuideTexts {

    fun sections(type: PermissionGuideType): List<PermissionGuideSection> = when (type) {
        PermissionGuideType.NOTIFICATION_LISTENER -> listOf(
            PermissionGuideSection(
                "Értesítés olvasás engedély",
                "A Super DL saját értesítés-olvasót használ, külső alkalmazás nélkül. " +
                    "Engedélyezés: Beállítások, Alkalmazások, Speciális hozzáférés, " +
                    "Értesítés hozzáférés, majd kapcsold be a Super DL-t. " +
                    "Utána vissza a Super DL-be, és válaszd az Értesítések olvasása menüpontot."
            )
        )
        PermissionGuideType.CALL_SCREENING -> CallFilterHelper.screeningGuideSections()
        PermissionGuideType.DIALER_ROLE -> DialerRoleHelper.dialerGuideSections()
        PermissionGuideType.EXACT_ALARM -> listOf(
            PermissionGuideSection(
                "Pontos ébresztő engedély",
                "A Super DL saját ébresztőt használ, nem a rendszer óra alkalmazást. " +
                    "Android 12 vagy újabb rendszeren engedélyezd a pontos ébresztőt: " +
                    "Beállítások, Alkalmazások, Super DL, Ébresztők és emlékeztetők, " +
                    "majd kapcsold be az engedélyt."
            )
        )
        PermissionGuideType.LAUNCHER_EXIT -> listOf(
            PermissionGuideSection(
                "Launcher váltás",
                "A Super DL a telefon fő kezelőfelülete. Más launcher használatához: " +
                    "Beállítások, Alkalmazások, Alapértelmezett alkalmazások, " +
                    "Kezdőképernyő alkalmazás, és válassz másik launchert. " +
                    "A Super DL bármikor visszaállítható ugyanitt."
            ),
            PermissionGuideSection(
                "Visszatérés Super DL-re",
                "Ha vissza szeretnél térni a Super DL-re, nyomd meg a Home gombot, " +
                    "és ha a rendszer kérdez, válaszd a Super DL-t mindig opcióval."
            )
        )
        PermissionGuideType.WIFI_MANUAL -> listOf(
            PermissionGuideSection(
                "WiFi kézi kapcsolás",
                "Ezen az Android verzión a WiFi közvetlen kapcsolója nem elérhető az alkalmazásból. " +
                    "Használd a gyorsbeállítások panelt: húzd lefelé a képernyő tetejétől, " +
                    "és érintsd meg a WiFi ikont."
            )
        )
        PermissionGuideType.BLUETOOTH_MANUAL -> listOf(
            PermissionGuideSection(
                "Bluetooth kézi kapcsolás",
                "A Bluetooth engedély nem adott a Super DL-nek. " +
                    "Beállítások, Kapcsolódás, Bluetooth, és kapcsold be vagy ki."
            )
        )
        PermissionGuideType.CALENDAR_WRITE -> listOf(
            PermissionGuideSection(
                "Naptár írás engedély",
                "A Super DL saját naptár-bejegyzést hoz létre, külső naptár alkalmazás nélkül. " +
                    "Engedélyezés: Beállítások, Alkalmazások, Super DL, Engedélyek, " +
                    "Naptár, majd kapcsold be az olvasást és írást is. " +
                    "Utána vissza a Super DL-be, és válaszd az Új program beállítása menüpontot."
            )
        )
        PermissionGuideType.ASSISTANT_ROLE -> AssistantRoleHelper.assistantGuideSections()
        PermissionGuideType.SMS_ROLE -> SmsRoleHelper.smsGuideSections()
    }
}