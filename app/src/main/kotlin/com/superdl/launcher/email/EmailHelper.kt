package com.superdl.launcher.email

import android.accounts.Account
import android.accounts.AccountManager
import android.content.Context
import android.provider.ContactsContract
import android.util.Patterns
import java.util.Locale
import java.util.regex.Pattern

object EmailHelper {

    private val EMAIL_IN_TEXT = Pattern.compile("[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}", Pattern.CASE_INSENSITIVE)

    fun isValidEmail(value: String): Boolean =
        value.isNotBlank() && Patterns.EMAIL_ADDRESS.matcher(value.trim()).matches()

    fun isConfigured(context: Context): Boolean = SmtpConfigStore.isConfigured(context)

    fun speakAddress(email: String): String =
        email.replace("@", " kukac ").replace(".", " pont ")

    fun parseSpokenAddress(spoken: String): String? {
        var text = spoken.trim().lowercase(Locale("hu", "HU"))
        if (text.isBlank()) return null

        text = text
            .replace("kukac", "@")
            .replace(" pont ", ".")
            .replace(" pont", ".")
            .replace("pont ", ".")
            .replace(Regex("\\s+"), "")

        val match = EMAIL_IN_TEXT.matcher(text)
        if (match.find()) return match.group().lowercase()

        if (text.contains("@") && isValidEmail(text)) return text
        return null
    }

    fun searchRecipients(context: Context, query: String): List<EmailRecipient> {
        val normalized = query.trim()
        if (normalized.isBlank()) return emptyList()

        val results = linkedMapOf<String, EmailRecipient>()

        EmailStore.getAll(context).forEach { recipient ->
            if (recipient.label.contains(normalized, ignoreCase = true) ||
                recipient.email.contains(normalized, ignoreCase = true)
            ) {
                results.putIfAbsent(recipient.email.lowercase(), recipient)
            }
        }

        searchContactEmails(context, normalized).forEach { recipient ->
            results.putIfAbsent(recipient.email.lowercase(), recipient)
        }

        parseSpokenAddress(normalized)?.let { parsed ->
            results.putIfAbsent(parsed, EmailRecipient(parsed, parsed))
        }

        return results.values.take(20).toList()
    }

    fun resolveRecipient(spoken: String, matches: List<EmailRecipient>): EmailRecipient? {
        parseSpokenAddress(spoken)?.let { parsed ->
            return EmailRecipient(parsed, parsed)
        }
        if (matches.size == 1) return matches.first()
        return null
    }

    fun importFromPhone(context: Context): ImportResult {
        val incoming = linkedMapOf<String, EmailRecipient>()
        var contactCount = 0
        var accountCount = 0

        searchContactEmails(context, "", limit = 200).forEach { recipient ->
            if (incoming.putIfAbsent(recipient.email.lowercase(), recipient) == null) {
                contactCount++
            }
        }

        getDeviceAccounts(context).forEach { account ->
            val email = account.name.trim().lowercase()
            if (!isValidEmail(email)) return@forEach
            val label = accountLabel(account)
            if (incoming.putIfAbsent(email, EmailRecipient(email, label)) == null) {
                accountCount++
            }
        }

        val added = EmailStore.importAll(context, incoming.values.toList())
        return ImportResult(
            added = added,
            contactsFound = contactCount,
            accountsFound = accountCount,
            totalCandidates = incoming.size
        )
    }

    fun send(context: Context, recipient: EmailRecipient, subject: String, body: String): Boolean {
        val config = SmtpConfigStore.get(context) ?: return false
        return SmtpSender.send(config, recipient.email, subject, body)
    }

    fun sendWithAttachment(
        context: Context,
        recipient: EmailRecipient,
        subject: String,
        body: String,
        attachment: java.io.File,
        attachmentMime: String,
        attachmentName: String? = null
    ): Boolean {
        val config = SmtpConfigStore.get(context) ?: return false
        return SmtpSender.send(
            config,
            recipient.email,
            subject,
            body,
            attachment,
            attachmentMime,
            attachmentName
        )
    }

    private fun searchContactEmails(context: Context, query: String, limit: Int = 40): List<EmailRecipient> {
        val results = linkedMapOf<String, EmailRecipient>()
        val projection = arrayOf(
            ContactsContract.CommonDataKinds.Email.CONTACT_ID,
            ContactsContract.CommonDataKinds.Email.DISPLAY_NAME,
            ContactsContract.CommonDataKinds.Email.ADDRESS
        )
        val selection = if (query.isBlank()) {
            null
        } else {
            "${ContactsContract.CommonDataKinds.Email.DISPLAY_NAME} LIKE ? OR " +
                "${ContactsContract.CommonDataKinds.Email.ADDRESS} LIKE ?"
        }
        val selectionArgs = if (query.isBlank()) null else arrayOf("%$query%", "%$query%")

        context.contentResolver.query(
            ContactsContract.CommonDataKinds.Email.CONTENT_URI,
            projection,
            selection,
            selectionArgs,
            ContactsContract.CommonDataKinds.Email.DISPLAY_NAME
        )?.use { cursor ->
            val nameIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Email.DISPLAY_NAME)
            val emailIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Email.ADDRESS)
            while (cursor.moveToNext() && results.size < limit) {
                val name = cursor.getString(nameIdx)?.trim().orEmpty()
                val email = cursor.getString(emailIdx)?.trim().orEmpty()
                if (!isValidEmail(email)) continue
                val label = name.ifBlank { email }
                results.putIfAbsent(email.lowercase(), EmailRecipient(email.lowercase(), label))
            }
        }
        return results.values.toList()
    }

    private fun getDeviceAccounts(context: Context): List<Account> {
        return try {
            AccountManager.get(context).accounts
                .filter { account ->
                    val type = account.type.lowercase(Locale.ROOT)
                    isValidEmail(account.name) ||
                        type.contains("google") ||
                        type.contains("mail") ||
                        type.contains("exchange") ||
                        type.contains("email")
                }
                .toList()
        } catch (_: SecurityException) {
            emptyList()
        }
    }

    private fun accountLabel(account: Account): String {
        val type = account.type.lowercase(Locale.ROOT)
        return when {
            type.contains("google") -> "Google fiók"
            type.contains("exchange") -> "Exchange fiók"
            type.contains("mail") || type.contains("email") -> "E-mail fiók"
            else -> account.name
        }
    }

    data class ImportResult(
        val added: Int,
        val contactsFound: Int,
        val accountsFound: Int,
        val totalCandidates: Int
    )
}