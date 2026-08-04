package com.superdl.launcher.callfilter

import android.content.Context
import android.telecom.TelecomManager

object CallFilterEngine {

    private val HIDDEN_NUMBER_TOKENS = setOf(
        "unknown",
        "private",
        "rejtett",
        "ismeretlen",
        "hidden",
        "anonymous",
        "withheld",
        "unavailable"
    )

    fun shouldBlock(
        context: Context,
        phoneNumber: String?,
        handlePresentation: Int = TelecomManager.PRESENTATION_ALLOWED
    ): Boolean {
        val normalized = phoneNumber?.let(CallFilterStore::normalizePhone).orEmpty()

        if (normalized.isNotBlank() && CallFilterStore.isWhitelisted(context, normalized)) {
            return false
        }
        if (normalized.isNotBlank() && CallFilterStore.isBlacklisted(context, normalized)) {
            return true
        }

        return when (CallFilterStore.getMode(context)) {
            CallFilterMode.TOTAL_DND -> true
            CallFilterMode.PRIORITY_ONLY -> !CallContactLookup.isPriorityCaller(context, normalized)
            CallFilterMode.CONTACTS_ONLY -> {
                if (isPrivateOrHidden(normalized, handlePresentation)) return true
                !CallContactLookup.isKnownContact(context, normalized)
            }
            CallFilterMode.ACCEPT_ALL -> isPrivateOrHidden(normalized, handlePresentation)
        }
    }

    fun isPrivateOrHidden(phoneNumber: String, handlePresentation: Int): Boolean {
        if (phoneNumber.isBlank()) return true
        if (phoneNumber.lowercase() in HIDDEN_NUMBER_TOKENS) return true
        return handlePresentation == TelecomManager.PRESENTATION_RESTRICTED ||
            handlePresentation == TelecomManager.PRESENTATION_UNKNOWN
    }

    fun speakBlockReason(context: Context, phoneNumber: String?, handlePresentation: Int): String {
        val normalized = phoneNumber?.let(CallFilterStore::normalizePhone).orEmpty()
        return when {
            CallFilterStore.getMode(context) == CallFilterMode.TOTAL_DND ->
                "Teljes Ne Zavarj mód. Hívás blokkolva."
            normalized.isNotBlank() && CallFilterStore.isBlacklisted(context, normalized) ->
                "Letiltott szám."
            CallFilterStore.getMode(context) == CallFilterMode.PRIORITY_ONLY ->
                "Részleges szűrés. Csak kedvenc és csillagozott hívások engedélyezettek."
            CallFilterStore.getMode(context) == CallFilterMode.CONTACTS_ONLY &&
                !CallContactLookup.isKnownContact(context, normalized) ->
                "Laza szűrés. Ismeretlen szám blokkolva."
            CallFilterStore.getMode(context) == CallFilterMode.ACCEPT_ALL &&
                isPrivateOrHidden(normalized, handlePresentation) ->
                "Rejtett számú hívás blokkolva."
            else -> "Hívás blokkolva."
        }
    }
}