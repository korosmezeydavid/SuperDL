package com.superdl.launcher.lock.keyguard

import android.accessibilityservice.AccessibilityService
import android.os.Build
import android.util.Log
import android.view.accessibility.AccessibilityNodeInfo

object HotspotAccessibilityHelper {

    private const val TAG = "SuperDL-HotspotA11y"

    private val hotspotLabels = listOf(
        "hotspot",
        "wi-fi hotspot",
        "wifi hotspot",
        "mobil hotspot",
        "mobile hotspot",
        "personal hotspot",
        "internetmegosztás",
        "internetes megosztás",
        "megosztás",
        "tethering",
        "hordozható",
        "wlan hotspot"
    )

    private val enabledHints = listOf(
        "bekapcsolva",
        "be van kapcsolva",
        "enabled",
        "on",
        "aktív",
        "active"
    )

    private val disabledHints = listOf(
        "kikapcsolva",
        "ki van kapcsolva",
        "disabled",
        "off",
        "inaktív",
        "inactive"
    )

    fun toggleViaQuickSettings(service: AccessibilityService, targetEnabled: Boolean): Boolean {
        return try {
            service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_QUICK_SETTINGS)
            sleepInterruptibly(500L)
            val root = service.rootInActiveWindow
            if (root == null) {
                Log.w(TAG, "Quick settings root is null")
                closeQuickSettings(service)
                return false
            }
            val tile = findHotspotTile(root)
            if (tile == null) {
                Log.w(TAG, "Hotspot tile not found in quick settings")
                @Suppress("DEPRECATION")
                root.recycle()
                closeQuickSettings(service)
                return false
            }
            val currentState = readTileEnabled(tile)
            if (currentState == targetEnabled) {
                Log.i(TAG, "Hotspot tile already target=$targetEnabled")
                @Suppress("DEPRECATION")
                tile.recycle()
                @Suppress("DEPRECATION")
                root.recycle()
                closeQuickSettings(service)
                return true
            }
            val clicked = tile.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            @Suppress("DEPRECATION")
            tile.recycle()
            @Suppress("DEPRECATION")
            root.recycle()
            sleepInterruptibly(700L)
            closeQuickSettings(service)
            Log.i(TAG, "Hotspot tile clicked=$clicked target=$targetEnabled previous=$currentState")
            clicked
        } catch (e: Exception) {
            Log.w(TAG, "Hotspot quick-settings toggle failed", e)
            closeQuickSettings(service)
            false
        }
    }

    private fun closeQuickSettings(service: AccessibilityService) {
        service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
        sleepInterruptibly(200L)
        service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
    }

    private fun findHotspotTile(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.add(AccessibilityNodeInfo.obtain(root))
        var best: AccessibilityNodeInfo? = null

        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            if (node.isClickable || node.isCheckable) {
                val haystack = nodeText(node)
                if (hotspotLabels.any { haystack.contains(it) }) {
                    if (best != null) {
                        @Suppress("DEPRECATION")
                        best.recycle()
                    }
                    best = AccessibilityNodeInfo.obtain(node)
                }
            }
            for (index in 0 until node.childCount) {
                node.getChild(index)?.let { queue.add(it) }
            }
            if (best == null || node !== best) {
                @Suppress("DEPRECATION")
                node.recycle()
            }
        }
        return best
    }

    private fun readTileEnabled(node: AccessibilityNodeInfo): Boolean? {
        if (node.isCheckable) return node.isChecked
        val haystack = nodeText(node)
        if (enabledHints.any { haystack.contains(it) }) return true
        if (disabledHints.any { haystack.contains(it) }) return false
        return null
    }

    private fun nodeText(node: AccessibilityNodeInfo): String = buildString {
        node.text?.let { append(it).append(' ') }
        node.contentDescription?.let { append(it).append(' ') }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            node.stateDescription?.let { append(it).append(' ') }
        }
        node.viewIdResourceName?.let { append(it) }
    }.trim().lowercase()

    private fun sleepInterruptibly(delayMs: Long) {
        if (delayMs <= 0L || Thread.currentThread().isInterrupted) return
        try {
            Thread.sleep(delayMs)
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        }
    }
}