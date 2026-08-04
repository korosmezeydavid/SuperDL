package com.superdl.launcher.dictaphone

import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder

object DictaphoneWavWriter {

    fun writeFromPcm(pcmFile: File, outputFile: File, config: DictaphoneConfig): File {
        val pcmSize = pcmFile.length()
        val channels = config.channels.count
        val sampleRate = config.sampleRate.hz
        val bitsPerSample = 16
        val byteRate = sampleRate * channels * bitsPerSample / 8
        val blockAlign = channels * bitsPerSample / 8

        FileOutputStream(outputFile).use { out ->
            out.write("RIFF".toByteArray())
            out.write(intLE(36 + pcmSize.toInt()))
            out.write("WAVE".toByteArray())
            out.write("fmt ".toByteArray())
            out.write(intLE(16))
            out.write(shortLE(1))
            out.write(shortLE(channels))
            out.write(intLE(sampleRate))
            out.write(intLE(byteRate))
            out.write(shortLE(blockAlign))
            out.write(shortLE(bitsPerSample))
            out.write("data".toByteArray())
            out.write(intLE(pcmSize.toInt()))
            FileInputStream(pcmFile).use { input -> input.copyTo(out) }
        }
        return outputFile
    }

    private fun intLE(value: Int): ByteArray =
        ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(value).array()

    private fun shortLE(value: Int): ByteArray =
        ByteBuffer.allocate(2).order(ByteOrder.LITTLE_ENDIAN).putShort(value.toShort()).array()
}