package com.superdl.launcher.settings

import android.content.Context
import android.content.Intent
import android.provider.Settings

object LauncherExitHelper {

    fun createHomeSettingsIntent(context: Context): Intent? {
        val candidates = listOf(
            Intent(Settings.ACTION_HOME_SETTINGS),
            Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS),
        )
        return candidates.firstOrNull { it.resolveActivity(context.packageManager) != null }
    }
}