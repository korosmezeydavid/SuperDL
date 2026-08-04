package com.superdl.launcher.hearingaid

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.View
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.superdl.launcher.R
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager

class HearingAidActivity : AppCompatActivity() {

    private lateinit var tvStatus: TextView
    private lateinit var tvSetting: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gestureListener: SwipeGestureListener

    private var settings = HearingAidSettings()
    private var settingIndex = 0

    private enum class SettingField(val label: String) {
        POWER("Bekapcsolás"),
        MIC_SOURCE("Mikrofon forrás"),
        MASTER("Fő erősítés"),
        MIC("Mikrofon erősítés"),
        BASS("Mély hang"),
        MID("Közép hang"),
        TREBLE("Magas hang"),
        BALANCE("Balansz")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_hearing_aid)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvStatus = findViewById(R.id.tvHearingAidStatus)
        tvSetting = findViewById(R.id.tvHearingAidSetting)
        settings = HearingAidStore.load(this)

        tts = TtsManager(this)
        sounds = SoundFeedback(this)

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = {
                sounds.play(SoundType.SWIPE_UP)
                cycleSetting(-1)
            },
            onSwipeDown = {
                sounds.play(SoundType.SWIPE_DOWN)
                cycleSetting(1)
            },
            onSwipeRight = {
                sounds.play(SoundType.SWIPE_RIGHT)
                adjustCurrent(+1)
            },
            onSwipeLeft = {
                sounds.play(SoundType.SWIPE_LEFT)
                adjustCurrent(-1)
            }
        )

        findViewById<View>(R.id.hearingAidRoot).setOnTouchListener { _, event ->
            gestureListener.detector.onTouchEvent(event)
            true
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = finishAid()
        })

        if (!hasMicPermission()) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), REQ_MIC)
        } else {
            showIntro()
        }
        refreshUi()
    }

    private fun showIntro() {
        tts.speakThen(
            "Hallás erősítő. Valós idejű hangátvitel Bluetooth fejhallgatóval is. " +
                "Fel-le: beállítás választása. Jobbra: növelés vagy bekapcsolás. Balra: csökkentés, kikapcsolás vagy kilépés."
        ) {
            speakCurrentSetting()
        }
    }

    private fun cycleSetting(delta: Int) {
        val fields = SettingField.entries
        settingIndex = (settingIndex + delta + fields.size) % fields.size
        refreshUi()
        speakCurrentSetting()
    }

    private fun adjustCurrent(delta: Int) {
        when (SettingField.entries[settingIndex]) {
            SettingField.POWER -> {
                if (delta > 0 && !HearingAidStore.isRunning) toggleRunning()
                else if (delta < 0) {
                    if (HearingAidStore.isRunning) toggleRunning() else finishAid()
                }
                return
            }
            else -> Unit
        }
        settings = when (val field = SettingField.entries[settingIndex]) {
            SettingField.POWER -> settings
            SettingField.MIC_SOURCE -> settings.copy(
                micSource = HearingAidStore.cycleMicSource(settings.micSource)
            )
            SettingField.MASTER -> settings.copy(
                masterGain = HearingAidStore.adjustGain(settings.masterGain, delta)
            )
            SettingField.MIC -> settings.copy(
                micGain = HearingAidStore.adjustGain(settings.micGain, delta)
            )
            SettingField.BASS -> settings.copy(
                bassGain = HearingAidStore.adjustGain(settings.bassGain, delta)
            )
            SettingField.MID -> settings.copy(
                midGain = HearingAidStore.adjustGain(settings.midGain, delta)
            )
            SettingField.TREBLE -> settings.copy(
                trebleGain = HearingAidStore.adjustGain(settings.trebleGain, delta)
            )
            SettingField.BALANCE -> settings.copy(
                balance = HearingAidStore.cycleBalance(settings.balance)
            )
        }
        HearingAidStore.save(this, settings)
        if (HearingAidStore.isRunning) {
            // A mikrofon-forrás váltásához újra kell indítani a felvételt;
            // a többi beállítás menet közben is frissíthető.
            if (SettingField.entries[settingIndex] == SettingField.MIC_SOURCE) {
                HearingAidService.stop(this)
                HearingAidService.start(this)
            } else {
                HearingAidService.updateSettings(this)
            }
        }
        refreshUi()
        speakCurrentSetting()
    }

    private fun toggleRunning() {
        if (HearingAidStore.isRunning) {
            HearingAidService.stop(this)
            tts.speak("Hallás erősítő kikapcsolva.")
        } else {
            if (!hasMicPermission()) {
                ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), REQ_MIC)
                return
            }
            HearingAidService.start(this)
            tts.speak("Hallás erősítő bekapcsolva. ${settings.speakSummary()}")
        }
        refreshUi()
    }

    private fun speakCurrentSetting() {
        val field = SettingField.entries[settingIndex]
        val value = when (field) {
            SettingField.POWER -> if (HearingAidStore.isRunning) "bekapcsolva" else "kikapcsolva"
            SettingField.MIC_SOURCE -> settings.micSource.speakHu()
            SettingField.MASTER -> "${(settings.masterGain * 100).toInt()} százalék"
            SettingField.MIC -> "${(settings.micGain * 100).toInt()} százalék"
            SettingField.BASS -> "${(settings.bassGain * 100).toInt()} százalék"
            SettingField.MID -> "${(settings.midGain * 100).toInt()} százalék"
            SettingField.TREBLE -> "${(settings.trebleGain * 100).toInt()} százalék"
            SettingField.BALANCE -> settings.balance.speakHu()
        }
        tts.speak("${field.label}: $value")
    }

    private fun refreshUi() {
        val running = HearingAidStore.isRunning
        tvStatus.text = if (running) getString(R.string.hearing_aid_status_on) else getString(R.string.hearing_aid_status_off)
        val field = SettingField.entries[settingIndex]
        val value = when (field) {
            SettingField.POWER -> if (running) "BE" else "KI"
            SettingField.MIC_SOURCE -> settings.micSource.speakHu()
            SettingField.MASTER -> "${(settings.masterGain * 100).toInt()}%"
            SettingField.MIC -> "${(settings.micGain * 100).toInt()}%"
            SettingField.BASS -> "${(settings.bassGain * 100).toInt()}%"
            SettingField.MID -> "${(settings.midGain * 100).toInt()}%"
            SettingField.TREBLE -> "${(settings.trebleGain * 100).toInt()}%"
            SettingField.BALANCE -> settings.balance.speakHu()
        }
        tvSetting.text = "${field.label}: $value"
    }

    private fun finishAid() {
        tts.speak("Hallás erősítő bezárva.")
        finish()
    }

    private fun hasMicPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_MIC) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                showIntro()
            } else {
                tts.speakThen("Mikrofon engedély nélkül a hallás erősítő nem működik.") { finish() }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        refreshUi()
    }

    override fun onDestroy() {
        tts.shutdown()
        sounds.release()
        super.onDestroy()
    }

    companion object {
        private const val REQ_MIC = 4101
    }
}