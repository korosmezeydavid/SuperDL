package com.superdl.launcher.contacts

enum class ContactContextAction(val label: String) {
    CALL("Hívás indítása"),
    SEND_SMS("SMS küldés"),
    RINGTONE("Egyéni csengőhang"),
    EDIT("Névjegy szerkesztése"),
    DELETE("Névjegy törlése");

    companion object {
        val browseActions: List<ContactContextAction> = entries.toList()
    }
}