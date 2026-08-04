package com.superdl.launcher.contacts

sealed class ContactBookItem {
    object SyncAction : ContactBookItem()
    data class Entry(val contact: ContactMatch) : ContactBookItem()

    fun speakLabel(): String = when (this) {
        SyncAction -> "Szinkronizálás a telefon névjegyzékével"
        is Entry -> "${contact.name}, ${ContactHelper.maskPhone(contact.phone)}"
    }
}