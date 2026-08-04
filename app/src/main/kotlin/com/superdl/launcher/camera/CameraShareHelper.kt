package com.superdl.launcher.camera

import android.content.Context
import android.content.Intent
import android.net.Uri
import com.superdl.launcher.R

object CameraShareHelper {

    fun sharePhoto(context: Context, uri: Uri, fileName: String): Boolean {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "image/jpeg"
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_SUBJECT, fileName)
            putExtra(Intent.EXTRA_TEXT, "Super DL fénykép: $fileName")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        val chooser = Intent.createChooser(intent, context.getString(R.string.face_camera_share_chooser))
        chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(chooser)
            true
        } catch (_: Exception) {
            false
        }
    }
}