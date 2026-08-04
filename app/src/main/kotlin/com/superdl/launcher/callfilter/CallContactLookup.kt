package com.superdl.launcher.callfilter

import android.content.Context
import android.net.Uri
import android.provider.ContactsContract
import com.superdl.launcher.favorites.FavoritesStore

object CallContactLookup {

    fun isPriorityCaller(context: Context, phone: String): Boolean {
        val normalized = CallFilterStore.normalizePhone(phone)
        if (normalized.isBlank()) return false
        if (FavoritesStore.contains(context, normalized)) return true
        return isStarredInContacts(context, normalized)
    }

    fun isKnownContact(context: Context, phone: String): Boolean {
        val normalized = CallFilterStore.normalizePhone(phone)
        if (normalized.isBlank()) return false
        return lookupContactId(context, normalized) != null
    }

    private fun isStarredInContacts(context: Context, phone: String): Boolean {
        val uri = lookupUri(phone) ?: return false
        val projection = arrayOf(
            ContactsContract.PhoneLookup.STARRED,
            ContactsContract.PhoneLookup._ID
        )
        context.contentResolver.query(uri, projection, null, null, null)?.use { cursor ->
            if (!cursor.moveToFirst()) return false
            val starredIdx = cursor.getColumnIndex(ContactsContract.PhoneLookup.STARRED)
            if (starredIdx >= 0 && cursor.getInt(starredIdx) == 1) return true
        }
        val contactId = lookupContactId(context, phone) ?: return false
        return isContactStarredById(context, contactId)
    }

    private fun isContactStarredById(context: Context, contactId: String): Boolean {
        val uri = ContactsContract.Contacts.CONTENT_URI
        val projection = arrayOf(ContactsContract.Contacts.STARRED)
        context.contentResolver.query(
            uri,
            projection,
            "${ContactsContract.Contacts._ID}=?",
            arrayOf(contactId),
            null
        )?.use { cursor ->
            if (!cursor.moveToFirst()) return false
            val starredIdx = cursor.getColumnIndex(ContactsContract.Contacts.STARRED)
            return starredIdx >= 0 && cursor.getInt(starredIdx) == 1
        }
        return false
    }

    private fun lookupContactId(context: Context, phone: String): String? {
        val uri = lookupUri(phone) ?: return null
        context.contentResolver.query(
            uri,
            arrayOf(ContactsContract.PhoneLookup._ID),
            null,
            null,
            null
        )?.use { cursor ->
            if (cursor.moveToFirst()) {
                return cursor.getString(0)
            }
        }
        return null
    }

    private fun lookupUri(phone: String): Uri? {
        val normalized = CallFilterStore.normalizePhone(phone)
        if (normalized.isBlank()) return null
        return Uri.withAppendedPath(
            ContactsContract.PhoneLookup.CONTENT_FILTER_URI,
            Uri.encode(normalized)
        )
    }
}