package com.superdl.launcher.sms

import android.Manifest
import android.app.PendingIntent
import android.content.ContentResolver
import android.content.ContentUris
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Telephony
import android.telephony.SmsManager
import android.telephony.SubscriptionManager
import android.util.Log
import androidx.core.content.ContextCompat
import com.superdl.launcher.contacts.ContactHelper
import com.superdl.launcher.sos.SosPreferences

enum class SmsFolder(val label: String) {
    INBOX("Bejövő"),
    SENT("Kimenő")
}

data class SmsMessage(
    val id: Long,
    val address: String,
    val body: String,
    val date: Long,
    val folder: SmsFolder = SmsFolder.INBOX
)

object SmsHelper {

    private const val TAG = "SmsHelper"
    private const val DUPLICATE_WINDOW_MS = 8_000L

    fun hasReadPermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.READ_SMS) ==
            PackageManager.PERMISSION_GRANTED

    /**
     * SMS küldése.
     *
     * FONTOS (miért íródott át):
     * Korábban egyetlen sendTextMessage hívás ment, darabolás nélkül. Egy SMS-be
     * 160 karakter fér — DE ÉKEZETES MAGYAR SZÖVEGNÉL CSAK 70, mert olyankor a
     * telefon másik karakterkódolásra vált. Egy diktált mondat ezt könnyen
     * túllépi, és a hosszabb üzenet ilyenkor CSENDBEN ELVESZETT: a kimenő
     * mappában látszott, de a hálózatra nem ment ki.
     *
     * Most: a rendszerrel daraboljuk az üzenetet, és több részes küldést
     * használunk, ha kell. Ráadásul KÉRÜNK VISSZAJELZÉST a küldésről, így ha a
     * hálózat elutasítja, arról tudomást szerzünk (SmsSendReceiver).
     */
    fun send(context: Context, phone: String, message: String): Boolean {
        val trimmedPhone = normalizePhoneForSms(phone)
        val trimmedMessage = message.trim()
        if (trimmedPhone.isBlank() || trimmedMessage.isBlank()) return false
        return try {
            val manager = context.getSystemService(SmsManager::class.java)
                ?: @Suppress("DEPRECATION") SmsManager.getDefault()

            val parts = manager.divideMessage(trimmedMessage)
            Log.i(
                "SDL_SMS",
                "SMS küldés: ${trimmedMessage.length} karakter, ${parts.size} rész, " +
                    "szám hossza=${trimmedPhone.length}, kezdete=${trimmedPhone.take(4)}"
            )

            if (parts.size > 1) {
                val sentIntents = ArrayList<PendingIntent>(parts.size)
                val deliveryIntents = ArrayList<PendingIntent>(parts.size)
                for (i in parts.indices) {
                    sentIntents.add(buildSentIntent(context, i, parts.size))
                    deliveryIntents.add(buildDeliveredIntent(context, i, parts.size))
                }
                manager.sendMultipartTextMessage(
                    trimmedPhone, null, parts, sentIntents, deliveryIntents
                )
            } else {
                manager.sendTextMessage(
                    trimmedPhone, null, trimmedMessage,
                    buildSentIntent(context, 0, 1),
                    buildDeliveredIntent(context, 0, 1)
                )
            }
            storeMessage(context, trimmedPhone, trimmedMessage, Telephony.Sms.MESSAGE_TYPE_SENT)
            true
        } catch (e: Exception) {
            Log.w(TAG, "SMS küldés sikertelen", e)
            false
        }
    }

    /**
     * A telefonszám előkészítése küldéshez.
     *
     * MIÉRT KELL: a diktált vagy névjegyből vett szám gyakran tartalmaz
     * SZÓKÖZT, KÖTŐJELET vagy ZÁRÓJELET ("+36 30 123-4567"). A hálózat az ilyet
     * elfogadhatja — a küldés "sikeresnek" látszik —, de NEM KÉZBESÍTI.
     * Ez pontosan az a tünet, amikor a rendszer szerint elment, mégsem érkezik meg.
     *
     * Csak a számjegyeket és a vezető pluszt tartjuk meg.
     */
    fun normalizePhoneForSms(raw: String): String {
        val trimmed = raw.trim()
        if (trimmed.isBlank()) return ""
        val hasPlus = trimmed.startsWith("+")
        val digits = trimmed.filter { it.isDigit() }
        return if (hasPlus) "+$digits" else digits
    }

    /**
     * A küldés eredményét kérő jelzés. Enélkül az app nem tudja meg, hogy a
     * hálózat átvette-e az üzenetet — csak annyit lát, hogy elindította.
     */
    private fun buildSentIntent(context: Context, index: Int, total: Int): PendingIntent {
        val intent = Intent(ACTION_SMS_SENT).apply {
            setPackage(context.packageName)
            putExtra(EXTRA_PART_INDEX, index)
            putExtra(EXTRA_PART_TOTAL, total)
        }
        return PendingIntent.getBroadcast(
            context,
            System.currentTimeMillis().toInt() + index,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    /**
     * KÉZBESÍTÉSI visszajelzés kérése.
     *
     * A küldés-visszajelzés csak annyit mond, hogy a telefon ÁTADTA a hálózatnak.
     * Ez akkor is "sikeres", ha az üzenet végül nem jut el a címzetthez (rossz
     * szám, kikapcsolt készülék, hálózati elutasítás). A kézbesítés-visszajelzés
     * mondja meg, hogy TÉNYLEG MEGÉRKEZETT-e — enélkül vakon repülünk.
     */
    private fun buildDeliveredIntent(context: Context, index: Int, total: Int): PendingIntent {
        val intent = Intent(ACTION_SMS_DELIVERED).apply {
            setPackage(context.packageName)
            putExtra(EXTRA_PART_INDEX, index)
            putExtra(EXTRA_PART_TOTAL, total)
        }
        return PendingIntent.getBroadcast(
            context,
            (System.currentTimeMillis().toInt() + index) * 2 + 1,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    const val ACTION_SMS_SENT = "com.superdl.launcher.SMS_SENT"
    const val ACTION_SMS_DELIVERED = "com.superdl.launcher.SMS_DELIVERED"
    const val EXTRA_PART_INDEX = "part_index"
    const val EXTRA_PART_TOTAL = "part_total"

    fun messageExists(
        context: Context,
        address: String,
        body: String,
        timestamp: Long,
        windowMs: Long = DUPLICATE_WINDOW_MS
    ): Boolean {
        val minDate = (timestamp - windowMs).coerceAtLeast(0L)
        val maxDate = timestamp + windowMs
        return try {
            context.contentResolver.query(
                Telephony.Sms.CONTENT_URI,
                arrayOf(Telephony.Sms._ID),
                "${Telephony.Sms.ADDRESS} = ? AND ${Telephony.Sms.DATE} BETWEEN ? AND ? AND ${Telephony.Sms.BODY} = ?",
                arrayOf(address, minDate.toString(), maxDate.toString(), body),
                null
            )?.use { cursor -> cursor.moveToFirst() } ?: false
        } catch (e: Exception) {
            Log.w(TAG, "Duplikáció-ellenőrzés sikertelen", e)
            false
        }
    }

    fun storeIncomingMessage(
        context: Context,
        address: String,
        body: String,
        timestamp: Long,
        subscriptionId: Int = SubscriptionManager.INVALID_SUBSCRIPTION_ID,
        serviceCenter: String = ""
    ): Boolean = storeMessage(
        context = context,
        address = address,
        body = body,
        type = Telephony.Sms.MESSAGE_TYPE_INBOX,
        date = timestamp,
        read = false,
        subscriptionId = subscriptionId,
        serviceCenter = serviceCenter
    )

    fun getRecentMessages(
        context: Context,
        folder: SmsFolder = SmsFolder.INBOX,
        limit: Int = 20
    ): List<SmsMessage> {
        if (!hasReadPermission(context)) {
            Log.w(TAG, "READ_SMS engedély hiányzik – üzenetek nem olvashatók.")
            return emptyList()
        }

        val type = when (folder) {
            SmsFolder.INBOX -> Telephony.Sms.MESSAGE_TYPE_INBOX
            SmsFolder.SENT -> Telephony.Sms.MESSAGE_TYPE_SENT
        }
        val folderUri = when (folder) {
            SmsFolder.INBOX -> Telephony.Sms.Inbox.CONTENT_URI
            SmsFolder.SENT -> Telephony.Sms.Sent.CONTENT_URI
        }

        val attempts = listOf(
            QuerySpec(folderUri, null, null),
            QuerySpec(
                Telephony.Sms.CONTENT_URI,
                "${Telephony.Sms.TYPE} = ?",
                arrayOf(type.toString())
            )
        )

        for (spec in attempts) {
            val messages = queryMessages(context, spec.uri, folder, limit, spec.selection, spec.selectionArgs)
            if (messages.isNotEmpty()) return messages
        }
        return emptyList()
    }

    private data class QuerySpec(
        val uri: Uri,
        val selection: String?,
        val selectionArgs: Array<String>?
    )

    private fun queryMessages(
        context: Context,
        uri: Uri,
        folder: SmsFolder,
        limit: Int,
        selection: String? = null,
        selectionArgs: Array<String>? = null
    ): List<SmsMessage> {
        val messages = mutableListOf<SmsMessage>()
        try {
            val cursor = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val queryArgs = Bundle().apply {
                    putStringArray(
                        ContentResolver.QUERY_ARG_SORT_COLUMNS,
                        arrayOf(Telephony.Sms.DATE)
                    )
                    putInt(
                        ContentResolver.QUERY_ARG_SORT_DIRECTION,
                        ContentResolver.QUERY_SORT_DIRECTION_DESCENDING
                    )
                    putInt(ContentResolver.QUERY_ARG_LIMIT, limit)
                    if (!selection.isNullOrBlank()) {
                        putString(ContentResolver.QUERY_ARG_SQL_SELECTION, selection)
                        if (selectionArgs != null) {
                            putStringArray(ContentResolver.QUERY_ARG_SQL_SELECTION_ARGS, selectionArgs)
                        }
                    }
                }
                context.contentResolver.query(uri, SMS_PROJECTION, queryArgs, null)
            } else {
                @Suppress("DEPRECATION")
                context.contentResolver.query(
                    uri,
                    SMS_PROJECTION,
                    selection,
                    selectionArgs,
                    "${Telephony.Sms.DATE} DESC"
                )
            }
            cursor?.use {
                val idIdx = cursorColumnIndex(it, Telephony.Sms._ID, "_id")
                val addressIdx = cursorColumnIndex(it, Telephony.Sms.ADDRESS, "address")
                val bodyIdx = cursorColumnIndex(it, Telephony.Sms.BODY, "body")
                val dateIdx = cursorColumnIndex(it, Telephony.Sms.DATE, "date")
                if (idIdx < 0 || addressIdx < 0 || bodyIdx < 0 || dateIdx < 0) {
                    Log.w(TAG, "SMS oszlopok hiányoznak a lekérdezésben: $uri")
                    return emptyList()
                }
                while (it.moveToNext() && messages.size < limit) {
                    val id = it.getLong(idIdx)
                    val address = it.getString(addressIdx)?.trim().orEmpty()
                    val body = it.getString(bodyIdx).orEmpty()
                    val date = it.getLong(dateIdx)
                    if (address.isNotBlank()) {
                        messages.add(SmsMessage(id, address, body, date, folder))
                    }
                }
            } ?: Log.w(TAG, "SMS lekérdezés null kurzort adott: $uri")
        } catch (e: Exception) {
            Log.w(TAG, "SMS lekérdezés sikertelen: $uri", e)
        }
        return messages
    }

    private val SMS_PROJECTION = arrayOf(
        Telephony.Sms._ID,
        Telephony.Sms.ADDRESS,
        Telephony.Sms.BODY,
        Telephony.Sms.DATE
    )

    private fun cursorColumnIndex(cursor: android.database.Cursor, vararg names: String): Int {
        for (name in names) {
            val idx = cursor.getColumnIndex(name)
            if (idx >= 0) return idx
        }
        return -1
    }

    private fun storeMessage(
        context: Context,
        address: String,
        body: String,
        type: Int,
        date: Long = System.currentTimeMillis(),
        read: Boolean = true,
        subscriptionId: Int = SubscriptionManager.INVALID_SUBSCRIPTION_ID,
        serviceCenter: String = ""
    ): Boolean {
        val trimmedAddress = address.trim()
        if (trimmedAddress.isBlank()) return false
        val threadId = try {
            Telephony.Threads.getOrCreateThreadId(context, setOf(trimmedAddress))
        } catch (e: Exception) {
            Log.w(TAG, "Thread ID sikertelen", e)
            return false
        }

        val attempts = listOf(
            buildContentValues(
                context, trimmedAddress, body, type, date, read,
                subscriptionId, serviceCenter, threadId, full = true
            ),
            buildContentValues(
                context, trimmedAddress, body, type, date, read,
                subscriptionId, serviceCenter, threadId, full = false
            )
        )
        for (values in attempts) {
            if (values != null && insertMessage(context, values, type)) return true
        }
        return false
    }

    private fun buildContentValues(
        context: Context,
        address: String,
        body: String,
        type: Int,
        date: Long,
        read: Boolean,
        subscriptionId: Int,
        serviceCenter: String,
        threadId: Long,
        full: Boolean
    ): ContentValues? {
        return try {
            ContentValues().apply {
                put(Telephony.Sms.ADDRESS, address)
                put(Telephony.Sms.BODY, body)
                put(Telephony.Sms.DATE, date)
                put(Telephony.Sms.READ, if (read) 1 else 0)
                put(Telephony.Sms.TYPE, type)
                put(Telephony.Sms.THREAD_ID, threadId)
                if (full) {
                    put(Telephony.Sms.DATE_SENT, date)
                    put(Telephony.Sms.SEEN, if (read) 1 else 0)
                    put(Telephony.Sms.PROTOCOL, 0)
                    if (serviceCenter.isNotBlank()) {
                        put(Telephony.Sms.SERVICE_CENTER, serviceCenter)
                    }
                    put(Telephony.Sms.CREATOR, context.packageName)
                    if (type == Telephony.Sms.MESSAGE_TYPE_SENT) {
                        put(Telephony.Sms.STATUS, Telephony.Sms.STATUS_NONE)
                    }
                    if (subscriptionId != SubscriptionManager.INVALID_SUBSCRIPTION_ID) {
                        put(Telephony.Sms.SUBSCRIPTION_ID, subscriptionId)
                    }
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "SMS ContentValues összeállítás sikertelen", e)
            null
        }
    }

    private fun insertMessage(context: Context, values: ContentValues, type: Int): Boolean {
        val targets = buildList {
            add(Telephony.Sms.CONTENT_URI)
            when (type) {
                Telephony.Sms.MESSAGE_TYPE_INBOX -> add(Telephony.Sms.Inbox.CONTENT_URI)
                Telephony.Sms.MESSAGE_TYPE_SENT -> add(Telephony.Sms.Sent.CONTENT_URI)
            }
        }
        for (uri in targets.distinct()) {
            try {
                val inserted = context.contentResolver.insert(uri, values)
                if (inserted != null) return true
                Log.w(TAG, "SMS beszúrás null URI-t adott vissza: $uri")
            } catch (e: Exception) {
                Log.w(TAG, "SMS beszúrás sikertelen: $uri", e)
            }
        }
        return false
    }

    fun deleteMessage(context: Context, id: Long): Boolean {
        return try {
            val uri = ContentUris.withAppendedId(Telephony.Sms.CONTENT_URI, id)
            context.contentResolver.delete(uri, null, null) > 0
        } catch (e: Exception) {
            Log.w(TAG, "SMS törlés sikertelen", e)
            false
        }
    }

    fun resolveSenderLabel(context: Context, address: String): String =
        ContactHelper.findNameByPhone(context, address) ?: address

    fun resolveRecipient(spoken: String, contacts: List<com.superdl.launcher.contacts.ContactMatch>): Recipient? {
        val normalizedNumber = SosPreferences.normalizeSpokenNumber(spoken)
        if (normalizedNumber != null && normalizedNumber.isNotBlank()) {
            return Recipient(normalizedNumber, normalizedNumber)
        }
        if (contacts.size == 1) {
            val contact = contacts.first()
            return Recipient(contact.phone, contact.name)
        }
        return null
    }
}

data class Recipient(
    val phone: String,
    val label: String
)