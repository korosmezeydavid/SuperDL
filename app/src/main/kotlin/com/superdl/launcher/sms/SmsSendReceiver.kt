package com.superdl.launcher.sms

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.telephony.SmsManager
import android.util.Log

/**
 * Az SMS-küldés TÉNYLEGES eredményét fogadja.
 *
 * Enélkül az alkalmazás csak annyit tudott, hogy elindította a küldést — ezért
 * az üzenet megjelent a kimenő mappában akkor is, ha a hálózat elutasította.
 * Innen jött a panasz: "látszik a kimenőben, mégsem ment el".
 *
 * A hibát naplózzuk (SDL_SMS), és a küldő képernyő ez alapján tud szólni a
 * felhasználónak, ha valami nem sikerült.
 */
class SmsSendReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context?, intent: Intent?) {
        val index = intent?.getIntExtra(SmsHelper.EXTRA_PART_INDEX, 0)?.plus(1) ?: 1
        val total = intent?.getIntExtra(SmsHelper.EXTRA_PART_TOTAL, 1) ?: 1

        when (intent?.action) {
            SmsHelper.ACTION_SMS_SENT -> handleSent(index, total)
            SmsHelper.ACTION_SMS_DELIVERED -> handleDelivered(index, total)
            else -> return
        }
    }

    /** A telefon átadta a hálózatnak — ez MÉG NEM kézbesítés! */
    private fun handleSent(index: Int, total: Int) {
        when (resultCode) {
            Activity.RESULT_OK -> {
                Log.i(TAG, "SMS rész $index/$total: ELKÜLDVE a hálózatnak")
                lastError = null
            }
            SmsManager.RESULT_ERROR_GENERIC_FAILURE -> fail(index, total, "általános hiba")
            SmsManager.RESULT_ERROR_NO_SERVICE -> fail(index, total, "nincs hálózat")
            SmsManager.RESULT_ERROR_NULL_PDU -> fail(index, total, "üres üzenet")
            SmsManager.RESULT_ERROR_RADIO_OFF -> fail(index, total, "a rádió ki van kapcsolva")
            else -> fail(index, total, "ismeretlen hiba ($resultCode)")
        }
    }

    /**
     * A címzett készüléke MEGKAPTA az üzenetet — ez a valódi siker.
     *
     * Ha ez sosem érkezik meg, miközben a küldés "sikeres" volt, akkor az
     * üzenet elakadt a hálózatban (hibás szám, kikapcsolt készülék, a
     * szolgáltató elutasította).
     */
    private fun handleDelivered(index: Int, total: Int) {
        when (resultCode) {
            Activity.RESULT_OK -> {
                Log.i(TAG, "SMS rész $index/$total: KÉZBESÍTVE a címzettnek")
                lastDelivered = true
                lastError = null
            }
            else -> {
                Log.w(TAG, "SMS rész $index/$total: NEM KÉZBESÍTHETŐ (kód: $resultCode)")
                lastDelivered = false
                lastError = "az üzenet nem jutott el a címzetthez"
            }
        }
    }

    private fun fail(index: Int, total: Int, reason: String) {
        Log.w(TAG, "SMS rész $index/$total: SIKERTELEN — $reason")
        lastError = reason
    }

    companion object {
        private const val TAG = "SDL_SMS"

        /**
         * A legutóbbi küldés hibája emberi nyelven, vagy null, ha sikerült.
         * A küldő képernyő ezt tudja bemondani a felhasználónak.
         */
        @Volatile
        var lastError: String? = null
            private set

        /**
         * Megérkezett-e a legutóbbi üzenet a címzetthez.
         * Null = még nem tudjuk (a kézbesítési visszajelzés késhet percekig).
         */
        @Volatile
        var lastDelivered: Boolean? = null
            private set

        fun clearLastError() {
            lastError = null
            lastDelivered = null
        }
    }
}
