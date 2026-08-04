package com.superdl.launcher.camera

import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.view.PreviewView
import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit

object CameraStabilityHelper {

    fun configurePreviewView(previewView: PreviewView) {
        previewView.implementationMode = PreviewView.ImplementationMode.COMPATIBLE
        previewView.scaleType = PreviewView.ScaleType.FIT_CENTER
    }

    fun buildLightPreview(surfaceProvider: Preview.SurfaceProvider): Preview =
        Preview.Builder()
            .setResolutionSelector(FaceCameraAnalysisConfig.previewResolutionSelector())
            .build()
            .also { it.setSurfaceProvider(surfaceProvider) }

    fun buildLightImageAnalysis(): ImageAnalysis.Builder =
        FaceCameraAnalysisConfig.imageAnalysisBuilder()

    fun shutdownExecutor(executor: ExecutorService) {
        try {
            executor.shutdown()
            if (!executor.awaitTermination(2, TimeUnit.SECONDS)) {
                executor.shutdownNow()
            }
        } catch (_: Exception) {
            executor.shutdownNow()
        }
    }
}