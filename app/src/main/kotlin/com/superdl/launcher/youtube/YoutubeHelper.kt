package com.superdl.launcher.youtube

import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import java.util.concurrent.atomic.AtomicInteger

object YoutubeHelper {

    private val mainHandler = Handler(Looper.getMainLooper())

    fun search(
        query: String,
        page: Int = 0,
        onResult: (YoutubeSearchPage) -> Unit,
        onError: (String) -> Unit
    ): () -> Unit {
        val generation = AtomicInteger(0)
        val token = generation.incrementAndGet()
        val worker = Thread({
            try {
                val result = YoutubeExtractor.search(query, page)
                mainHandler.post {
                    if (generation.get() != token) return@post
                    if (result.videos.isEmpty()) onError("Nincs találat: $query")
                    else onResult(result)
                }
            } catch (_: Exception) {
                mainHandler.post {
                    if (generation.get() != token) return@post
                    onError("YouTube keresés sikertelen. Ellenőrizd az internetkapcsolatot.")
                }
            }
        }, "SuperDL-YoutubeSearch")
        worker.start()
        return {
            generation.incrementAndGet()
            worker.interrupt()
        }
    }

    fun playVideo(context: Context, video: YoutubeVideo): Boolean {
        val intent = Intent(context, YoutubePlayerActivity::class.java).apply {
            putExtra(YoutubePlayerActivity.EXTRA_VIDEO_ID, video.videoId)
            putExtra(YoutubePlayerActivity.EXTRA_TITLE, video.title)
            putExtra(YoutubePlayerActivity.EXTRA_CHANNEL, video.channel)
            putExtra(YoutubePlayerActivity.EXTRA_DURATION, video.durationSeconds)
            if (context !is android.app.Activity) {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
        }
        context.startActivity(intent)
        return true
    }
}