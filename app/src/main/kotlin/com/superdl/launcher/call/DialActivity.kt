package com.superdl.launcher.call

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.superdl.launcher.MainActivity

/**
 * Required entry point for the default dialer role. Forwards tel: intents to [MainActivity].
 */
class DialActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val number = extractPhoneNumber(intent)
        val launch = Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            if (number.isNotBlank()) {
                putExtra(EXTRA_DIAL_NUMBER, number)
            }
        }
        startActivity(launch)
        finish()
    }

    private fun extractPhoneNumber(intent: Intent): String {
        intent.data?.let { uri ->
            if (uri.scheme == "tel") return uri.schemeSpecificPart.orEmpty()
        }
        return intent.getStringExtra(Intent.EXTRA_PHONE_NUMBER).orEmpty()
    }

    companion object {
        const val EXTRA_DIAL_NUMBER = "dial_number"
    }
}