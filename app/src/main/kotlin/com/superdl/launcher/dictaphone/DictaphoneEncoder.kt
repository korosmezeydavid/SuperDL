package com.superdl.launcher.dictaphone

import java.io.File

object DictaphoneEncoder {

    fun encode(config: DictaphoneConfig, pcmFile: File, outputFile: File): File {
        if (!pcmFile.exists() || pcmFile.length() == 0L) {
            throw DictaphoneException("Üres vagy hiányzó hangminta.")
        }
        return when (config.format) {
            DictaphoneFormat.WAV -> DictaphoneWavWriter.writeFromPcm(pcmFile, outputFile, config)
            DictaphoneFormat.MP3 -> DictaphoneMp3Encoder.encodeFromPcm(pcmFile, outputFile, config)
            DictaphoneFormat.FLAC -> DictaphoneFlacWriter.writeFromPcm(pcmFile, outputFile, config)
            DictaphoneFormat.AAC -> DictaphoneAacEncoder.encodeFromPcm(pcmFile, outputFile, config)
        }
    }
}

class DictaphoneException(message: String) : Exception(message)