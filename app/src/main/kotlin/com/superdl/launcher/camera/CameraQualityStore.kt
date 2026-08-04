package com.superdl.launcher.camera

import android.content.Context

object CameraQualityStore {

    private const val PREFS = "camera_quality"
    private const val KEY_PROFILE = "profile"

    fun load(context: Context): CameraQualityProfile =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).let { prefs ->
            CameraQualityProfile.entries.getOrElse(prefs.getInt(KEY_PROFILE, CameraQualityProfile.MEDIUM.ordinal)) {
                CameraQualityProfile.MEDIUM
            }
        }

    fun save(context: Context, profile: CameraQualityProfile) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putInt(KEY_PROFILE, profile.ordinal)
            .apply()
    }

    fun updateProfile(context: Context, profile: CameraQualityProfile) =
        save(context, profile)
}