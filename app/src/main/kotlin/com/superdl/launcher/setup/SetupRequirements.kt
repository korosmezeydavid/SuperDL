package com.superdl.launcher.setup

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.core.content.ContextCompat
import com.superdl.launcher.alarm.AlarmScheduler
import com.superdl.launcher.assistant.AssistantRoleHelper
import com.superdl.launcher.call.DialerRoleHelper
import com.superdl.launcher.callfilter.CallFilterHelper
import com.superdl.launcher.settings.PermissionGuideType
import com.superdl.launcher.sms.SmsRoleHelper

/**
 * A SuperDL működéséhez szükséges engedélyek és szerepkörök KÖZPONTI felmérése.
 *
 * MIÉRT KELL: az engedély-ellenőrzés eddig kb. 30 helyen, ad-hoc módon szórva
 * volt a kódban. Minden funkció külön nézte a sajátját, és ha hiányzott, a
 * felhasználó ott, akkor szembesült vele — de nem volt EGY hely, ami megmondja:
 * "ez hiányzik, és emiatt ez nem fog menni".
 *
 * Vakon ez különösen fájó: 24 service, mindegyik más rendszerképernyőn kér
 * jogot. Aki most kapja kézbe a telefont, egyedül nem jut át rajta.
 *
 * Ez az osztály NEM kér engedélyt és nem nyit meg semmit — csak MEGÁLLAPÍTJA
 * az állapotot. A kérés a hívó dolga (telefonos flow vagy a /setup portál-oldal).
 */
object SetupRequirements {

    /**
     * Mennyire súlyos, ha hiányzik.
     *
     * MIÉRT HÁROM SZINT: nem minden engedély egyenlő. Telefonálás nélkül a
     * SuperDL nem az, aminek szánták; kamera nélkül viszont csak néhány funkció
     * esik ki. A felhasználót nem szabad ugyanúgy riogatni mindkettőért.
     */
    enum class Severity {
        /** Enélkül a SuperDL alapvető funkciói nem működnek. */
        ESSENTIAL,

        /** Enélkül egy komplett funkciócsoport kiesik. */
        IMPORTANT,

        /** Kényelmi vagy kiegészítő; enélkül is használható a telefon. */
        OPTIONAL
    }

    /** Hogyan lehet megadni. */
    enum class RequestKind {
        /** Sima futásidejű engedély — requestPermissions() elég. */
        RUNTIME,

        /** Szerepkör (RoleManager) — külön intent, a rendszer kérdez rá. */
        ROLE,

        /** Rendszerbeállítás — csak odanavigálni tudunk, a kapcsolót a user nyomja. */
        SYSTEM_SCREEN
    }

    data class Requirement(
        val id: String,
        /** Rövid, felolvasható név. */
        val title: String,
        /** Mit veszít, ha nincs meg. Ez a lényeg, nem a technikai név. */
        val whatBreaks: String,
        val severity: Severity,
        val kind: RequestKind,
        /** Futásidejű engedélyeknél a manifest-nevek; egyébként üres. */
        val permissions: List<String> = emptyList(),
        /** Van-e részletes magyar útmutató hozzá. */
        val guide: PermissionGuideType? = null,
        val granted: Boolean
    ) {
        fun speakStatus(): String = "$title: ${if (granted) "megvan" else "hiányzik"}."

        fun speakDetail(): String =
            if (granted) "$title: megvan." else "$title: hiányzik. $whatBreaks"

        fun severityLabel(): String = when (severity) {
            Severity.ESSENTIAL -> "alapvető"
            Severity.IMPORTANT -> "fontos"
            Severity.OPTIONAL -> "kiegészítő"
        }

        /**
         * "3 / 7." — hol tartunk a listában.
         *
         * MIÉRT KELL: vakon a pozíció az egyetlen fogódzó, hogy tudd, hol vagy
         * és mennyi van hátra. Ugyanez a minta az összes böngésző flow-ban.
         */
        fun index1Of(list: List<Requirement>, index: Int = list.indexOf(this)): String =
            "${index + 1} / ${list.size}."
    }

    /**
     * Minden követelmény, aktuális állapottal.
     *
     * A sorrend szándékos: előbb ami nélkül a telefon nem telefon, aztán a
     * funkciócsoportok, végül a kényelem.
     */
    fun all(context: Context): List<Requirement> = listOf(
        // ---- ALAPVETŐ ----
        runtime(
            context,
            id = "phone",
            title = "Telefonálás",
            whatBreaks = "Nem tudsz hívást indítani a SuperDL-ből.",
            severity = Severity.ESSENTIAL,
            permissions = listOf(Manifest.permission.CALL_PHONE)
        ),
        runtime(
            context,
            id = "contacts",
            title = "Névjegyek",
            whatBreaks = "Nem lehet névből hívni, és bejövő hívásnál nem a nevet mondja, csak a számot.",
            severity = Severity.ESSENTIAL,
            permissions = listOf(
                Manifest.permission.READ_CONTACTS,
                Manifest.permission.WRITE_CONTACTS
            )
        ),
        runtime(
            context,
            id = "sms",
            title = "Üzenetek",
            whatBreaks = "Nem tudsz SMS-t olvasni és küldeni.",
            severity = Severity.ESSENTIAL,
            permissions = listOf(
                Manifest.permission.SEND_SMS,
                Manifest.permission.READ_SMS
            )
        ),
        runtime(
            context,
            id = "microphone",
            title = "Mikrofon",
            whatBreaks = "Nem működik a diktálás és Elena. Enélkül mindent gesztussal kell vezérelni.",
            severity = Severity.ESSENTIAL,
            permissions = listOf(Manifest.permission.RECORD_AUDIO)
        ),
        runtime(
            context,
            id = "notifications_post",
            title = "Értesítések megjelenítése",
            whatBreaks = "Az ébresztő, a gyógyszer emlékeztető és a hívásjelzés nem tud megjelenni, " +
                "ezért néma maradhat.",
            severity = Severity.ESSENTIAL,
            // Android 13 alatt nem létezik ez az engedély: ott nincs mit kérni.
            permissions = if (Build.VERSION.SDK_INT >= 33) {
                listOf(Manifest.permission.POST_NOTIFICATIONS)
            } else {
                emptyList()
            }
        ),
        Requirement(
            id = "role_sms",
            title = "Alapértelmezett üzenet alkalmazás",
            whatBreaks = "A bejövő SMS-eket nem a SuperDL kapja meg, ezért nem olvassa fel.",
            severity = Severity.ESSENTIAL,
            kind = RequestKind.ROLE,
            guide = PermissionGuideType.SMS_ROLE,
            granted = safe { SmsRoleHelper.isDefaultSmsApp(context) }
        ),
        Requirement(
            id = "exact_alarm",
            title = "Pontos ébresztő",
            whatBreaks = "Az ébresztő és a gyógyszer emlékeztető késhet vagy elmaradhat. " +
                "Ez egészségügyi kockázat.",
            severity = Severity.ESSENTIAL,
            kind = RequestKind.SYSTEM_SCREEN,
            guide = PermissionGuideType.EXACT_ALARM,
            granted = safe { AlarmScheduler.canScheduleExact(context) }
        ),
        // MIÉRT ESSENTIAL ÉS MIÉRT ITT: ez a némaság LEGGYAKORIBB oka. A gyártók
        // (Ulefone, Xiaomi, Huawei) agresszíven altatják a háttérappokat, és
        // ilyenkor a gyógyszer emlékeztető hiába van pontosan beütemezve.
        // Külön menüpontként könnyű kihagyni egy friss telefonon — a varázslóban
        // nem lehet átsiklani rajta.
        Requirement(
            id = "battery_optimization",
            title = "Korlátlan háttérfutás",
            whatBreaks = "A rendszer altathatja a SuperDL-t, ezért a gyógyszer " +
                "emlékeztető és az ébresztő késhet vagy elmaradhat. Ez a némaság " +
                "leggyakoribb oka.",
            severity = Severity.ESSENTIAL,
            kind = RequestKind.SYSTEM_SCREEN,
            granted = isIgnoringBatteryOptimizations(context)
        ),

        // ---- FONTOS ----
        Requirement(
            id = "role_dialer",
            title = "Alapértelmezett telefon alkalmazás",
            whatBreaks = "A hívásokat nem a SuperDL akadálymentes hívásképernyője kezeli.",
            severity = Severity.IMPORTANT,
            kind = RequestKind.ROLE,
            guide = PermissionGuideType.DIALER_ROLE,
            granted = safe { DialerRoleHelper.isDefaultDialer(context) }
        ),
        Requirement(
            id = "role_assistant",
            title = "Alapértelmezett asszisztens",
            whatBreaks = "Elena nem indul a rendszer asszisztens-gombjával vagy a headset gombjával.",
            severity = Severity.IMPORTANT,
            kind = RequestKind.ROLE,
            guide = PermissionGuideType.ASSISTANT_ROLE,
            granted = safe { AssistantRoleHelper.isAssistantRoleHeld(context) }
        ),
        runtime(
            context,
            id = "location",
            title = "Helymeghatározás",
            whatBreaks = "Nem működik a Hol vagyok, a GPS Kitekintő, a megállók és a környezeti figyelő.",
            severity = Severity.IMPORTANT,
            permissions = listOf(Manifest.permission.ACCESS_FINE_LOCATION)
        ),
        runtime(
            context,
            id = "camera",
            title = "Kamera",
            whatBreaks = "Nem működik a pénzfelismerő, a szövegolvasó, a QR olvasó, a színfelismerő " +
                "és a zseblámpa.",
            severity = Severity.IMPORTANT,
            permissions = listOf(Manifest.permission.CAMERA)
        ),
        runtime(
            context,
            id = "calendar",
            title = "Naptár",
            whatBreaks = "Nem olvassa fel a napi programot, és nem tud programot rögzíteni.",
            severity = Severity.IMPORTANT,
            permissions = listOf(
                Manifest.permission.READ_CALENDAR,
                Manifest.permission.WRITE_CALENDAR
            ),
            guide = PermissionGuideType.CALENDAR_WRITE
        ),
        Requirement(
            id = "notification_listener",
            title = "Értesítések olvasása",
            whatBreaks = "A SuperDL nem tudja felolvasni más alkalmazások értesítéseit.",
            severity = Severity.IMPORTANT,
            kind = RequestKind.SYSTEM_SCREEN,
            guide = PermissionGuideType.NOTIFICATION_LISTENER,
            granted = isNotificationListenerEnabled(context)
        ),
        runtime(
            context,
            id = "audio_media",
            title = "Zene és hangfájlok",
            whatBreaks = "A zenelejátszó és a saját csengőhangok nem érik el a fájlokat.",
            severity = Severity.IMPORTANT,
            permissions = if (Build.VERSION.SDK_INT >= 33) {
                listOf(Manifest.permission.READ_MEDIA_AUDIO)
            } else {
                listOf(Manifest.permission.READ_EXTERNAL_STORAGE)
            }
        ),

        // ---- KIEGÉSZÍTŐ ----
        Requirement(
            id = "role_screening",
            title = "Hívás szűrő",
            whatBreaks = "A letiltott és rejtett számok szűrése nem működik.",
            severity = Severity.OPTIONAL,
            kind = RequestKind.ROLE,
            guide = PermissionGuideType.CALL_SCREENING,
            granted = safe { CallFilterHelper.isScreeningRoleHeld(context) }
        ),
        runtime(
            context,
            id = "call_log",
            title = "Hívásnapló",
            whatBreaks = "Nem tudja felolvasni a hívásnaplót.",
            severity = Severity.OPTIONAL,
            permissions = listOf(Manifest.permission.READ_CALL_LOG)
        ),
        runtime(
            context,
            id = "bluetooth",
            title = "Bluetooth",
            whatBreaks = "Nem kapcsolható a Bluetooth a menüből, és a headset gomb nem indítja Elenát.",
            severity = Severity.OPTIONAL,
            permissions = if (Build.VERSION.SDK_INT >= 31) {
                listOf(Manifest.permission.BLUETOOTH_CONNECT)
            } else {
                emptyList()
            },
            guide = PermissionGuideType.BLUETOOTH_MANUAL
        )
    )

    fun missing(context: Context): List<Requirement> = all(context).filter { !it.granted }

    fun missingEssential(context: Context): List<Requirement> =
        missing(context).filter { it.severity == Severity.ESSENTIAL }

    /** Minden lényeges megvan-e (a kiegészítők nem számítanak bele). */
    fun isReady(context: Context): Boolean =
        missing(context).none { it.severity != Severity.OPTIONAL }

    /**
     * Egymondatos, felolvasható összefoglaló.
     *
     * MIÉRT ÍGY: a felhasználót nem a százalék érdekli, hanem hogy MI nem megy.
     * Ezért a legfontosabb hiányzó tételt a következményével együtt mondjuk ki.
     */
    fun speakSummary(context: Context): String {
        val missing = missing(context)
        if (missing.isEmpty()) {
            return "Minden engedély megvan. A SuperDL teljes egészében működik."
        }
        val essential = missing.count { it.severity == Severity.ESSENTIAL }
        val important = missing.count { it.severity == Severity.IMPORTANT }
        val optional = missing.count { it.severity == Severity.OPTIONAL }

        val parts = mutableListOf<String>()
        if (essential > 0) parts.add("$essential alapvető")
        if (important > 0) parts.add("$important fontos")
        if (optional > 0) parts.add("$optional kiegészítő")

        val head = "Hiányzik ${parts.joinToString(", ")} engedély."
        val first = missing.first()
        return "$head A legfontosabb: ${first.title}. ${first.whatBreaks}"
    }

    /**
     * A rendszerképernyő vagy szerepkör-kérés, ahol az adott tétel megadható.
     *
     * Futásidejű engedélyeknél null — azokat requestPermissions()-szel kell kérni,
     * ami Activity-t igényel, ezért nem itt van.
     */
    fun systemIntentFor(context: Context, requirement: Requirement): Intent? =
        when (requirement.id) {
            "role_sms" -> safeIntent { SmsRoleHelper.createRoleRequestIntent(context) }
            "role_dialer" -> safeIntent { DialerRoleHelper.createRoleRequestIntent(context) }
            "role_assistant" -> safeIntent { AssistantRoleHelper.createRoleRequestIntent(context) }
            "role_screening" -> safeIntent { CallFilterHelper.createRoleRequestIntent(context) }
            "exact_alarm" -> if (Build.VERSION.SDK_INT >= 31) {
                Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM).apply {
                    data = Uri.parse("package:${context.packageName}")
                }
            } else {
                null
            }
            "notification_listener" -> Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
            "battery_optimization" -> if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                    data = Uri.parse("package:${context.packageName}")
                }
            } else {
                null
            }
            else -> null
        }

    /** Az app saját beállítás-oldala — ide navigálunk, ha más út nincs. */
    fun appSettingsIntent(context: Context): Intent =
        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
            data = Uri.parse("package:${context.packageName}")
        }

    // ==================== Segédek ====================

    private fun runtime(
        context: Context,
        id: String,
        title: String,
        whatBreaks: String,
        severity: Severity,
        permissions: List<String>,
        guide: PermissionGuideType? = null
    ): Requirement = Requirement(
        id = id,
        title = title,
        whatBreaks = whatBreaks,
        severity = severity,
        kind = RequestKind.RUNTIME,
        permissions = permissions,
        guide = guide,
        // Üres lista = ezen az Android verzión nincs mit kérni, tehát rendben van.
        granted = permissions.isEmpty() || permissions.all { granted(context, it) }
    )

    private fun granted(context: Context, permission: String): Boolean =
        ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

    private fun isNotificationListenerEnabled(context: Context): Boolean = safe {
        val enabled = Settings.Secure.getString(
            context.contentResolver,
            "enabled_notification_listeners"
        ).orEmpty()
        enabled.contains(context.packageName)
    }

    /**
     * Fel van-e mentve az app az akku-optimalizálás alól.
     *
     * Android 6 alatt nincs ilyen korlátozás, ott mindig igaz.
     */
    private fun isIgnoringBatteryOptimizations(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return true
        return safe {
            val pm = context.getSystemService(PowerManager::class.java)
            pm?.isIgnoringBatteryOptimizations(context.packageName) == true
        }
    }

    /**
     * A státusz-lekérdezés SOHA ne döntse el az appot.
     *
     * Ha egy helper kivételt dob (OEM-eltérés, hiányzó rendszerszolgáltatás),
     * inkább mondjuk azt, hogy "hiányzik": az legfeljebb egy fölösleges kérés,
     * míg egy összeomlás pont a setup képernyőn végzetes lenne.
     */
    private inline fun safe(block: () -> Boolean): Boolean = try {
        block()
    } catch (_: Exception) {
        false
    }

    private inline fun safeIntent(block: () -> Intent?): Intent? = try {
        block()
    } catch (_: Exception) {
        null
    }
}
