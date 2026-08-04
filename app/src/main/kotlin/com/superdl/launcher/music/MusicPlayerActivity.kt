package com.superdl.launcher.music

import android.content.Context
import android.media.AudioManager
import android.media.MediaPlayer
import android.net.Uri
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
import com.superdl.launcher.tts.TtsManager

/**
 * Vak-barát zenelejátszó, fa-struktúrás menüvel.
 *
 * A lejátszás automatikusan indul. A képernyőn egy menü van, a vezérlők
 * egymás alatt – fel/le lépkedsz köztük, jobbra aktiválod a kijelöltet,
 * balra kilépsz (és leáll a zene).
 *
 * Menüpontok: Szünet/Folytatás, Következő szám, Előző szám, Előre tekerés,
 * Vissza tekerés, Hol tartok, Lejátszás leállítása.
 *
 * A tekerés egysége és a lejátszási mód a Zene beállítások menüben állítható.
 */
class MusicPlayerActivity : AppCompatActivity() {

    private lateinit var tvTitle: TextView
    private lateinit var tvStatus: TextView
    private lateinit var tvPosition: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gestureListener: SwipeGestureListener

    private var mediaPlayer: MediaPlayer? = null
    private var paused = false
    private var equalizer: MusicEqualizer? = null

    private var playlist: List<MusicTrack> = emptyList()
    private var currentIndex = 0

    private var seekStepSec = MusicPlayerPrefs.DEFAULT_SEEK_STEP
    private var playMode = PlayMode.SEQUENTIAL

    // ==================== Audio focus (hívás, más appok hangja) ====================
    private lateinit var audioManager: AudioManager
    private var audioFocusRequest: android.media.AudioFocusRequest? = null

    // ==================== MediaSession (Bluetooth füles gombjai) ====================
    /**
     * A MediaSession az a szabványos csatorna, amin a rendszer továbbítja a
     * Bluetooth fülhallgató és a vezetékes headset gombnyomásait.
     *
     * FONTOS: a NATÍV android.media.session.MediaSession-t használjuk, nem a
     * régi support-könyvtárbelit (MediaSessionCompat) – az utóbbi egy olyan
     * ArrayMap-et keres, ami ebben a projektben nincs benne, és összeomlik.
     */
    private var mediaSession: android.media.session.MediaSession? = null

    private fun setupMediaSession() {
        try {
            val session = android.media.session.MediaSession(this, "SuperDL_Music")
            session.setCallback(object : android.media.session.MediaSession.Callback() {
                override fun onPlay() {
                    if (paused) togglePause()
                }

                override fun onPause() {
                    if (!paused) togglePause()
                }

                override fun onSkipToNext() {
                    skipToNext(manual = true)
                }

                override fun onSkipToPrevious() {
                    skipToPrevious()
                }

                override fun onStop() {
                    stopAndFinish("Lejátszás leállítva.")
                }

                override fun onSeekTo(pos: Long) {
                    try {
                        mediaPlayer?.seekTo(pos.toInt())
                    } catch (_: Exception) {
                    }
                }
            })
            session.isActive = true
            mediaSession = session
            updateSessionState()
        } catch (e: Exception) {
            // Ha bármiért nem megy, a lejátszó ettől még működjön tovább.
            android.util.Log.w("SuperDL.Music", "MediaSession setup failed", e)
            mediaSession = null
        }
    }

    /** A rendszer és a füles felé jelezzük, hogy épp játszunk-e. */
    private fun updateSessionState() {
        val session = mediaSession ?: return
        try {
            val state = if (paused) {
                android.media.session.PlaybackState.STATE_PAUSED
            } else {
                android.media.session.PlaybackState.STATE_PLAYING
            }
            val position = try {
                mediaPlayer?.currentPosition?.toLong() ?: 0L
            } catch (_: Exception) {
                0L
            }
            val playbackState = android.media.session.PlaybackState.Builder()
                .setActions(
                    android.media.session.PlaybackState.ACTION_PLAY or
                        android.media.session.PlaybackState.ACTION_PAUSE or
                        android.media.session.PlaybackState.ACTION_PLAY_PAUSE or
                        android.media.session.PlaybackState.ACTION_SKIP_TO_NEXT or
                        android.media.session.PlaybackState.ACTION_SKIP_TO_PREVIOUS or
                        android.media.session.PlaybackState.ACTION_STOP or
                        android.media.session.PlaybackState.ACTION_SEEK_TO
                )
                .setState(state, position, 1.0f)
                .build()
            session.setPlaybackState(playbackState)

            // A szám adatai: ez jelenik meg a füles kijelzőjén / az autórádión.
            val track = playlist.getOrNull(currentIndex) ?: return
            val duration = try {
                mediaPlayer?.duration?.toLong() ?: 0L
            } catch (_: Exception) {
                0L
            }
            val metadata = android.media.MediaMetadata.Builder()
                .putString(android.media.MediaMetadata.METADATA_KEY_TITLE, track.title)
                .putString(android.media.MediaMetadata.METADATA_KEY_ARTIST, track.artist)
                .putLong(android.media.MediaMetadata.METADATA_KEY_DURATION, duration)
                .build()
            session.setMetadata(metadata)
        } catch (e: Exception) {
            android.util.Log.w("SuperDL.Music", "updateSessionState failed", e)
        }
    }

    private fun releaseMediaSession() {
        try {
            mediaSession?.isActive = false
            mediaSession?.release()
        } catch (_: Exception) {
        }
        mediaSession = null
    }

    /** Igaz, ha a lejátszást AZ AUDIO FOCUS állította meg (nem a felhasználó). */
    private var pausedByFocusLoss = false

    /**
     * Az Android akkor szól, ha más veszi el a hangot: bejövő hívás, navigáció,
     * másik zenelejátszó. Enélkül a zenénk hívás közben is szólna.
     */
    private val focusListener = AudioManager.OnAudioFocusChangeListener { change ->
        when (change) {
            AudioManager.AUDIOFOCUS_LOSS -> {
                // Végleges elvesztés (pl. másik zenelejátszó indult): leállunk.
                if (mediaPlayer?.isPlaying == true) {
                    mediaPlayer?.pause()
                    paused = true
                    pausedByFocusLoss = false
                    tvStatus.text = getString(R.string.player_paused)
                }
            }
            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT,
            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK -> {
                // Átmeneti (hívás, navigációs bemondás): szünet, és utána folytatjuk.
                if (mediaPlayer?.isPlaying == true) {
                    mediaPlayer?.pause()
                    paused = true
                    pausedByFocusLoss = true
                    tvStatus.text = getString(R.string.player_paused)
                }
            }
            AudioManager.AUDIOFOCUS_GAIN -> {
                // Visszakaptuk (vége a hívásnak): csak akkor folytatjuk, ha
                // NEM a felhasználó állította meg.
                if (pausedByFocusLoss && paused) {
                    mediaPlayer?.start()
                    paused = false
                    pausedByFocusLoss = false
                    tvStatus.text = getString(R.string.player_playing)
                }
            }
        }
    }

    /** Audio focus kérése lejátszás előtt. Igaz, ha megkaptuk. */
    private fun requestAudioFocus(): Boolean {
        val attrs = android.media.AudioAttributes.Builder()
            .setUsage(android.media.AudioAttributes.USAGE_MEDIA)
            .setContentType(android.media.AudioAttributes.CONTENT_TYPE_MUSIC)
            .build()
        return if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            val request = android.media.AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
                .setAudioAttributes(attrs)
                .setOnAudioFocusChangeListener(focusListener)
                .setWillPauseWhenDucked(true)
                .build()
            audioFocusRequest = request
            audioManager.requestAudioFocus(request) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        } else {
            @Suppress("DEPRECATION")
            audioManager.requestAudioFocus(
                focusListener,
                AudioManager.STREAM_MUSIC,
                AudioManager.AUDIOFOCUS_GAIN
            ) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        }
    }

    private fun abandonAudioFocus() {
        try {
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                audioFocusRequest?.let { audioManager.abandonAudioFocusRequest(it) }
            } else {
                @Suppress("DEPRECATION")
                audioManager.abandonAudioFocus(focusListener)
            }
        } catch (_: Exception) {
        }
        audioFocusRequest = null
    }

    private val handler = Handler(Looper.getMainLooper())

    // A lejátszó-ablak vezérlő-menüje.
    private enum class ControlItem(val label: String) {
        PLAY_PAUSE("Szünet vagy folytatás"),
        NEXT("Következő szám"),
        PREVIOUS("Előző szám"),
        SEEK_FORWARD("Előre tekerés"),
        SEEK_BACKWARD("Vissza tekerés"),
        POSITION("Hol tartok"),
        STOP("Lejátszás leállítása")
    }

    private val menuItems = ControlItem.entries
    private var menuIndex = 0

    enum class PlayMode { SEQUENTIAL, REPEAT_ONE, REPEAT_ALL, SHUFFLE }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_media_player)
        applyImmersive()

        tvTitle = findViewById(R.id.tvPlayerTitle)
        tvStatus = findViewById(R.id.tvPlayerStatus)
        tvPosition = findViewById(R.id.tvPlayerPosition)
        findViewById<TextView>(R.id.tvPlayerHint).text =
            "Fel-le: vezérlők. Jobbra: kiválaszt. Balra: kilépés."

        tts = TtsManager(this)
        sounds = SoundFeedback(this)
        audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        // A Bluetooth füles gombjainak fogadása (lejátszás, következő, előző, stop).
        setupMediaSession()
        seekStepSec = MusicPlayerPrefs.getSeekStep(this)
        playMode = MusicPlayerPrefs.getPlayMode(this)

        playlist = MusicPlaylistHolder.tracks
        currentIndex = intent.getIntExtra(EXTRA_INDEX, 0).coerceIn(0, (playlist.size - 1).coerceAtLeast(0))

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                navigateMenu(-1)
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                navigateMenu(+1)
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                activateMenuItem()
            },
            onSwipeLeft = {
                sounds.play(SoundType.SWIPE_LEFT)
                stopAndFinish("Lejátszás leállítva.")
            }
        )

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = stopAndFinish("Lejátszás leállítva.")
        })

        if (playlist.isEmpty()) {
            tts.speakThen("Nincs lejátszható zene.") { finish() }
            return
        }
        playCurrent(announceMode = true)
    }

    private fun navigateMenu(delta: Int) {
        menuIndex = (menuIndex + delta + menuItems.size) % menuItems.size
        val item = menuItems[menuIndex]
        updateHint(item)
        tts.speak(item.label)
    }

    private fun updateHint(item: ControlItem) {
        findViewById<TextView>(R.id.tvPlayerHint).text =
            "${item.label}  •  jobbra: kiválaszt  •  balra: kilépés"
    }

    private fun activateMenuItem() {
        when (menuItems[menuIndex]) {
            ControlItem.PLAY_PAUSE -> togglePause()
            ControlItem.NEXT -> skipToNext(manual = true)
            ControlItem.PREVIOUS -> skipToPrevious()
            ControlItem.SEEK_FORWARD -> seekBy(seekStepSec)
            ControlItem.SEEK_BACKWARD -> seekBy(-seekStepSec)
            ControlItem.POSITION -> announcePosition()
            ControlItem.STOP -> stopAndFinish("Lejátszás leállítva.")
        }
    }

    /**
     * Csak akkor mond ki valamit, ha a beszéd-visszajelzés BE van kapcsolva a
     * Zene beállításokban. Az AUTOMATIKUS (maguktól induló) bemondásokra való:
     * szám címe váltáskor, szünet/folytatás, "szám elejéről".
     *
     * NEM ezt használjuk a vezérlők bemondásához (amikor a felhasználó lépked),
     * a kért pozíció-információhoz és a HIBAÜZENETEKHEZ — azoknak némítva is
     * szólniuk kell, különben a lejátszó vakon kezelhetetlen lenne.
     */
    private fun speakIfEnabled(text: String) {
        if (MusicPlayerPrefs.isSpeechEnabled(this)) tts.speak(text)
    }

    private fun currentTrack() = playlist[currentIndex]

    private fun playCurrent(announceMode: Boolean = false) {
        releasePlayer()
        val track = currentTrack()
        tvTitle.text = track.title
        tvPosition.text = track.artist.ifBlank { "Zenelejátszás" }
        tvStatus.text = getString(R.string.player_loading)
        // Audio focus kérése: enélkül a zene hívás közben is szólna.
        if (!requestAudioFocus()) {
            tts.speak("Most nem tudom lejátszani, mert más használja a hangot. Próbáld újra.")
            return
        }
        try {
            mediaPlayer = MediaPlayer().apply {
                setDataSource(this@MusicPlayerActivity, track.contentUri)
                setOnPreparedListener {
                    tvStatus.text = getString(R.string.player_playing)
                    // A mentett hangszínprofil (EQ) rákapcsolása a lejátszóra.
                    try {
                        equalizer?.release()
                        equalizer = MusicEqualizer(this@MusicPlayerActivity).also { eq ->
                            eq.attach(audioSessionId)
                        }
                    } catch (_: Exception) {
                    }
                    // FOLYTATÁS: ha erre a számra van mentett pozíció (hosszú
                    // hanganyag, amit korábban félbehagytál), oda ugrunk és
                    // felajánljuk a folytatást. A mentést fogyasztás után töröljük,
                    // hogy legközelebb ne ugorjon oda újra magától.
                    val resumeMs = MusicPlayerPrefs.getSavedPosition(
                        this@MusicPlayerActivity, track.id
                    )
                    if (resumeMs > 3000L && resumeMs < duration - 3000L) {
                        seekTo(resumeMs.toInt())
                        MusicPlayerPrefs.clearPosition(this@MusicPlayerActivity)
                    }
                    start()
                    paused = false
                    // Az új szám adatai a füles / autórádió kijelzőjére.
                    updateSessionState()
                    val modePart = if (announceMode) " ${playModeSpeak()}." else ""
                    val pos = "${currentIndex + 1} / ${playlist.size}."
                    val resumePart = if (resumeMs > 3000L && resumeMs < duration - 3000L) {
                        " Folytatás innen: ${formatClock(resumeMs.toInt())}."
                    } else ""
                    speakIfEnabled("$pos ${track.speakPreview()}$modePart$resumePart")
                }
                setOnCompletionListener { onTrackCompleted() }
                setOnErrorListener { _, _, _ ->
                    tts.speak("Ez a szám nem játszható le. Következő.")
                    skipToNext(manual = false)
                    true
                }
                prepareAsync()
            }
        } catch (_: Exception) {
            tts.speak("Ez a szám nem játszható le. Következő.")
            skipToNext(manual = false)
        }
    }

    private fun onTrackCompleted() {
        when (playMode) {
            PlayMode.REPEAT_ONE -> playCurrent()
            PlayMode.SEQUENTIAL -> {
                if (currentIndex < playlist.size - 1) {
                    currentIndex++
                    playCurrent()
                } else {
                    stopAndFinish("A lejátszási lista végére értél.")
                }
            }
            PlayMode.REPEAT_ALL -> {
                currentIndex = (currentIndex + 1) % playlist.size
                playCurrent()
            }
            PlayMode.SHUFFLE -> {
                currentIndex = playlist.indices.random()
                playCurrent()
            }
        }
    }

    private fun skipToNext(manual: Boolean) {
        when (playMode) {
            PlayMode.SHUFFLE -> currentIndex = playlist.indices.random()
            else -> currentIndex = (currentIndex + 1) % playlist.size
        }
        playCurrent()
    }

    private fun skipToPrevious() {
        // Ha 3 másodpercnél beljebb vagyunk, a szám elejére ugrunk, különben előző szám.
        val player = mediaPlayer
        if (player != null && player.currentPosition > 3000) {
            player.seekTo(0)
            speakIfEnabled("A szám elejéről.")
            return
        }
        currentIndex = (currentIndex - 1 + playlist.size) % playlist.size
        playCurrent()
    }

    private fun togglePause() {
        val player = mediaPlayer ?: return
        if (paused) {
            player.start()
            paused = false
            // A felhasználó indította: ha korábban hívás miatt állt le, azt töröljük.
            pausedByFocusLoss = false
            tvStatus.text = getString(R.string.player_playing)
            speakIfEnabled("Folytatás.")
        } else {
            player.pause()
            paused = true
            pausedByFocusLoss = false
            tvStatus.text = getString(R.string.player_paused)
            speakIfEnabled("Szünet.")
        }
        // A füles / autórádió is tudjon róla, hogy most játszunk-e.
        updateSessionState()
    }

    private fun seekBy(deltaSec: Int) {
        val player = mediaPlayer ?: return
        val duration = player.duration
        val target = (player.currentPosition + deltaSec * 1000).coerceIn(0, duration)
        player.seekTo(target)
        if (MusicPlayerPrefs.getSpeakOnSeek(this)) {
            val dir = if (deltaSec > 0) "előre" else "vissza"
            tts.speak("$dir ${Math.abs(deltaSec)} másodperc. ${formatClock(target)}.")
        }
    }

    private fun announcePosition() {
        val player = mediaPlayer ?: return
        val pos = formatClock(player.currentPosition)
        val dur = formatClock(player.duration)
        val remaining = formatClock((player.duration - player.currentPosition).coerceAtLeast(0))
        tts.speak("$pos a $dur-ból. Hátra van $remaining. Tekerés egység $seekStepSec másodperc.")
    }

    // ==================== Hangerőgomb = tekerés ====================

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        return when (keyCode) {
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
    }

    private fun playModeSpeak(): String = when (playMode) {
        PlayMode.SEQUENTIAL -> "sorban lejátszás"
        PlayMode.REPEAT_ONE -> "egy szám ismétlése"
        PlayMode.REPEAT_ALL -> "teljes lista ismétlése"
        PlayMode.SHUFFLE -> "véletlen sorrend"
    }

    private fun formatClock(ms: Int): String {
        if (ms <= 0) return "0 másodperc"
        val totalSec = ms / 1000
        val mins = totalSec / 60
        val secs = totalSec % 60
        return if (mins > 0) "$mins perc $secs másodperc" else "$secs másodperc"
    }

    private fun stopAndFinish(message: String) {
        // A pozíció mentése MÉG a lejátszó eldobása ELŐTT — hogy egy hosszú
        // hanganyag (film, hangoskönyv) folytatható legyen a következő indításkor.
        saveCurrentPosition()
        releasePlayer()
        // A füles-vezérlés csak a tényleges kilépéskor záruljon, ne számváltáskor.
        releaseMediaSession()
        // FONTOS: a finish() NEM várhatja meg a TTS végét (speakThen), mert akkor
        // a képernyő csak a mondat elhangzása után záródna. Ha a felhasználó
        // közben újra söpör, a még élő Activity újra lefuttatja ezt, és a mondat
        // 3-4-szer elhangzik ("hurok-bug"). A beszéd elindul, de a kilépés azonnali.
        // A leállítás-beszéd elhagyható, ha a felhasználó kikapcsolta.
        if (MusicPlayerPrefs.getSpeakOnStop(this)) tts.speak(message)
        finish()
    }

    /** A mostani szám aktuális pozíciójának mentése (folytatáshoz). */
    private fun saveCurrentPosition() {
        val player = mediaPlayer ?: return
        if (playlist.isEmpty()) return
        try {
            MusicPlayerPrefs.savePosition(
                this,
                currentTrack().id,
                player.currentPosition.toLong()
            )
        } catch (_: Exception) {
        }
    }

    private fun releasePlayer() {
        equalizer?.release()
        equalizer = null
        mediaPlayer?.runCatching {
            if (isPlaying) stop()
            release()
        }
        mediaPlayer = null
        // Az audio focus elengedése: enélkül más appok hangja is akadozna.
        abandonAudioFocus()
        pausedByFocusLoss = false
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

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        releasePlayer()
        releaseMediaSession()
        tts.shutdown()
        sounds.release()
        super.onDestroy()
    }

    companion object {
        const val EXTRA_INDEX = "music_index"
        // A régi belépési pontok kompatibilitása miatt megtartva (nem használt).
        const val EXTRA_URI = "music_uri"
        const val EXTRA_TITLE = "music_title"
        const val EXTRA_ARTIST = "music_artist"
    }
}
