package com.superdl.launcher.contacts

import android.accounts.Account
import android.content.ContentResolver
import android.content.Context
import android.os.Bundle
import android.provider.ContactsContract
import android.util.Log

object ContactSyncHelper {

    private const val TAG = "ContactSyncHelper"

    data class SyncResult(
        val count: Int,
        val syncedAtMs: Long,
        val googleAccountsTriggered: Int
    ) {
        fun speakSummary(): String =
            if (count == 0) {
                "Szinkronizálás kész. Nincs telefonszámmal rendelkező névjegy."
            } else {
                "Szinkronizálás kész. $count névjegy frissítve."
            }
    }

    fun sync(context: Context): SyncResult {
        val appContext = context.applicationContext
        val googleTriggered = requestGoogleContactsSync(appContext)
        val contacts = ContactHelper.listAllWithPhone(appContext)
        val syncedAt = System.currentTimeMillis()
        ContactStore.save(appContext, contacts, syncedAt)
        Log.i(TAG, "Synced ${contacts.size} contacts, googleAccounts=$googleTriggered")
        return SyncResult(contacts.size, syncedAt, googleTriggered)
    }

    fun syncIfNeeded(context: Context): SyncResult? {
        if (!ContactStore.needsDailySync(context)) return null
        return sync(context)
    }

    private fun requestGoogleContactsSync(context: Context): Int {
        var triggered = 0
        try {
            @Suppress("DEPRECATION")
            val accounts = android.accounts.AccountManager.get(context).accounts
            for (account in accounts) {
                if (!account.type.contains("google", ignoreCase = true)) continue
                val authority = ContactsContract.AUTHORITY
                if (!ContentResolver.getSyncAutomatically(account, authority)) continue
                ContentResolver.requestSync(account, authority, Bundle.EMPTY)
                triggered++
            }
        } catch (e: Exception) {
            Log.w(TAG, "Google névjegy szinkron kérés sikertelen", e)
        }
        return triggered
    }
}