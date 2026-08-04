package com.superdl.launcher.currency

import androidx.camera.core.Camera
import com.superdl.launcher.tools.FlashlightState

class BanknoteTorchController {

    private var camera: Camera? = null
    private var torchEnabled = false
    private var lastToggleAt = 0L
    private var announcedTorch = false

    fun attach(camera: Camera) {
        this.camera = camera
    }

    fun isTorchOn(): Boolean = torchEnabled

    fun update(metrics: BanknoteFrameGate.Metrics): Boolean {
        val now = System.currentTimeMillis()
        if (now - lastToggleAt < TOGGLE_COOLDOWN_MS) return announcedTorch

        return when {
            !torchEnabled && metrics.meanLuminance < TORCH_ON_BELOW -> {
                setTorch(true)
                lastToggleAt = now
                announcedTorch = true
                true
            }
            torchEnabled && metrics.meanLuminance > TORCH_OFF_ABOVE -> {
                setTorch(false)
                lastToggleAt = now
                announcedTorch = false
                false
            }
            else -> announcedTorch
        }
    }

    fun forceOn() {
        if (!torchEnabled) {
            setTorch(true)
            announcedTorch = true
            lastToggleAt = System.currentTimeMillis()
        }
    }

    fun release() {
        setTorch(false)
        camera = null
        announcedTorch = false
    }

    private fun setTorch(enabled: Boolean) {
        try {
            camera?.cameraControl?.enableTorch(enabled)
            torchEnabled = enabled
            FlashlightState.isOn = enabled
        } catch (_: Exception) {
            torchEnabled = false
        }
    }

    companion object {
        private const val TORCH_ON_BELOW = 0.26f
        private const val TORCH_OFF_ABOVE = 0.40f
        private const val TOGGLE_COOLDOWN_MS = 900L
    }
}