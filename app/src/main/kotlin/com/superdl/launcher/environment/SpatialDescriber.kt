package com.superdl.launcher.environment

import android.graphics.RectF
import kotlin.math.abs
import kotlin.math.hypot

object SpatialDescriber {

    fun describe(boundingBox: RectF): String {
        val centerX = (boundingBox.left + boundingBox.right) / 2f
        val centerY = (boundingBox.top + boundingBox.bottom) / 2f
        val area = boundingBox.width() * boundingBox.height()

        val distance = when {
            area >= 0.22f -> "közvetlenül előtted"
            area >= 0.10f -> "egy méterre előtted"
            area >= 0.04f -> "két méterre"
            else -> "távolabb"
        }

        val horizontal = when {
            centerX < 0.33f -> "balra"
            centerX > 0.67f -> "jobbra"
            else -> null
        }
        val vertical = when {
            centerY < 0.35f -> "felül"
            centerY > 0.65f -> "lent"
            else -> null
        }

        return when {
            horizontal != null && vertical != null -> "$distance $horizontal, $vertical"
            horizontal != null -> "$distance $horizontal"
            vertical != null -> "$distance $vertical"
            else -> distance
        }
    }

    fun centerDistance(boundingBox: RectF): Float {
        val centerX = (boundingBox.left + boundingBox.right) / 2f
        val centerY = (boundingBox.top + boundingBox.bottom) / 2f
        return hypot((centerX - 0.5f).toDouble(), (centerY - 0.5f).toDouble()).toFloat()
    }

    fun isCentered(boundingBox: RectF, threshold: Float = 0.18f): Boolean =
        centerDistance(boundingBox) <= threshold

    fun formatAnnouncement(category: ObjectCategory, boundingBox: RectF): String {
        val centerY = (boundingBox.top + boundingBox.bottom) / 2f
        val name = when {
            category == ObjectCategory.FLOOR_OBJECT && centerY >= 0.60f ->
                "Földön lévő tárgy"
            category == ObjectCategory.FLOOR_OBJECT && centerY < 0.60f ->
                category.hungarianName
            else -> category.hungarianName
        }
        return "$name, ${describe(boundingBox)}"
    }
}