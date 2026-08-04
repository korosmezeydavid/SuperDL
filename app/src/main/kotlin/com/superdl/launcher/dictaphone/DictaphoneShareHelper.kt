package com.superdl.launcher.dictaphone

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import java.io.File

object DictaphoneShareHelper {

    fun shareViaSystem(context: Context, entry: DictaphoneRecordingEntry): Boolean {
        val file = entry.file
        if (!file.exists() || file.length() <= 0L) return false
        val uri = fileUri(context, file) ?: return false
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = entry.format.mimeType
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_SUBJECT, entry.displayName())
            putExtra(Intent.EXTRA_TEXT, "Super DL diktafon felvétel: ${entry.displayName()}")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        val chooser = Intent.createChooser(intent, "Felvétel megosztása")
        chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(chooser)
            true
        } catch (_: Exception) {
            false
        }
    }

    fun fileUri(context: Context, file: File) =
        try {
            FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        } catch (_: Exception) {
            null
        }
}