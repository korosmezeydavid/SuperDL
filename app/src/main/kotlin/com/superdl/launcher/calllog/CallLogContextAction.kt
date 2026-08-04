package com.superdl.launcher.calllog

import android.content.Context
import com.superdl.launcher.contacts.ContactHelper

enum class CallLogContextAction(val label: String) {
    CALL("Hívás indítása"),
    SEND_SMS("SMS küldés"),
    COPY_NUMBER("Szám másolása"),
    SAVE_CONTACT("Mentés névjegyként"),
    ADD_FAVORITE("Hozzáadás a Kedvencekhez"),
    BLOCK_NUMBER("Telefonszám letiltása");

    companion object {
        fun forEntry(context: Context, entry: CallLogEntry): List<CallLogContextAction> {
            val actions = mutableListOf(CALL, SEND_SMS, COPY_NUMBER)
            if (!ContactHelper.isKnownNumber(context, entry.number)) {
                actions.add(SAVE_CONTACT)
            }
            actions.add(ADD_FAVORITE)
            if (entry.number.isNotBlank()) {
                actions.add(BLOCK_NUMBER)
            }
            return actions
        }
    }
}