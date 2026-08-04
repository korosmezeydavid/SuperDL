package com.superdl.launcher.info

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.telephony.TelephonyManager
import com.superdl.launcher.qr.QrScanActivity
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object InfoHelper {

    fun speakDateTime(): String {
        val now = Date()
        val dateFmt = SimpleDateFormat("yyyy. MMMM d., EEEE", Locale("hu", "HU"))
        val timeFmt = SimpleDateFormat("H:mm", Locale("hu", "HU"))
        return "Ma ${dateFmt.format(now)}. Az idő ${timeFmt.format(now)}."
    }

    /**
     * Akkumulátor töltöttség és térerő egyben, vak felhasználónak felolvasva.
     */
    fun batteryAndSignalReport(context: Context): String {
        return "${batteryReport(context)} ${signalReport(context)}"
    }

    /**
     * Rövid állapotsor a főmenü szélén ("már a főmenüben vagy" után):
     * pontos idő dátum nélkül, akku százalék, térerő százalékban (ha mérhető).
     */
    fun mainMenuStatusLine(context: Context): String {
        val timeFmt = SimpleDateFormat("H' óra 'm' perc'", Locale("hu", "HU"))
        val time = timeFmt.format(Date())
        val battery = batteryReport(context)
        val signal = signalPercentReport(context)
        return listOf("$time.", battery, signal)
            .filter { it.isNotBlank() }
            .joinToString(" ")
    }

    /** Térerő százalékban (a 0–4 szintből számolva), vagy üres ha nem mérhető. */
    fun signalPercentReport(context: Context): String {
        val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager
            ?: return ""
        if (tm.simState == TelephonyManager.SIM_STATE_ABSENT) return "Nincs SIM kártya."
        val level: Int = try {
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
                tm.signalStrength?.level ?: -1
            } else {
                -1
            }
        } catch (_: Exception) {
            -1
        }
        return if (level in 0..4) "Térerő ${level * 25} százalék." else ""
    }

    fun batteryReport(context: Context): String {
        val bm = context.getSystemService(Context.BATTERY_SERVICE) as? BatteryManager
        val level = bm?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: -1
        if (level < 0) return "Az akkumulátor szintje nem elérhető."

        val status = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val plugged = status?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) ?: 0
        val charging = plugged != 0
        return if (charging) {
            "Akkumulátor $level százalék, töltés alatt."
        } else {
            "Akkumulátor $level százalék."
        }
    }

    fun signalReport(context: Context): String {
        val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager
            ?: return "A térerő nem elérhető."

        // Repülő mód / nincs SIM
        if (tm.simState == TelephonyManager.SIM_STATE_ABSENT) {
            return "Nincs SIM kártya."
        }

        val level: Int = try {
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
                tm.signalStrength?.level ?: -1
            } else {
                -1
            }
        } catch (_: SecurityException) {
            -1
        } catch (_: Exception) {
            -1
        }

        val operator = tm.networkOperatorName?.takeIf { it.isNotBlank() }
        val levelText = when (level) {
            0 -> "nincs térerő"
            1 -> "gyenge térerő"
            2 -> "közepes térerő"
            3 -> "jó térerő"
            4 -> "kiváló térerő"
            else -> "a térerő szintje ismeretlen"
        }
        return if (operator != null) {
            "$operator, $levelText."
        } else {
            "${levelText.replaceFirstChar { it.uppercase() }}."
        }
    }

    fun openQrScanner(context: Context): Boolean {
        val intent = Intent(context, QrScanActivity::class.java)
        if (context !is android.app.Activity) {
            intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        context.startActivity(intent)
        return true
    }
}