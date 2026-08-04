package com.superdl.launcher.feedback

import android.content.Context
import com.superdl.launcher.battery.BatteryPatrolManager
import com.superdl.launcher.callfilter.CallFilterStore
import com.superdl.launcher.menu.MenuAction
import com.superdl.launcher.patrol.PatrolStore
import com.superdl.launcher.security.LockPinStore
import com.superdl.launcher.system.ConnectivityHelper
import com.superdl.launcher.tools.FlashlightState

object ToggleAnnouncement {

    private data class ToggleSpec(
        val label: String,
        val isEnabled: (Context) -> Boolean
    )

    private val specs: Map<MenuAction, ToggleSpec> = mapOf(
        MenuAction.BATTERY_PATROL_TOGGLE to ToggleSpec("Teljes őrség") { BatteryPatrolManager.isEnabled(it) },
        MenuAction.PATROL_BATTERY_TOGGLE to ToggleSpec("Akkumulátor figyelés") { PatrolStore.isBatteryEnabled(it) },
        MenuAction.PATROL_CALL_ALERT_TOGGLE to ToggleSpec("Hívás értesítés") { PatrolStore.isCallAlertEnabled(it) },
        MenuAction.PATROL_SMS_ALERT_TOGGLE to ToggleSpec("Üzenet értesítés") { PatrolStore.isSmsAlertEnabled(it) },
        MenuAction.PATROL_NOTIFICATION_ALERT_TOGGLE to ToggleSpec("Egyéb értesítés") {
            PatrolStore.isNotificationAlertEnabled(it)
        },
        MenuAction.PATROL_TIME_ANNOUNCE_TOGGLE to ToggleSpec("Idő bemondás") { PatrolStore.isTimeAnnounceEnabled(it) },
        MenuAction.PATROL_NIGHT_MODE_TOGGLE to ToggleSpec("Éjszakai csend") { PatrolStore.isNightModeEnabled(it) },
        MenuAction.PATROL_POWER_BUTTON_TIME_TOGGLE to ToggleSpec("Bekapcsoló gomb idő bemondás") {
            PatrolStore.isPowerButtonTimeEnabled(it)
        },
        MenuAction.WIFI_TOGGLE to ToggleSpec("WiFi") { ConnectivityHelper.isWifiEnabled(it) },
        MenuAction.HOTSPOT_TOGGLE to ToggleSpec("Hotspot") { ConnectivityHelper.isHotspotEnabled(it) },
        MenuAction.BT_TOGGLE to ToggleSpec("Bluetooth") { ConnectivityHelper.isBluetoothEnabled(it) },
        MenuAction.LOCK_PIN_TOGGLE to ToggleSpec("PIN zárolás") { LockPinStore.isEnabled(it) },
        MenuAction.CALL_FILTER_BLOCK_PRIVATE_TOGGLE to ToggleSpec("Rejtett számok tiltása") {
            CallFilterStore.isBlockPrivateEnabled(it)
        },
        MenuAction.FLASHLIGHT to ToggleSpec("Zseblámpa") { FlashlightState.isOn }
    )

    fun isToggle(action: MenuAction): Boolean = action in specs

    fun speakFocused(context: Context, itemLabel: String, action: MenuAction): String {
        val spec = specs[action] ?: return itemLabel
        val state = runCatching { spec.isEnabled(context) }.getOrDefault(false)
        return "$itemLabel. ${speakFocusedState(spec.label, state)}"
    }

    fun speakFocusedState(label: String, enabled: Boolean): String =
        "$label jelenleg ${stateWord(enabled)}."

    fun speakBeforeToggle(context: Context, action: MenuAction): String? {
        val spec = specs[action] ?: return null
        val enabled = spec.isEnabled(context)
        return "${spec.label} jelenleg ${stateWord(enabled)}. ${actionWord(enabled)}"
    }

    fun speakBinaryToggle(label: String, currentlyEnabled: Boolean): String =
        "$label jelenleg ${stateWord(currentlyEnabled)}. ${actionWord(currentlyEnabled)}"

    fun speakAfterToggle(label: String, nowEnabled: Boolean, extra: String = ""): String {
        val suffix = if (extra.isBlank()) {
            if (nowEnabled) "Bekapcsolva." else "Kikapcsolva."
        } else {
            extra
        }
        return "$label jelenleg ${stateWord(nowEnabled)}. $suffix"
    }

    private fun stateWord(enabled: Boolean): String = if (enabled) "BEKAPCSOLVA" else "KIKAPCSOLVA"

    private fun actionWord(currentlyEnabled: Boolean): String =
        if (currentlyEnabled) "Kikapcsolás." else "Bekapcsolás."
}