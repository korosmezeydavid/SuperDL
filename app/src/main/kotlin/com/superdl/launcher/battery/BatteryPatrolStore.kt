package com.superdl.launcher.battery

import android.content.Context
import com.superdl.launcher.patrol.PatrolStore

object BatteryPatrolStore {

    fun isEnabled(context: Context): Boolean = PatrolStore.isMasterEnabled(context)

    fun setEnabled(context: Context, enabled: Boolean) = PatrolStore.setMasterEnabled(context, enabled)

    fun getLastAlertedThreshold(context: Context): Int = PatrolStore.getLastAlertedThreshold(context)

    fun setLastAlertedThreshold(context: Context, threshold: Int) =
        PatrolStore.setLastAlertedThreshold(context, threshold)

    fun resetAlertState(context: Context) = PatrolStore.resetAlertState(context)
}