package com.superdl.launcher.podcast

import android.content.Context
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * Podcast-epizódok letöltése offline hallgatáshoz.
 * A hangfájlok az app saját mappájába kerülnek, a hozzájuk tartozó adatok
 * (cím, hossz, műsor) egy kis JSON-katalógusba.
 */
object PodcastDownloadHelper {

    private const val TAG = "SuperDL.PodcastDl"
    private const val PREFS = "superdl"
    private const val KEY_DOWNLOADS = "podcast_downloads"

    private fun dir(context: Context): File {
        val d = File(context.getExternalFilesDir(null), "podcast_downloads")
        if (!d.exists()) d.mkdirs()
        return d
    }

    private fun fileFor(context: Context, ep: PodcastEpisode): File {
        val safe = ep.audioUrl.hashCode().toString().replace("-", "n")
        return File(dir(context), "$safe.mp3")
    }

    fun isDownloaded(context: Context, ep: PodcastEpisode): Boolean =
        fileFor(context, ep).exists()

    /** Letölti az epizódot. Háttérszálon futtasd! */
    fun download(context: Context, ep: PodcastEpisode): Boolean {
        val target = fileFor(context, ep)
        if (target.exists()) return true
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(ep.audioUrl).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 20_000
                readTimeout = 60_000
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", "SuperDL/1.9")
            }
            if (conn.responseCode !in 200..299) return false
            conn.inputStream.use { input ->
                target.outputStream().use { output ->
                    input.copyTo(output, 64 * 1024)
                }
            }
            addToCatalog(context, ep, target.absolutePath)
            true
        } catch (e: Exception) {
            Log.w(TAG, "download failed", e)
            try {
                if (target.exists()) target.delete()
            } catch (_: Exception) {
            }
            false
        } finally {
            conn?.disconnect()
        }
    }

    /** A letöltött epizódok (a helyi fájlra mutató audioUrl-lel). */
    fun downloadedEpisodes(context: Context): List<PodcastEpisode> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_DOWNLOADS, null) ?: return emptyList()
        return try {
            val arr = JSONArray(raw)
            (0 until arr.length()).mapNotNull { i ->
                val o = arr.getJSONObject(i)
                val path = o.optString("path")
                if (path.isBlank() || !File(path).exists()) return@mapNotNull null
                PodcastEpisode(
                    title = o.optString("title"),
                    audioUrl = path,
                    durationSeconds = o.optInt("duration"),
                    publishedText = o.optString("published"),
                    description = o.optString("description"),
                    podcastTitle = o.optString("podcastTitle")
                )
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun addToCatalog(context: Context, ep: PodcastEpisode, path: String) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val raw = prefs.getString(KEY_DOWNLOADS, null)
        val arr = try {
            if (raw != null) JSONArray(raw) else JSONArray()
        } catch (_: Exception) {
            JSONArray()
        }
        arr.put(JSONObject().apply {
            put("title", ep.title)
            put("path", path)
            put("duration", ep.durationSeconds)
            put("published", ep.publishedText)
            put("description", ep.description)
            put("podcastTitle", ep.podcastTitle)
        })
        prefs.edit().putString(KEY_DOWNLOADS, arr.toString()).apply()
    }
}
