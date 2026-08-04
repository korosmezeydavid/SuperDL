package com.superdl.launcher.apps

import android.content.Context
import com.superdl.launcher.menu.MenuAction
import com.superdl.launcher.menu.MenuItem
import com.superdl.launcher.menu.MenuTree

data class FavoriteAppCandidate(
    val type: FavoriteAppType,
    val id: String,
    val label: String
) {
    fun toEntry(): FavoriteAppEntry = FavoriteAppEntry(type, id, label)

    fun speakPreview(): String = when (type) {
        FavoriteAppType.INTERNAL -> "Super DL: $label"
        FavoriteAppType.EXTERNAL -> "Külső: $label"
    }
}

object FavoriteAppCatalog {

    private val excludedActions = setOf(
        MenuAction.SUBMENU,
        MenuAction.EXIT_LAUNCHER,
        MenuAction.EXTERNAL_APPS,
        MenuAction.FAVORITE_APPS_LAUNCH,
        MenuAction.FAVORITE_APPS_ADD,
        MenuAction.FAVORITE_APPS_REMOVE
    )

    fun getAddableCandidates(context: Context): List<FavoriteAppCandidate> {
        val favorites = FavoriteAppsStore.getAll(context)
        val candidates = mutableListOf<FavoriteAppCandidate>()

        internalCandidates().forEach { candidate ->
            if (!favorites.any { it.type == candidate.type && it.id == candidate.id }) {
                candidates.add(candidate)
            }
        }
        externalCandidates(context).forEach { candidate ->
            if (!favorites.any { it.type == candidate.type && it.id == candidate.id }) {
                candidates.add(candidate)
            }
        }
        return candidates.sortedBy { it.label.lowercase() }
    }

    fun resolveEntry(context: Context, entry: FavoriteAppEntry): FavoriteAppEntry? {
        return when (entry.type) {
            FavoriteAppType.INTERNAL -> {
                val item = MenuTree.allItems().firstOrNull { it.action.name == entry.id } ?: return null
                entry.copy(label = item.label)
            }
            FavoriteAppType.EXTERNAL -> {
                if (!ExternalAppHelper.isInstalled(context, entry.id)) return null
                val apps = ExternalAppHelper.getLaunchableApps(context)
                val app = apps.firstOrNull { it.packageName == entry.id } ?: return entry
                entry.copy(label = app.label)
            }
        }
    }

    fun getActiveFavorites(context: Context): List<FavoriteAppEntry> {
        return FavoriteAppsStore.getAll(context).mapNotNull { resolveEntry(context, it) }
    }

    private fun internalCandidates(): List<FavoriteAppCandidate> {
        return MenuTree.allItems()
            .filter { item -> isFavoriteableInternal(item) }
            .distinctBy { it.action.name }
            .map { item ->
                FavoriteAppCandidate(
                    type = FavoriteAppType.INTERNAL,
                    id = item.action.name,
                    label = item.label
                )
            }
    }

    private fun externalCandidates(context: Context): List<FavoriteAppCandidate> {
        return ExternalAppHelper.getLaunchableApps(context).map { app ->
            FavoriteAppCandidate(
                type = FavoriteAppType.EXTERNAL,
                id = app.packageName,
                label = app.label
            )
        }
    }

    private fun isFavoriteableInternal(item: MenuItem): Boolean {
        if (item.action in excludedActions) return false
        if (item.id.endsWith("_back")) return false
        if (item.label.contains("Vissza", ignoreCase = true)) return false
        return true
    }
}