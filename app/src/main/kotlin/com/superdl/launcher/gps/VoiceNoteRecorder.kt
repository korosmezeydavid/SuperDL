package com.superdl.launcher.gps

import android.content.Context
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.os.Build
import java.io.File

/**
 * Rövid hangjegyzetek rögzítése és lejátszása mentett GPS pontokhoz
 * ("hangos emlékhely"). A vak felhasználó saját hangján rögzíthet
 * eligazítást egy helyhez (pl. "a bejárat kicsit beljebb, vigyázz a lépcsőre"),
 * amit az app később, a helyhez érve lejátszik.
 *
 * Szándékosan különálló a diktafontól (DictaphoneManager): az hosszú
 * felvételekhez való foreground service-szel; ez egy egyszerű, rövid
 * jegyzet-rögzítő, ami nem ütközik a diktafon állapotával.
 */
object VoiceNoteRecorder {

    private var recorder: MediaRecorder? = null
    private var player: MediaPlayer? = null
    private var currentOutput: File? = null

    var isRecording: Boolean = false
        private set

    private fun voiceNoteDir(context: Context): File {
        val dir = File(context.filesDir, "voice_notes")
        if (!dir.exists()) dir.mkdirs()
        return dir
    }

    /** Új hangjegyzet-fájl útvonala egy pont ID-hoz. */
    private fun outputFileFor(context: Context, poiId: String): File {
        return File(voiceNoteDir(context), "poi_${poiId}_${System.currentTimeMillis()}.m4a")
    }

    /**
     * Elindítja a felvételt. Igazat ad vissza, ha sikeresen elindult.
     * A hívónak előbb ellenőriznie kell a RECORD_AUDIO engedélyt.
     */
    fun startRecording(context: Context, poiId: String): Boolean {
        if (isRecording) return false
        val output = outputFileFor(context, poiId)
        val rec = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            MediaRecorder(context)
        } else {
            @Suppress("DEPRECATION")
            MediaRecorder()
        }
        return try {
            rec.setAudioSource(MediaRecorder.AudioSource.MIC)
            rec.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            rec.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            rec.setAudioEncodingBitRate(96000)
            rec.setAudioSamplingRate(44100)
            rec.setOutputFile(output.absolutePath)
            rec.prepare()
            rec.start()
            recorder = rec
            currentOutput = output
            isRecording = true
            true
        } catch (_: Exception) {
            try {
                rec.reset()
                rec.release()
            } catch (_: Exception) {
            }
            output.delete()
            recorder = null
            currentOutput = null
            isRecording = false
            false
        }
    }

    /**
     * Leállítja és menti a felvételt. Visszaadja a mentett fájl abszolút
     * útvonalát, vagy null-t, ha hiba történt (pl. túl rövid felvétel).
     */
    fun stopRecording(): String? {
        val rec = recorder ?: return null
        val output = currentOutput
        return try {
            rec.stop()
            rec.release()
            recorder = null
            isRecording = false
            val path = output?.absolutePath
            currentOutput = null
            if (path != null && File(path).length() > 0L) path else null
        } catch (_: Exception) {
            try {
                rec.release()
            } catch (_: Exception) {
            }
            recorder = null
            isRecording = false
            output?.delete()
            currentOutput = null
            null
        }
    }

    /** Megszakítja a felvételt mentés nélkül. */
    fun cancelRecording() {
        val rec = recorder ?: return
        try {
            rec.reset()
            rec.release()
        } catch (_: Exception) {
        }
        currentOutput?.delete()
        recorder = null
        currentOutput = null
        isRecording = false
    }

    /**
     * Lejátssza a megadott hangjegyzetet. Az onComplete akkor hívódik,
     * amikor a lejátszás véget ér (vagy azonnal, ha nem sikerült elindítani).
     */
    fun play(path: String, onComplete: () -> Unit) {
        stopPlayback()
        val file = File(path)
        if (!file.exists() || file.length() == 0L) {
            onComplete()
            return
        }
        try {
            val mp = MediaPlayer()
            mp.setDataSource(path)
            mp.setOnCompletionListener {
                it.release()
                if (player === it) player = null
                onComplete()
            }
            mp.setOnErrorListener { p, _, _ ->
                p.release()
                if (player === p) player = null
                onComplete()
                true
            }
            mp.prepare()
            mp.start()
            player = mp
        } catch (_: Exception) {
            onComplete()
        }
    }

    fun stopPlayback() {
        player?.let {
            try {
                it.stop()
                it.release()
            } catch (_: Exception) {
            }
        }
        player = null
    }

    /** Törli egy hangjegyzet fájlját a lemezről. */
    fun deleteFile(path: String?) {
        if (path.isNullOrBlank()) return
        try {
            File(path).delete()
        } catch (_: Exception) {
        }
    }
}
