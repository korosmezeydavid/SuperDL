package com.superdl.launcher.camera

import com.google.mlkit.vision.face.Face

object FacePositionSpeaker {

    private val gridPhrases = arrayOf(
        arrayOf("bal felső sarokhoz közel", "felül középen", "jobb felső sarokhoz közel"),
        arrayOf("balszélhez közel", "középen", "jobszélhez közel"),
        arrayOf("bal alsó sarokhoz közel", "lent középen", "jobb alsó sarokhoz közel")
    )

    fun describe(faces: List<Face>, imageWidth: Int, imageHeight: Int, selfieMode: Boolean): String? {
        if (imageWidth <= 0 || imageHeight <= 0) return null

        return when (faces.size) {
            0 -> "Nincs arc a képen"
            1 -> {
                val face = faces.first()
                val centerX = face.boundingBox.centerX().toFloat() / imageWidth
                val centerY = face.boundingBox.centerY().toFloat() / imageHeight
                val position = gridPhrase(centerX, centerY, selfieMode)
                "Arc a $position"
            }
            2 -> "Két arc látható"
            else -> "${faces.size} arc látható"
        }
    }

    fun debounceKey(faces: List<Face>, imageWidth: Int, imageHeight: Int, selfieMode: Boolean): String {
        if (faces.isEmpty()) return "none"
        if (faces.size > 1) return "count_${faces.size}"

        val face = faces.first()
        val centerX = face.boundingBox.centerX().toFloat() / imageWidth
        val centerY = face.boundingBox.centerY().toFloat() / imageHeight
        val col = gridColumn(centerX, selfieMode)
        val row = gridRow(centerY)
        return "single_${row}_${col}"
    }

    private fun gridPhrase(centerX: Float, centerY: Float, selfieMode: Boolean): String {
        val col = gridColumn(centerX, selfieMode)
        val row = gridRow(centerY)
        return gridPhrases[row][col]
    }

    private fun gridColumn(centerX: Float, mirror: Boolean): Int {
        val x = if (mirror) 1f - centerX else centerX
        return when {
            x < 0.33f -> 0
            x < 0.67f -> 1
            else -> 2
        }
    }

    private fun gridRow(centerY: Float): Int = when {
        centerY < 0.33f -> 0
        centerY < 0.67f -> 1
        else -> 2
    }
}

class FaceAnnounceDebouncer(private val cooldownMs: Long = 2000L) {
    private var lastKey: String? = null
    private var lastSpokenAt = 0L

    fun shouldAnnounce(key: String, now: Long = System.currentTimeMillis()): Boolean {
        if (key == lastKey && now - lastSpokenAt < cooldownMs) return false
        lastKey = key
        lastSpokenAt = now
        return true
    }

    fun reset() {
        lastKey = null
        lastSpokenAt = 0L
    }
}