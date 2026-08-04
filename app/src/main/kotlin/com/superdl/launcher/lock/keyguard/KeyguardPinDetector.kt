package com.superdl.launcher.lock.keyguard

import android.app.KeyguardManager
import android.content.Context
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

object KeyguardPinDetector {

    const val SYSTEM_UI_PACKAGE = "com.android.systemui"
    const val LEGACY_KEYGUARD_PACKAGE = "com.android.keyguard"

    enum class CredentialState {
        NONE,
        KEYGUARD_IDLE,
        BIOMETRIC_PROMPT,
        PIN_OR_PASSWORD,
        PATTERN,
        OTHER_CREDENTIAL
    }

    private val spokenDigits = mapOf(
        "nulla" to '0',
        "egy" to '1',
        "kettő" to '2',
        "ketto" to '2',
        "három" to '3',
        "harom" to '3',
        "négy" to '4',
        "negy" to '4',
        "öt" to '5',
        "ot" to '5',
        "hat" to '6',
        "hét" to '7',
        "het" to '7',
        "nyolc" to '8',
        "kilenc" to '9',
        "zero" to '0',
        "one" to '1',
        "two" to '2',
        "three" to '3',
        "four" to '4',
        "five" to '5',
        "six" to '6',
        "seven" to '7',
        "eight" to '8',
        "nine" to '9'
    )

    private val pinClassMarkers = listOf(
        "KeyguardPINView",
        "KeyguardPasswordView",
        "KeyguardSimPinView",
        "KeyguardSimPukView",
        "KeyguardAbsKeyInputView",
        "PasswordTextView",
        "PinPad",
        "NumPadKey",
        "NumPadButton",
        "KeyButtonView",
        "Bouncer",
        "PinBouncer",
        "KeyguardSecurityContainer",
        "EmergencyDialer",
        "PinShapeView"
    )

    private val patternClassMarkers = listOf(
        "KeyguardPatternView",
        "LockPatternView",
        "PatternView"
    )

    private val biometricClassMarkers = listOf(
        "Biometric",
        "Fingerprint",
        "FaceUnlock",
        "Udfps",
        "Sidefps"
    )

    fun isKeyguardLocked(context: Context): Boolean {
        val keyguard = context.getSystemService(KeyguardManager::class.java) ?: return false
        return keyguard.isKeyguardLocked
    }

    fun isDeviceSecure(context: Context): Boolean {
        val keyguard = context.getSystemService(KeyguardManager::class.java) ?: return false
        return keyguard.isDeviceSecure
    }

    fun isSystemUiPackage(packageName: CharSequence?): Boolean {
        val pkg = packageName?.toString().orEmpty()
        return pkg == SYSTEM_UI_PACKAGE || pkg == LEGACY_KEYGUARD_PACKAGE
    }

    fun isRelevantEvent(event: AccessibilityEvent): Boolean {
        return when (event.eventType) {
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED,
            AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED,
            AccessibilityEvent.TYPE_WINDOWS_CHANGED,
            AccessibilityEvent.TYPE_VIEW_FOCUSED,
            AccessibilityEvent.TYPE_VIEW_CLICKED,
            AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED -> true
            else -> false
        }
    }

    fun analyzeEvent(event: AccessibilityEvent, context: Context): CredentialState {
        if (!isKeyguardLocked(context)) return CredentialState.NONE
        if (!isRelevantEvent(event)) return CredentialState.KEYGUARD_IDLE

        val source = event.source
        if (source != null) {
            return try {
                analyzeNodeTree(source)
            } finally {
                @Suppress("DEPRECATION")
                source.recycle()
            }
        }

        val className = event.className?.toString().orEmpty()
        return classifyByClassName(className, CredentialState.KEYGUARD_IDLE)
    }

    fun analyzeRoot(root: AccessibilityNodeInfo?, context: Context): CredentialState {
        if (!isKeyguardLocked(context) || root == null) return CredentialState.NONE
        return analyzeNodeTree(root)
    }

    fun findPinInputField(root: AccessibilityNodeInfo?): AccessibilityNodeInfo? {
        if (root == null) return null
        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.add(AccessibilityNodeInfo.obtain(root))

        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            if (isPinInputNode(node)) {
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

    private fun isPinInputNode(node: AccessibilityNodeInfo): Boolean {
        val className = node.className?.toString().orEmpty()
        if (node.isPassword) return true
        if (className.contains("EditText", ignoreCase = true) && node.isEditable) return true
        if (className.contains("PasswordText", ignoreCase = true)) return true
        if (className.contains("KeyguardPassword", ignoreCase = true)) return true
        if (className.contains("KeyguardPIN", ignoreCase = true)) return true
        return false
    }

    private fun analyzeNodeTree(root: AccessibilityNodeInfo): CredentialState {
        var hasPattern = false
        var hasBiometric = false
        var hasPinMarker = false
        var hasPasswordField = false
        val digitButtons = mutableSetOf<Char>()

        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.add(AccessibilityNodeInfo.obtain(root))

        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            val className = node.className?.toString().orEmpty()

            if (patternClassMarkers.any { className.contains(it, ignoreCase = true) }) {
                hasPattern = true
            }
            if (pinClassMarkers.any { className.contains(it, ignoreCase = true) }) {
                hasPinMarker = true
            }
            if (biometricClassMarkers.any { className.contains(it, ignoreCase = true) }) {
                hasBiometric = true
            }
            if (isPinInputNode(node)) {
                hasPasswordField = true
            }

            val digit = extractDigit(node)
            if (digit != null) {
                val className = node.className?.toString().orEmpty()
                val viewId = node.viewIdResourceName.orEmpty().lowercase()
                val isKeyButton = node.isClickable || node.isFocusable || node.isLongClickable ||
                    viewId.startsWith("key") || viewId.contains(":key") ||
                    className.contains("ViewGroup", ignoreCase = true)
                if (isKeyButton) {
                    digitButtons.add(digit)
                }
            }

            for (index in 0 until node.childCount) {
                node.getChild(index)?.let { queue.add(it) }
            }
            @Suppress("DEPRECATION")
            node.recycle()
        }

        return when {
            hasPattern -> CredentialState.PATTERN
            hasPinMarker -> CredentialState.PIN_OR_PASSWORD
            hasPasswordField -> CredentialState.PIN_OR_PASSWORD
            digitButtons.size >= 6 -> CredentialState.PIN_OR_PASSWORD
            hasBiometric && digitButtons.size < 4 -> CredentialState.BIOMETRIC_PROMPT
            else -> CredentialState.KEYGUARD_IDLE
        }
    }

    private fun classifyByClassName(
        className: String,
        fallback: CredentialState
    ): CredentialState {
        if (patternClassMarkers.any { className.contains(it, ignoreCase = true) }) {
            return CredentialState.PATTERN
        }
        if (pinClassMarkers.any { className.contains(it, ignoreCase = true) }) {
            return CredentialState.PIN_OR_PASSWORD
        }
        if (className.contains("EditText", ignoreCase = true) ||
            className.contains("PasswordText", ignoreCase = true)
        ) {
            return CredentialState.PIN_OR_PASSWORD
        }
        if (biometricClassMarkers.any { className.contains(it, ignoreCase = true) }) {
            return CredentialState.BIOMETRIC_PROMPT
        }
        return fallback
    }

    fun extractDigit(node: AccessibilityNodeInfo): Char? {
        val candidates = buildList {
            node.text?.toString()?.let { add(it) }
            node.contentDescription?.toString()?.let { add(it) }
            node.viewIdResourceName?.substringAfterLast('/')?.let { add(it) }
        }
        for (raw in candidates) {
            val normalized = raw.trim().lowercase()
                .replace('.', ' ')
                .replace(',', ' ')
            spokenDigits[normalized]?.let { return it }
            val firstWord = normalized.substringBefore(' ')
            if (firstWord.isNotEmpty()) {
                spokenDigits[firstWord]?.let { return it }
            }
            if (normalized.length == 1 && normalized[0].isDigit()) {
                return normalized[0]
            }
            val digitOnly = normalized.filter { it.isDigit() }
            if (digitOnly.length == 1) return digitOnly[0]
            Regex("""key[_-]?(\d)""").find(normalized)?.groupValues?.getOrNull(1)?.firstOrNull()?.let {
                return it
            }
            Regex("""digit[_-]?(\d)""").find(normalized)?.groupValues?.getOrNull(1)?.firstOrNull()?.let {
                return it
            }
            Regex("""pin[_-]?(\d)""").find(normalized)?.groupValues?.getOrNull(1)?.firstOrNull()?.let {
                return it
            }
            Regex("""num[_-]?(\d)""").find(normalized)?.groupValues?.getOrNull(1)?.firstOrNull()?.let {
                return it
            }
            Regex("""button[_-]?(\d)""").find(normalized)?.groupValues?.getOrNull(1)?.firstOrNull()?.let {
                return it
            }
        }
        return null
    }
}