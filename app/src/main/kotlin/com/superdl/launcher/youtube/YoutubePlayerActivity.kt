package com.superdl.launcher.youtube

import android.annotation.SuppressLint
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.webkit.JavascriptInterface
import android.webkit.WebSettings
import android.webkit.WebView
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.superdl.launcher.R
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager

/**
 * YouTube lejátszó a HIVATALOS IFrame Player API-val – bejelentkezés nélkül a
 * legstabilabb mód. A WebView betölti a YouTube saját JS-lejátszóját, amit
 * JavaScriptből vezérlünk (play/pause/tekerés/pozíció), és a lejátszó
 * állapotát egy JavaScript-hídon kapjuk vissza.
 *
 * Gesztusok:
 *  - fel: szünet / folytatás
 *  - le: pozíció bemondása (hol tartok / mennyi van hátra)
 *  - jobbra: cím és csatorna ismétlése
 *  - balra: kilépés
 * Hangerőgombok: tekerés előre/hátra (10 másodperc).
 */
class YoutubePlayerActivity : AppCompatActivity() {

    private lateinit var tvTitle: TextView
    private lateinit var tvStatus: TextView
    private lateinit var tvPosition: TextView
    private lateinit var tvHint: TextView
    private lateinit var webView: WebView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gestureListener: SwipeGestureListener
    private val mainHandler = Handler(Looper.getMainLooper())

    private lateinit var video: YoutubeVideo
    private var paused = false
    private var playbackStarted = false
    private var durationSec = 0
    private var positionSec = 0
    private var loadTimeout: Runnable? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_media_player)
        applyImmersive()

        tvTitle = findViewById(R.id.tvPlayerTitle)
        tvStatus = findViewById(R.id.tvPlayerStatus)
        tvPosition = findViewById(R.id.tvPlayerPosition)
        tvHint = findViewById(R.id.tvPlayerHint)
        webView = findViewById(R.id.webPlayerView)
        tvHint.text = "Fel: szünet. Le: hol tartok. Hangerőgomb: tekerés. Balra: kilépés."

        val videoId = intent.getStringExtra(EXTRA_VIDEO_ID).orEmpty()
        val title = intent.getStringExtra(EXTRA_TITLE).orEmpty()
        val channel = intent.getStringExtra(EXTRA_CHANNEL).orEmpty()
        val duration = intent.getIntExtra(EXTRA_DURATION, 0)
        video = YoutubeVideo(videoId, title, channel, duration)
        durationSec = duration

        tvTitle.text = title.ifBlank { "YouTube" }
        tvPosition.text = if (channel.isNotBlank()) channel else "YouTube lejátszás"
        tvStatus.text = getString(R.string.player_loading)

        tts = TtsManager(this)
        sounds = SoundFeedback(this)
        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = { sounds.play(SoundType.SWIPE_UP); togglePause() },
            onSwipeDown = { sounds.play(SoundType.SWIPE_DOWN); announcePosition() },
            onSwipeRight = { sounds.play(SoundType.SWIPE_RIGHT); tts.speak(video.speakFull()) },
            onSwipeLeft = { sounds.play(SoundType.SWIPE_LEFT); stopAndFinish("Lejátszás leállítva.") }
        )

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = stopAndFinish("Lejátszás leállítva.")
        })

        if (videoId.isBlank()) {
            tts.speakThen("A videó nem indítható.") { finish() }
            return
        }

        setupPlayer(videoId)
        tts.speak("Videó betöltése. Várj egy pillanatot.")

        // Ha 15 másodperc alatt nem indul a lejátszás, jelezzük.
        loadTimeout = Runnable {
            if (!playbackStarted && !isFinishing) {
                tvStatus.text = getString(R.string.player_error)
                tts.speak("A videó betöltése lassú vagy nem sikerült. Balra söprés a kilépéshez, vagy várj még.")
            }
        }
        mainHandler.postDelayed(loadTimeout!!, 15_000L)
    }

    @SuppressLint("SetJavaScriptEnabled", "AddJavascriptInterface")
    private fun setupPlayer(videoId: String) {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
            cacheMode = WebSettings.LOAD_DEFAULT
            userAgentString = ANDROID_USER_AGENT
        }
        webView.webChromeClient = android.webkit.WebChromeClient()
        webView.webViewClient = object : android.webkit.WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                // A hivatalos embed betöltődött; jelezzük hogy indul.
                if (!playbackStarted) {
                    playbackStarted = true
                    loadTimeout?.let { mainHandler.removeCallbacks(it) }
                    tvStatus.text = getString(R.string.player_playing)
                    tts.speak("Lejátszás: ${video.title}")
                }
            }
        }
        webView.addJavascriptInterface(JsBridge(), "AndroidBridge")
        webView.visibility = View.VISIBLE
        // Közvetlenül a hivatalos embed URL – valódi origin, a YouTube saját lejátszója.
        val url = "https://www.youtube.com/embed/$videoId?autoplay=1&playsinline=1&rel=0&fs=0"
        webView.loadUrl(url)
    }

    /** JavaScript a beágyazott lejátszó vezérléséhez (a HTML5 videó elemen keresztül). */
    private fun jsControl(script: String) {
        val wrapped = """
            (function(){
                var v = document.querySelector('video');
                if(v){ $script }
            })();
        """.trimIndent()
        webView.evaluateJavascript(wrapped, null)
    }

    /** JavaScript → Kotlin híd: a lejátszó állapotát kapjuk vissza. */
    private inner class JsBridge {
        @JavascriptInterface
        fun onPlaying(duration: Int) {
            mainHandler.post {
                durationSec = duration
                if (!playbackStarted) {
                    playbackStarted = true
                    loadTimeout?.let { mainHandler.removeCallbacks(it) }
                    tvStatus.text = getString(R.string.player_playing)
                    tts.speak("Lejátszás: ${video.title}")
                } else if (paused) {
                    paused = false
                    tvStatus.text = getString(R.string.player_playing)
                }
            }
        }

        @JavascriptInterface
        fun onPaused() {
            mainHandler.post {
                paused = true
                tvStatus.text = getString(R.string.player_paused)
            }
        }

        @JavascriptInterface
        fun onEnded() {
            mainHandler.post { stopAndFinish("A videó véget ért.") }
        }

        @JavascriptInterface
        fun onError(code: Int) {
            mainHandler.post {
                tvStatus.text = getString(R.string.player_error)
                tts.speak("Ez a videó nem játszható le beágyazva. Ez néhány videónál a feltöltő korlátozása miatt van. Balra söprés a kilépéshez.")
            }
        }

        @JavascriptInterface
        fun onPosition(posSec: Int, durSec: Int) {
            mainHandler.post {
                positionSec = posSec
                durationSec = durSec
                speakPositionNow()
            }
        }
    }

    private fun togglePause() {
        if (!playbackStarted) {
            tts.speak("A videó még töltődik.")
            return
        }
        if (paused) {
            jsControl("v.play();")
            paused = false
            tts.speak("Folytatás.")
        } else {
            jsControl("v.pause();")
            paused = true
            tts.speak("Szünet.")
        }
    }

    private fun seekBy(deltaSec: Int) {
        if (!playbackStarted) return
        jsControl("v.currentTime = Math.max(0, v.currentTime + ($deltaSec));")
        val dir = if (deltaSec > 0) "előre" else "vissza"
        tts.speak("$dir ${Math.abs(deltaSec)} másodperc.")
    }

    private fun announcePosition() {
        if (!playbackStarted) {
            tts.speak("A videó még töltődik.")
            return
        }
        webView.evaluateJavascript(
            "(function(){var v=document.querySelector('video');return v?Math.round(v.currentTime)+'/'+Math.round(v.duration):'';})();"
        ) { result ->
            val clean = result?.trim('"') ?: ""
            val parts = clean.split("/")
            if (parts.size == 2) {
                positionSec = parts[0].toIntOrNull() ?: 0
                durationSec = parts[1].toIntOrNull() ?: durationSec
            }
            speakPositionNow()
        }
    }

    private fun speakPositionNow() {
        val pos = formatClock(positionSec)
        val dur = formatClock(durationSec)
        val remaining = formatClock((durationSec - positionSec).coerceAtLeast(0))
        tts.speak("$pos a $dur-ból. Hátra van $remaining.")
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        return when (keyCode) {
            KeyEvent.KEYCODE_VOLUME_UP -> {
                if (event?.repeatCount == 0) seekBy(SEEK_STEP_SEC)
                true
            }
            KeyEvent.KEYCODE_VOLUME_DOWN -> {
                if (event?.repeatCount == 0) seekBy(-SEEK_STEP_SEC)
                true
            }
            else -> super.onKeyDown(keyCode, event)
        }
    }

    private fun formatClock(sec: Int): String {
        if (sec <= 0) return "0 másodperc"
        val mins = sec / 60
        val secs = sec % 60
        return if (mins > 0) "$mins perc $secs másodperc" else "$secs másodperc"
    }

    private fun stopAndFinish(message: String) {
        loadTimeout?.let { mainHandler.removeCallbacks(it) }
        jsControl("v.pause();")
        webView.loadUrl("about:blank")
        // Kilépés azonnal, a TTS ne blokkoljon (hurok-bug ismételt söprésnél).
        tts.speak(message)
        finish()
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
        loadTimeout?.let { mainHandler.removeCallbacks(it) }
        mainHandler.removeCallbacksAndMessages(null)
        webView.stopLoading()
        webView.destroy()
        tts.shutdown()
        sounds.release()
        super.onDestroy()
    }

    companion object {
        private const val SEEK_STEP_SEC = 10
        private const val ANDROID_USER_AGENT =
            "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"

        const val EXTRA_VIDEO_ID = "video_id"
        const val EXTRA_TITLE = "video_title"
        const val EXTRA_CHANNEL = "video_channel"
        const val EXTRA_DURATION = "video_duration"
    }
}
