package com.superdl.launcher.favorites

import com.superdl.launcher.contacts.ContactHelper

data class FavoriteEntry(
    val name: String,
    val phone: String
) {
    fun speakPreview(): String = name.ifBlank { phone }

    fun speakFull(): String {
        val who = name.ifBlank { phone }
        return "$who. ${ContactHelper.maskPhone(phone)}"
    }
}