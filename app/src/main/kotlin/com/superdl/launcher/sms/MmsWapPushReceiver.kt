package com.superdl.launcher.sms

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class MmsWapPushReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        // MMS fogadás – alap implementáció a default SMS app szerephez.
        // A Super DL fő funkciója az SMS; az MMS csak a rendszerkövetelmény miatt van jelen.
    }
}