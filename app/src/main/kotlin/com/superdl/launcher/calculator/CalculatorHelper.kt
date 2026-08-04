package com.superdl.launcher.calculator

import java.util.Locale

data class CalculatorResult(
    val expression: String,
    val value: Double
) {
    fun speak(): String {
        val formatted = CalculatorHelper.formatNumber(value)
        return "Eredmény: $formatted. Kifejezés: $expression."
    }
}

object CalculatorHelper {

    private val numberWords = mapOf(
        "nulla" to 0.0, "egy" to 1.0, "kettő" to 2.0, "ketto" to 2.0, "három" to 3.0, "harom" to 3.0,
        "négy" to 4.0, "negy" to 4.0, "öt" to 5.0, "ot" to 5.0, "hat" to 6.0, "hét" to 7.0, "het" to 7.0,
        "nyolc" to 8.0, "kilenc" to 9.0, "tíz" to 10.0, "tiz" to 10.0,
        "tizenegy" to 11.0, "tizenkettő" to 12.0, "tizenketto" to 12.0,
        "húsz" to 20.0, "husz" to 20.0, "harminc" to 30.0, "negyven" to 40.0,
        "ötven" to 50.0, "otven" to 50.0, "hatvan" to 60.0, "hetven" to 70.0,
        "nyolcvan" to 80.0, "kilencven" to 90.0, "száz" to 100.0, "szaz" to 100.0
    )

    fun evaluate(spoken: String): CalculatorResult? {
        val expression = normalizeExpression(spoken) ?: return null
        return evaluateExpression(expression)
    }

    fun evaluateExpression(expression: String): CalculatorResult? {
        val normalized = expression
            .replace("×", "*")
            .replace("÷", "/")
            .replace(Regex("\\s+"), "")
        if (normalized.isBlank()) return null
        if (!normalized.matches(Regex("^[0-9+\\-*/().]+$"))) return null
        val value = compute(normalized) ?: return null
        return CalculatorResult(normalized, value)
    }

    private fun normalizeExpression(raw: String): String? {
        var text = raw.lowercase(Locale("hu", "HU"))
            .replace("mennyi", "")
            .replace("az", "")
            .replace("egyenlő", "=")
            .replace("egyenlo", "=")
            .replace("plusz", "+")
            .replace("meg", "+")
            .replace("összead", "+")
            .replace("osszead", "+")
            .replace("mínusz", "-")
            .replace("minusz", "-")
            .replace("kivon", "-")
            .replace("szorozva", "*")
            .replace("szoroz", "*")
            .replace("szor", "*")
            .replace("osztva", "/")
            .replace("oszt", "/")
            .replace("÷", "/")
            .replace("×", "*")
            .replace(",", ".")
            .replace(Regex("\\s+"), " ")
            .trim()

        if (text.isBlank()) return null

        for ((word, value) in numberWords.entries.sortedByDescending { it.key.length }) {
            text = text.replace(Regex("\\b${Regex.escape(word)}\\b"), value.toString())
        }

        text = text.replace(Regex("[^0-9+\\-*/().\\s]"), " ")
            .replace(Regex("\\s+"), "")
        if (text.isBlank()) return null
        if (!text.matches(Regex("^[0-9+\\-*/().]+$"))) return null
        return text
    }

    private fun compute(expression: String): Double? {
        return try {
            val tokens = tokenize(expression) ?: return null
            val rpn = toRpn(tokens) ?: return null
            evalRpn(rpn)
        } catch (_: Exception) {
            null
        }
    }

    private fun tokenize(expr: String): List<String>? {
        val tokens = mutableListOf<String>()
        var i = 0
        while (i < expr.length) {
            when {
                expr[i].isDigit() || expr[i] == '.' -> {
                    val start = i
                    while (i < expr.length && (expr[i].isDigit() || expr[i] == '.')) i++
                    tokens.add(expr.substring(start, i))
                }
                expr[i] in "+-*/()" -> {
                    tokens.add(expr[i].toString())
                    i++
                }
                else -> return null
            }
        }
        return tokens
    }

    private fun toRpn(tokens: List<String>): List<String>? {
        val output = mutableListOf<String>()
        val ops = ArrayDeque<String>()
        var prev: String? = null
        for (token in tokens) {
            when {
                token.toDoubleOrNull() != null -> output.add(token)
                token == "(" -> ops.addLast(token)
                token == ")" -> {
                    while (ops.isNotEmpty() && ops.last() != "(") output.add(ops.removeLast())
                    if (ops.isEmpty() || ops.last() != "(") return null
                    ops.removeLast()
                }
                token in listOf("+", "-", "*", "/") -> {
                    if ((token == "-" || token == "+") && (prev == null || prev in listOf("(", "+", "-", "*", "/"))) {
                        output.add("0")
                    }
                    while (ops.isNotEmpty() && ops.last() != "(" && precedence(ops.last()) >= precedence(token)) {
                        output.add(ops.removeLast())
                    }
                    ops.addLast(token)
                }
                else -> return null
            }
            prev = token
        }
        while (ops.isNotEmpty()) {
            val op = ops.removeLast()
            if (op == "(") return null
            output.add(op)
        }
        return output
    }

    private fun precedence(op: String): Int = when (op) {
        "+", "-" -> 1
        "*", "/" -> 2
        else -> 0
    }

    private fun evalRpn(tokens: List<String>): Double? {
        val stack = ArrayDeque<Double>()
        for (token in tokens) {
            when {
                token.toDoubleOrNull() != null -> stack.addLast(token.toDouble())
                token in listOf("+", "-", "*", "/") -> {
                    if (stack.size < 2) return null
                    val b = stack.removeLast()
                    val a = stack.removeLast()
                    val result = when (token) {
                        "+" -> a + b
                        "-" -> a - b
                        "*" -> a * b
                        "/" -> if (b == 0.0) return null else a / b
                        else -> return null
                    }
                    stack.addLast(result)
                }
                else -> return null
            }
        }
        return stack.lastOrNull()
    }

    fun formatNumber(value: Double): String {
        return if (value == value.toLong().toDouble()) {
            value.toLong().toString()
        } else {
            String.format(Locale.US, "%.2f", value)
        }
    }
}