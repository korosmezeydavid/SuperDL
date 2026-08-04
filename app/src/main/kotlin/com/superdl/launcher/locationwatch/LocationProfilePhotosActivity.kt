package com.superdl.launcher.locationwatch

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.superdl.launcher.R
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager

class LocationProfilePhotosActivity : AppCompatActivity() {

    private lateinit var tvStatus: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback

    private var profile: LocationProfile? = null
    private var photoIndex = 0
    private var confirmDelete = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_location_profile_photos)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvStatus = findViewById(R.id.tvLocationPhotosStatus)
        tts = TtsManager(this)
        sounds = SoundFeedback(this)

        val profileId = intent.getStringExtra(EXTRA_PROFILE_ID).orEmpty()
        profile = LocationProfileStore.getById(this, profileId)
        if (profile == null || profile!!.referenceImagePaths.isEmpty()) {
            tts.speakThen(getString(R.string.location_photos_empty)) { finish() }
            return
        }

        val gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                cyclePhoto(-1)
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                cyclePhoto(1)
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                onConfirmAction()
            },
            onSwipeLeft = {
                sounds.play(SoundType.SWIPE_LEFT)
                if (confirmDelete) {
                    confirmDelete = false
                    refreshUi()
                    tts.speak(getString(R.string.location_photos_delete_cancelled))
                } else {
                    finishActivity()
                }
            }
        )

        findViewById<View>(R.id.locationPhotosRoot).setOnTouchListener { _, event ->
            gestureListener.detector.onTouchEvent(event)
            true
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = finishActivity()
        })

        refreshUi()
        tts.speakThen(
            getString(
                R.string.location_photos_intro,
                profile!!.name,
                profile!!.referenceImagePaths.size
            )
        ) {
            speakCurrentPhoto()
        }
    }

    private fun cyclePhoto(delta: Int) {
        val photos = profile?.referenceImagePaths.orEmpty()
        if (photos.isEmpty()) return
        confirmDelete = false
        photoIndex = (photoIndex + delta + photos.size) % photos.size
        refreshUi()
        speakCurrentPhoto()
    }

    private fun onConfirmAction() {
        val current = profile ?: return
        if (!confirmDelete) {
            confirmDelete = true
            refreshUi()
            tts.speak(getString(R.string.location_photos_delete_confirm, photoIndex + 1))
            return
        }
        val updated = LocationProfileStore.removeReferenceImage(this, current.id, photoIndex)
        if (updated == null) {
            sounds.play(SoundType.ACTION_OK)
            tts.speakThen(getString(R.string.location_photos_deleted_last, current.name)) { finish() }
            return
        }
        profile = updated
        confirmDelete = false
        sounds.play(SoundType.ACTION_OK)
        if (updated.referenceImagePaths.isEmpty()) {
            tts.speakThen(getString(R.string.location_photos_all_deleted, updated.name)) { finish() }
            return
        }
        photoIndex = photoIndex.coerceAtMost(updated.referenceImagePaths.lastIndex)
        refreshUi()
        tts.speak(
            getString(
                R.string.location_photos_deleted,
                updated.name,
                updated.referenceImagePaths.size
            )
        )
        speakCurrentPhoto()
    }

    private fun speakCurrentPhoto() {
        val photos = profile?.referenceImagePaths.orEmpty()
        if (photos.isEmpty()) return
        tts.speak(getString(R.string.location_photos_current, photoIndex + 1, photos.size))
    }

    private fun refreshUi() {
        val current = profile ?: return
        val photos = current.referenceImagePaths
        tvStatus.text = buildString {
            append(current.name)
            append("\n")
            append(getString(R.string.location_photos_current, photoIndex + 1, photos.size))
            if (confirmDelete) {
                append("\n")
                append(getString(R.string.location_photos_delete_pending))
            }
        }
    }

    private fun finishActivity() {
        tts.speakThen(getString(R.string.location_photos_exit)) { finish() }
    }

    override fun onDestroy() {
        tts.shutdown()
        sounds.release()
        super.onDestroy()
    }

    companion object {
        const val EXTRA_PROFILE_ID = "profile_id"

        fun intent(context: Context, profileId: String): Intent =
            Intent(context, LocationProfilePhotosActivity::class.java)
                .putExtra(EXTRA_PROFILE_ID, profileId)
    }
}