package com.superdl.launcher.dictaphone

import android.content.Context
import java.io.File

object DictaphoneLibrary {

    fun recordingsDir(context: Context): File {
        val dir = File(context.getExternalFilesDir(null), "ProfiDiktafon")
        if (!dir.exists()) dir.mkdirs()
        return dir
    }

    fun createOutputFile(context: Context, format: DictaphoneFormat): File {
        val stamp = System.currentTimeMillis()
        return File(recordingsDir(context), "felvetel_$stamp.${format.extension}")
    }

    fun listRecordings(context: Context): List<DictaphoneRecordingEntry> {
        val dir = recordingsDir(context)
        return dir.listFiles()
            ?.filter { it.isFile && it.length() > 0L }
            ?.mapNotNull { file ->
                val format = DictaphoneFormat.entries.firstOrNull { file.name.endsWith(".${it.extension}") }
                    ?: return@mapNotNull null
                DictaphoneRecordingEntry(file, file.lastModified(), format)
            }
            ?.sortedByDescending { it.createdAtMillis }
            ?: emptyList()
    }

    fun delete(entry: DictaphoneRecordingEntry): Boolean = entry.file.delete()
}