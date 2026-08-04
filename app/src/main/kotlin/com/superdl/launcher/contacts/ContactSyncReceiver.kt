package com.superdl.launcher.contacts

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class ContactSyncReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        ContactSyncHelper.syncIfNeeded(context) ?: ContactSyncHelper.sync(context)
        ContactSyncScheduler.reschedule(context)
    }
}