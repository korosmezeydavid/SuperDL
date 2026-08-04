package com.superdl.launcher.setup

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import com.superdl.launcher.medication.MedicationScheduler
import com.superdl.launcher.medication.MedicationStore
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Diagnosztika: mi működik MOST, és mi nem fog.
 *
 * MIÉRT KELL, HA MÁR VAN SetupRequirements: az engedély megléte NEM jelenti,
 * hogy a funkció működni is fog. A gyógyszer-emlékeztetőnél lehet engedély,
 * lehet felvéve az emlékeztető — és mégsem szólal meg, mert:
 *   - a gyártó (Ulefone, Xiaomi, Huawei...) megölte a háttérfolyamatot,
 *   - az akku-optimalizálás altatja az appot,
 *   - az emlékeztető ki van kapcsolva,
 *   - vagy nincs is beütemezve következő riasztás.
 *
 * A SetupRequirements azt mondja meg, MI HIÁNYZIK. Ez azt, hogy MI NEM MEGY.
 * A kettő nem ugyanaz — és a néma hiba a projekt legveszélyesebb hibatípusa.
 */
object DiagnosticsReport {

    enum class Level { OK, WARN, FAIL }

    data class Check(
        val title: String,
        val level: Level,
        /** Mit jelent ez a felhasználónak — nem technikai szöveg. */
        val detail: String,
        /** Mit tehet ellene, ha baj van. */
        val action: String? = null
    ) {
        fun levelLabel(): String = when (level) {
            Level.OK -> "rendben"
            Level.WARN -> "figyelmeztetés"
            Level.FAIL -> "hiba"
        }

        fun speak(): String = buildString {
            append("$title: ${levelLabel()}. $detail")
            if (level != Level.OK && action != null) append(" $action")
        }
    }

    /** Minden ellenőrzés lefuttatva. */
    fun runAll(context: Context): List<Check> = listOf(
        batteryOptimization(context),
        autostart(context),
        exactAlarm(context),
        medicationHealth(context),
        backgroundRestriction(context),
        storageSpace(context)
    )

    fun speakSummary(context: Context): String {
        val checks = runAll(context)
        val fails = checks.count { it.level == Level.FAIL }
        val warns = checks.count { it.level == Level.WARN }

        if (fails == 0 && warns == 0) {
            return "Diagnosztika: minden rendben. Nem találtam problémát."
        }
        val parts = mutableListOf<String>()
        if (fails > 0) parts.add("$fails hiba")
        if (warns > 0) parts.add("$warns figyelmeztetés")

        val worst = checks.firstOrNull { it.level == Level.FAIL }
            ?: checks.first { it.level == Level.WARN }
        return "Diagnosztika: ${parts.joinToString(", ")}. A legfontosabb: ${worst.speak()}"
    }

    /**
     * Akku-optimalizálás.
     *
     * MIÉRT EZ AZ ELSŐ: ez a némaság leggyakoribb oka. A gyártók agresszíven
     * altatják a háttérben futó appokat — az Ulefone is. Ha ez be van kapcsolva,
     * a gyógyszer-emlékeztető és az ébresztő KÉSHET vagy ELMARADHAT, hiába van
     * meg minden engedély. A projekt eddig sehol nem ellenőrizte ezt.
     */
    fun batteryOptimization(context: Context): Check {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) {
            return Check("Akkumulátor-optimalizálás", Level.OK, "Ezen az Android verzión nem korlátoz.")
        }
        val pm = context.getSystemService(PowerManager::class.java)
        val ignoring = try {
            pm?.isIgnoringBatteryOptimizations(context.packageName) == true
        } catch (_: Exception) {
            false
        }
        return if (ignoring) {
            Check(
                "Akkumulátor-optimalizálás",
                Level.OK,
                "A SuperDL korlátozás nélkül futhat a háttérben. Az emlékeztetők időben szólnak."
            )
        } else {
            Check(
                "Akkumulátor-optimalizálás",
                Level.FAIL,
                "A rendszer altathatja a SuperDL-t a háttérben. Emiatt a gyógyszer " +
                    "emlékeztető és az ébresztő késhet vagy elmaradhat.",
                "Engedélyezd a korlátlan háttérfutást: a Diagnosztika menüben, " +
                    "vagy a rendszer beállításaiban az Akkumulátor résznél."
            )
        }
    }

    /** Az akku-optimalizálás alóli felmentés kérése (rendszerpárbeszéd). */
    fun batteryOptimizationIntent(context: Context): Intent? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                data = Uri.parse("package:${context.packageName}")
            }
        } else {
            null
        }

    /**
     * Gyártói automatikus indítás.
     *
     * ŐSZINTE KORLÁT: NEM tudjuk lekérdezni, hogy be van-e kapcsolva — erre
     * semmilyen API nincs. Csak azt tudjuk megmondani, hogy LÉTEZIK-E ilyen
     * képernyő ezen a telefonon. Ezért ez soha nem FAIL, csak figyelmeztetés:
     * hazugság lenne hibát jelenteni valamire, amit nem tudunk megmérni.
     */
    private fun autostart(context: Context): Check {
        val brand = AutostartHelper.manufacturerLabel()
        return if (AutostartHelper.isAvailable(context)) {
            Check(
                "Gyártói automatikus indítás",
                Level.WARN,
                "A $brand telefonokon külön automatikus indítás beállítás is van, " +
                    "az Android akku-beállításán FELÜL. Nem tudjuk lekérdezni, hogy " +
                    "be van-e kapcsolva — ezt neked kell ellenőrizned.",
                "Telefonon: Beállítások, Automatikus indítás a gyártónál."
            )
        } else {
            Check(
                "Gyártói automatikus indítás",
                Level.OK,
                "Ezen a telefonon ($brand) nincs külön gyártói automatikus indítás " +
                    "beállítás. Elég a korlátlan háttérfutás."
            )
        }
    }

    private fun exactAlarm(context: Context): Check {
        val can = try {
            MedicationScheduler.canScheduleExact(context)
        } catch (_: Exception) {
            false
        }
        return if (can) {
            Check("Pontos ébresztő", Level.OK, "Az emlékeztetők pontos időben szólalnak meg.")
        } else {
            Check(
                "Pontos ébresztő",
                Level.FAIL,
                "Nincs engedély a pontos időzítésre. Az ébresztő és a gyógyszer " +
                    "emlékeztető akár órákat is késhet.",
                "Add meg: Beállítások, Beállítás varázsló."
            )
        }
    }

    /**
     * A gyógyszer-emlékeztetők TÉNYLEGES egészsége.
     *
     * MIÉRT KÜLÖN ELLENŐRZÉS: az, hogy egy emlékeztető létezik a listában, NEM
     * jelenti, hogy meg is fog szólalni. Ez a projekt legveszélyesebb néma
     * hibája: a felhasználó azt hiszi, be van állítva, és nem kapja meg.
     *
     * Amit tényleg megnézünk:
     *  - van-e egyáltalán bekapcsolt emlékeztető,
     *  - a bekapcsoltakhoz van-e ÉRVÉNYES következő időpont (nextTriggerMillis),
     *  - lejárt-e a kúra (akkor nem hiba, hogy nincs következő).
     */
    private fun medicationHealth(context: Context): Check {
        val all = try {
            MedicationStore.getAll(context)
        } catch (_: Exception) {
            return Check(
                "Gyógyszer emlékeztetők",
                Level.WARN,
                "Az emlékeztetők most nem olvashatók."
            )
        }

        if (all.isEmpty()) {
            return Check(
                "Gyógyszer emlékeztetők",
                Level.OK,
                "Nincs felvéve emlékeztető."
            )
        }

        val enabled = all.filter { it.enabled }
        if (enabled.isEmpty()) {
            return Check(
                "Gyógyszer emlékeztetők",
                Level.WARN,
                "${all.size} emlékeztető van felvéve, de MIND ki van kapcsolva. " +
                    "Egyik sem fog megszólalni.",
                "Kapcsold be a portálon a Patika Őrangyal fülön, vagy vedd fel újra."
            )
        }

        val now = System.currentTimeMillis()
        val dead = mutableListOf<String>()
        var soonest = Long.MAX_VALUE
        var soonestName = ""

        for (r in enabled) {
            val next = try {
                MedicationScheduler.nextTriggerMillis(r)
            } catch (_: Exception) {
                0L
            }
            if (next <= 0L || next <= now) {
                // Nincs jövőbeli időpont: vagy lejárt a kúra, vagy nem ütemezhető.
                dead.add(r.name)
            } else if (next < soonest) {
                soonest = next
                soonestName = r.name
            }
        }

        val nextText = if (soonest != Long.MAX_VALUE) {
            val fmt = SimpleDateFormat("MM. dd. HH:mm", Locale("hu"))
            "A következő: $soonestName, ${fmt.format(Date(soonest))}."
        } else {
            ""
        }

        return when {
            dead.isEmpty() -> Check(
                "Gyógyszer emlékeztetők",
                Level.OK,
                "${enabled.size} aktív emlékeztető, mind be van ütemezve. $nextText"
            )
            dead.size == enabled.size -> Check(
                "Gyógyszer emlékeztetők",
                Level.FAIL,
                "${enabled.size} emlékeztető be van kapcsolva, de EGYIKHEZ SINCS " +
                    "következő időpont. Lehet, hogy lejárt a kúra vége.",
                "Ellenőrizd a portálon a Patika Őrangyal fülön: ${dead.take(3).joinToString(", ")}."
            )
            else -> Check(
                "Gyógyszer emlékeztetők",
                Level.WARN,
                "${enabled.size} aktív emlékeztetőből ${dead.size} nem fog megszólalni " +
                    "(lejárt kúra vagy hiányos beállítás): ${dead.take(3).joinToString(", ")}. $nextText",
                "Nézd meg őket a portálon a Patika Őrangyal fülön."
            )
        }
    }

    /**
     * Háttér-korlátozás (Data Saver / Background restricted).
     *
     * MIÉRT: ha a rendszer "korlátozott" állapotba tette az appot, a háttér-
     * szolgáltatások (őrség, időzítő, Elena figyelő) leállhatnak.
     */
    private fun backgroundRestriction(context: Context): Check {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.P) {
            return Check("Háttérfutás", Level.OK, "Ezen az Android verzión nem korlátozott.")
        }
        val am = context.getSystemService(ActivityManager::class.java)
        val restricted = try {
            am?.isBackgroundRestricted == true
        } catch (_: Exception) {
            false
        }
        return if (restricted) {
            Check(
                "Háttérfutás",
                Level.FAIL,
                "A rendszer korlátozza a SuperDL háttérfutását. Az őrség, az " +
                    "időzítők és Elena figyelő leállhat.",
                "Rendszer beállítások, Alkalmazások, SuperDL, Akkumulátor, " +
                    "és engedélyezd a háttérben futást."
            )
        } else {
            Check("Háttérfutás", Level.OK, "A SuperDL futhat a háttérben.")
        }
    }

    /**
     * Szabad tárhely.
     *
     * MIÉRT: ha betelik a tárhely, a mentés, a diktafon-felvétel és a
     * beállítások írása is csendben elbukhat.
     */
    private fun storageSpace(context: Context): Check {
        val free = try {
            context.filesDir.freeSpace
        } catch (_: Exception) {
            -1L
        }
        val mb = free / (1024 * 1024)
        return when {
            free < 0 -> Check("Tárhely", Level.WARN, "A szabad hely nem állapítható meg.")
            mb < 50 -> Check(
                "Tárhely",
                Level.FAIL,
                "Csak $mb megabájt szabad hely maradt. A beállítások mentése és a " +
                    "hangfelvétel is meghiúsulhat.",
                "Törölj felesleges fájlokat vagy felvételeket."
            )
            mb < 300 -> Check(
                "Tárhely",
                Level.WARN,
                "$mb megabájt szabad hely maradt. Érdemes helyet felszabadítani."
            )
            else -> Check("Tárhely", Level.OK, "$mb megabájt szabad hely.")
        }
    }
}
