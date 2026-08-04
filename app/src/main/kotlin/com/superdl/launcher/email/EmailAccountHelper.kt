package com.superdl.launcher.email

import android.accounts.Account
import android.accounts.AccountManager
import android.content.Context
import java.util.Locale

object EmailAccountHelper {

    fun getSmtpCandidates(context: Context): List<String> {
        return try {
            AccountManager.get(context).accounts
                .mapNotNull { account -> accountToEmail(account) }
                .distinct()
                .sorted()
        } catch (_: SecurityException) {
            emptyList()
        }
    }

    private fun accountToEmail(account: Account): String? {
        val email = account.name.trim().lowercase(Locale.ROOT)
        if (!EmailHelper.isValidEmail(email)) return null
        val type = account.type.lowercase(Locale.ROOT)
        return when {
            type.contains("google") -> email
            type.contains("mail") -> email
            type.contains("exchange") -> email
            type.contains("email") -> email
            email.endsWith("@gmail.com") -> email
            else -> email
        }
    }

    fun speakAccount(email: String): String =
        "A telefonon beállított e-mail: ${EmailHelper.speakAddress(email)}."
}