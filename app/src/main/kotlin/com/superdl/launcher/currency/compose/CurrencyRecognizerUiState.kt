package com.superdl.launcher.currency.compose

import android.graphics.RectF
import com.superdl.launcher.currency.BanknotePipelineMode

data class CurrencyRecognizerUiState(
    val statusText: String = "",
    val hintText: String = "",
    val isScanning: Boolean = false,
    val isTwoStageEnabled: Boolean = false,
    /** Prioritásos hibrid kaszkád (szín→OCR→opcionális YOLO) aktív. */
    val cascadeMode: Boolean = false,
    val yoloFallbackEnabled: Boolean = false,
    val pipelineMode: BanknotePipelineMode? = null,
    val detectionBox: RectF? = null,
    val showDetectionOverlay: Boolean = false,
    val fatalError: String? = null
)