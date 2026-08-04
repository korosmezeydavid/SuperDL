package com.superdl.launcher.dictaphone

import com.naman14.androidlame.AndroidLame
import com.naman14.androidlame.LameBuilder
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

object DictaphoneMp3Encoder {

    fun encodeFromPcm(pcmFile: File, outputFile: File, config: DictaphoneConfig): File {
        val channels = config.channels.count
        val sampleRate = config.sampleRate.hz
        val lame = LameBuilder()
            .setInSampleRate(sampleRate)
            .setOutChannels(channels)
            .setOutBitrate(config.bitrate.kbps)
            .setOutSampleRate(sampleRate)
            .setMode(if (channels == 1) LameBuilder.Mode.MONO else LameBuilder.Mode.STEREO)
            .build()

        val bufferSize = 8192
        val pcmBuffer = ByteArray(bufferSize)
        val mp3Buffer = ByteArray(bufferSize)

        FileOutputStream(outputFile).use { out ->
            FileInputStream(pcmFile).use { input ->
                if (channels == 1) {
                    val shortBuf = ShortArray(bufferSize / 2)
                    while (true) {
                        val read = input.read(pcmBuffer)
                        if (read <= 0) break
                        val shorts = read / 2
                        ByteBuffer.wrap(pcmBuffer, 0, read).order(ByteOrder.LITTLE_ENDIAN)
                            .asShortBuffer().get(shortBuf, 0, shorts)
                        val encoded = lame.encode(shortBuf, shortBuf, shorts, mp3Buffer)
                        if (encoded > 0) out.write(mp3Buffer, 0, encoded)
                    }
                    val flush = lame.flush(mp3Buffer)
                    if (flush > 0) out.write(mp3Buffer, 0, flush)
                } else {
                    val left = ShortArray(bufferSize / 4)
                    val right = ShortArray(bufferSize / 4)
                    val temp = ShortArray(bufferSize / 2)
                    while (true) {
                        val read = input.read(pcmBuffer)
                        if (read <= 0) break
                        val frameSamples = read / 4
                        ByteBuffer.wrap(pcmBuffer, 0, read).order(ByteOrder.LITTLE_ENDIAN)
                            .asShortBuffer().get(temp, 0, frameSamples * 2)
                        for (i in 0 until frameSamples) {
                            left[i] = temp[i * 2]
                            right[i] = temp[i * 2 + 1]
                        }
                        val encoded = lame.encode(left, right, frameSamples, mp3Buffer)
                        if (encoded > 0) out.write(mp3Buffer, 0, encoded)
                    }
                    val flush = lame.flush(mp3Buffer)
                    if (flush > 0) out.write(mp3Buffer, 0, flush)
                }
            }
        }
        lame.close()
        return outputFile
    }
}