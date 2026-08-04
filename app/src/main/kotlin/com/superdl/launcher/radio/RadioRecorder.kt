package com.superdl.launcher.radio

import android.content.Context
import android.util.Log
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.concurrent.thread

/**
 * Rádióadás felvétele fájlba.
 *
 * Módszer: külön HTTP-kapcsolattal ráállunk ugyanarra a stream-URL-re, mint a
 * lejátszó, és a nyers hangfolyam byte-jait fájlba írjuk, amíg a felhasználó
 * le nem állítja (vagy le nem jár az időzített slot). A lejátszó (MediaPlayer)
 * ettől függetlenül szól — a két kapcsolat nem zavarja egymást. Kis csúszás
 * lehet a hallott hang és a felvett anyag között, ami felvételnél nem gond.
 *
 * A byte-folyam nyers (jellemzően MP3 vagy AAC ADTS), amit a legtöbb lejátszó
 * gond nélkül megnyit. A kiterjesztést a stream Content-Type-jából találjuk ki.
 */
class RadioRecorder(private val context: Context) {

    @Volatile
    var isRecording: Boolean = false
        private set

    private var worker: Thread? = null
    private var outFile: File? = null
    private var connection: HttpURLConnection? = null

    /** Elindítja a felvételt. true, ha sikerült elindulni. Nem blokkol. */
    fun start(station: RadioStation): Boolean {
        if (isRecording) return false
        val target = newFileFor(station)
        outFile = target
        isRecording = true
        worker = thread(name = "RadioRecorder", isDaemon = true) {
            recordLoop(station.streamUrl, target)
        }
        return true
    }

    /** Leállítja a felvételt, és visszaadja a kész fájlt (vagy null, ha hiba volt). */
    fun stop(): File? {
        if (!isRecording) return outFile
        isRecording = false
        try {
            connection?.disconnect()
        } catch (_: Exception) {
        }
        worker?.join(3000)
        worker = null
        val f = outFile
        // Ha semmi értékelhető nem került bele, ne hagyjunk üres fájlt.
        return if (f != null && f.exists() && f.length() > 1024L) f else {
            f?.delete()
            null
        }
    }

    private fun recordLoop(streamUrl: String, target: File) {
        var conn: HttpURLConnection? = null
        try {
            conn = (URL(streamUrl).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 15_000
                readTimeout = 15_000
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", "SuperDL-Android/1.0")
            }
            connection = conn
            if (conn.responseCode !in 200..299) {
                isRecording = false
                return
            }
            conn.inputStream.use { input ->
                target.outputStream().use { output ->
                    val buffer = ByteArray(16 * 1024)
                    while (isRecording) {
                        val read = input.read(buffer)
                        if (read < 0) break
                        output.write(buffer, 0, read)
                    }
                    output.flush()
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "recordLoop failed", e)
        } finally {
            try {
                conn?.disconnect()
            } catch (_: Exception) {
            }
            isRecording = false
        }
    }

    private fun newFileFor(station: RadioStation): File {
        val stamp = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())
        val safeName = station.name.replace(Regex("[^A-Za-z0-9._-]"), "_").take(40)
        val ext = if (station.streamUrl.contains(".aac", true)) "aac" else "mp3"
        return File(dir(context), "radio-${safeName}-${stamp}.${ext}")
    }

    companion object {
        private const val TAG = "SuperDL.RadioRec"

        fun dir(context: Context): File {
            val d = File(context.getExternalFilesDir(null), "radio_recordings")
            if (!d.exists()) d.mkdirs()
            return d
        }
    }
}
