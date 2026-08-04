package com.superdl.launcher.setup

import android.content.Context
import android.content.Intent
import android.os.Build

/**
 * Gyártóspecifikus "automatikus indítás" (autostart) beállítás.
 *
 * MIÉRT KELL, HA MÁR VAN AKKU-OPTIMALIZÁLÁS: EZ KÜLÖN VAN. Több gyártó
 * (Xiaomi, Huawei, Oppo, Vivo, Samsung...) saját, az Android fölé épített
 * háttérvédelmet is futtat. Attól, hogy az Android akku-optimalizálása alól
 * felmentetted az appot, a GYÁRTÓ még megölheti a háttérben. Ilyenkor a
 * gyógyszer emlékeztető némán elmarad — a felhasználó nem érti, miért.
 *
 * ŐSZINTE KORLÁT: erre NINCS szabványos Android API. Csak nem dokumentált,
 * gyártónkénti Activity-nevek vannak, amik verzióról verzióra változhatnak, és
 * bármikor eltűnhetnek. Ezért:
 *  - MINDIG ellenőrizzük, hogy az intent egyáltalán megnyitható-e (resolveActivity),
 *  - ha nem, NEM hazudunk: útmutatót mondunk helyette,
 *  - és NEM állítjuk, hogy "sikerült" — azt a felhasználó látja, nem mi.
 *
 * NEM tudjuk lekérdezni, hogy be van-e kapcsolva: erre semmilyen API nincs.
 * Ezért ez nem a SetupRequirements része (ott a "granted" valós állapot),
 * hanem külön, tájékoztató jellegű menüpont.
 */
object AutostartHelper {

    /** Egy gyártói beállítóképernyő: csomag + osztály. */
    private data class Candidate(val pkg: String, val cls: String)

    /**
     * Ismert gyártói autostart képernyők.
     *
     * A sorrend számít: az általánosabb (biztonsági központ főoldala) hátrébb,
     * a konkrét autostart-lista előrébb.
     */
    private val CANDIDATES: Map<String, List<Candidate>> = mapOf(
        "xiaomi" to listOf(
            Candidate("com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity"),
            Candidate("com.miui.securitycenter", "com.miui.securityscan.MainActivity")
        ),
        "redmi" to listOf(
            Candidate("com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity")
        ),
        "poco" to listOf(
            Candidate("com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity")
        ),
        "huawei" to listOf(
            Candidate("com.huawei.systemmanager", "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity"),
            Candidate("com.huawei.systemmanager", "com.huawei.systemmanager.appcontrol.activity.StartupAppControlActivity"),
            Candidate("com.huawei.systemmanager", "com.huawei.systemmanager.optimize.process.ProtectActivity")
        ),
        "honor" to listOf(
            Candidate("com.huawei.systemmanager", "com.huawei.systemmanager.optimize.process.ProtectActivity")
        ),
        "oppo" to listOf(
            Candidate("com.coloros.safecenter", "com.coloros.safecenter.permission.startup.StartupAppListActivity"),
            Candidate("com.coloros.safecenter", "com.coloros.safecenter.startupapp.StartupAppListActivity"),
            Candidate("com.oppo.safe", "com.oppo.safe.permission.startup.StartupAppListActivity")
        ),
        "realme" to listOf(
            Candidate("com.coloros.safecenter", "com.coloros.safecenter.permission.startup.StartupAppListActivity")
        ),
        "vivo" to listOf(
            Candidate("com.vivo.permissionmanager", "com.vivo.permissionmanager.activity.BgStartUpManagerActivity"),
            Candidate("com.iqoo.secure", "com.iqoo.secure.ui.phoneoptimize.BgStartUpManager")
        ),
        "oneplus" to listOf(
            Candidate("com.oneplus.security", "com.oneplus.security.chainlaunch.view.ChainLaunchAppListActivity")
        ),
        "asus" to listOf(
            Candidate("com.asus.mobilemanager", "com.asus.mobilemanager.autostart.AutoStartActivity")
        ),
        "letv" to listOf(
            Candidate("com.letv.android.letvsafe", "com.letv.android.letvsafe.AutobootManageActivity")
        ),
        "meizu" to listOf(
            Candidate("com.meizu.safe", "com.meizu.safe.security.SHOW_APPSEC")
        )
    )

    /** Van-e ezen a telefonon ismert, megnyitható autostart képernyő. */
    fun isAvailable(context: Context): Boolean = findIntent(context) != null

    /**
     * A gyártó neve, ahogy a felhasználónak mondjuk.
     * Üres, ha nem ismerjük fel.
     */
    fun manufacturerLabel(): String = Build.MANUFACTURER.orEmpty().trim()

    /**
     * A megnyitható autostart intent, vagy null.
     *
     * MIÉRT ELLENŐRZÜNK resolveActivity-vel: a gyártói Activity-nevek nem
     * dokumentáltak. Ha vakon indítanánk, ActivityNotFoundException lenne belőle
     * — a felhasználó szemszögéből "a SuperDL összeomlott".
     */
    fun findIntent(context: Context): Intent? {
        val manufacturer = Build.MANUFACTURER.orEmpty().lowercase().trim()
        val brand = Build.BRAND.orEmpty().lowercase().trim()

        // A gyártó és a márka is számít: pl. Poco telefon MIUI-val.
        val keys = listOfNotNull(
            manufacturer.takeIf { it.isNotBlank() },
            brand.takeIf { it.isNotBlank() && it != manufacturer }
        )

        for (key in keys) {
            val candidates = CANDIDATES[key] ?: continue
            for (c in candidates) {
                val intent = Intent().setClassName(c.pkg, c.cls)
                if (canOpen(context, intent)) return intent
            }
        }
        return null
    }

    private fun canOpen(context: Context, intent: Intent): Boolean = try {
        context.packageManager.resolveActivity(intent, 0) != null
    } catch (_: Exception) {
        false
    }

    /**
     * Mit mondjunk a felhasználónak.
     *
     * Három eset:
     *  1. Ismerjük a gyártót és megnyitható a képernyő -> odavisszük
     *  2. Nem ismerjük, vagy nem nyitható -> ÚTMUTATÓT mondunk, nem hazudunk
     *  3. A gyártó nem is használ ilyet (pl. Ulefone, Pixel) -> megnyugtatjuk
     */
    fun speakStatus(context: Context): String {
        val brand = manufacturerLabel()
        return if (isAvailable(context)) {
            "A $brand telefonokon külön automatikus indítás beállítás is van, " +
                "az Android akku-beállításán felül. Ha ez nincs bekapcsolva a " +
                "SuperDL-hez, a gyógyszer emlékeztető elmaradhat. " +
                "Söpörj jobbra a megnyitáshoz."
        } else {
            "Ezen a telefonon nem találtam külön automatikus indítás beállítást. " +
                "Ez jó hír: valószínűleg elég a korlátlan háttérfutás engedélyezése, " +
                "amit a Beállítás varázslóban adhatsz meg. Ha a gyógyszer emlékeztető " +
                "mégis elmaradna, keresd a telefon beállításaiban az akkumulátor " +
                "vagy az alkalmazáskezelő résznél."
        }
    }
}
