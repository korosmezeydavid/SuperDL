package com.superdl.launcher.files

import android.content.Context
import android.provider.MediaStore
import java.io.File

/**
 * Összegyűjti a telefonon a SuperDL által készített MÉDIÁT a WiFi portál
 * "Fotók és hangok" oldalához: hangfelvételeket (diktafon, hangjegyzetek,
 * rádió-felvételek) az app saját mappáiból, és a kamerával készült fotókat a
 * MediaStore-ból (a rendszer galériájából).
 *
 * A letöltéshez minden fájlt egy TOKEN azonosít (a teljes elérési út base64-ben),
 * hogy a portál biztonságosan, csak az engedélyezett fájlokat szolgálja ki.
 */
object PortalMediaHelper {

    data class MediaEntry(
        val displayName: String,
        val category: String,     // "Hangfelvétel" / "Fotó"
        val sizeBytes: Long,
        val token: String,        // base64(elérési út) VAGY "ms:" + MediaStore id
        val mimeType: String
    )

    /** Az engedélyezett hang-mappák (csak ezekből tölthető le). */
    private fun audioDirs(context: Context): List<Pair<String, File>> = listOfNotNull(
        context.getExternalFilesDir(null)?.let { "Diktafon" to File(it, "ProfiDiktafon") },
        context.getExternalFilesDir(null)?.let { "Rádió-felvétel" to File(it, "radio_recordings") },
        "Hangjegyzet" to File(context.filesDir, "voice_notes"),
    )

    fun listAudio(context: Context): List<MediaEntry> {
        val out = mutableListOf<MediaEntry>()
        for ((label, dir) in audioDirs(context)) {
            if (!dir.exists() || !dir.isDirectory) continue
            dir.listFiles()?.filter { it.isFile }?.forEach { f ->
                out.add(
                    MediaEntry(
                        displayName = "${f.name}  ($label)",
                        category = "Hangfelvétel",
                        sizeBytes = f.length(),
                        token = "f:" + android.util.Base64.encodeToString(
                            f.absolutePath.toByteArray(), android.util.Base64.NO_WRAP or android.util.Base64.URL_SAFE
                        ),
                        mimeType = guessAudioMime(f.name)
                    )
                )
            }
        }
        return out.sortedByDescending { it.displayName }
    }

    fun listPhotos(context: Context, limit: Int = 200): List<MediaEntry> {
        val out = mutableListOf<MediaEntry>()
        val projection = arrayOf(
            MediaStore.Images.Media._ID,
            MediaStore.Images.Media.DISPLAY_NAME,
            MediaStore.Images.Media.SIZE,
            MediaStore.Images.Media.MIME_TYPE
        )
        // Csak a SuperDL által készített fotók (a fájlnév "SuperDL_" előtaggal).
        val selection = "${MediaStore.Images.Media.DISPLAY_NAME} LIKE ?"
        val args = arrayOf("SuperDL_%")
        val sort = "${MediaStore.Images.Media.DATE_ADDED} DESC"
        try {
            context.contentResolver.query(
                MediaStore.Images.Media.EXTERNAL_CONTENT_URI, projection, selection, args, sort
            )?.use { c ->
                val idCol = c.getColumnIndexOrThrow(MediaStore.Images.Media._ID)
                val nameCol = c.getColumnIndexOrThrow(MediaStore.Images.Media.DISPLAY_NAME)
                val sizeCol = c.getColumnIndexOrThrow(MediaStore.Images.Media.SIZE)
                val mimeCol = c.getColumnIndexOrThrow(MediaStore.Images.Media.MIME_TYPE)
                var count = 0
                while (c.moveToNext() && count < limit) {
                    val id = c.getLong(idCol)
                    out.add(
                        MediaEntry(
                            displayName = c.getString(nameCol) ?: "kép_$id",
                            category = "Fotó",
                            sizeBytes = c.getLong(sizeCol),
                            token = "ms:$id",
                            mimeType = c.getString(mimeCol) ?: "image/jpeg"
                        )
                    )
                    count++
                }
            }
        } catch (_: Exception) {
        }
        return out
    }

    /**
     * Egy token feloldása letölthető bájtokká. Visszaadja a (bájtok, név, mime)
     * hármast, vagy null ha nem található / nem engedélyezett.
     */
    fun resolveToken(context: Context, token: String): Triple<ByteArray, String, String>? {
        return try {
            when {
                token.startsWith("f:") -> {
                    val path = String(
                        android.util.Base64.decode(
                            token.removePrefix("f:"),
                            android.util.Base64.NO_WRAP or android.util.Base64.URL_SAFE
                        )
                    )
                    // Biztonság: csak az engedélyezett mappákból.
                    val allowed = audioDirs(context).any { (_, dir) ->
                        path.startsWith(dir.absolutePath)
                    }
                    if (!allowed) return null
                    val f = File(path)
                    if (!f.exists() || !f.isFile) return null
                    Triple(f.readBytes(), f.name, guessAudioMime(f.name))
                }
                token.startsWith("ms:") -> {
                    val id = token.removePrefix("ms:").toLongOrNull() ?: return null
                    val uri = android.content.ContentUris.withAppendedId(
                        MediaStore.Images.Media.EXTERNAL_CONTENT_URI, id
                    )
                    val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                        ?: return null
                    Triple(bytes, "SuperDL_foto_$id.jpg", "image/jpeg")
                }
                else -> null
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun guessAudioMime(name: String): String = when {
        name.endsWith(".mp3", true) -> "audio/mpeg"
        name.endsWith(".m4a", true) -> "audio/mp4"
        name.endsWith(".aac", true) -> "audio/aac"
        name.endsWith(".wav", true) -> "audio/wav"
        name.endsWith(".ogg", true) -> "audio/ogg"
        else -> "application/octet-stream"
    }
}
