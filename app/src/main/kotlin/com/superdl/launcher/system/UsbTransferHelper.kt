package com.superdl.launcher.system

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.BatteryManager
import android.util.Log

/**
 * USB fájlátvitel (MTP) gyors elérése vak felhasználóknak.
 *
 * FONTOS KORLÁT: az USB-mód átkapcsolása az Android egyik védett rendszer-
 * beállítása – csak gyári rendszeralkalmazás (vagy root) tudja programból
 * átállítani. Még az ADB-nek sincs joga hozzá. Ezért NEM tudunk helyette
 * kapcsolni; amit tudunk – és ez vakon a lényeg –, hogy EGYETLEN menüponttal
 * pontosan arra a képernyőre visszük, ahol egy söpréssel átkapcsolható,
 * a keresgélős értesítés-lehúzás helyett.
 */
object UsbTransferHelper {

    private const val TAG = "SuperDL.UsbTransfer"

    /** Rá van-e dugva a telefon egy gépre (USB-kábellel). */
    fun isUsbConnected(context: Context): Boolean = try {
        val intent = context.registerReceiver(null, android.content.IntentFilter("android.hardware.usb.action.USB_STATE"))
        intent?.getBooleanExtra("connected", false) ?: isChargingOverUsb(context)
    } catch (e: Exception) {
        Log.w(TAG, "isUsbConnected failed", e)
        isChargingOverUsb(context)
    }

    /** Be van-e kapcsolva a fájlátvitel (MTP) mód. */
    fun isFileTransferOn(context: Context): Boolean = try {
        val intent = context.registerReceiver(null, android.content.IntentFilter("android.hardware.usb.action.USB_STATE"))
        intent?.getBooleanExtra("mtp", false) ?: false
    } catch (e: Exception) {
        Log.w(TAG, "isFileTransferOn failed", e)
        false
    }

    private fun isChargingOverUsb(context: Context): Boolean = try {
        val bm = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val plugged = android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED).let {
            context.registerReceiver(null, it)?.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1) ?: -1
        }
        plugged == BatteryManager.BATTERY_PLUGGED_USB
    } catch (_: Exception) {
        false
    }

    /**
     * Megnyitja az USB-beállítások képernyőt, ahol a fájlátvitel kapcsolható.
     * Több útvonalat próbál, mert a gyártók eltérően nevezik el.
     * @return igaz, ha sikerült megnyitni valamelyiket.
     */
    fun openUsbSettings(context: Context): Boolean {
        // 1) Android 10+ dedikált USB-képernyő (ez a legpontosabb).
        val direct = Intent().apply {
            component = ComponentName(
                "com.android.settings",
                "com.android.settings.Settings\$UsbDetailsActivity"
            )
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        if (tryStart(context, direct)) return true

        // 2) Csatlakoztatott eszközök képernyő.
        val connected = Intent("android.settings.DEVICE_INFO_SETTINGS").apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        if (tryStart(context, connected)) return true

        // 3) Végső esetben a fejlesztői beállítások (ott is van USB-konfiguráció).
        val dev = Intent(android.provider.Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        return tryStart(context, dev)
    }

    private fun tryStart(context: Context, intent: Intent): Boolean = try {
        context.startActivity(intent)
        true
    } catch (e: Exception) {
        Log.w(TAG, "openUsbSettings variant failed", e)
        false
    }

    /** A helyzethez illő, felolvasható eligazítás. */
    fun speakStatus(context: Context): String {
        val connected = isUsbConnected(context)
        val mtpOn = isFileTransferOn(context)
        return when {
            !connected ->
                "A telefon most nincs kábellel géphez csatlakoztatva. " +
                    "Dugd rá a kábelt, aztán nyisd meg ezt a menüpontot újra."
            mtpOn ->
                "A fájlátvitel be van kapcsolva, a gép látja a telefon tartalmát. " +
                    "Megnyitom az USB beállításokat, ahol ki tudod kapcsolni: " +
                    "söpörj a Fájlátvitel vagy a Nincs adatátvitel lehetőségre."
            else ->
                "A fájlátvitel most ki van kapcsolva, a telefon csak töltődik. " +
                    "Megnyitom az USB beállításokat: keresd a Fájlátvitel lehetőséget, " +
                    "és koppints rá a bekapcsoláshoz."
        }
    }
}
