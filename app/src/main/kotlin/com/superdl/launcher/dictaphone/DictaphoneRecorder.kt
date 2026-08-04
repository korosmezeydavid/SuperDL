package com.superdl.launcher.dictaphone

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import androidx.core.content.ContextCompat
import java.io.File
import java.io.FileOutputStream
import java.io.IOException

class DictaphoneRecorder(
    context: Context,
    private val config: DictaphoneConfig
) {
    private val appContext = context.applicationContext
    private var audioRecord: AudioRecord? = null
    private var effects: DictaphoneAudioEffects? = null
    private var recordingThread: Thread? = null
    private var pcmTempFile: File? = null
    private var outputStream: FileOutputStream? = null

    @Volatile
    var isPaused: Boolean = false
        private set

    @Volatile
    var isActive: Boolean = false
        private set

    fun start(outputFile: File): Boolean {
        DictaphoneStore.lastError = null
        if (ContextCompat.checkSelfPermission(appContext, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            DictaphoneStore.setError("Mikrofon engedély hiányzik.")
            return false
        }
        stopInternal(deleteTemp = true)
        val channelConfig = config.channels.inputConfig
        val encoding = AudioFormat.ENCODING_PCM_16BIT
        val bufferSize = AudioRecord.getMinBufferSize(config.sampleRate.hz, channelConfig, encoding)
        if (bufferSize <= 0) {
            DictaphoneStore.setError("A mikrofon nem támogatja a kiválasztott hangbeállítást.")
            return false
        }

        // A hangforrás a "nyers felvétel" beállítástól függ: nyers módban a
        // rendszer feldolgozatlan forrását kérjük, mert a szokásos mikrofon-
        // forráson a készülék hardveresen is szűr, amit szoftverből nem lehet
        // kikapcsolni.
        val sourceChoice = DictaphoneAudioSource.resolve(appContext, config.rawCapture)
        Log.i(TAG, "Felvetel hangforras: ${sourceChoice.label} (nyers=${sourceChoice.trulyRaw})")

        val record = AudioRecord(
            sourceChoice.source,
            config.sampleRate.hz,
            channelConfig,
            encoding,
            bufferSize * 4
        )
        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            DictaphoneStore.setError("A mikrofon inicializálása sikertelen.")
            return false
        }

        pcmTempFile = File(appContext.cacheDir, "dictaphone_${System.currentTimeMillis()}.pcm")
        outputStream = try {
            FileOutputStream(pcmTempFile)
        } catch (e: IOException) {
            Log.e(TAG, "PCM temp file open failed", e)
            record.release()
            DictaphoneStore.setError("Nincs elég tárhely a felvételhez.")
            return false
        }
        // Nyers módban SEMMILYEN effekt nem lehet aktív, akkor sem, ha a
        // zajszűrés kapcsoló véletlenül be van kapcsolva.
        effects = DictaphoneAudioEffects.apply(
            record.audioSessionId,
            config.noiseSuppressionEnabled && !config.rawCapture
        )

        audioRecord = record
        isPaused = false
        isActive = true
        try {
            record.startRecording()
        } catch (e: Exception) {
            Log.e(TAG, "AudioRecord.startRecording failed", e)
            stopInternal(deleteTemp = true)
            DictaphoneStore.setError("Felvétel indítása sikertelen.")
            return false
        }

        val captureBuffer = ByteArray(bufferSize)
        recordingThread = Thread {
            try {
                while (isActive) {
                    if (isPaused) {
                        Thread.sleep(40L)
                        continue
                    }
                    val read = record.read(captureBuffer, 0, captureBuffer.size)
                    if (read > 0) {
                        synchronized(this@DictaphoneRecorder) {
                            outputStream?.write(captureBuffer, 0, read)
                        }
                    } else if (read < 0) {
                        throw IOException("AudioRecord.read returned error code $read")
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Recording thread failed", e)
                DictaphoneStore.setError("Felvétel megszakadt: ${e.message ?: "ismeretlen hiba"}")
                isActive = false
            }
        }.also { it.start() }

        DictaphoneStore.outputFile = outputFile
        DictaphoneStore.config = config
        return true
    }

    fun pause() {
        if (!isActive || isPaused) return
        isPaused = true
    }

    fun resume() {
        if (!isActive || !isPaused) return
        isPaused = false
    }

    fun stopAndSave(): File? {
        if (!isActive) return null
        isActive = false
        isPaused = false
        recordingThread?.join(8_000L)
        recordingThread = null

        try {
            audioRecord?.stop()
        } catch (e: Exception) {
            Log.w(TAG, "AudioRecord.stop failed", e)
        }
        audioRecord?.release()
        audioRecord = null
        effects?.release()
        effects = null

        synchronized(this) {
            try {
                outputStream?.flush()
                outputStream?.close()
            } catch (e: Exception) {
                Log.w(TAG, "PCM stream close failed", e)
            }
            outputStream = null
        }

        val pcm = pcmTempFile
        val target = DictaphoneStore.outputFile
        val configSnapshot = DictaphoneStore.config ?: config
        if (pcm == null || target == null) {
            DictaphoneStore.setError("Felvétel mentése sikertelen: hiányzó fájl.")
            return null
        }
        return try {
            val saved = DictaphoneEncoder.encode(configSnapshot, pcm, target)
            pcm.delete()
            pcmTempFile = null
            saved
        } catch (e: Exception) {
            Log.e(TAG, "Encoding failed", e)
            DictaphoneStore.setError("Felvétel mentése sikertelen: ${e.message ?: "kódolási hiba"}")
            null
        } finally {
            DictaphoneStore.outputFile = null
        }
    }

    fun cancel() {
        stopInternal(deleteTemp = true)
        DictaphoneStore.outputFile?.delete()
        DictaphoneStore.outputFile = null
    }

    private fun stopInternal(deleteTemp: Boolean) {
        isActive = false
        isPaused = false
        recordingThread?.join(2_000L)
        recordingThread = null
        try {
            audioRecord?.stop()
        } catch (_: Exception) {
        }
        audioRecord?.release()
        audioRecord = null
        effects?.release()
        effects = null
        synchronized(this) {
            try {
                outputStream?.close()
            } catch (_: Exception) {
            }
            outputStream = null
        }
        if (deleteTemp) {
            pcmTempFile?.delete()
            pcmTempFile = null
        }
    }

    companion object {
        private const val TAG = "SuperDL.DictaphoneRecorder"
    }
}