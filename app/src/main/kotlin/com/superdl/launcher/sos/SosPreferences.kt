package com.superdl.launcher.sos

import android.content.Context

object SosPreferences {

    private const val PREFS_NAME = "superdl"
    private val SLOT_KEYS = arrayOf("sos_1", "sos_2", "sos_3", "sos_4")

    fun getNumber(context: Context, slot: Int): String {
        require(slot in 1..4) { "SOS slot must be 1..4" }
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getString(SLOT_KEYS[slot - 1], "") ?: ""
    }

    fun getNumbers(context: Context): List<String> =
        (1..4).map { getNumber(context, it) }

    fun setNumber(context: Context, slot: Int, value: String) {
        require(slot in 1..4) { "SOS slot must be 1..4" }
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(SLOT_KEYS[slot - 1], value)
            .apply()
    }

    fun clearNumber(context: Context, slot: Int) = setNumber(context, slot, "")

    fun normalizeSpokenNumber(raw: String): String? {
        val trimmed = raw.trim()
        if (trimmed.equals("töröl", ignoreCase = true) ||
            trimmed.equals("torol", ignoreCase = true) ||
            trimmed.equals("törlés", ignoreCase = true)
        ) {
            return ""
        }
        val digits = trimmed.filter { it.isDigit() || it == '+' }
        if (digits.isBlank()) return null
        return digits
    }
}