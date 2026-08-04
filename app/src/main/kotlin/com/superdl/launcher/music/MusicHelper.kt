package com.superdl.launcher.music

import android.content.Context
import android.net.Uri
import android.provider.MediaStore

object MusicHelper {

    /**
     * A telefon ÉS a memóriakártya zenéit összegyűjti a MediaStore-ból
     * (az EXTERNAL_CONTENT_URI mindkét tárhelyet lefedi).
     *
     * Ha vannak zenék a "music" nevű mappákban (pl. /storage/.../Music vagy a
     * kártyán), azok kerülnek előre – a felhasználó a saját gyűjteményét
     * várja legelöl. A cím szerint, ékezet-érzéketlenül rendezve.
     */
    fun getTracks(context: Context, limit: Int = 300): List<MusicTrack> {
        val all = mutableListOf<Pair<MusicTrack, String>>() // track + relatív útvonal (rendezéshez)
        val collection = MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
        val projection = arrayOf(
            MediaStore.Audio.Media._ID,
            MediaStore.Audio.Media.TITLE,
            MediaStore.Audio.Media.ARTIST,
            MediaStore.Audio.Media.DURATION,
            MediaStore.Audio.Media.DATA,
            MediaStore.Audio.Media.IS_MUSIC
        )
        val selection = "${MediaStore.Audio.Media.IS_MUSIC} != 0 AND ${MediaStore.Audio.Media.DURATION} > 30000"
        val sort = "${MediaStore.Audio.Media.TITLE} COLLATE NOCASE ASC"

        context.contentResolver.query(collection, projection, selection, null, sort)?.use { cursor ->
            val idIdx = cursor.getColumnIndex(MediaStore.Audio.Media._ID)
            val titleIdx = cursor.getColumnIndex(MediaStore.Audio.Media.TITLE)
            val artistIdx = cursor.getColumnIndex(MediaStore.Audio.Media.ARTIST)
            val durationIdx = cursor.getColumnIndex(MediaStore.Audio.Media.DURATION)
            val dataIdx = cursor.getColumnIndex(MediaStore.Audio.Media.DATA)
            while (cursor.moveToNext() && all.size < limit) {
                val id = cursor.getLong(idIdx)
                val title = cursor.getString(titleIdx)?.trim().orEmpty()
                if (title.isBlank()) continue
                val path = if (dataIdx >= 0) cursor.getString(dataIdx)?.lowercase().orEmpty() else ""
                val uri = Uri.withAppendedPath(collection, id.toString())
                val track = MusicTrack(
                    id = id,
                    title = title,
                    artist = cursor.getString(artistIdx)?.trim().orEmpty(),
                    durationMs = cursor.getLong(durationIdx),
                    contentUri = uri
                )
                all.add(track to path)
            }
        }

        // A "music" mappában lévő zenék előre; azon belül cím szerint.
        return all
            .sortedWith(
                compareByDescending<Pair<MusicTrack, String>> { it.second.contains("/music/") }
                    .thenBy { it.first.title.lowercase() }
            )
            .map { it.first }
    }
}
