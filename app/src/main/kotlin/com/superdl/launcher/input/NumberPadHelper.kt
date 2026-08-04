package com.superdl.launcher.input

enum class NumberPadPurpose {
    PHONE,
    SOS,
    CALCULATOR,
    CONTACT,
    PIN,
    TIME,
    AMOUNT,
    DATE,
    PRICE
}

enum class NumberPadKey {
    DIGIT,
    OPERATOR,
    VOICE,
    DONE,
    CLEAR,
    CONFIRM
}

data class NumberPadItem(
    val key: NumberPadKey,
    val value: String,
    val label: String
) {
    fun speakLabel(): String = when (key) {
        NumberPadKey.DIGIT -> label
        NumberPadKey.OPERATOR -> label
        NumberPadKey.VOICE -> label
        NumberPadKey.DONE -> label
        NumberPadKey.CLEAR -> label
        NumberPadKey.CONFIRM -> label
    }
}

object NumberPadHelper {

    val phoneItems: List<NumberPadItem> = buildList {
        for (digit in listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")) {
            add(NumberPadItem(NumberPadKey.DIGIT, digit, digit))
        }
        add(NumberPadItem(NumberPadKey.DIGIT, "+", "plusz"))
        add(NumberPadItem(NumberPadKey.DONE, "", "Kész"))
    }

    val calculatorItems: List<NumberPadItem> = buildList {
        for (digit in listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")) {
            add(NumberPadItem(NumberPadKey.DIGIT, digit, digit))
        }
        add(NumberPadItem(NumberPadKey.OPERATOR, "+", "összeadás"))
        add(NumberPadItem(NumberPadKey.OPERATOR, "-", "kivonás"))
        add(NumberPadItem(NumberPadKey.OPERATOR, "*", "szorzás"))
        add(NumberPadItem(NumberPadKey.OPERATOR, "/", "osztás"))
        add(NumberPadItem(NumberPadKey.VOICE, "", "Diktálás"))
        add(NumberPadItem(NumberPadKey.DONE, "", "Kész"))
    }

    val pinItems: List<NumberPadItem> = buildList {
        for (digit in listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")) {
            add(NumberPadItem(NumberPadKey.DIGIT, digit, digit))
        }
        add(NumberPadItem(NumberPadKey.CLEAR, "", "Törlés"))
        add(NumberPadItem(NumberPadKey.CONFIRM, "", "Megerősítés"))
    }

    val timeItems: List<NumberPadItem> = buildList {
        for (digit in listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")) {
            add(NumberPadItem(NumberPadKey.DIGIT, digit, digit))
        }
        add(NumberPadItem(NumberPadKey.DONE, "", "Kész"))
    }

    val amountItems: List<NumberPadItem> = buildList {
        for (digit in listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")) {
            add(NumberPadItem(NumberPadKey.DIGIT, digit, digit))
        }
        add(NumberPadItem(NumberPadKey.DONE, "", "Kész"))
    }

    val dateItems: List<NumberPadItem> = buildList {
        for (digit in listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")) {
            add(NumberPadItem(NumberPadKey.DIGIT, digit, digit))
        }
        add(NumberPadItem(NumberPadKey.DONE, "", "Kész"))
    }

    val priceItems: List<NumberPadItem> = buildList {
        for (digit in listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")) {
            add(NumberPadItem(NumberPadKey.DIGIT, digit, digit))
        }
        add(NumberPadItem(NumberPadKey.DONE, "", "Kész"))
    }

    val dtmfItems: List<NumberPadItem> = buildList {
        for (digit in listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")) {
            add(NumberPadItem(NumberPadKey.DIGIT, digit, digit))
        }
        add(NumberPadItem(NumberPadKey.OPERATOR, "*", "csillag"))
        add(NumberPadItem(NumberPadKey.OPERATOR, "#", "kettőskereszt"))
    }

    fun itemsFor(purpose: NumberPadPurpose): List<NumberPadItem> = when (purpose) {
        NumberPadPurpose.PHONE, NumberPadPurpose.SOS, NumberPadPurpose.CONTACT -> phoneItems
        NumberPadPurpose.CALCULATOR -> calculatorItems
        NumberPadPurpose.PIN -> pinItems
        NumberPadPurpose.TIME -> timeItems
        NumberPadPurpose.AMOUNT -> amountItems
        NumberPadPurpose.DATE -> dateItems
        NumberPadPurpose.PRICE -> priceItems
    }

    fun speakBuffer(buffer: String): String =
        if (buffer.isBlank()) "Üres bevitel." else "Bevitel: ${speakChars(buffer)}."

    fun speakPinLength(buffer: String): String =
        if (buffer.isEmpty()) "Nincs beírt számjegy." else "${buffer.length} számjegy beírva."

    fun speakPinDigitEntered(buffer: String): String =
        "Számjegy beírva. ${speakPinLength(buffer)}"

    fun speakPinBackspace(buffer: String): String =
        if (buffer.isEmpty()) "Nincs törlendő számjegy."
        else "Egy számjegy törölve. ${speakPinLength(buffer)}"

    fun speakChars(value: String): String =
        value.map { char ->
            when (char) {
                '+' -> "plusz"
                '-' -> "mínusz"
                '*' -> "szor"
                '/' -> "oszt"
                else -> char.toString()
            }
        }.joinToString(" ")

    private val spokenDigitWords = mapOf(
        "nulla" to "0", "egy" to "1", "kettő" to "2", "ketto" to "2", "három" to "3", "harom" to "3",
        "négy" to "4", "negy" to "4", "öt" to "5", "ot" to "5", "hat" to "6", "hét" to "7", "het" to "7",
        "nyolc" to "8", "kilenc" to "9"
    )

    fun parseSpokenPhone(spoken: String): String {
        val normalized = spoken.trim().lowercase()
            .replace("plusz", "+")
            .replace(Regex("[^0-9+\\sa-záéíóöőúüű]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
        if (normalized.isBlank()) return ""

        val directDigits = Regex("[+0-9]+").find(normalized)?.value
        if (!directDigits.isNullOrBlank() && directDigits.any { it.isDigit() }) {
            return directDigits
        }

        val builder = StringBuilder()
        normalized.split(" ").filter { it.isNotBlank() }.forEach { token ->
            when {
                token == "+" -> builder.append('+')
                token.all { it.isDigit() } -> builder.append(token)
                spokenDigitWords.containsKey(token) -> builder.append(spokenDigitWords.getValue(token))
            }
        }
        return builder.toString()
    }

    fun append(buffer: String, item: NumberPadItem): String? = when (item.key) {
        NumberPadKey.DIGIT, NumberPadKey.OPERATOR -> buffer + item.value
        else -> null
    }

    fun appendTimeDigit(buffer: String, digit: String): String? {
        if (buffer.length >= 4) return null
        return buffer + digit
    }

    fun appendAmountDigit(buffer: String, digit: String): String? {
        if (buffer.length >= 4) return null
        return buffer + digit
    }

    fun appendDateDigit(buffer: String, digit: String): String? {
        if (buffer.length >= 8) return null
        return buffer + digit
    }

    fun appendPriceDigit(buffer: String, digit: String): String? {
        if (buffer.length >= 7) return null
        return buffer + digit
    }

    fun parseAmountBuffer(buffer: String): Int? {
        val digits = buffer.filter { it.isDigit() }
        if (digits.isBlank()) return null
        val value = digits.toIntOrNull() ?: return null
        return if (value > 0) value else null
    }

    fun parseDateBuffer(buffer: String): Long? {
        val digits = buffer.filter { it.isDigit() }
        if (digits.length != 8) return null
        val year = digits.substring(0, 4).toIntOrNull() ?: return null
        val month = digits.substring(4, 6).toIntOrNull() ?: return null
        val day = digits.substring(6, 8).toIntOrNull() ?: return null
        if (month !in 1..12 || day !in 1..31) return null
        val cal = java.util.Calendar.getInstance().apply {
            set(java.util.Calendar.YEAR, year)
            set(java.util.Calendar.MONTH, month - 1)
            set(java.util.Calendar.DAY_OF_MONTH, day)
            set(java.util.Calendar.HOUR_OF_DAY, 0)
            set(java.util.Calendar.MINUTE, 0)
            set(java.util.Calendar.SECOND, 0)
            set(java.util.Calendar.MILLISECOND, 0)
        }
        return cal.timeInMillis
    }

    fun speakDateBuffer(buffer: String): String {
        val digits = buffer.filter { it.isDigit() }
        return when (digits.length) {
            0 -> "Nincs beírt dátum."
            in 1..4 -> "Év: ${speakChars(digits)}."
            in 5..6 -> {
                val year = digits.take(4)
                val month = digits.drop(4)
                "Dátum: ${speakChars(year)} ${speakChars(month)}."
            }
            else -> {
                val year = digits.take(4)
                val month = digits.substring(4, 6)
                val day = digits.drop(6)
                "Dátum: ${speakChars(year)} ${speakChars(month)} ${speakChars(day)}."
            }
        }
    }

    fun speakAmountBuffer(buffer: String): String =
        if (buffer.isBlank()) "Nincs beírt szám." else "Szám: ${speakChars(buffer)}."

    fun speakPriceBuffer(buffer: String): String =
        if (buffer.isBlank()) "Nincs beírt ár." else "Ár: ${speakChars(buffer)} forint."

    fun parseTimeBuffer(buffer: String): Pair<Int, Int>? {
        val digits = buffer.filter { it.isDigit() }
        if (digits.length != 4) return null
        val hour = digits.substring(0, 2).toIntOrNull() ?: return null
        val minute = digits.substring(2, 4).toIntOrNull() ?: return null
        if (hour !in 0..23 || minute !in 0..59) return null
        return hour to minute
    }

    fun speakTimeBuffer(buffer: String): String {
        val digits = buffer.filter { it.isDigit() }
        return when (digits.length) {
            0 -> "Nincs beírt idő."
            1, 2 -> "Óra: ${speakChars(digits)}."
            3, 4 -> {
                val hour = digits.take(2)
                val minute = digits.drop(2)
                "Idő: ${speakChars(hour)} ${speakChars(minute)}."
            }
            else -> speakBuffer(buffer)
        }
    }

    fun backspace(buffer: String): String =
        if (buffer.isEmpty()) "" else buffer.dropLast(1)

    fun clear(): String = ""
}