package com.superdl.launcher.radio

import android.media.AudioAttributes
import android.media.MediaPlayer
import android.os.Bundle
import android.view.MotionEvent
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.superdl.launcher.R
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager

/**
 * Internetes rádió-lejátszó, a zenelejátszó / podcast-lejátszó fa-menüs elvén:
 * fel/le a vezérlők között, jobbra aktivál, balra kilép (és leáll).
 *
 * Rádió-specifikum: ÉLŐ adás — nincs pozíció, tekerés, sebesség. Csak
 * play/szünet, állomásváltás (előző/következő), kedvencbe mentés, felvétel.
 */
class RadioPlayerActivity : AppCompatActivity() {

    private lateinit var tvTitle: TextView
    private lateinit var tvStatus: TextView
    private lateinit var tvPosition: TextView
    private lateinit var tvHint: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gestureListener: SwipeGestureListener

    private var mediaPlayer: MediaPlayer? = null
    private var prepared = false
    private var paused = false

    private var stations: List<RadioStation> = emptyList()
    private var currentIndex = 0

    private var recorder: RadioRecorder? = null

    private fun currentStation(): RadioStation? = stations.getOrNull(currentIndex)

    private enum class ControlItem(val label: String) {
        PLAY_PAUSE("Szünet vagy folytatás"),
        NEXT("Következő állomás"),
        PREVIOUS("Előző állomás"),
        SAVE("Mentés a kedvencekhez"),
        RECORD("Felvétel indítása vagy leállítása"),
        STOP("Rádió leállítása")
    }

    private val menuItems = ControlItem.entries
    private var menuIndex = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_media_player)
        applyImmersive()

        tvTitle = findViewById(R.id.tvPlayerTitle)
        tvStatus = findViewById(R.id.tvPlayerStatus)
        tvPosition = findViewById(R.id.tvPlayerPosition)
        tvHint = findViewById(R.id.tvPlayerHint)
        tvHint.text = "Fel-le: vezérlők. Jobbra: kiválaszt. Balra: kilépés."

        tts = TtsManager(this)
        sounds = SoundFeedback(this)

        stations = RadioPlaylistHolder.stations
        currentIndex = RadioPlaylistHolder.startIndex.coerceIn(0, (stations.size - 1).coerceAtLeast(0))

        if (stations.isEmpty()) {
            tts.speakThen("Nincs lejátszható állomás.") { finish() }
            return
        }

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = { sounds.play(SoundType.SWIPE_UP); navigateMenu(-1) },
            onSwipeDown = { sounds.play(SoundType.SWIPE_DOWN); navigateMenu(+1) },
            onSwipeRight = { sounds.play(SoundType.SWIPE_RIGHT); activateMenuItem() },
            onSwipeLeft = { sounds.play(SoundType.SWIPE_LEFT); stopAndFinish("Rádió leállítva.") }
        )

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = stopAndFinish("Rádió leállítva.")
        })

        playCurrent()
    }

    override fun onTouchEvent(event: MotionEvent): Boolean =
        gestureListener.detector.onTouchEvent(event) || super.onTouchEvent(event)

    private fun playCurrent() {
        val station = currentStation() ?: return
        releasePlayer()
        prepared = false
        paused = false
        tvTitle.text = station.name
        tvPosition.text = "Rádió"
        tvStatus.text = getString(R.string.player_loading)
        tts.speak("${station.name}. Betöltés.")
        // Az URL feloldása HÁTTÉRSZÁLON: ha .pls/.m3u lista, kibányásszuk belőle a
        // valódi stream-címet (a MediaPlayer a listákat nem tudja lejátszani).
        Thread {
            val resolved = RadioPlaylistResolver.resolve(station.streamUrl)
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                if (resolved == null) {
                    tts.speak("Ez az állomás most nem elérhető.")
                    return@runOnUiThread
                }
                startStream(station, resolved)
            }
        }.start()
    }

    /** A feloldott stream-URL tényleges lejátszása. */
    private fun startStream(station: RadioStation, streamUrl: String) {
        try {
            mediaPlayer = MediaPlayer().apply {
                setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                        .build()
                )
                setDataSource(streamUrl)
                setOnPreparedListener {
                    prepared = true
                    tvStatus.text = getString(R.string.player_playing)
                    start()
                    tts.speak("Szól a(z) ${station.name}.")
                }
                setOnErrorListener { _, _, _ ->
                    tts.speak("Ez az állomás most nem elérhető.")
                    true
                }
                prepareAsync()
            }
        } catch (_: Exception) {
            tts.speak("Ez az állomás most nem elérhető.")
        }
    }

    private fun navigateMenu(delta: Int) {
        menuIndex = (menuIndex + delta + menuItems.size) % menuItems.size
        val item = menuItems[menuIndex]
        tvHint.text = "${item.label}  •  jobbra: kiválaszt  •  balra: kilépés"
        tts.speak(item.label)
    }

    private fun activateMenuItem() {
        when (menuItems[menuIndex]) {
            ControlItem.PLAY_PAUSE -> togglePause()
            ControlItem.NEXT -> switchStation(+1)
            ControlItem.PREVIOUS -> switchStation(-1)
            ControlItem.SAVE -> saveCurrentToFavorites()
            ControlItem.RECORD -> toggleRecording()
            ControlItem.STOP -> stopAndFinish("Rádió leállítva.")
        }
    }

    private fun togglePause() {
        val player = mediaPlayer ?: return
        if (!prepared) {
            tts.speak("Az állomás még töltődik.")
            return
        }
        if (paused) {
            player.start()
            paused = false
            tvStatus.text = getString(R.string.player_playing)
            tts.speak("Folytatás.")
        } else {
            player.pause()
            paused = true
            tvStatus.text = getString(R.string.player_paused)
            tts.speak("Szünet.")
        }
    }

    private fun switchStation(delta: Int) {
        if (stations.size <= 1) {
            tts.speak("Nincs másik állomás.")
            return
        }
        currentIndex = (currentIndex + delta + stations.size) % stations.size
        playCurrent()
    }

    private fun saveCurrentToFavorites() {
        val station = currentStation() ?: return
        if (RadioStore.isSaved(this, station)) {
            tts.speak("Ez az állomás már a kedvenceid között van.")
            return
        }
        RadioStore.addStation(this, station)
        tts.speak("${station.name} elmentve a kedvencekhez.")
    }

    private fun toggleRecording() {
        val station = currentStation() ?: return
        val rec = recorder
        if (rec != null && rec.isRecording) {
            val file = rec.stop()
            recorder = null
            tts.speak(
                if (file != null) "Felvétel leállítva. Elmentve: ${file.name}."
                else "Felvétel leállítva."
            )
        } else {
            val newRec = RadioRecorder(this)
            val started = newRec.start(station)
            if (started) {
                recorder = newRec
                tts.speak("Felvétel elindult: ${station.name}.")
            } else {
                tts.speak("A felvételt most nem sikerült elindítani.")
            }
        }
    }

    private fun stopAndFinish(message: String) {
        // Ha épp felvétel megy, azt is lezárjuk kilépéskor.
        recorder?.let { if (it.isRecording) it.stop() }
        recorder = null
        releasePlayer()
        // A hurok-bug elkerülése: a finish() NEM várja meg a TTS végét.
        tts.speak(message)
        finish()
    }

    private fun releasePlayer() {
        mediaPlayer?.runCatching {
            if (isPlaying) stop()
            release()
        }
        mediaPlayer = null
        prepared = false
    }

    override fun onDestroy() {
        recorder?.let { if (it.isRecording) it.stop() }
        recorder = null
        releasePlayer()
        tts.shutdown()
        sounds.release()
        super.onDestroy()
    }

    private fun applyImmersive() {
        window.decorView.systemUiVisibility =
            (android.view.View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                or android.view.View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                or android.view.View.SYSTEM_UI_FLAG_FULLSCREEN)
    }
}
