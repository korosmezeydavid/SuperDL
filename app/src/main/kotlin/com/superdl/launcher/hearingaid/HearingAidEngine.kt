package com.superdl.launcher.hearingaid

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.os.Build
import android.util.Log
import androidx.core.content.ContextCompat

class HearingAidEngine(private val context: Context) {

    private val processor = HearingAidProcessor()
    private var audioRecord: AudioRecord? = null
    private var audioTrack: AudioTrack? = null
    private var worker: Thread? = null

    @Volatile
    private var running = false

    @Volatile
    private var lastError: String? = null

    @Volatile
    private var activeMicSource: HearingAidSettings.MicSource = HearingAidSettings.MicSource.AUTO

    fun lastErrorMessage(): String? = lastError

    fun isRunning(): Boolean = running

    fun updateSettings(settings: HearingAidSettings) {
        processor.updateSettings(settings)
    }

    fun start(settings: HearingAidSettings): Boolean {
        stop()
        lastError = null
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            lastError = "Mikrofon engedély hiányzik."
            return false
        }

        processor.updateSettings(settings)
        activeMicSource = settings.micSource
        val sampleRate = 44100
        val channelIn = AudioFormat.CHANNEL_IN_MONO
        val channelOut = AudioFormat.CHANNEL_OUT_STEREO
        val encoding = AudioFormat.ENCODING_PCM_16BIT
        val minIn = AudioRecord.getMinBufferSize(sampleRate, channelIn, encoding)
        val minOut = AudioTrack.getMinBufferSize(sampleRate, channelOut, encoding)
        if (minIn <= 0 || minOut <= 0) {
            lastError = "A hangrendszer nem támogatja a valós idejű feldolgozást."
            return false
        }

        val record = createAudioRecord(sampleRate, channelIn, encoding, minIn * 2)
            ?: return false

        val track = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setSampleRate(sampleRate)
                    .setEncoding(encoding)
                    .setChannelMask(channelOut)
                    .build()
            )
            .setTransferMode(AudioTrack.MODE_STREAM)
            .setBufferSizeInBytes(minOut * 2)
            .build()

        if (track.state != AudioTrack.STATE_INITIALIZED) {
            record.release()
            track.release()
            lastError = "Hangkimenet inicializálása sikertelen."
            return false
        }

        configureAudioRoute()
        audioRecord = record
        audioTrack = track
        running = true
        HearingAidStore.isRunning = true

        try {
            record.startRecording()
            track.play()
        } catch (e: Exception) {
            Log.e(TAG, "start failed", e)
            stop()
            lastError = "Hallás erősítő indítása sikertelen."
            return false
        }

        val frameSamples = 1024
        worker = Thread({
            val input = ShortArray(frameSamples)
            val output = ShortArray(frameSamples * 2)
            while (running) {
                val read = record.read(input, 0, input.size)
                if (read <= 0) continue
                processor.processMonoToStereo(input, output)
                track.write(output, 0, read * 2)
            }
        }, "SuperDL-HearingAid").also { it.start() }
        return true
    }

    fun stop() {
        running = false
        HearingAidStore.isRunning = false
        worker?.interrupt()
        worker = null
        try {
            audioRecord?.stop()
        } catch (_: Exception) {
        }
        try {
            audioTrack?.stop()
        } catch (_: Exception) {
        }
        audioRecord?.release()
        audioTrack?.release()
        audioRecord = null
        audioTrack = null
        restoreAudioRoute()
    }

    private fun createAudioRecord(
        sampleRate: Int,
        channelIn: Int,
        encoding: Int,
        bufferSize: Int
    ): AudioRecord? {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            lastError = "Nincs mikrofon engedély."
            return null
        }
        val sources = intArrayOf(
            MediaRecorder.AudioSource.VOICE_COMMUNICATION,
            MediaRecorder.AudioSource.MIC,
            MediaRecorder.AudioSource.CAMCORDER,
            MediaRecorder.AudioSource.DEFAULT
        )
        for (source in sources) {
            try {
                val record = AudioRecord(source, sampleRate, channelIn, encoding, bufferSize)
                if (record.state == AudioRecord.STATE_INITIALIZED) {
                    Log.i(TAG, "AudioRecord source=$source")
                    applyPreferredMic(record)
                    return record
                }
                record.release()
            } catch (e: Exception) {
                Log.w(TAG, "AudioRecord source=$source failed", e)
            }
        }
        lastError = "Nem található működő mikrofon."
        return null
    }

    /**
     * A kiválasztott mikrofon-forrás (telefon vagy fülhallgató) beállítása.
     * AUTO esetén nem avatkozunk be, a rendszer dönt.
     */
    private fun applyPreferredMic(record: AudioRecord) {
        if (activeMicSource == HearingAidSettings.MicSource.AUTO) return
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return
        try {
            val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            val inputs = audioManager.getDevices(AudioManager.GET_DEVICES_INPUTS)
            val target = when (activeMicSource) {
                HearingAidSettings.MicSource.PHONE -> inputs.firstOrNull {
                    it.type == AudioDeviceInfo.TYPE_BUILTIN_MIC
                }
                HearingAidSettings.MicSource.HEADSET -> inputs.firstOrNull {
                    it.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO ||
                        it.type == AudioDeviceInfo.TYPE_BLE_HEADSET ||
                        it.type == AudioDeviceInfo.TYPE_WIRED_HEADSET
                }
                else -> null
            }
            if (target != null) {
                val ok = record.setPreferredDevice(target)
                Log.i(TAG, "Preferred mic=${target.type} (${target.productName}) applied=$ok")
            } else {
                Log.w(TAG, "No matching input device for $activeMicSource")
            }
        } catch (e: Exception) {
            Log.w(TAG, "applyPreferredMic failed", e)
        }
    }

    private fun configureAudioRoute() {
        val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        try {
            audioManager.mode = AudioManager.MODE_IN_COMMUNICATION
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val preferred = audioManager.availableCommunicationDevices
                    .firstOrNull { device ->
                        device.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO ||
                            device.type == AudioDeviceInfo.TYPE_BLE_HEADSET ||
                            device.type == AudioDeviceInfo.TYPE_WIRED_HEADSET ||
                            device.type == AudioDeviceInfo.TYPE_WIRED_HEADPHONES
                    }
                if (preferred != null) {
                    audioManager.setCommunicationDevice(preferred)
                    Log.i(TAG, "Communication device: ${preferred.productName}")
                }
            } else {
                @Suppress("DEPRECATION")
                audioManager.isSpeakerphoneOn = false
            }
            audioManager.isMicrophoneMute = false
        } catch (e: Exception) {
            Log.w(TAG, "Audio route config failed", e)
        }
    }

    private fun restoreAudioRoute() {
        val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                audioManager.clearCommunicationDevice()
            }
            audioManager.mode = AudioManager.MODE_NORMAL
        } catch (_: Exception) {
        }
    }

    companion object {
        private const val TAG = "SuperDL-HearingAid"
    }
}