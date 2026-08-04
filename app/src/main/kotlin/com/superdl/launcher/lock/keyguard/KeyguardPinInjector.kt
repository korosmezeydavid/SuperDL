package com.superdl.launcher.lock.keyguard

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.accessibility.AccessibilityNodeInfo
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

object KeyguardPinInjector {

    private const val TAG = "SuperDL-PinInject"

    private val confirmTokens = listOf(
        "enter",
        "ok",
        "done",
        "confirm",
        "check",
        "megerősítés",
        "mehet",
        "kész",
        "beküldés",
        "feloldás",
        "unlock"
    )

    private val deleteTokens = listOf(
        "delete",
        "backspace",
        "clear",
        "törlés",
        "torles",
        "remove"
    )

    private val pinRevealTokens = listOf(
        "pin",
        "jelszó",
        "jelszo",
        "password",
        "passcode",
        "számkód",
        "szamkod",
        "számkó",
        "szamko",
        "emergency",
        "sürgősségi",
        "surgossegi",
        "lock_icon",
        "feloldás",
        "feloldas"
    )

    fun hasPinBouncerPublic(root: AccessibilityNodeInfo?): Boolean =
        root != null && hasPinBouncer(root)

    fun countAvailableDigits(root: AccessibilityNodeInfo?): Int {
        if (root == null) return 0
        val digits = mutableSetOf<Char>()
        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.add(AccessibilityNodeInfo.obtain(root))
        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            if (isDigitKeyNode(node)) {
                KeyguardPinDetector.extractDigit(node)?.let { digits.add(it) }
            }
            for (index in 0 until node.childCount) {
                node.getChild(index)?.let { queue.add(it) }
            }
            @Suppress("DEPRECATION")
            node.recycle()
        }
        return digits.size
    }

    fun revealPinBouncer(service: AccessibilityService, root: AccessibilityNodeInfo?): Boolean {
        if (root == null) return false
        if (hasPinBouncer(root) || countAvailableDigits(root) >= 4) return true

        Log.i(TAG, "PIN bouncer not visible, trying to reveal. pkg=${root.packageName}")

        findNodeByViewIdSuffix(root, "lock_icon_view")?.let { node ->
            clickNode(service, node)
            @Suppress("DEPRECATION")
            node.recycle()
            sleepInterruptibly(450L)
            return true
        }

        findActionNode(root, pinRevealTokens)?.let { node ->
            clickNode(service, node)
            @Suppress("DEPRECATION")
            node.recycle()
            sleepInterruptibly(450L)
            return true
        }

        val metrics = service.resources.displayMetrics
        val centerX = metrics.widthPixels / 2f
        dispatchSwipe(
            service,
            centerX,
            metrics.heightPixels * 0.9f,
            centerX,
            metrics.heightPixels * 0.52f,
            durationMs = 420L
        )
        sleepInterruptibly(500L)
        return true
    }

    fun clickDigit(service: AccessibilityService, root: AccessibilityNodeInfo?, digit: Char): Boolean {
        if (root == null) return false

        findNodeByViewIdSuffix(root, "key$digit")?.let { node ->
            val clicked = clickNode(service, node)
            @Suppress("DEPRECATION")
            node.recycle()
            if (clicked) {
                Log.i(TAG, "Digit clicked via key$digit")
                return true
            }
        }

        findDigitNode(root, digit)?.let { node ->
            val clicked = clickNode(service, node)
            @Suppress("DEPRECATION")
            node.recycle()
            if (clicked) {
                Log.i(TAG, "Digit clicked via tree search: $digit")
                return true
            }
            Log.w(TAG, "Digit click failed: $digit")
        }

        Log.w(
            TAG,
            "Digit node not found: $digit pkg=${root.packageName} visibleDigits=${countAvailableDigits(root)}"
        )
        logClickableSummary(root)
        return tapDigitCoordinate(service, digit)
    }

    fun clickConfirm(service: AccessibilityService, root: AccessibilityNodeInfo?): Boolean {
        if (root == null) return false
        findNodeByViewIdSuffix(root, "key_enter")?.let { node ->
            val clicked = clickNode(service, node)
            @Suppress("DEPRECATION")
            node.recycle()
            if (clicked) return true
        }
        return findActionNode(root, confirmTokens)?.let { node ->
            val clicked = clickNode(service, node)
            @Suppress("DEPRECATION")
            node.recycle()
            clicked
        } ?: false
    }

    fun clickDelete(service: AccessibilityService, root: AccessibilityNodeInfo?): Boolean {
        if (root == null) return false
        findNodeByViewIdSuffix(root, "delete_button")?.let { node ->
            val clicked = clickNode(service, node)
            @Suppress("DEPRECATION")
            node.recycle()
            if (clicked) return true
        }
        return findActionNode(root, deleteTokens)?.let { node ->
            val clicked = clickNode(service, node)
            @Suppress("DEPRECATION")
            node.recycle()
            clicked
        } ?: false
    }

    fun appendDigitToPasswordField(root: AccessibilityNodeInfo?, digit: Char): Boolean {
        if (root == null) return false
        val field = findPasswordField(root) ?: return false
        field.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
        field.performAction(AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS)
        field.performAction(AccessibilityNodeInfo.ACTION_CLICK)

        val current = field.text?.toString().orEmpty()
        val args = Bundle().apply {
            putCharSequence(
                AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,
                current + digit
            )
        }
        val set = field.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
        @Suppress("DEPRECATION")
        field.recycle()
        return set
    }

    fun findKeyguardRoot(service: AccessibilityService): AccessibilityNodeInfo? {
        if (!KeyguardPinDetector.isKeyguardLocked(service)) return null
        val ownPackage = service.packageName

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            var systemUiFallback: AccessibilityNodeInfo? = null
            service.windows?.forEach { window ->
                val root = window.root ?: return@forEach
                try {
                    val pkg = root.packageName?.toString().orEmpty()
                    if (pkg == ownPackage) return@forEach

                    if (hasPinBouncer(root)) {
                        systemUiFallback?.let {
                            @Suppress("DEPRECATION")
                            it.recycle()
                        }
                        Log.i(TAG, "Found PIN bouncer window pkg=$pkg")
                        return AccessibilityNodeInfo.obtain(root)
                    }

                    if (KeyguardPinDetector.isSystemUiPackage(pkg) && systemUiFallback == null) {
                        systemUiFallback = AccessibilityNodeInfo.obtain(root)
                    }

                    val pinField = KeyguardPinDetector.findPinInputField(root)
                    if (pinField != null) {
                        @Suppress("DEPRECATION")
                        pinField.recycle()
                        systemUiFallback?.let {
                            @Suppress("DEPRECATION")
                            it.recycle()
                        }
                        systemUiFallback = AccessibilityNodeInfo.obtain(root)
                    }
                } finally {
                    @Suppress("DEPRECATION")
                    root.recycle()
                }
            }
            systemUiFallback?.let { return it }
        }

        val active = service.rootInActiveWindow ?: return null
        val activePkg = active.packageName?.toString().orEmpty()
        if (activePkg == ownPackage) {
            @Suppress("DEPRECATION")
            active.recycle()
            return null
        }

        val activePinField = KeyguardPinDetector.findPinInputField(active)
        if (KeyguardPinDetector.isSystemUiPackage(active.packageName) || activePinField != null) {
            activePinField?.let {
                @Suppress("DEPRECATION")
                it.recycle()
            }
            return AccessibilityNodeInfo.obtain(active)
        }
        if (KeyguardPinDetector.isKeyguardLocked(service)) {
            return AccessibilityNodeInfo.obtain(active)
        }
        @Suppress("DEPRECATION")
        active.recycle()
        return null
    }

    private fun clickNode(service: AccessibilityService, node: AccessibilityNodeInfo): Boolean {
        if (tapNodeBounds(service, node)) return true
        node.performAction(AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS)
        node.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
        if (node.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true
        return clickViaParent(node)
    }

    private fun clickViaParent(node: AccessibilityNodeInfo): Boolean {
        var parent = node.parent
        var depth = 0
        while (parent != null && depth < 5) {
            parent.performAction(AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS)
            if (parent.isClickable && parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                @Suppress("DEPRECATION")
                parent.recycle()
                return true
            }
            val next = parent.parent
            @Suppress("DEPRECATION")
            parent.recycle()
            parent = next
            depth++
        }
        return false
    }

    private fun tapNodeBounds(service: AccessibilityService, node: AccessibilityNodeInfo): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.N) return false
        val rect = Rect()
        node.getBoundsInScreen(rect)
        if (rect.width() <= 0 || rect.height() <= 0) return false
        val x = (rect.left + rect.right) / 2f
        val y = (rect.top + rect.bottom) / 2f
        return dispatchTap(service, x, y)
    }

    private fun tapDigitCoordinate(service: AccessibilityService, digit: Char): Boolean {
        val point = digitCoordinate(service, digit) ?: return false
        Log.i(TAG, "Coordinate fallback tap for digit=$digit at ${point.first},${point.second}")
        return dispatchTap(service, point.first, point.second)
    }

    private fun digitCoordinate(service: AccessibilityService, digit: Char): Pair<Float, Float>? {
        val metrics = service.resources.displayMetrics
        val width = metrics.widthPixels.toFloat()
        val layoutHeight = minOf(metrics.heightPixels.toFloat(), 2198f)
        val columns = mapOf(
            '1' to 0, '4' to 0, '7' to 0,
            '2' to 1, '5' to 1, '8' to 1, '0' to 1,
            '3' to 2, '6' to 2, '9' to 2
        )
        val rows = mapOf(
            '1' to 0, '2' to 0, '3' to 0,
            '4' to 1, '5' to 1, '6' to 1,
            '7' to 2, '8' to 2, '9' to 2,
            '0' to 3
        )
        val colCenters = floatArrayOf(228f, 540f, 852f)
        val rowCenters = floatArrayOf(1080f, 1356f, 1632f, 1908f)
        val col = columns[digit] ?: return null
        val row = rows[digit] ?: return null
        val x = width * (colCenters[col] / 1080f)
        val y = layoutHeight * (rowCenters[row] / 2198f)
        return x to y
    }

    private fun dispatchSwipe(
        service: AccessibilityService,
        x1: Float,
        y1: Float,
        x2: Float,
        y2: Float,
        durationMs: Long = 350L
    ): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.N) return false
        val latch = CountDownLatch(1)
        var completed = false
        val path = Path().apply {
            moveTo(x1, y1)
            lineTo(x2, y2)
        }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0L, durationMs))
            .build()
        val dispatched = service.dispatchGesture(
            gesture,
            object : AccessibilityService.GestureResultCallback() {
                override fun onCompleted(gestureDescription: GestureDescription?) {
                    completed = true
                    latch.countDown()
                }

                override fun onCancelled(gestureDescription: GestureDescription?) {
                    latch.countDown()
                }
            },
            null
        )
        if (!dispatched) return false
        latch.await(900, TimeUnit.MILLISECONDS)
        return completed
    }

    private fun dispatchTap(service: AccessibilityService, x: Float, y: Float): Boolean {
        val latch = CountDownLatch(1)
        var completed = false
        val path = Path().apply { moveTo(x, y) }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0L, 80L))
            .build()
        val dispatched = service.dispatchGesture(
            gesture,
            object : AccessibilityService.GestureResultCallback() {
                override fun onCompleted(gestureDescription: GestureDescription?) {
                    completed = true
                    latch.countDown()
                }

                override fun onCancelled(gestureDescription: GestureDescription?) {
                    latch.countDown()
                }
            },
            null
        )
        if (!dispatched) return false
        latch.await(800, TimeUnit.MILLISECONDS)
        return completed
    }

    private fun hasPinBouncer(root: AccessibilityNodeInfo): Boolean {
        findNodeByViewIdSuffix(root, "keyguard_pin_view")?.let {
            @Suppress("DEPRECATION")
            it.recycle()
            return true
        }
        findNodeByViewIdSuffix(root, "key1")?.let {
            @Suppress("DEPRECATION")
            it.recycle()
            return true
        }
        return false
    }

    private fun findNodeByViewIdSuffix(
        root: AccessibilityNodeInfo,
        suffix: String
    ): AccessibilityNodeInfo? {
        val needle = suffix.lowercase()
        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.add(AccessibilityNodeInfo.obtain(root))
        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            val viewId = node.viewIdResourceName.orEmpty().lowercase()
            if (viewId.endsWith(needle) || viewId.contains(":$needle")) {
                queue.forEach {
                    if (it !== node) {
                        @Suppress("DEPRECATION")
                        it.recycle()
                    }
                }
                return AccessibilityNodeInfo.obtain(node)
            }
            for (index in 0 until node.childCount) {
                node.getChild(index)?.let { queue.add(it) }
            }
            @Suppress("DEPRECATION")
            node.recycle()
        }
        return null
    }

    private fun logClickableSummary(root: AccessibilityNodeInfo) {
        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.add(AccessibilityNodeInfo.obtain(root))
        var logged = 0
        while (queue.isNotEmpty() && logged < 12) {
            val node = queue.removeFirst()
            if (node.isClickable || node.isFocusable) {
                val label = buildString {
                    node.text?.let { append(it).append(' ') }
                    node.contentDescription?.let { append(it).append(' ') }
                    node.viewIdResourceName?.let { append(it) }
                }.trim()
                if (label.isNotEmpty()) {
                    val bounds = Rect()
                    node.getBoundsInScreen(bounds)
                    Log.d(TAG, "Clickable[$logged]: $label bounds=$bounds")
                    logged++
                }
            }
            for (index in 0 until node.childCount) {
                node.getChild(index)?.let { queue.add(it) }
            }
            @Suppress("DEPRECATION")
            node.recycle()
        }
    }

    private fun sleepInterruptibly(delayMs: Long) {
        if (delayMs <= 0L || Thread.currentThread().isInterrupted) return
        try {
            Thread.sleep(delayMs)
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        }
    }

    private fun findDigitNode(root: AccessibilityNodeInfo, digit: Char): AccessibilityNodeInfo? {
        findDigitNodeByViewId(root, digit)?.let { return it }

        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.add(AccessibilityNodeInfo.obtain(root))

        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            if (KeyguardPinDetector.extractDigit(node) == digit && isDigitKeyNode(node)) {
                queue.forEach {
                    if (it !== node) {
                        @Suppress("DEPRECATION")
                        it.recycle()
                    }
                }
                return AccessibilityNodeInfo.obtain(node)
            }
            for (index in 0 until node.childCount) {
                node.getChild(index)?.let { queue.add(it) }
            }
            @Suppress("DEPRECATION")
            node.recycle()
        }
        return null
    }

    private fun findDigitNodeByViewId(root: AccessibilityNodeInfo, digit: Char): AccessibilityNodeInfo? {
        val digitText = digit.toString()
        val suffixes = listOf(
            "key$digitText",
            "key_$digitText",
            "digit$digitText",
            "digit_$digitText",
            "pin$digitText",
            "pin_$digitText",
            "num$digitText",
            "num_$digitText",
            "button$digitText",
            "btn$digitText"
        )
        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.add(AccessibilityNodeInfo.obtain(root))

        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            val viewId = node.viewIdResourceName.orEmpty().lowercase()
            if (suffixes.any { suffix -> viewId.endsWith(suffix) || viewId.contains(":$suffix") }) {
                queue.forEach {
                    if (it !== node) {
                        @Suppress("DEPRECATION")
                        it.recycle()
                    }
                }
                return AccessibilityNodeInfo.obtain(node)
            }
            for (index in 0 until node.childCount) {
                node.getChild(index)?.let { queue.add(it) }
            }
            @Suppress("DEPRECATION")
            node.recycle()
        }
        return null
    }

    private fun isDigitKeyNode(node: AccessibilityNodeInfo): Boolean {
        if (node.isClickable || node.isFocusable || node.isLongClickable) return true
        val className = node.className?.toString().orEmpty()
        val viewId = node.viewIdResourceName.orEmpty().lowercase()
        return className.contains("Key", ignoreCase = true) ||
            className.contains("Button", ignoreCase = true) ||
            className.contains("NumPad", ignoreCase = true) ||
            className.contains("Pin", ignoreCase = true) ||
            viewId.contains("key") ||
            viewId.contains("digit") ||
            viewId.contains("pin") ||
            viewId.contains("num")
    }

    private fun findActionNode(root: AccessibilityNodeInfo, tokens: List<String>): AccessibilityNodeInfo? {
        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.add(AccessibilityNodeInfo.obtain(root))

        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            if (node.isClickable || node.isFocusable) {
                val haystack = buildString {
                    node.text?.let { append(it).append(' ') }
                    node.contentDescription?.let { append(it).append(' ') }
                    node.viewIdResourceName?.let { append(it) }
                }.lowercase()
                if (tokens.any { haystack.contains(it) }) {
                    queue.forEach {
                        if (it !== node) {
                            @Suppress("DEPRECATION")
                            it.recycle()
                        }
                    }
                    return AccessibilityNodeInfo.obtain(node)
                }
            }
            for (index in 0 until node.childCount) {
                node.getChild(index)?.let { queue.add(it) }
            }
            @Suppress("DEPRECATION")
            node.recycle()
        }
        return null
    }

    private fun findPasswordField(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        KeyguardPinDetector.findPinInputField(root)?.let { return it }
        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.add(AccessibilityNodeInfo.obtain(root))

        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            val className = node.className?.toString().orEmpty()
            if ((node.isPassword || className.contains("PasswordText", ignoreCase = true)) &&
                (node.isEditable || node.isFocusable || node.isClickable)
            ) {
                queue.forEach {
                    if (it !== node) {
                        @Suppress("DEPRECATION")
                        it.recycle()
                    }
                }
                return AccessibilityNodeInfo.obtain(node)
            }
            for (index in 0 until node.childCount) {
                node.getChild(index)?.let { queue.add(it) }
            }
            @Suppress("DEPRECATION")
            node.recycle()
        }
        return null
    }
}