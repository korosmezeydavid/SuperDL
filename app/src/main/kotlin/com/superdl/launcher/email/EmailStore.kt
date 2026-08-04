package com.superdl.launcher.email

import android.content.Context
import com.superdl.launcher.storage.JsonPrefsHelper
import org.json.JSONArray
import org.json.JSONObject

object EmailStore {

    private const val PREFS = "email_prefs"
    private const val KEY_RECIPIENTS = "recipients"
    private const val KEY_RECIPIENTS_SCHEMA = "recipients_schema"
    private const val SCHEMA_VERSION = 1
    private const val MAX_RECIPIENTS = 50

    fun getAll(context: Context): List<EmailRecipient> {
        val list = mutableListOf<EmailRecipient>()
        val array = JsonPrefsHelper.readJsonArray(
            context = context,
            prefsName = PREFS,
            dataKey = KEY_RECIPIENTS,
            schemaVersionKey = KEY_RECIPIENTS_SCHEMA,
            currentSchemaVersion = SCHEMA_VERSION
        )
        for (i in 0 until array.length()) {
            val obj = array.optJSONObject(i) ?: continue
            val email = obj.optString("email").trim()
            if (!EmailHelper.isValidEmail(email)) continue
            val label = obj.optString("label").trim().ifBlank { email }
            list.add(EmailRecipient(email, label))
        }
        return list.sortedBy { it.label.lowercase() }
    }

    fun add(context: Context, recipient: EmailRecipient): Boolean {
        val email = recipient.email.trim().lowercase()
        if (!EmailHelper.isValidEmail(email)) return false
        val recipients = getAll(context).toMutableList()
        if (recipients.any { it.email.equals(email, ignoreCase = true) }) return true
        if (recipients.size >= MAX_RECIPIENTS) return false
        recipients.add(EmailRecipient(email, recipient.label.trim().ifBlank { email }))
        save(context, recipients)
        return true
    }

    fun importAll(context: Context, incoming: List<EmailRecipient>): Int {
        if (incoming.isEmpty()) return 0
        val existing = getAll(context).map { it.email.lowercase() }.toMutableSet()
        val recipients = getAll(context).toMutableList()
        var added = 0
        for (item in incoming) {
            val email = item.email.trim().lowercase()
            if (!EmailHelper.isValidEmail(email) || existing.contains(email)) continue
            if (recipients.size >= MAX_RECIPIENTS) break
            recipients.add(EmailRecipient(email, item.label.trim().ifBlank { email }))
            existing.add(email)
            added++
        }
        if (added > 0) save(context, recipients)
        return added
    }

    private fun save(context: Context, recipients: List<EmailRecipient>) {
        val array = JSONArray()
        recipients.forEach { recipient ->
            array.put(
                JSONObject()
                    .put("email", recipient.email)
                    .put("label", recipient.label)
            )
        }
        JsonPrefsHelper.saveJsonArray(
            context,
            PREFS,
            KEY_RECIPIENTS,
            KEY_RECIPIENTS_SCHEMA,
            SCHEMA_VERSION,
            array
        )
    }
}