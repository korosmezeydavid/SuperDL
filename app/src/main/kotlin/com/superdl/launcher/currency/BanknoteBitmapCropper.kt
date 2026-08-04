package com.superdl.launcher.currency

import android.graphics.Bitmap
import android.graphics.Rect
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

internal object BanknoteBitmapCropper {

    fun crop(bitmap: Bitmap, detection: BanknoteDetection, paddingFraction: Float = 0.06f): Bitmap? {
        if (bitmap.isRecycled) return null
        val rect = toPixelRect(bitmap.width, bitmap.height, detection.boundingBox, paddingFraction)
        if (rect.width() < MIN_CROP_PX || rect.height() < MIN_CROP_PX) return null
        return try {
            Bitmap.createBitmap(bitmap, rect.left, rect.top, rect.width(), rect.height())
        } catch (_: Exception) {
            null
        }
    }

    fun centerRoi(bitmap: Bitmap, widthFraction: Float = 0.72f, heightFraction: Float = 0.58f): Bitmap? {
        if (bitmap.isRecycled) return null
        val roiWidth = (bitmap.width * widthFraction).roundToInt().coerceAtLeast(MIN_CROP_PX)
        val roiHeight = (bitmap.height * heightFraction).roundToInt().coerceAtLeast(MIN_CROP_PX)
        val left = ((bitmap.width - roiWidth) / 2f).roundToInt().coerceIn(0, bitmap.width - 1)
        val top = ((bitmap.height - roiHeight) / 2f).roundToInt().coerceIn(0, bitmap.height - 1)
        val width = min(roiWidth, bitmap.width - left)
        val height = min(roiHeight, bitmap.height - top)
        if (width < MIN_CROP_PX || height < MIN_CROP_PX) return null
        return try {
            Bitmap.createBitmap(bitmap, left, top, width, height)
        } catch (_: Exception) {
            null
        }
    }

    private fun toPixelRect(
        imageWidth: Int,
        imageHeight: Int,
        box: android.graphics.RectF,
        paddingFraction: Float
    ): Rect {
        val padX = box.width() * paddingFraction
        val padY = box.height() * paddingFraction

        val left = ((box.left - padX) * imageWidth).roundToInt().coerceIn(0, imageWidth - 1)
        val top = ((box.top - padY) * imageHeight).roundToInt().coerceIn(0, imageHeight - 1)
        val right = ((box.right + padX) * imageWidth).roundToInt().coerceIn(left + 1, imageWidth)
        val bottom = ((box.bottom + padY) * imageHeight).roundToInt().coerceIn(top + 1, imageHeight)

        return Rect(left, top, right, bottom)
    }

    private const val MIN_CROP_PX = 48
}