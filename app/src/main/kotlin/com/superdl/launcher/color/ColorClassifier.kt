package com.superdl.launcher.color

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

object ColorClassifier {

    data class Result(
        val name: String,
        val brightnessPercent: Int
    )

    fun classify(r: Int, g: Int, b: Int): Result {
        val red = r.coerceIn(0, 255)
        val green = g.coerceIn(0, 255)
        val blue = b.coerceIn(0, 255)
        val max = max(red, max(green, blue))
        val min = min(red, min(green, blue))
        val brightness = (red + green + blue) / 3
        val saturation = if (max == 0) 0f else (max - min).toFloat() / max

        val name = when {
            brightness < 35 -> "fekete"
            brightness > 225 && saturation < 0.12f -> "fehér"
            saturation < 0.14f -> "szürke"
            red > green + 45 && red > blue + 45 -> when {
                green > 130 && blue < 110 -> "narancssárga"
                green < 95 -> "piros"
                else -> "rózsaszín"
            }
            green > red + 35 && green > blue + 35 -> "zöld"
            blue > red + 35 && blue > green + 35 -> when {
                red > 95 && green < 150 -> "lila"
                else -> "kék"
            }
            red > 150 && green > 130 && blue < 110 -> "sárga"
            red > 110 && green > 70 && blue > 50 && abs(red - green) < 55 -> "barna"
            red > 100 && green > 80 && blue > 80 -> "bézs"
            else -> "vegyes színű"
        }

        val brightnessPercent = ((brightness / 255f) * 100f).toInt().coerceIn(0, 100)
        return Result(name, brightnessPercent)
    }
}