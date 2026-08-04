package com.superdl.launcher.podcast

import android.media.AudioAttributes
import android.media.MediaPlayer
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.superdl.launcher.R
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.music.MusicPlayerPrefs
import com.superdl.launcher.tts.TtsManager

/**
 * Podcast-lejátszó, a zenelejátszóval azonos fa-menüs elven:
 * fel/le a vezérlők között, jobbra aktivál, balra kilép (és leáll).
 *
 * Podcast-specifikus extrák:
 *  - pozíció-memória: ahol abbahagytad, onnan folytatja
 *  - lejátszási sebesség (1x / 1.25x / 1.5x / 2x)
 *  - alvás-időzítő (15/30/60 perc, vagy ki)
 */
class PodcastPlayerActivity : AppCompatActivity() {

    private lateinit var tvTitle: TextView
    private lateinit var tvStatus: TextView
    private lateinit var tvPosition: TextView
    private lateinit var tvHint: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gestureListener: SwipeGestureListener

    private var mediaPlayer: MediaPlayer? = null
    private var paused = false
    private var prepared = false
    private var episode: PodcastEpisode? = null

    private var seekStepSec = 30
    private var speed = 1.0f
    private var sleepTimerRunnable: Runnable? = null
    private var sleepMinutes = 0

    private val handler = Handler(Looper.getMainLooper())

    private enum class ControlItem(val label: String) {
        PLAY_PAUSE("Szünet vagy folytatás"),
        SEEK_FORWARD("Előre tekerés"),
        SEEK_BACKWARD("Vissza tekerés"),
        POSITION("Hol tartok"),
        SPEED("Lejátszási sebesség"),
        SLEEP_TIMER("Alvás időzítő"),
        DESCRIPTION("Leírás felolvasása"),
        STOP("Lejátszás leállítása")
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
        seekStepSec = MusicPlayerPrefs.getSeekStep(this)
        speed = PodcastStore.getSpeed(this)

        episode = PodcastEpisodeHolder.current
        val ep = episode
        if (ep == null) {
            tts.speakThen("Nincs lejátszható adás.") { finish() }
            return
        }

        tvTitle.text = ep.title
        tvPosition.text = ep.podcastTitle.ifBlank { "Podcast" }
        tvStatus.text = getString(R.string.player_loading)

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = { sounds.play(SoundType.SWIPE_UP); navigateMenu(-1) },
            onSwipeDown = { sounds.play(SoundType.SWIPE_DOWN); navigateMenu(+1) },
            onSwipeRight = { sounds.play(SoundType.SWIPE_RIGHT); activateMenuItem() },
            onSwipeLeft = { sounds.play(SoundType.SWIPE_LEFT); stopAndFinish("Lejátszás leállítva.") }
        )

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = stopAndFinish("Lejátszás leállítva.")
        })

        startPlayback(ep)
    }

    private fun startPlayback(ep: PodcastEpisode) {
        val savedPos = PodcastStore.getPosition(this, ep.positionKey())
        tts.speak(
            if (savedPos > 0) {
                "${ep.title}. Folytatás onnan ahol abbahagytad. Betöltés."
            } else {
                "${ep.title}. Betöltés."
            }
        )
        try {
            mediaPlayer = MediaPlayer().apply {
                setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                setDataSource(ep.audioUrl)
                setOnPreparedListener {
                    prepared = true
                    tvStatus.text = getString(R.string.player_playing)
                    if (savedPos > 0) seekTo(savedPos)
                    applySpeed(this)
                    start()
                    paused = false
                    tts.speak("Lejátszás. Söpörj fel-le a vezérlőkhöz.")
                }
                setOnCompletionListener {
                    // Végigért: töröljük a pozíciót, hogy legközelebb elölről induljon.
                    PodcastStore.setPosition(this@PodcastPlayerActivity, ep.positionKey(), 0)
                    stopAndFinish("Az adás véget ért.")
                }
                setOnErrorListener { _, _, _ ->
                    tts.speak("Ez az adás nem játszható le. Ellenőrizd az internetet.")
                    tvStatus.text = getString(R.string.player_error)
                    true
                }
                prepareAsync()
            }
        } catch (_: Exception) {
            tts.speak("Ez az adás nem játszható le.")
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
            ControlItem.SEEK_FORWARD -> seekBy(seekStepSec)
            ControlItem.SEEK_BACKWARD -> seekBy(-seekStepSec)
            ControlItem.POSITION -> announcePosition()
            ControlItem.SPEED -> cycleSpeed()
            ControlItem.SLEEP_TIMER -> cycleSleepTimer()
            ControlItem.DESCRIPTION -> readDescription()
            ControlItem.STOP -> stopAndFinish("Lejátszás leállítva.")
        }
    }

    private fun togglePause() {
        val player = mediaPlayer ?: return
        if (!prepared) {
            tts.speak("Az adás még töltődik.")
            return
        }
        if (paused) {
            applySpeed(player)
            player.start()
            paused = false
            tvStatus.text = getString(R.string.player_playing)
            tts.speak("Folytatás.")
        } else {
            player.pause()
            paused = true
            savePosition()
            tvStatus.text = getString(R.string.player_paused)
            tts.speak("Szünet.")
        }
    }

    private fun seekBy(deltaSec: Int) {
        val player = mediaPlayer ?: return
        if (!prepared) return
        val target = (player.currentPosition + deltaSec * 1000).coerceIn(0, player.duration)
        player.seekTo(target)
        savePosition()
        val dir = if (deltaSec > 0) "előre" else "vissza"
        tts.speak("$dir ${Math.abs(deltaSec)} másodperc. ${formatClock(target)}.")
    }

    private fun announcePosition() {
        val player = mediaPlayer ?: return
        if (!prepared) {
            tts.speak("Az adás még töltődik.")
            return
        }
        val pos = formatClock(player.currentPosition)
        val dur = formatClock(player.duration)
        val remaining = formatClock((player.duration - player.currentPosition).coerceAtLeast(0))
        tts.speak("$pos a $dur-ból. Hátra van $remaining.")
    }

    private fun cycleSpeed() {
        val speeds = PodcastStore.SPEEDS
        val idx = speeds.indexOfFirst { it == speed }.let { if (it < 0) 0 else it }
        speed = speeds[(idx + 1) % speeds.size]
        PodcastStore.setSpeed(this, speed)
        mediaPlayer?.let { if (prepared && !paused) applySpeed(it) }
        val label = when (speed) {
            1.0f -> "normál"
            1.25f -> "egy egész két öt szeres"
            1.5f -> "másfélszeres"
            else -> "kétszeres"
        }
        tts.speak("Sebesség: $label.")
    }

    private fun applySpeed(player: MediaPlayer) {
        try {
            val wasPlaying = player.isPlaying
            player.playbackParams = player.playbackParams.setSpeed(speed)
            if (!wasPlaying) player.pause()
        } catch (_: Exception) {
        }
    }

    private fun cycleSleepTimer() {
        val options = listOf(0, 15, 30, 60)
        val idx = options.indexOf(sleepMinutes).let { if (it < 0) 0 else it }
        sleepMinutes = options[(idx + 1) % options.size]
        sleepTimerRunnable?.let { handler.removeCallbacks(it) }
        if (sleepMinutes == 0) {
            tts.speak("Alvás időzítő kikapcsolva.")
            return
        }
        val r = Runnable { stopAndFinish("Alvás időzítő lejárt. Jó éjszakát.") }
        sleepTimerRunnable = r
        handler.postDelayed(r, sleepMinutes * 60_000L)
        tts.speak("Alvás időzítő: $sleepMinutes perc.")
    }

    private fun readDescription() {
        val desc = episode?.description?.trim()
        if (desc.isNullOrBlank()) {
            tts.speak("Ehhez az adáshoz nincs leírás.")
            return
        }
        tts.speak(desc.take(900))
    }

    private fun savePosition() {
        val player = mediaPlayer ?: return
        val ep = episode ?: return
        if (!prepared) return
        PodcastStore.setPosition(this, ep.positionKey(), player.currentPosition)
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean = when (keyCode) {
        KeyEvent.KEYCODE_VOLUME_UP -> {
            if (event?.repeatCount == 0) seekBy(seekStepSec)
            true
        }
        KeyEvent.KEYCODE_VOLUME_DOWN -> {
            if (event?.repeatCount == 0) seekBy(-seekStepSec)
            true
        }
        else -> super.onKeyDown(keyCode, event)
    }

    private fun formatClock(ms: Int): String {
        if (ms <= 0) return "0 másodperc"
        val totalSec = ms / 1000
        val hours = totalSec / 3600
        val mins = (totalSec % 3600) / 60
        val secs = totalSec % 60
        return when {
            hours > 0 -> "$hours óra $mins perc"
            mins > 0 -> "$mins perc $secs másodperc"
            else -> "$secs másodperc"
        }
    }

    private fun stopAndFinish(message: String) {
        savePosition()
        sleepTimerRunnable?.let { handler.removeCallbacks(it) }
        releasePlayer()
        // A kilépés NEM várhatja meg a TTS végét (hurok-bug): ismételt söprésnél
        // a mondat többször elhangzana. Beszéd elindul, kilépés azonnali.
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

    private fun applyImmersive() {
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            )
    }

    override fun onTouchEvent(event: MotionEvent): Boolean =
        gestureListener.detector.onTouchEvent(event) || super.onTouchEvent(event)

    override fun onPause() {
        super.onPause()
        savePosition()
    }

    override fun onDestroy() {
        savePosition()
        handler.removeCallbacksAndMessages(null)
        releasePlayer()
        tts.shutdown()
        sounds.release()
        super.onDestroy()
    }
}

/** Az épp lejátszandó epizód átadása a lejátszónak (intent helyett). */
object PodcastEpisodeHolder {
    @Volatile
    var current: PodcastEpisode? = null
}
