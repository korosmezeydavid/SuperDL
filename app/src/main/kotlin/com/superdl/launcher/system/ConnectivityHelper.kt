package com.superdl.launcher.system

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.provider.Settings
import android.util.Log
import androidx.core.content.ContextCompat
import com.superdl.launcher.SuperDlApplication
import com.superdl.launcher.lock.keyguard.AccessibilityAssistBridge
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean


object ConnectivityHelper {

    private val hotspotToggleLock = Any()

    private const val TAG = "SuperDL-Hotspot"
    private const val TETHERING_WIFI = 0
    private const val WIFI_AP_STATE_DISABLED = 11
    private const val WIFI_AP_STATE_ENABLED = 13
    private val HOTSPOT_SYSFS_IFACES = listOf("ap0", "softap0", "swlan0")

    fun isOnline(context: Context): Boolean {
        val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return false
        val network = manager.activeNetwork ?: return false
        val caps = manager.getNetworkCapabilities(network) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    fun isWifiEnabled(context: Context): Boolean {
        return try {
            readWifiEnabledViaWifiManager(context)
        } catch (_: Exception) {
            false
        }
    }

    fun isBluetoothEnabled(context: Context): Boolean =
        try {
            bluetoothAdapter(context)?.isEnabled == true
        } catch (_: Exception) {
            false
        }

    fun wifiStatus(context: Context): String =
        if (isWifiEnabled(context)) "WiFi bekapcsolva." else "WiFi kikapcsolva."

    fun bluetoothStatus(context: Context): String {
        val adapter = bluetoothAdapter(context) ?: return "Bluetooth nem elérhető."
        return if (adapter.isEnabled) "Bluetooth bekapcsolva." else "Bluetooth kikapcsolva."
    }

    fun isHotspotEnabled(context: Context): Boolean {
        return try {
            resolveHotspotEnabled(context)
        } catch (_: Exception) {
            HotspotStateStore.get(context) ?: false
        }
    }

    private fun resolveHotspotEnabled(context: Context): Boolean {
        ensureHiddenApiAccess()
        readHotspotHardwareState(context)?.let {
            HotspotStateStore.set(context, it)
            return it
        }

        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            return readHotspotViaWifiApState(context)
                ?: readHotspotViaWifiManagerIsApEnabled(context)
                ?: HotspotStateStore.get(context)
                ?: false
        }

        if (readHotspotViaWifiApState(context) == false) return false
        if (readHotspotViaWifiManagerIsApEnabled(context) == false) return false

        return HotspotStateStore.get(context) ?: false
    }

    private fun readHotspotHardwareState(context: Context): Boolean? {
        readHotspotViaSettingsKeys(context)?.let { return it }
        readHotspotViaSysfs()?.let { return it }
        readHotspotViaTetheredWifiIface(context)?.let { return it }
        return null
    }

    private fun ensureHiddenApiAccess() {
        SuperDlApplication.ensureHiddenApiAccess()
    }

    fun hotspotStatus(context: Context): String =
        if (isHotspotEnabled(context)) "Hotspot bekapcsolva." else "Hotspot kikapcsolva."

    fun hasNearbyWifiPermission(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return true
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.NEARBY_WIFI_DEVICES
        ) == PackageManager.PERMISSION_GRANTED
    }

    fun toggleWifi(context: Context): ToggleResult {
        val wasEnabled = isWifiEnabled(context)
        val targetEnabled = !wasEnabled

        val wifiManager = wifiManager(context)
            ?: return ToggleResult(
                success = false,
                nowEnabled = wasEnabled,
                failureMessage = "WiFi szolgáltatás nem elérhető ezen az eszközön."
            )

        val ok = setWifiEnabledDirect(wifiManager, targetEnabled)
        val nowEnabled = if (ok) targetEnabled else isWifiEnabled(context)

        return if (ok || nowEnabled == targetEnabled) {
            ToggleResult(success = true, nowEnabled = nowEnabled)
        } else {
            ToggleResult(
                success = false,
                nowEnabled = wasEnabled,
                failureMessage = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    "A WiFi közvetlen kapcsolása nem sikerült ezen az eszközön. " +
                        "Ellenőrizd, hogy a Super DL rendelkezik WiFi módosítási engedéllyel."
                } else {
                    "WiFi kapcsoló nem működött."
                }
            )
        }
    }

    fun toggleHotspot(context: Context, knownWasEnabled: Boolean? = null): ToggleResult = synchronized(hotspotToggleLock) {
        if (!HotspotStateStore.tryBeginToggle()) {
            val current = isHotspotEnabled(context)
            return@synchronized ToggleResult(
                success = false,
                nowEnabled = current,
                failureMessage = "Hotspot kapcsolás folyamatban. Várj egy pillanatot."
            )
        }

        ensureHiddenApiAccess()
        try {
            val wasEnabled = knownWasEnabled
                ?: readHotspotHardwareState(context)
                ?: HotspotStateStore.get(context)
                ?: false
            val targetEnabled = !wasEnabled

            readHotspotHardwareState(context)?.let { hardwareNow ->
                if (hardwareNow == targetEnabled) {
                    HotspotStateStore.set(context, hardwareNow)
                    return@synchronized ToggleResult(success = true, nowEnabled = hardwareNow)
                }
            }

            val commandResult = setHotspotState(context, targetEnabled)
            if (!commandResult.invoked) {
                if (AccessibilityAssistBridge.isServiceRunning()) {
                    val viaA11y = AccessibilityAssistBridge.toggleHotspot(targetEnabled)
                    if (viaA11y) {
                        HotspotStateStore.set(context, targetEnabled)
                        return@synchronized ToggleResult(success = true, nowEnabled = targetEnabled)
                    }
                }
                return@synchronized ToggleResult(
                    success = false,
                    nowEnabled = wasEnabled,
                    failureMessage = when {
                        !hasNearbyWifiPermission(context) ->
                            "A közeli WiFi eszközök engedély szükséges a hotspot-hoz."
                        !AccessibilityAssistBridge.isServiceRunning() ->
                            "Hotspot közvetlen kapcsolása nem sikerült. Kapcsold be a Super DL rendszer PIN segéd szolgáltatást a Kisegítő lehetőségekben."
                        targetEnabled ->
                            "Hotspot közvetlen kapcsolása nem sikerült. Ellenőrizd, hogy a mobilnet be van kapcsolva."
                        else ->
                            "Hotspot kikapcsolása nem sikerült."
                    }
                )
            }

            val detected = readHotspotHardwareAfterToggle(context, targetEnabled)
            val success = detected == targetEnabled || commandResult.confirmed
            val nowEnabled = detected ?: if (success) targetEnabled else wasEnabled
            if (success) {
                HotspotStateStore.set(context, nowEnabled)
            }
            ToggleResult(
                success = success,
                nowEnabled = nowEnabled,
                failureMessage = if (success) {
                    null
                } else if (targetEnabled) {
                    "Hotspot bekapcsolása nem sikerült."
                } else {
                    "Hotspot kikapcsolása nem sikerült."
                }
            )
        } finally {
            HotspotStateStore.endToggle()
        }
    }

    private data class HotspotCommandResult(
        val invoked: Boolean,
        val confirmed: Boolean = false
    )

    private fun setHotspotState(context: Context, enabled: Boolean): HotspotCommandResult {
        return if (enabled) {
            startHotspot(context)
        } else {
            stopHotspot(context)
        }
    }

    private fun startHotspot(context: Context): HotspotCommandResult {
        if (readHotspotHardwareState(context) == true) {
            HotspotStateStore.set(context, true)
            return HotspotCommandResult(invoked = true, confirmed = true)
        }

        prepareRadioForHotspot(context)

        val attempts = buildList {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                add { startHotspotViaTetheringRequest(context) }
                add { startHotspotViaTetheringManager(context) }
                add { startHotspotViaWifiManager(context) }
            }
            add { startHotspotViaWifiApReflection(context) }
            connectivityManager(context)?.let { manager ->
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    add { startHotspotViaConnectivityManager(context, manager) }
                }
            }
            add { startHotspotViaSettingsGlobal(context) }
            add { startHotspotViaOemKeys(context, true) }
        }

        var anyInvoked = false
        for (attempt in attempts) {
            val result = attempt()
            if (result.invoked) anyInvoked = true
            if (result.confirmed) {
                HotspotStateStore.set(context, true)
                return result
            }
            if (readHotspotHardwareState(context) == true) {
                HotspotStateStore.set(context, true)
                return HotspotCommandResult(invoked = true, confirmed = true)
            }
        }

        if (AccessibilityAssistBridge.isServiceRunning()) {
            val viaA11y = AccessibilityAssistBridge.toggleHotspot(targetEnabled = true)
            if (viaA11y || readHotspotHardwareState(context) == true) {
                HotspotStateStore.set(context, true)
                return HotspotCommandResult(invoked = true, confirmed = true)
            }
        }

        Log.w(TAG, "All hotspot start paths failed (invoked=$anyInvoked)")
        return HotspotCommandResult(invoked = anyInvoked, confirmed = false)
    }

    private fun stopHotspot(context: Context): HotspotCommandResult {
        if (readHotspotHardwareState(context) == false) {
            HotspotStateStore.set(context, false)
            return HotspotCommandResult(invoked = true, confirmed = true)
        }

        var invoked = false
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            invoked = stopHotspotViaWifiManager(context) || invoked
            invoked = stopHotspotViaTetheringManager(context) || invoked
        }
        connectivityManager(context)?.let { manager ->
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                invoked = stopHotspotViaConnectivityManager(manager) || invoked
            }
        }
        invoked = startHotspotViaWifiApReflection(context, enable = false).invoked || invoked
        invoked = stopHotspotViaSettingsGlobal(context) || invoked
        invoked = startHotspotViaOemKeys(context, false).invoked || invoked

        waitForHotspotHardwareState(context, false, attempts = 14, sleepMs = 400L)
        var detected = readHotspotHardwareState(context)
        if (detected == false) {
            HotspotStateStore.set(context, false)
            return HotspotCommandResult(invoked = invoked, confirmed = true)
        }

        if (AccessibilityAssistBridge.isServiceRunning()) {
            val viaA11y = AccessibilityAssistBridge.toggleHotspot(targetEnabled = false)
            detected = readHotspotHardwareState(context)
            if (viaA11y || detected == false) {
                HotspotStateStore.set(context, false)
                return HotspotCommandResult(invoked = true, confirmed = true)
            }
        }

        return HotspotCommandResult(invoked = invoked, confirmed = false)
    }

    private fun startHotspotViaSettingsGlobal(context: Context): HotspotCommandResult {
        return try {
            val resolver = context.contentResolver
            Settings.Global.putInt(resolver, "soft_ap_wifi_enabled", 1)
            Log.i(TAG, "Settings.Global soft_ap_wifi_enabled=1")
            waitForHotspotHardwareState(context, true, attempts = 10, sleepMs = 400L)
            when (readHotspotHardwareState(context)) {
                true -> {
                    HotspotStateStore.set(context, true)
                    HotspotCommandResult(invoked = true, confirmed = true)
                }
                else -> HotspotCommandResult(invoked = true, confirmed = false)
            }
        } catch (e: Exception) {
            Log.w(TAG, "Settings.Global hotspot enable failed", e)
            HotspotCommandResult(invoked = false)
        }
    }

    private fun stopHotspotViaSettingsGlobal(context: Context): Boolean {
        return try {
            Settings.Global.putInt(context.contentResolver, "soft_ap_wifi_enabled", 0)
            Log.i(TAG, "Settings.Global soft_ap_wifi_enabled=0")
            true
        } catch (e: Exception) {
            Log.w(TAG, "Settings.Global hotspot disable failed", e)
            false
        }
    }

    fun openHotspotSettings(context: Context): Boolean {
        val intents = listOf(
            Intent("android.settings.TETHER_SETTINGS"),
            Intent("android.settings.TETHER_WIFI_SETTINGS"),
            Intent(Settings.ACTION_WIRELESS_SETTINGS),
            Intent(Settings.ACTION_WIFI_SETTINGS)
        )
        for (intent in intents) {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            if (intent.resolveActivity(context.packageManager) != null) {
                return try {
                    context.startActivity(intent)
                    true
                } catch (_: Exception) {
                    false
                }
            }
        }
        return false
    }

    fun toggleBluetooth(context: Context): ToggleResult {
        val adapter = bluetoothAdapter(context)
            ?: return ToggleResult(success = false, nowEnabled = false, failureMessage = "Bluetooth nem elérhető ezen az eszközön.")

        return try {
            if (adapter.isEnabled) {
                @Suppress("DEPRECATION")
                adapter.disable()
                ToggleResult(success = true, nowEnabled = false)
            } else {
                @Suppress("DEPRECATION")
                adapter.enable()
                ToggleResult(success = true, nowEnabled = true)
            }
        } catch (_: SecurityException) {
            ToggleResult(
                success = false,
                nowEnabled = adapter.isEnabled,
                failureMessage = "Bluetooth engedély szükséges. " +
                    "Engedélyezd a Beállítások, Alkalmazások, Super DL, Engedélyek menüben a közeli eszközöket."
            )
        }
    }

    data class ToggleResult(
        val success: Boolean,
        val nowEnabled: Boolean,
        val failureMessage: String? = null,
        val openedPanel: Boolean = false
    )

    @Suppress("DEPRECATION")
    private fun setWifiEnabledDirect(wifiManager: WifiManager, enabled: Boolean): Boolean {
        return try {
            wifiManager.isWifiEnabled = enabled
            true
        } catch (_: Exception) {
            try {
                wifiManager.setWifiEnabled(enabled)
            } catch (_: Exception) {
                false
            }
        }
    }

    private fun wifiManager(context: Context): WifiManager? =
        context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager

    @Suppress("DEPRECATION")
    private fun readWifiEnabledViaWifiManager(context: Context): Boolean {
        val wifiManager = wifiManager(context) ?: return false
        return wifiManager.isWifiEnabled
    }

    private fun connectivityManager(context: Context): ConnectivityManager? =
        context.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager

    private fun readHotspotViaSysfs(): Boolean? {
        var sawIface = false
        for (iface in HOTSPOT_SYSFS_IFACES) {
            val operState = readIfaceOperState(iface) ?: continue
            sawIface = true
            if (operState == "up") return true
        }
        return if (sawIface) false else null
    }

    private fun readIfaceOperState(iface: String): String? {
        return try {
            File("/sys/class/net/$iface/operstate").readText().trim().lowercase()
        } catch (_: Exception) {
            null
        }
    }

    private fun readHotspotViaSettingsKeys(context: Context): Boolean? {
        val resolver = context.contentResolver
        readSettingsGlobalInt(resolver, "wifi_ap_state")?.let { return apStateToBoolean(it) }
        readSettingsSecureInt(resolver, "wifi_ap_state")?.let { return apStateToBoolean(it) }
        readSettingsGlobalInt(resolver, "soft_ap_wifi_enabled")?.let { return it == 1 }
        readSettingsGlobalInt(resolver, "wifi_hotspot_state")?.let { return it == 1 }
        readSettingsSecureInt(resolver, "wifi_ap_enabled")?.let { return it == 1 }
        return null
    }

    private fun readSettingsGlobalInt(
        resolver: android.content.ContentResolver,
        key: String
    ): Int? {
        return try {
            Settings.Global.getInt(resolver, key)
        } catch (_: Settings.SettingNotFoundException) {
            null
        } catch (_: Exception) {
            null
        }
    }

    private fun readSettingsSecureInt(
        resolver: android.content.ContentResolver,
        key: String
    ): Int? {
        return try {
            Settings.Secure.getInt(resolver, key)
        } catch (_: Settings.SettingNotFoundException) {
            null
        } catch (_: Exception) {
            null
        }
    }

    private fun apStateToBoolean(state: Int): Boolean? = when (state) {
        WIFI_AP_STATE_ENABLED -> true
        WIFI_AP_STATE_DISABLED -> false
        1 -> true
        0 -> false
        else -> null
    }

    @Suppress("DiscouragedPrivateApi")
    private fun readHotspotViaWifiApState(context: Context): Boolean? {
        val wifiManager = wifiManager(context) ?: return null
        return try {
            val method = wifiManager.javaClass.getMethod("getWifiApState")
            when (val state = method.invoke(wifiManager) as? Int) {
                WIFI_AP_STATE_ENABLED -> true
                WIFI_AP_STATE_DISABLED -> false
                else -> null
            }
        } catch (_: Exception) {
            null
        }
    }

    @Suppress("DiscouragedPrivateApi")
    private fun readHotspotViaWifiManagerIsApEnabled(context: Context): Boolean? {
        val wifiManager = wifiManager(context) ?: return null
        return try {
            val method = wifiManager.javaClass.getMethod("isWifiApEnabled")
            method.invoke(wifiManager) as? Boolean
        } catch (_: Exception) {
            null
        }
    }

    @Suppress("DiscouragedPrivateApi")
    private fun readHotspotViaTetheredWifiIface(context: Context): Boolean? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return null
        val manager = connectivityManager(context) ?: return null
        return try {
            val method = manager.javaClass.getMethod("getTetheredIfaces")
            val raw = method.invoke(manager) as? Array<*> ?: return false
            raw.any { iface ->
                val name = iface?.toString()?.lowercase().orEmpty()
                isWifiHotspotIface(name)
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun isWifiHotspotIface(name: String): Boolean {
        if (name.isBlank()) return false
        if (name.contains("rndis") || name.contains("usb") ||
            name.contains("bt-pan") || name.contains("bluetooth") || name.contains("pan")
        ) {
            return false
        }
        if (name.matches(Regex("wlan\\d*"))) return false
        return name.matches(Regex("ap\\d*")) || name.contains("softap") || name.contains("swlan")
    }

    private fun readHotspotHardwareAfterToggle(context: Context, targetEnabled: Boolean): Boolean? {
        val attempts = if (targetEnabled) 16 else 14
        val sleepMs = if (targetEnabled) 450L else 400L
        return waitForHotspotHardwareState(context, targetEnabled, attempts, sleepMs)
    }

    private fun waitForHotspotHardwareState(
        context: Context,
        targetEnabled: Boolean,
        attempts: Int,
        sleepMs: Long
    ): Boolean? {
        var last: Boolean? = null
        for (attempt in 0 until attempts) {
            last = readHotspotHardwareState(context)
            if (last == targetEnabled) return last
            if (attempt < attempts - 1) {
                try {
                    Thread.sleep(sleepMs)
                } catch (_: InterruptedException) {
                    Thread.currentThread().interrupt()
                    return readHotspotHardwareState(context)
                }
            }
        }
        return last
    }

    private fun prepareRadioForHotspot(context: Context) {
        val manager = wifiManager(context) ?: return
        try {
            if (!isWifiEnabled(context)) {
                setWifiEnabledDirect(manager, true)
                Thread.sleep(500)
            }
        } catch (e: Exception) {
            Log.w(TAG, "Radio prepare before hotspot failed", e)
        }
    }

    @Suppress("DiscouragedPrivateApi")
    private fun resolveSoftApConfiguration(context: Context): Any? {
        val manager = wifiManager(context) ?: return null
        try {
            val existing = manager.javaClass.getMethod("getSoftApConfiguration").invoke(manager)
            if (existing != null) return existing
        } catch (_: Exception) {
        }
        return buildFallbackSoftApConfiguration()
    }

    @Suppress("DiscouragedPrivateApi")
    private fun buildFallbackSoftApConfiguration(): Any? {
        return try {
            val builderClass = Class.forName("android.net.wifi.SoftApConfiguration\$Builder")
            val builder = builderClass.getConstructor().newInstance()
            val securityWpa2 = 1
            builderClass.getMethod("setPassphrase", String::class.java, Int::class.javaPrimitiveType)
                .invoke(builder, "SuperDL1234", securityWpa2)
            builderClass.getMethod("setSsid", String::class.java)
                .invoke(builder, "SuperDL_Hotspot")
            builderClass.getMethod("build").invoke(builder)
        } catch (e: Exception) {
            Log.w(TAG, "Fallback SoftApConfiguration build failed", e)
            null
        }
    }

    @Suppress("DiscouragedPrivateApi")
    private fun startHotspotViaTetheringRequest(context: Context): HotspotCommandResult {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) {
            return HotspotCommandResult(invoked = false)
        }
        val latch = CountDownLatch(1)
        val started = AtomicBoolean(false)
        val failed = AtomicBoolean(false)
        return try {
            val tetheringManager = context.getSystemService("tethering")
                ?: return HotspotCommandResult(invoked = false)
            val callbackClass = Class.forName("android.net.TetheringManager\$StartTetheringCallback")
            val callback = java.lang.reflect.Proxy.newProxyInstance(
                callbackClass.classLoader,
                arrayOf(callbackClass)
            ) { _, method, _ ->
                when (method.name) {
                    "onTetheringStarted" -> {
                        started.set(true)
                        latch.countDown()
                    }
                    "onTetheringFailed" -> {
                        failed.set(true)
                        latch.countDown()
                    }
                }
                null
            }
            val requestBuilderClass = Class.forName("android.net.TetheringManager\$TetheringRequest\$Builder")
            val requestBuilder = requestBuilderClass.getConstructor(Int::class.javaPrimitiveType)
                .newInstance(TETHERING_WIFI)
            try {
                requestBuilderClass.getMethod("setShouldShowEntitlementUi", Boolean::class.javaPrimitiveType)
                    .invoke(requestBuilder, false)
            } catch (_: Exception) {
            }
            val request = requestBuilderClass.getMethod("build").invoke(requestBuilder)
            val requestClass = Class.forName("android.net.TetheringManager\$TetheringRequest")
            val executor = java.util.concurrent.Executor { command ->
                Thread(command, "SuperDL-HotspotReq").start()
            }
            val startMethod = tetheringManager.javaClass.getMethod(
                "startTethering",
                requestClass,
                java.util.concurrent.Executor::class.java,
                callbackClass
            )
            startMethod.invoke(tetheringManager, request, executor, callback)
            Log.i(TAG, "TetheringRequest.startTethering invoked")
            latch.await(14, TimeUnit.SECONDS)
            waitForHotspotHardwareState(context, true, attempts = 6, sleepMs = 400L)
            when {
                started.get() -> HotspotCommandResult(invoked = true, confirmed = true)
                readHotspotHardwareState(context) == true ->
                    HotspotCommandResult(invoked = true, confirmed = true)
                failed.get() -> HotspotCommandResult(invoked = true, confirmed = false)
                else -> HotspotCommandResult(invoked = true, confirmed = false)
            }
        } catch (e: Exception) {
            Log.w(TAG, "TetheringRequest.startTethering failed", e)
            HotspotCommandResult(invoked = false)
        }
    }

    @Suppress("DiscouragedPrivateApi")
    private fun startHotspotViaWifiApReflection(context: Context, enable: Boolean = true): HotspotCommandResult {
        val wifiManager = wifiManager(context) ?: return HotspotCommandResult(invoked = false)
        return try {
            if (enable) {
                val softApConfig = resolveSoftApConfiguration(context)
                if (softApConfig != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    val configClass = Class.forName("android.net.wifi.SoftApConfiguration")
                    val startMethod = wifiManager.javaClass.getMethod("startTetheredHotspot", configClass)
                    startMethod.invoke(wifiManager, softApConfig)
                    Log.i(TAG, "startTetheredHotspot with config invoked")
                    waitForHotspotHardwareState(context, true, attempts = 12, sleepMs = 400L)
                    if (readHotspotHardwareState(context) == true) {
                        return HotspotCommandResult(invoked = true, confirmed = true)
                    }
                    return HotspotCommandResult(invoked = true, confirmed = false)
                }
            }
            val legacyConfig = try {
                wifiManager.javaClass.getMethod("getWifiApConfiguration").invoke(wifiManager)
            } catch (_: Exception) {
                null
            }
            val setMethod = wifiManager.javaClass.getMethod(
                "setWifiApEnabled",
                android.net.wifi.WifiConfiguration::class.java,
                Boolean::class.javaPrimitiveType
            )
            val ok = setMethod.invoke(wifiManager, legacyConfig, enable) as? Boolean ?: false
            Log.i(TAG, "setWifiApEnabled($enable) -> $ok")
            if (ok) {
                waitForHotspotHardwareState(context, enable, attempts = 12, sleepMs = 400L)
                val detected = readHotspotHardwareState(context)
                if (detected == enable) {
                    return HotspotCommandResult(invoked = true, confirmed = true)
                }
            }
            HotspotCommandResult(invoked = ok, confirmed = readHotspotHardwareState(context) == enable)
        } catch (e: Exception) {
            Log.w(TAG, "startHotspotViaWifiApReflection failed (enable=$enable)", e)
            HotspotCommandResult(invoked = false)
        }
    }

    private fun startHotspotViaOemKeys(context: Context, enabled: Boolean): HotspotCommandResult {
        val resolver = context.contentResolver
        val keys = listOf(
            "soft_ap_wifi_enabled",
            "wifi_hotspot_state",
            "wifi_hotspot_on",
            "wifi_tethering_on",
            "wifi_ap_state"
        )
        var invoked = false
        for (key in keys) {
            try {
                Settings.Global.putInt(resolver, key, if (enabled) 1 else 0)
                invoked = true
                Log.i(TAG, "Settings.Global $key=${if (enabled) 1 else 0}")
            } catch (_: Exception) {
            }
            try {
                Settings.Secure.putInt(resolver, key, if (enabled) 1 else 0)
                invoked = true
            } catch (_: Exception) {
            }
        }
        if (!invoked) return HotspotCommandResult(invoked = false)
        waitForHotspotHardwareState(context, enabled, attempts = 10, sleepMs = 400L)
        val detected = readHotspotHardwareState(context)
        return HotspotCommandResult(
            invoked = true,
            confirmed = detected == enabled
        )
    }

    @Suppress("DiscouragedPrivateApi")
    private fun startHotspotViaWifiManager(context: Context): HotspotCommandResult =
        startHotspotViaWifiApReflection(context, enable = true)

    @Suppress("DiscouragedPrivateApi")
    private fun stopHotspotViaWifiManager(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return false
        return try {
            val manager = wifiManager(context) ?: return false
            val stopMethod = manager.javaClass.getMethod("stopSoftAp")
            stopMethod.invoke(manager)
            Log.i(TAG, "stopSoftAp invoked")
            true
        } catch (e: Exception) {
            Log.w(TAG, "stopSoftAp failed", e)
            false
        }
    }

    @Suppress("DiscouragedPrivateApi")
    private fun startHotspotViaConnectivityManager(
        context: Context,
        manager: ConnectivityManager
    ): HotspotCommandResult {
        val callbackThread = HandlerThread("SuperDL-HotspotCb")
        callbackThread.start()
        return try {
            val callbackClass = Class.forName("android.net.ConnectivityManager\$OnStartTetheringCallback")
            val latch = CountDownLatch(1)
            val started = AtomicBoolean(false)
            val failed = AtomicBoolean(false)
            val callback = java.lang.reflect.Proxy.newProxyInstance(
                callbackClass.classLoader,
                arrayOf(callbackClass)
            ) { _, method, _ ->
                when (method.name) {
                    "onTetheringStarted" -> {
                        started.set(true)
                        HotspotStateStore.set(context, true)
                        latch.countDown()
                    }
                    "onTetheringFailed" -> {
                        failed.set(true)
                        latch.countDown()
                    }
                }
                null
            }
            val startMethod = manager.javaClass.getMethod(
                "startTethering",
                Int::class.javaPrimitiveType,
                Boolean::class.javaPrimitiveType,
                callbackClass,
                Handler::class.java
            )
            startMethod.invoke(
                manager,
                TETHERING_WIFI,
                false,
                callback,
                Handler(callbackThread.looper)
            )
            Log.i(TAG, "ConnectivityManager.startTethering invoked")
            latch.await(12, TimeUnit.SECONDS)
            when {
                started.get() -> HotspotCommandResult(invoked = true, confirmed = true)
                failed.get() -> HotspotCommandResult(invoked = true, confirmed = false)
                readHotspotHardwareState(context) == true ->
                    HotspotCommandResult(invoked = true, confirmed = true)
                else -> HotspotCommandResult(invoked = true, confirmed = false)
            }
        } catch (e: Exception) {
            Log.w(TAG, "ConnectivityManager.startTethering failed", e)
            HotspotCommandResult(invoked = false)
        } finally {
            callbackThread.quitSafely()
        }
    }

    @Suppress("DiscouragedPrivateApi")
    private fun startHotspotViaTetheringManager(context: Context): HotspotCommandResult {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) {
            return HotspotCommandResult(invoked = false)
        }
        val latch = CountDownLatch(1)
        val started = AtomicBoolean(false)
        val failed = AtomicBoolean(false)
        return try {
            val tetheringManager = context.getSystemService("tethering")
                ?: return HotspotCommandResult(invoked = false)
            val callbackClass = Class.forName("android.net.TetheringManager\$StartTetheringCallback")
            val callback = java.lang.reflect.Proxy.newProxyInstance(
                callbackClass.classLoader,
                arrayOf(callbackClass)
            ) { _, method, _ ->
                when (method.name) {
                    "onTetheringStarted" -> {
                        started.set(true)
                        HotspotStateStore.set(context, true)
                        latch.countDown()
                    }
                    "onTetheringFailed" -> {
                        failed.set(true)
                        Log.w(TAG, "TetheringManager onTetheringFailed")
                        latch.countDown()
                    }
                }
                null
            }
            val executor = java.util.concurrent.Executor { command ->
                Thread(command, "SuperDL-HotspotStart").start()
            }
            val invoked = try {
                val startMethod = tetheringManager.javaClass.getMethod(
                    "startTethering",
                    Int::class.javaPrimitiveType,
                    java.util.concurrent.Executor::class.java,
                    callbackClass
                )
                startMethod.invoke(tetheringManager, TETHERING_WIFI, executor, callback)
                true
            } catch (first: Exception) {
                Log.w(TAG, "TetheringManager.startTethering(3-arg) failed", first)
                try {
                    val startMethod = tetheringManager.javaClass.getMethod(
                        "startTethering",
                        Int::class.javaPrimitiveType,
                        Boolean::class.javaPrimitiveType,
                        java.util.concurrent.Executor::class.java,
                        callbackClass
                    )
                    startMethod.invoke(tetheringManager, TETHERING_WIFI, false, executor, callback)
                    true
                } catch (second: Exception) {
                    Log.w(TAG, "TetheringManager.startTethering(4-arg) failed", second)
                    false
                }
            }
            if (!invoked) return HotspotCommandResult(invoked = false)
            Log.i(TAG, "TetheringManager.startTethering invoked")
            latch.await(12, TimeUnit.SECONDS)
            when {
                started.get() -> HotspotCommandResult(invoked = true, confirmed = true)
                failed.get() -> HotspotCommandResult(invoked = true, confirmed = false)
                readHotspotHardwareState(context) == true ->
                    HotspotCommandResult(invoked = true, confirmed = true)
                else -> HotspotCommandResult(invoked = true, confirmed = false)
            }
        } catch (e: Exception) {
            Log.w(TAG, "TetheringManager hotspot start failed", e)
            HotspotCommandResult(invoked = false)
        }
    }

    @Suppress("DiscouragedPrivateApi")
    private fun stopHotspotViaTetheringManager(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return false
        return try {
            val tetheringManager = context.getSystemService("tethering") ?: return false
            val stopMethod = tetheringManager.javaClass.getMethod(
                "stopTethering",
                Int::class.javaPrimitiveType
            )
            stopMethod.invoke(tetheringManager, TETHERING_WIFI)
            Log.i(TAG, "TetheringManager.stopTethering invoked")
            true
        } catch (e: Exception) {
            Log.w(TAG, "TetheringManager.stopTethering failed", e)
            false
        }
    }

    @Suppress("DiscouragedPrivateApi")
    private fun stopHotspotViaConnectivityManager(manager: ConnectivityManager): Boolean {
        return try {
            val stopMethod = manager.javaClass.getMethod("stopTethering", Int::class.javaPrimitiveType)
            stopMethod.invoke(manager, TETHERING_WIFI)
            Log.i(TAG, "ConnectivityManager.stopTethering invoked")
            true
        } catch (e: Exception) {
            Log.w(TAG, "ConnectivityManager.stopTethering failed", e)
            false
        }
    }

    private fun bluetoothAdapter(context: Context): BluetoothAdapter? {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            context.getSystemService(BluetoothManager::class.java)?.adapter
        } else {
            @Suppress("DEPRECATION")
            BluetoothAdapter.getDefaultAdapter()
        }
    }
}