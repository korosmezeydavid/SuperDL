package com.superdl.launcher.camera

import android.util.Size
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy

object FaceCameraAnalysisConfig {

    private val analysisSize = Size(320, 240)
    private val previewSize = Size(320, 240)

    fun imageAnalysisBuilder(): ImageAnalysis.Builder =
        ImageAnalysis.Builder()
            .setResolutionSelector(
                ResolutionSelector.Builder()
                    .setResolutionStrategy(
                        ResolutionStrategy(
                            analysisSize,
                            ResolutionStrategy.FALLBACK_RULE_CLOSEST_LOWER
                        )
                    )
                    .build()
            )
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)

    fun previewResolutionSelector(): ResolutionSelector =
        ResolutionSelector.Builder()
            .setResolutionStrategy(
                ResolutionStrategy(
                    previewSize,
                    ResolutionStrategy.FALLBACK_RULE_CLOSEST_LOWER
                )
            )
            .build()
}