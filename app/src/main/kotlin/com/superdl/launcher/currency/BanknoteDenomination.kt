package com.superdl.launcher.currency

enum class BanknoteDenomination(
    val valueHuf: Int,
    val labelKey: String,
    val speechHu: String
) {
    HUF_500(500, "huf_500", "Ötszáz forint"),
    HUF_1000(1000, "huf_1000", "Ezer forint"),
    HUF_2000(2000, "huf_2000", "Kétezer forint"),
    HUF_5000(5000, "huf_5000", "Ötezer forint"),
    HUF_10000(10000, "huf_10000", "Tízezer forint"),
    HUF_20000(20000, "huf_20000", "Húszezer forint");

    companion object {
        fun fromLabel(label: String): BanknoteDenomination? =
            entries.firstOrNull { it.labelKey == label }

        /** A címlet értékéből ("500", "10000") enum. */
        fun fromValue(value: String): BanknoteDenomination? {
            val v = value.trim().toIntOrNull() ?: return null
            return entries.firstOrNull { it.valueHuf == v }
        }
    }
}