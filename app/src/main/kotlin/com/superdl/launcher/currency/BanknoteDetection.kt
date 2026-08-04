package com.superdl.launcher.currency

import android.graphics.RectF

data class BanknoteDetection(
    val label: String,
    val classIndex: Int,
    val confidence: Float,
    val boundingBox: RectF
) {
    val denomination: BanknoteDenomination? = BanknoteDenomination.fromLabel(label)

    val areaFraction: Float
        get() {
            val w = boundingBox.width().coerceAtLeast(0f)
            val h = boundingBox.height().coerceAtLeast(0f)
            return w * h
        }
}