package com.superdl.launcher.apps

import com.superdl.launcher.menu.MenuAction

enum class FavoriteAppType {
    INTERNAL,
    EXTERNAL
}

data class FavoriteAppEntry(
    val type: FavoriteAppType,
    val id: String,
    val label: String
) {
    fun speakPreview(): String = label
}