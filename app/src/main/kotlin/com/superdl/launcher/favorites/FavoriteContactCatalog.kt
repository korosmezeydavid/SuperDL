package com.superdl.launcher.favorites

import android.content.Context
import com.superdl.launcher.contacts.ContactHelper
import com.superdl.launcher.contacts.ContactMatch

data class FavoriteContactCandidate(
    val contact: ContactMatch
) {
    fun speakPreview(): String {
        val name = contact.name.ifBlank { contact.phone }
        return "$name. ${ContactHelper.maskPhone(contact.phone)}"
    }

    fun name(): String = contact.name
    fun phone(): String = contact.phone
}

object FavoriteContactCatalog {

    fun getAddableCandidates(context: Context): List<FavoriteContactCandidate> {
        return ContactHelper.listAllWithPhone(context)
            .filterNot { FavoritesStore.contains(context, it.phone) }
            .map { FavoriteContactCandidate(it) }
    }
}