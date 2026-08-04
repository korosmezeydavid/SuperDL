package com.superdl.launcher.contacts

import android.content.ContentProviderOperation
import android.content.ContentUris
import android.content.Context
import android.provider.ContactsContract

data class ContactMatch(
    val id: String,
    val name: String,
    val phone: String
) {
    fun speakPreview(index: Int, total: Int): String =
        "$index / $total. $name, ${ContactHelper.maskPhone(phone)}"
}

object ContactHelper {

    fun searchByName(context: Context, query: String): List<ContactMatch> {
        val normalizedQuery = com.superdl.launcher.assistant.VoiceAssistantHelper.normalize(query)
        if (normalizedQuery.isBlank()) return emptyList()

        val sqlToken = normalizedQuery.split(" ").firstOrNull { it.length >= 2 } ?: normalizedQuery
        val queryWords = normalizedQuery.split(" ").filter { it.length >= 2 }

        val results = linkedMapOf<String, ContactMatch>()
        val projection = arrayOf(
            ContactsContract.CommonDataKinds.Phone.CONTACT_ID,
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
            ContactsContract.CommonDataKinds.Phone.NUMBER
        )
        val selection = "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} LIKE ?"
        val selectionArgs = arrayOf("%$sqlToken%")

        context.contentResolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            projection,
            selection,
            selectionArgs,
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME
        )?.use { cursor ->
            val idIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.CONTACT_ID)
            val nameIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
            val phoneIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
            while (cursor.moveToNext() && results.size < 40) {
                val id = cursor.getString(idIdx) ?: continue
                val name = cursor.getString(nameIdx)?.trim().orEmpty()
                val phone = cursor.getString(phoneIdx)?.replace(" ", "")?.trim().orEmpty()
                if (name.isBlank() || phone.isBlank()) continue
                val normalizedName = com.superdl.launcher.assistant.VoiceAssistantHelper.normalize(name)
                val matches = normalizedName.contains(normalizedQuery) ||
                    queryWords.all { word -> normalizedName.contains(word) }
                if (!matches) continue
                results.putIfAbsent("$id|$phone", ContactMatch(id, name, phone))
            }
        }
        return results.values.take(20).toList()
    }

    fun maskPhone(phone: String): String {
        val digits = phone.filter { it.isDigit() }
        if (digits.length < 4) return phone
        return "vége ${digits.takeLast(4)}"
    }

    fun findNameByPhone(context: Context, phone: String): String? {
        val normalized = normalizePhone(phone)
        if (normalized.isBlank()) return null
        val suffix = normalized.filter { it.isDigit() }.takeLast(7)
        if (suffix.length < 4) return null

        context.contentResolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            arrayOf(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME, ContactsContract.CommonDataKinds.Phone.NUMBER),
            null,
            null,
            null
        )?.use { cursor ->
            val nameIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
            val phoneIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
            while (cursor.moveToNext()) {
                val stored = normalizePhone(cursor.getString(phoneIdx).orEmpty())
                if (stored.isBlank()) continue
                if (stored == normalized || stored.endsWith(suffix) || normalized.endsWith(stored.takeLast(7))) {
                    val name = cursor.getString(nameIdx)?.trim().orEmpty()
                    if (name.isNotBlank()) return name
                }
            }
        }
        return null
    }

    fun listAllWithPhone(context: Context, limit: Int = 500): List<ContactMatch> {
        val results = linkedMapOf<String, ContactMatch>()
        val projection = arrayOf(
            ContactsContract.CommonDataKinds.Phone.CONTACT_ID,
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
            ContactsContract.CommonDataKinds.Phone.NUMBER
        )
        context.contentResolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            projection,
            null,
            null,
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME
        )?.use { cursor ->
            val idIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.CONTACT_ID)
            val nameIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
            val phoneIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
            while (cursor.moveToNext() && results.size < limit) {
                val id = cursor.getString(idIdx) ?: continue
                val name = cursor.getString(nameIdx)?.trim().orEmpty()
                val phone = cursor.getString(phoneIdx)?.replace(" ", "")?.trim().orEmpty()
                if (name.isBlank() || phone.isBlank()) continue
                results.putIfAbsent("$id|$phone", ContactMatch(id, name, phone))
            }
        }
        return results.values.sortedBy { it.name.lowercase() }
    }

    fun isKnownNumber(context: Context, phone: String): Boolean =
        findNameByPhone(context, phone) != null

    fun insertContact(context: Context, name: String, phone: String): Boolean {
        val trimmedName = name.trim()
        val trimmedPhone = phone.trim()
        if (trimmedName.isBlank() || trimmedPhone.isBlank()) return false
        return try {
            val ops = ArrayList<ContentProviderOperation>()
            ops.add(
                ContentProviderOperation.newInsert(ContactsContract.RawContacts.CONTENT_URI)
                    .withValue(ContactsContract.RawContacts.ACCOUNT_TYPE, null)
                    .withValue(ContactsContract.RawContacts.ACCOUNT_NAME, null)
                    .build()
            )
            ops.add(
                ContentProviderOperation.newInsert(ContactsContract.Data.CONTENT_URI)
                    .withValueBackReference(ContactsContract.Data.RAW_CONTACT_ID, 0)
                    .withValue(
                        ContactsContract.Data.MIMETYPE,
                        ContactsContract.CommonDataKinds.StructuredName.CONTENT_ITEM_TYPE
                    )
                    .withValue(ContactsContract.CommonDataKinds.StructuredName.DISPLAY_NAME, trimmedName)
                    .build()
            )
            ops.add(
                ContentProviderOperation.newInsert(ContactsContract.Data.CONTENT_URI)
                    .withValueBackReference(ContactsContract.Data.RAW_CONTACT_ID, 0)
                    .withValue(
                        ContactsContract.Data.MIMETYPE,
                        ContactsContract.CommonDataKinds.Phone.CONTENT_ITEM_TYPE
                    )
                    .withValue(ContactsContract.CommonDataKinds.Phone.NUMBER, trimmedPhone)
                    .withValue(ContactsContract.CommonDataKinds.Phone.TYPE, ContactsContract.CommonDataKinds.Phone.TYPE_MOBILE)
                    .build()
            )
            context.contentResolver.applyBatch(ContactsContract.AUTHORITY, ops)
            true
        } catch (_: Exception) {
            false
        }
    }

    fun updateContact(context: Context, contactId: String, name: String, phone: String): Boolean {
        val trimmedName = name.trim()
        val trimmedPhone = phone.trim()
        if (trimmedName.isBlank() || trimmedPhone.isBlank()) return false
        return try {
            val ops = ArrayList<ContentProviderOperation>()
            val nameSelection = (
                "${ContactsContract.Data.CONTACT_ID}=? AND " +
                    "${ContactsContract.Data.MIMETYPE}=?"
                )
            val nameArgs = arrayOf(
                contactId,
                ContactsContract.CommonDataKinds.StructuredName.CONTENT_ITEM_TYPE
            )
            ops.add(
                ContentProviderOperation.newUpdate(ContactsContract.Data.CONTENT_URI)
                    .withSelection(nameSelection, nameArgs)
                    .withValue(ContactsContract.CommonDataKinds.StructuredName.DISPLAY_NAME, trimmedName)
                    .withValue(ContactsContract.CommonDataKinds.StructuredName.GIVEN_NAME, trimmedName)
                    .build()
            )
            val phoneSelection = (
                "${ContactsContract.Data.CONTACT_ID}=? AND " +
                    "${ContactsContract.Data.MIMETYPE}=?"
                )
            val phoneArgs = arrayOf(
                contactId,
                ContactsContract.CommonDataKinds.Phone.CONTENT_ITEM_TYPE
            )
            ops.add(
                ContentProviderOperation.newUpdate(ContactsContract.Data.CONTENT_URI)
                    .withSelection(phoneSelection, phoneArgs)
                    .withValue(ContactsContract.CommonDataKinds.Phone.NUMBER, trimmedPhone)
                    .build()
            )
            context.contentResolver.applyBatch(ContactsContract.AUTHORITY, ops)
            true
        } catch (_: Exception) {
            false
        }
    }

    fun deleteContact(context: Context, contactId: String): Boolean {
        return try {
            val uri = ContentUris.withAppendedId(
                ContactsContract.Contacts.CONTENT_URI,
                contactId.toLong()
            )
            context.contentResolver.delete(uri, null, null) > 0
        } catch (_: Exception) {
            false
        }
    }

    private fun normalizePhone(phone: String): String =
        phone.replace(" ", "").trim()
}