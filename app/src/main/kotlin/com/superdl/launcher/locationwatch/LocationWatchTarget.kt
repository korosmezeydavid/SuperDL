package com.superdl.launcher.locationwatch

sealed class LocationWatchTarget {

    abstract fun debounceKey(): String

    data class ProfileId(val id: String) : LocationWatchTarget() {
        override fun debounceKey(): String = "profile:$id"
    }

    data class FreeText(val text: String) : LocationWatchTarget() {
        override fun debounceKey(): String = "text:${LocationMatcher.normalize(text)}"
    }

    object AllProfiles : LocationWatchTarget() {
        override fun debounceKey(): String = "all_profiles"
    }
}

object LocationWatchState {

    @Volatile
    private var activeTarget: LocationWatchTarget? = null

    fun setActive(target: LocationWatchTarget?) {
        activeTarget = target
    }

    fun getActive(): LocationWatchTarget? = activeTarget

    fun clear() {
        activeTarget = null
    }

    fun isActive(): Boolean = activeTarget != null
}