package com.superdl.launcher.dictaphone

import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.min

object DictaphoneFlacWriter {

    private const val FRAME_SAMPLES = 4096

    fun writeFromPcm(pcmFile: File, outputFile: File, config: DictaphoneConfig): File {
        val channels = config.channels.count
        val sampleRate = config.sampleRate.hz
        val bytesPerSample = 2
        val frameBytes = FRAME_SAMPLES * channels * bytesPerSample

        FileOutputStream(outputFile).use { out ->
            out.write("fLaC".toByteArray())
            writeStreamInfo(out, channels, sampleRate, pcmFile.length(), bytesPerSample)

            FileInputStream(pcmFile).use { input ->
                val buffer = ByteArray(frameBytes)
                var totalSamples = 0L
                while (true) {
                    val read = input.read(buffer)
                    if (read <= 0) break
                    val samplesInFrame = read / (channels * bytesPerSample)
                    writeFrame(out, buffer, read, channels, bytesPerSample, totalSamples)
                    totalSamples += samplesInFrame
                }
            }
        }
        return outputFile
    }

    private fun writeStreamInfo(
        out: FileOutputStream,
        channels: Int,
        sampleRate: Int,
        pcmBytes: Long,
        bytesPerSample: Int
    ) {
        val block = ByteArray(34)
        block[0] = ((block.size - 1) shl 1).toByte()
        block[1] = 0
        block[8] = 0
        block[9] = channels.toByte()
        val samples = (pcmBytes / (channels * bytesPerSample)).coerceAtMost(Int.MAX_VALUE.toLong()).toInt()
        val bps = bytesPerSample * 8
        val sr = sampleRate
        block[10] = ((sr shr 12) and 0xFF).toByte()
        block[11] = ((sr shr 4) and 0xFF).toByte()
        block[12] = (((sr and 0x0F) shl 4) or ((samples ushr 28) and 0x0F)).toByte()
        block[13] = ((samples ushr 20) and 0xFF).toByte()
        block[14] = ((samples ushr 12) and 0xFF).toByte()
        block[15] = ((samples ushr 4) and 0xFF).toByte()
        block[16] = ((samples shl 4) and 0xF0).toByte()
        block[17] = 0
        block[18] = bps.toByte()
        out.write(block)
    }

    private fun writeFrame(
        out: FileOutputStream,
        pcm: ByteArray,
        pcmLen: Int,
        channels: Int,
        bytesPerSample: Int,
        sampleOffset: Long
    ) {
        val samples = pcmLen / (channels * bytesPerSample)
        val frameHeader = ByteArray(4)
        val headerValue = (0x3FFE shl 16) or (samples - 1)
        frameHeader[0] = ((headerValue shr 24) and 0xFF).toByte()
        frameHeader[1] = ((headerValue shr 16) and 0xFF).toByte()
        frameHeader[2] = ((headerValue shr 8) and 0xFF).toByte()
        frameHeader[3] = (headerValue and 0xFF).toByte()

        val subframes = ByteArrayOutput()
        for (ch in 0 until channels) {
            subframes.write(0)
            val channelData = extractChannel(pcm, pcmLen, channels, bytesPerSample, ch)
            subframes.write(channelData)
        }

        val footer = ByteArray(2)
        val crc = crc16(subframes.toByteArray())
        footer[0] = ((crc shr 8) and 0xFF).toByte()
        footer[1] = (crc and 0xFF).toByte()

        out.write(frameHeader)
        out.write(subframes.toByteArray())
        out.write(footer)
    }

    private fun extractChannel(
        pcm: ByteArray,
        pcmLen: Int,
        channels: Int,
        bytesPerSample: Int,
        channel: Int
    ): ByteArray {
        val samples = pcmLen / (channels * bytesPerSample)
        val out = ByteArray(samples * bytesPerSample)
        var outPos = 0
        for (i in 0 until samples) {
            val src = i * channels * bytesPerSample + channel * bytesPerSample
            out[outPos++] = pcm[src]
            out[outPos++] = pcm[src + 1]
        }
        return out
    }

    private fun crc16(data: ByteArray): Int {
        var crc = 0
        for (b in data) {
            crc = crc xor ((b.toInt() and 0xFF) shl 8)
            repeat(8) {
                crc = if (crc and 0x8000 != 0) (crc shl 1) xor 0x1021 else crc shl 1
            }
        }
        return crc and 0xFFFF
    }

    private class ByteArrayOutput {
        private val buffer = mutableListOf<Byte>()
        fun write(byte: Int) { buffer.add(byte.toByte()) }
        fun write(bytes: ByteArray) { bytes.forEach { buffer.add(it) } }
        fun toByteArray(): ByteArray = buffer.toByteArray()
    }
}