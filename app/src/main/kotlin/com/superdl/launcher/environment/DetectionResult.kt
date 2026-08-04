package com.superdl.launcher.environment

import android.graphics.RectF

data class DetectionResult(
    val category: ObjectCategory,
    val label: String,
    val confidence: Float,
    val boundingBox: RectF
) {
    val centerX: Float get() = (boundingBox.left + boundingBox.right) / 2f
    val centerY: Float get() = (boundingBox.top + boundingBox.bottom) / 2f
    val area: Float get() = boundingBox.width() * boundingBox.height()
}