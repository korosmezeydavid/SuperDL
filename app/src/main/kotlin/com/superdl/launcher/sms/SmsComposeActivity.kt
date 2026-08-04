package com.superdl.launcher.sms

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.superdl.launcher.MainActivity

class SmsComposeActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val address = extractAddress(intent)
        val body = intent.getStringExtra("sms_body").orEmpty()
        val launch = Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            if (address.isNotBlank()) putExtra(EXTRA_SMS_COMPOSE_ADDRESS, address)
            if (body.isNotBlank()) putExtra(EXTRA_SMS_COMPOSE_BODY, body)
            action = ACTION_SMS_COMPOSE
        }
        startActivity(launch)
        finish()
    }

    private fun extractAddress(intent: Intent): String {
        intent.data?.let { uri ->
            if (uri.scheme == "smsto" || uri.scheme == "sms") {
                return uri.schemeSpecificPart?.substringBefore('?').orEmpty().trim()
            }
        }
        return intent.getStringExtra("address").orEmpty().trim()
    }

    companion object {
        const val ACTION_SMS_COMPOSE = "com.superdl.launcher.action.SMS_COMPOSE"
        const val EXTRA_SMS_COMPOSE_ADDRESS = "sms_compose_address"
        const val EXTRA_SMS_COMPOSE_BODY = "sms_compose_body"
    }
}