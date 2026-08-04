package com.superdl.launcher.sms

import android.app.Service
import android.content.Intent
import android.os.IBinder
class HeadlessSmsSendService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val phone = intent?.getStringExtra(Intent.EXTRA_PHONE_NUMBER).orEmpty().trim()
        val message = intent?.getStringExtra("android.intent.extra.MESSAGE").orEmpty().trim()
        if (phone.isNotBlank() && message.isNotBlank()) {
            SmsHelper.send(this, phone, message)
        }
        stopSelf(startId)
        return START_NOT_STICKY
    }
}