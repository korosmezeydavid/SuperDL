package com.superdl.launcher.screenreader

import android.accessibilityservice.AccessibilityService
import android.graphics.Bitmap
import android.graphics.Rect
import android.os.Build
import android.view.accessibility.AccessibilityNodeInfo
import com.superdl.launcher.textreader.TextRecognitionEngine

/**
 * KÉPFELOLVASÁS — mi van azon a képen?
 *
 * MIÉRT KELL: rengeteg alkalmazásban a fontos információ KÉPEN van, felirat
 * nélkül — egy gomb ikonja, egy plakát, egy képernyőkép, egy számla fotója.
 * A képernyőolvasó ilyenkor csak annyit tud mondani, hogy "kép", és a
 * felhasználó nem jut hozzá a tartalomhoz.
 *
 * MEGOLDÁS: lefényképezzük a képernyőt, kivágjuk belőle a kiválasztott elemet,
 * és a telefonon futó szövegfelismerővel elolvassuk, mi van rajta. A kép NEM
 * megy sehova — a felismerés helyben történik.
 *
 * KORLÁT: a képernyőkép készítése Android 11 (API 30) felett érhető el.
 * Régebbi rendszeren ezt jelezzük a felhasználónak.
 */
class ScreenReaderImageReader(private val service: AccessibilityService) {

    private val ocr = TextRecognitionEngine()

    fun isAvailable(): Boolean = Build.VERSION.SDK_INT >= Build.VERSION_CODES.R

    /**
     * A megadott elem területének felolvasása.
     * @param onResult a felismert szöveg, vagy null ha nincs rajta olvasható
     */
    fun readImage(node: AccessibilityNodeInfo?, onResult: (String?) -> Unit) {
        if (!isAvailable()) {
            onResult(null)
            return
        }
        val bounds = Rect().also { node?.getBoundsInScreen(it) }
        try {
            service.takeScreenshot(
                android.view.Display.DEFAULT_DISPLAY,
                { it.run() },
                object : AccessibilityService.TakeScreenshotCallback {
                    override fun onSuccess(result: AccessibilityService.ScreenshotResult) {
                        val bitmap = toBitmap(result)
                        if (bitmap == null) {
                            onResult(null)
                            return
                        }
                        val cropped = cropTo(bitmap, bounds)
                        ocr.recognize(
                            bitmap = cropped,
                            onResult = { text -> onResult(text.trim().takeIf { it.isNotBlank() }) },
                            onError = { onResult(null) }
                        )
                    }

                    override fun onFailure(errorCode: Int) {
                        android.util.Log.w(
                            ScreenReaderPrefs.TAG,
                            "kepernyokep sikertelen, hibakod=$errorCode"
                        )
                        onResult(null)
                    }
                }
            )
        } catch (e: Exception) {
            android.util.Log.w(ScreenReaderPrefs.TAG, "kepolvasas hiba: ${e.message}")
            onResult(null)
        }
    }

    /**
     * SZÍNMINTA az elem területéről.
     * Ugyanaz a képernyőkép-készítés, mint a képfelolvasásnál, csak itt nem
     * szöveget keresünk, hanem a színeket elemezzük.
     */
    fun sampleColors(
        node: AccessibilityNodeInfo?,
        onResult: (ScreenReaderColors.ColorReading?) -> Unit
    ) {
        if (!isAvailable()) {
            onResult(null)
            return
        }
        val bounds = Rect().also { node?.getBoundsInScreen(it) }
        try {
            service.takeScreenshot(
                android.view.Display.DEFAULT_DISPLAY,
                { it.run() },
                object : AccessibilityService.TakeScreenshotCallback {
                    override fun onSuccess(result: AccessibilityService.ScreenshotResult) {
                        val bitmap = toBitmap(result)
                        if (bitmap == null) {
                            onResult(null)
                            return
                        }
                        val cropped = cropTo(bitmap, bounds)
                        onResult(
                            try {
                                ScreenReaderColors.analyze(cropped)
                            } catch (_: Exception) {
                                null
                            }
                        )
                    }

                    override fun onFailure(errorCode: Int) {
                        onResult(null)
                    }
                }
            )
        } catch (_: Exception) {
            onResult(null)
        }
    }

    private fun toBitmap(result: AccessibilityService.ScreenshotResult): Bitmap? = try {
        val buffer = result.hardwareBuffer
        val bitmap = Bitmap.wrapHardwareBuffer(buffer, result.colorSpace)
            ?.copy(Bitmap.Config.ARGB_8888, false)
        buffer.close()
        bitmap
    } catch (e: Exception) {
        android.util.Log.w(ScreenReaderPrefs.TAG, "bitmap keszites hiba: ${e.message}")
        null
    }

    /**
     * Kivágás az elem területére. Kis ráhagyással dolgozunk, mert a szöveg
     * gyakran épp a széleknél kezdődik. Ha az elem érvénytelen vagy túl kicsi,
     * a TELJES képernyőt olvassuk — az is többet ér a semminél.
     */
    private fun cropTo(source: Bitmap, bounds: Rect): Bitmap {
        val pad = 8
        val left = (bounds.left - pad).coerceIn(0, source.width - 1)
        val top = (bounds.top - pad).coerceIn(0, source.height - 1)
        val right = (bounds.right + pad).coerceIn(left + 1, source.width)
        val bottom = (bounds.bottom + pad).coerceIn(top + 1, source.height)
        val w = right - left
        val h = bottom - top
        if (w < 24 || h < 24) return source
        return try {
            Bitmap.createBitmap(source, left, top, w, h)
        } catch (_: Exception) {
            source
        }
    }

    fun release() {
        try {
            ocr.close()
        } catch (_: Exception) {
        }
    }
}
