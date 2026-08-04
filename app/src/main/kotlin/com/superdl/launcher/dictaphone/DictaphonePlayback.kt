package com.superdl.launcher.dictaphone

import android.content.Context
import android.media.MediaPlayer

object DictaphonePlayback {

    private var player: MediaPlayer? = null

    fun isPlaying(): Boolean = player?.isPlaying == true

    fun play(context: Context, entry: DictaphoneRecordingEntry, onDone: (() -> Unit)? = null) {
        stop()
        try {
            player = MediaPlayer().apply {
                setDataSource(entry.file.absolutePath)
                setOnCompletionListener {
                    stop()
                    onDone?.invoke()
                }
                setOnErrorListener { _, _, _ ->
                    stop()
                    onDone?.invoke()
                    true
                }
                prepare()
                start()
            }
        } catch (_: Exception) {
            stop()
            onDone?.invoke()
        }
    }

    fun stop() {
        try {
            player?.stop()
            player?.release()
        } catch (_: Exception) {
        }
        player = null
    }
}