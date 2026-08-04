package com.superdl.launcher

import android.Manifest
import android.content.BroadcastReceiver
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.hardware.camera2.CameraManager
import android.media.AudioManager
import android.net.Uri
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager

import android.view.View
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.superdl.launcher.book.BookBookmark
import com.superdl.launcher.book.BookEntry
import com.superdl.launcher.book.BookLibrary
import com.superdl.launcher.book.BookReader
import com.superdl.launcher.book.BookStore
import com.superdl.launcher.battery.BatteryPatrolManager
import com.superdl.launcher.patrol.PatrolStore
import com.superdl.launcher.input.NumberPadHelper
import com.superdl.launcher.input.NumberPadKey
import com.superdl.launcher.input.NumberPadPurpose
import com.superdl.launcher.input.PinPadMode
import com.superdl.launcher.lock.LockScreenActivity
import com.superdl.launcher.lock.keyguard.KeyguardPinSettings
import com.superdl.launcher.security.LockPinStore
import com.superdl.launcher.security.LockSession
import com.superdl.launcher.apps.ExternalAppHelper
import com.superdl.launcher.apps.FavoriteAppCatalog
import com.superdl.launcher.apps.FavoriteAppEntry
import com.superdl.launcher.apps.FavoriteAppsStore
import com.superdl.launcher.apps.FavoriteAppType
import com.superdl.launcher.apps.TalkBackHelper
import com.superdl.launcher.book.BookFolderHelper
import com.superdl.launcher.book.BookSearchHelper
import com.superdl.launcher.book.BookTextExtractor
import java.io.File
import com.superdl.launcher.alarm.AlarmEntry
import com.superdl.launcher.alarm.AlarmRepeatType
import com.superdl.launcher.alarm.AlarmScheduler
import com.superdl.launcher.alarm.AlarmStore
import com.superdl.launcher.sound.RingtonePickerActivity
import com.superdl.launcher.sound.RingtonePreferenceStore
import com.superdl.launcher.gps.CompassProvider
import com.superdl.launcher.gps.GnssStatusMonitor
import com.superdl.launcher.gps.GpsAccuracyRefiner
import com.superdl.launcher.gps.GpsLocationHelper
import com.superdl.launcher.gps.GpsPoi
import com.superdl.launcher.gps.GpsRadarContextAction
import com.superdl.launcher.gps.GpsRadarHelper
import com.superdl.launcher.gps.CompassScanManager
import com.superdl.launcher.gps.GpsRadarManager
import com.superdl.launcher.gps.GpsRadarStore
import com.superdl.launcher.gps.GpsStreetAnnouncer
import com.superdl.launcher.gps.GpsSurroundingsManager
import com.superdl.launcher.gps.GpsStreetHelper
import com.superdl.launcher.gps.SavedPoi
import com.superdl.launcher.gps.SavedPoiStore
import com.superdl.launcher.gps.SavedPoiContextAction
import com.superdl.launcher.gps.VoiceNoteRecorder
import com.superdl.launcher.timer.TimerEntry
import com.superdl.launcher.timer.TimerListMode
import com.superdl.launcher.timer.TimerManager
import com.superdl.launcher.timer.TimerSpeech
import com.superdl.launcher.timer.TimerStore
import com.superdl.launcher.timer.TimerUnitOption
import com.superdl.launcher.timer.VoiceDurationParser
import com.superdl.launcher.dictaphone.DictaphoneAudioEffects
import com.superdl.launcher.dictaphone.DictaphoneAudioSource
import com.superdl.launcher.dictaphone.DictaphoneCapabilities
import com.superdl.launcher.dictaphone.DictaphoneBitrate
import com.superdl.launcher.dictaphone.DictaphoneChannels
import com.superdl.launcher.dictaphone.DictaphoneFormat
import com.superdl.launcher.dictaphone.DictaphoneLibrary
import com.superdl.launcher.dictaphone.DictaphoneManager
import com.superdl.launcher.dictaphone.DictaphonePlayback
import com.superdl.launcher.dictaphone.DictaphoneRecordingEntry
import com.superdl.launcher.dictaphone.DictaphoneSampleRate
import com.superdl.launcher.dictaphone.DictaphoneSettingsOption
import com.superdl.launcher.dictaphone.DictaphoneSettingsStore
import com.superdl.launcher.dictaphone.DictaphoneSpeech
import com.superdl.launcher.call.CallHelper
import com.superdl.launcher.call.CallSession
import com.superdl.launcher.call.DialActivity
import com.superdl.launcher.call.DialerRoleHelper
import com.superdl.launcher.calllog.CallLogContextAction
import com.superdl.launcher.favorites.FavoriteEntry
import com.superdl.launcher.favorites.FavoritesListMode
import com.superdl.launcher.favorites.FavoritesStore
import com.superdl.launcher.sms.SmsContextAction
import com.superdl.launcher.calendar.CalendarAlarmAction
import com.superdl.launcher.calendar.CalendarAlertActivity
import com.superdl.launcher.calendar.CalendarAlarmReceiver
import com.superdl.launcher.calendar.CalendarAlarmService
import com.superdl.launcher.calendar.CalendarContextAction
import com.superdl.launcher.calendar.CalendarEvent
import com.superdl.launcher.calendar.CalendarHelper
import com.superdl.launcher.calendar.CalendarPreferenceStore
import com.superdl.launcher.calendar.CalendarRecurrence
import com.superdl.launcher.calendar.CalendarReminderScheduler
import com.superdl.launcher.calendar.CalendarReminderStore
import com.superdl.launcher.calllog.CallLogHelper
import com.superdl.launcher.calculator.CalculatorHelper
import com.superdl.launcher.notes.NoteEntry
import com.superdl.launcher.notes.NoteStore
import com.superdl.launcher.music.MusicHelper
import com.superdl.launcher.files.FileManagerActivity
import com.superdl.launcher.files.FileManagerHelper
import com.superdl.launcher.files.WifiPortalServer
import com.superdl.launcher.files.WifiPortalService
import com.superdl.launcher.voice.SpeechPunctuation
import com.superdl.launcher.system.UsbTransferHelper
import com.superdl.launcher.podcast.Podcast
import com.superdl.launcher.podcast.PodcastDownloadHelper
import com.superdl.launcher.podcast.PodcastEpisode
import com.superdl.launcher.podcast.PodcastEpisodeHolder
import com.superdl.launcher.podcast.PodcastHelper
import com.superdl.launcher.podcast.PodcastOpml
import com.superdl.launcher.podcast.PodcastPlayerActivity
import com.superdl.launcher.podcast.PodcastStore
import com.superdl.launcher.music.MusicEqualizer
import com.superdl.launcher.music.MusicPlayerPrefs
import com.superdl.launcher.music.MusicPlaylistHolder
import com.superdl.launcher.music.MusicPlayerActivity
import com.superdl.launcher.music.MusicTrack
import com.superdl.launcher.radio.RadioBrowserClient
import com.superdl.launcher.radio.RadioPlayerActivity
import com.superdl.launcher.radio.RadioPlaylistHolder
import com.superdl.launcher.radio.RadioRecorder
import com.superdl.launcher.radio.RadioStation
import com.superdl.launcher.radio.RadioStore
import com.superdl.launcher.weather.WeatherHelper
import com.superdl.launcher.contacts.ContactBookItem
import com.superdl.launcher.contacts.ContactContextAction
import com.superdl.launcher.contacts.ContactHelper
import com.superdl.launcher.contacts.ContactLetterIndex
import com.superdl.launcher.contacts.ContactMatch
import com.superdl.launcher.contacts.ContactRingtoneStore
import com.superdl.launcher.contacts.ContactStore
import com.superdl.launcher.contacts.ContactSyncHelper
import com.superdl.launcher.contacts.ContactSyncScheduler
import com.superdl.launcher.email.EmailAccountHelper
import com.superdl.launcher.email.EmailDiagnostics
import com.superdl.launcher.email.EmailHelper
import com.superdl.launcher.email.EmailRecipient
import com.superdl.launcher.email.EmailStore
import com.superdl.launcher.email.ImapMail
import com.superdl.launcher.email.ImapReader
import com.superdl.launcher.email.SmtpConfigStore
import com.superdl.launcher.search.ArticleTextExtractor
import com.superdl.launcher.search.SearchHelper
import com.superdl.launcher.search.SearchResult
import com.superdl.launcher.search.WikipediaHelper
import com.superdl.launcher.summary.DaySummaryHelper
import com.superdl.launcher.summary.StatusReportHelper
import com.superdl.launcher.shopping.ShoppingContextAction
import com.superdl.launcher.shopping.ShoppingItem
import com.superdl.launcher.shopping.ShoppingListContextAction
import com.superdl.launcher.shopping.ShoppingListStore
import com.superdl.launcher.weather.WeatherCityStore
import com.superdl.launcher.gps.LastLocationStore
import com.superdl.launcher.assistant.AssistantMediaButtonHandler
import com.superdl.launcher.assistant.BluetoothAssistantStore
import com.superdl.launcher.assistant.ElenaWakeHelper
import com.superdl.launcher.assistant.ElenaWakeListenService
import com.superdl.launcher.assistant.ElenaWakeStore
import com.superdl.launcher.qr.QrActionType
import com.superdl.launcher.qr.QrScanActivity
import com.superdl.launcher.settings.LauncherExitHelper
import com.superdl.launcher.setup.SetupRequirements
import com.superdl.launcher.setup.DiagnosticsReport
import com.superdl.launcher.setup.AutostartHelper
import com.superdl.launcher.settings.PermissionGuideTexts
import com.superdl.launcher.settings.PermissionGuideType
import com.superdl.launcher.callfilter.CallFilterHelper
import com.superdl.launcher.callfilter.CallFilterMode
import com.superdl.launcher.callfilter.CallFilterStore

import com.superdl.launcher.feedback.AlertSoundCategory
import com.superdl.launcher.feedback.AlertSoundPlayer
import com.superdl.launcher.feedback.AlertSoundPreset
import com.superdl.launcher.feedback.AlertSoundSettingsStore
import com.superdl.launcher.feedback.AlertSoundStore
import com.superdl.launcher.feedback.DeviceStateSoundManager
import com.superdl.launcher.feedback.GestureSoundHelper
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundTheme
import com.superdl.launcher.feedback.SoundThemeStore
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.feedback.ToggleAnnouncement
import com.superdl.launcher.tools.FlashlightState
import com.superdl.launcher.flow.AppFlow
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.color.ColorDetectorActivity
import com.superdl.launcher.games.blackjack.BlackjackActivity
import com.superdl.launcher.games.millebornes.MilleBornesActivity
import com.superdl.launcher.games.poker.PokerActivity
import com.superdl.launcher.games.uno.UnoActivity
import com.superdl.launcher.hearingaid.HearingAidActivity
import com.superdl.launcher.currency.CurrencyRecognizerActivity
import com.superdl.launcher.textreader.TextReaderActivity
import com.superdl.launcher.textreader.TextReaderMode
import com.superdl.launcher.environment.EnvironmentScannerActivity
import com.superdl.launcher.camera.CameraQualityProfile
import com.superdl.launcher.camera.CameraQualityStore
import com.superdl.launcher.camera.FaceCameraActivity
import com.superdl.launcher.light.LightDetectorActivity
import com.superdl.launcher.locationwatch.LocationProfile
import com.superdl.launcher.locationwatch.LocationProfileStore
import com.superdl.launcher.locationwatch.LocationProfilePhotosActivity
import com.superdl.launcher.locationwatch.LocationTrainerActivity
import com.superdl.launcher.locationwatch.LocationWatchActivity
import com.superdl.launcher.locationwatch.LocationWatchState
import com.superdl.launcher.cardorganizer.CardProfile
import com.superdl.launcher.cardorganizer.CardRecognizerActivity
import com.superdl.launcher.cardorganizer.CardStore
import com.superdl.launcher.cardorganizer.CardTrainerActivity
import com.superdl.launcher.gps.GpsRadarService
import com.superdl.launcher.route.GpsRouteRecording
import com.superdl.launcher.route.GpsRouteSession
import com.superdl.launcher.route.GpsRouteStore
import com.superdl.launcher.route.RouteEvent
import com.superdl.launcher.route.RouteEventType
import com.superdl.launcher.dictaphone.DictaphoneRecordingContextAction
import com.superdl.launcher.dictaphone.DictaphoneShareHelper
import com.superdl.launcher.info.DayGreetingStore
import com.superdl.launcher.info.DayInfoHelper
import com.superdl.launcher.info.InfoHelper
import com.superdl.launcher.legal.LegalSection
import com.superdl.launcher.legal.LegalTexts
import com.superdl.launcher.menu.MenuAction
import com.superdl.launcher.menu.MenuItem
import com.superdl.launcher.menu.MenuTree
import com.superdl.launcher.sms.Recipient
import com.superdl.launcher.sms.SmsHelper
import com.superdl.launcher.sms.SmsRoleHelper
import com.superdl.launcher.sms.SmsComposeActivity
import com.superdl.launcher.sms.SmsIncomingNotifier
import com.superdl.launcher.favorites.FavoriteContactCatalog
import com.superdl.launcher.favorites.FavoriteContactCandidate
import com.superdl.launcher.sms.SmsFolder
import com.superdl.launcher.sms.SmsMessage
import com.superdl.launcher.news.NewsFeed
import com.superdl.launcher.news.NewsFeedStore
import com.superdl.launcher.news.RssHelper
import com.superdl.launcher.notifications.NotificationHelper
import com.superdl.launcher.notifications.NotificationStore
import com.superdl.launcher.sos.SosPreferences
import com.superdl.launcher.sos.SosService
import com.superdl.launcher.system.ConnectivityHelper
import com.superdl.launcher.system.QuietModeHelper
import com.superdl.launcher.assistant.AssistantPrefs
import com.superdl.launcher.screen.ScreenCurtain
import com.superdl.launcher.screenreader.ScreenReaderPrefs
import com.superdl.launcher.assistant.AssistantRoleHelper
import com.superdl.launcher.assistant.SpeechContextBuilder
import com.superdl.launcher.assistant.VoiceAssistantHelper
import com.superdl.launcher.assistant.VoiceAssistantIntent
import com.superdl.launcher.navigation.NavigationHelper
import com.superdl.launcher.navigation.NavPlace
import com.superdl.launcher.transit.OsmHelper
import com.superdl.launcher.transit.TransitContextAction
import com.superdl.launcher.transit.TransitHelper
import com.superdl.launcher.transit.TransitPlace
import com.superdl.launcher.transit.TransitStopStore
import com.superdl.launcher.train.TrainContextAction
import com.superdl.launcher.train.TrainHelper
import com.superdl.launcher.train.TrainStation
import com.superdl.launcher.train.TrainStationStore
import com.superdl.launcher.tts.TtsEngineHelper
import com.superdl.launcher.tts.TtsVoiceCatalog
import com.superdl.launcher.tts.TtsVoiceOption
import com.superdl.launcher.tts.TtsManager
import com.superdl.launcher.youtube.YoutubeHelper
import com.superdl.launcher.youtube.YoutubeVideo
import com.superdl.launcher.voice.VoiceConfirmation
import com.superdl.launcher.voice.VoiceDateParser
import com.superdl.launcher.voice.VoiceInput
import com.superdl.launcher.voice.VoiceTimeParser
import com.superdl.launcher.medication.MedicationCycleType
import com.superdl.launcher.medication.MedicationTimeOfDay
import com.superdl.launcher.medication.MedicationReminder
import com.superdl.launcher.medication.MedicationScheduler
import com.superdl.launcher.medication.MedicationSearchHelper
import com.superdl.launcher.medication.MedicationSpeech
import com.superdl.launcher.medication.MedicationStore
import com.superdl.launcher.medication.MedicationWeekdays
import com.superdl.launcher.training.TrainingCurriculum
import com.superdl.launcher.training.TrainingStep

class MainActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_LAUNCH_VOICE_ASSISTANT = "launch_voice_assistant"
        const val EXTRA_ASSISTANT_FROM_KEYGUARD = "assistant_from_keyguard"
        const val EXTRA_WAKE_COMMAND = "wake_command"
        const val EXTRA_WAKE_GREETING_ONLY = "wake_greeting_only"
        const val ACTION_LAUNCH_VOICE_ASSISTANT = "com.superdl.launcher.action.LAUNCH_VOICE_ASSISTANT"
        const val ACTION_VOICE_ASSIST = "android.intent.action.VOICE_ASSIST"
        private const val TRAINING_DOUBLE_SWIPE_MS = 1500L
        private const val EXIT_DOUBLE_SWIPE_MS = 1500L

        @Volatile
        var isForeground: Boolean = false
    }

    private lateinit var tvItem: TextView
    private lateinit var tvHint: TextView
    private lateinit var tvPosition: TextView

    private lateinit var tts: TtsManager
    private lateinit var voiceInput: VoiceInput
    private lateinit var gestureListener: SwipeGestureListener
    private lateinit var sounds: SoundFeedback

    private val menuStack = ArrayDeque<List<MenuItem>>()
    private val menuIndexStack = ArrayDeque<Int>()
    private var currentMenu: List<MenuItem> = MenuTree.root
    private var currentIndex: Int = 0

    private var activeFlow: AppFlow = AppFlow.Menu
    private var vibrator: Vibrator? = null
    private var pendingVoiceAction: (() -> Unit)? = null
    private var sosCountdownActive = false
    private val countdownHandler = Handler(Looper.getMainLooper())
    private val mainHandler = Handler(Looper.getMainLooper())

    private inline fun postWhenAlive(crossinline block: () -> Unit) {
        mainHandler.post {
            if (isFinishing || isDestroyed) return@post
            block()
        }
    }
    private lateinit var bookReader: BookReader
    private lateinit var articleReader: BookReader
    private lateinit var noteReader: BookReader
    private var mediaButtonHandler: AssistantMediaButtonHandler? = null
    private val searchArticleBook = BookEntry("__search_article__", "Cikk", "txt", 0)
    private val noteReadingBook = BookEntry("__note_reading__", "Jegyzet", "txt", 0)

    private var smtpDraftUsername = ""
    private var smtpDraftPassword = ""
    private var voiceAssistantReturnPending = false
    private var assistantLockedMode = false
    private var pendingAssistantFromKeyguard = false
    private var pendingAssistantLaunch = false
    private var pendingWakeCommand: String? = null
    private var pendingWakeGreetingOnly = false
    /**
     * Igaz, amint a felhasználó először navigál a menüben. Ilyenkor a
     * késleltetett, hálózatról érkező bemondások (napi köszöntő) már nem
     * szólalnak meg – ne vágják félbe a menü-felolvasást.
     */
    private var userStartedNavigating = false
    private var pendingHotspotToggle = false

    private var lockReceiver: BroadcastReceiver? = null
    private var gpsArrivalReceiver: BroadcastReceiver? = null
    private var smsIncomingReceiver: BroadcastReceiver? = null
    private var radarCompass: CompassProvider? = null
    private var radarRefreshRunnable: Runnable? = null
    private var transitCompass: CompassProvider? = null
    private var dictaphoneElapsedRunnable: Runnable? = null
    private var pendingSmsForwardBody: String? = null
    private var pendingSmsFolderRead: SmsFolder? = null
    private var smsInboxRestore: AppFlow.SmsInbox? = null
    private var calendarEditEventId: Long? = null
    private var calendarPickPurpose: CalendarPickPurpose = CalendarPickPurpose.EDIT
    private var medicationDraftName: String? = null
    private var medicationDraftTimes: List<Pair<Int, Int>> = emptyList()
    private var medicationDraftCourseEndMillis: Long? = null
    private var alarmDraftRepeat: AlarmRepeatType = AlarmRepeatType.ONCE
    private var alarmDraftWeekDays: MutableSet<Int> = mutableSetOf()
    private var dictaphoneShareReturnBrowse: AppFlow.DictaphoneRecordingsBrowse? = null
    private var lastLeftSwipeAt = 0L
    private var lastExitConfirmSwipeAt = 0L
    private var gpsRefineCancel: (() -> Unit)? = null
    private var gnssCancel: (() -> Unit)? = null

    private val opmlImportLauncher = registerForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri == null) {
            tts.speak("OPML import megszakítva.")
            return@registerForActivityResult
        }
        try {
            val count = contentResolver.openInputStream(uri)?.use { stream ->
                NewsFeedStore.importOpml(this, stream)
            } ?: 0
            if (count > 0) {
                tts.speak("$count új hírforrás importálva OPML fájlból.")
            } else {
                tts.speak("Nem találtam importálható hírforrást az OPML fájlban.")
            }
        } catch (_: Exception) {
            tts.speak("Az OPML fájl beolvasása sikertelen.")
        }
    }

    private val callScreeningRoleLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { }

    private val dialerRoleLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        if (DialerRoleHelper.isDefaultDialer(this)) {
            tts.speak("Super DL beállítva alapértelmezett telefon alkalmazásként. A bejövő hívások száma mostantól látható.")
        } else {
            tts.speak("A Super DL még nincs alapértelmezett telefon alkalmazásként. A súgóban lépésről lépésre útmutató található.")
        }
    }

    private val assistantRoleLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        when {
            AssistantRoleHelper.isVoiceInteractionActive(this) ->
                tts.speak("Super DL asszisztens aktív. Az oldalsó gomb hosszú nyomására ${ElenaWakeHelper.ASSISTANT_NAME} indul.")

            AssistantRoleHelper.needsActivation(this) ->
                tts.speakThen(
                    "A Super DL ki lett választva, de a rendszer még nem aktiválta. " +
                        "Nyisd meg az alapértelmezett asszisztens beállítást, és válaszd újra a Super DL-t."
                ) {
                    openAssistantActivationSettings()
                }

            AssistantRoleHelper.isAssistantRoleHeld(this) ->
                tts.speak("Super DL beállítva alapértelmezett asszisztensként.")

            else ->
                tts.speak("A Super DL még nincs alapértelmezett asszisztensként beállítva. A súgóban lépésről lépésre útmutató található.")
        }
    }

    private val assistantActivationLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        activeFlow = AppFlow.Menu
        updateDisplay()
        tts.speak(AssistantRoleHelper.speakStatus(this))
    }

    private val smsRoleLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        if (SmsRoleHelper.isDefaultSmsApp(this)) {
            tts.speak(
                "Super DL beállítva alapértelmezett üzenet alkalmazásként. " +
                    "A bejövő üzeneteket az Üzenetek és E-mail menüben olvashatod."
            )
        } else {
            tts.speak("A Super DL még nincs alapértelmezett üzenet alkalmazásként. A súgóban lépésről lépésre útmutató található.")
        }
    }

    private val notificationListenerSettingsLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        activeFlow = AppFlow.Menu
        updateDisplay()
        if (NotificationHelper.isListenerEnabled(this)) {
            tts.speakAndRun("Értesítés olvasás engedélyezve.") {
                startNotificationReadFlow()
            }
        } else {
            tts.speak("Az értesítés olvasás még nincs engedélyezve. Kapcsold be a Super DL-t az értesítés hozzáférés listában.")
        }
    }

    private val launcherExitSettingsLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        activeFlow = AppFlow.Menu
        updateDisplay()
        tts.speak("Visszatértél a Super DL-be. Ha másik launchert választottál, a Home gomb onnan indul.")
    }

    private val podcastOpmlLauncher = registerForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri == null) {
            tts.speak("Nem választottál fájlt.")
            return@registerForActivityResult
        }
        Thread {
            val imported = try {
                contentResolver.openInputStream(uri)?.use { PodcastOpml.parseStream(it) } ?: emptyList()
            } catch (_: Exception) {
                emptyList()
            }
            postWhenAlive {
                if (imported.isEmpty()) {
                    tts.speak("Ebben a fájlban nem találtam podcast feliratkozásokat. Ellenőrizd, hogy O P M L fájlt választottál-e.")
                    return@postWhenAlive
                }
                var added = 0
                imported.forEach { podcast ->
                    if (!PodcastStore.isSubscribed(this, podcast)) {
                        PodcastStore.toggleSubscription(this, podcast)
                        added++
                    }
                }
                tts.speak(
                    if (added == 0) {
                        "Mind a ${imported.size} podcast már a feliratkozásaid között volt."
                    } else {
                        "$added új podcast hozzáadva a feliratkozásaidhoz."
                    }
                )
            }
        }.start()
    }

    private val ringtonePickerLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == RESULT_OK) {
            val uri = result.data?.getStringExtra(RingtonePickerActivity.EXTRA_RESULT_URI)
            val title = result.data?.getStringExtra(RingtonePickerActivity.EXTRA_RESULT_TITLE)
            RingtonePreferenceStore.setRingtone(this, uri, title)
            tts.speak("Csengőhang beállítva: ${title ?: "kiválasztott hang"}.")
        } else {
            tts.speak("A csengőhang nem változott.")
        }
    }

    private val alarmTonePickerLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == RESULT_OK && alarmToneEditId >= 0) {
            val uri = result.data?.getStringExtra(RingtonePickerActivity.EXTRA_RESULT_URI)
            val title = result.data?.getStringExtra(RingtonePickerActivity.EXTRA_RESULT_TITLE)
            val updated = AlarmStore.updateTone(this, alarmToneEditId, uri, title)
            if (updated != null) {
                AlarmScheduler.schedule(this, updated)
                tts.speak("Ébresztő hang beállítva: ${title ?: "kiválasztott hang"}.")
            } else {
                tts.speak("A hang nem változott.")
            }
        } else {
            tts.speak("A hang nem változott.")
        }
        alarmToneEditId = -1
    }

    private var contactRingtoneEditPhone: String? = null
    private var contactRingtoneEditName: String? = null

    private val contactRingtonePickerLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val phone = contactRingtoneEditPhone
        val name = contactRingtoneEditName ?: "A névjegy"
        contactRingtoneEditPhone = null
        contactRingtoneEditName = null
        if (result.resultCode == RESULT_OK && !phone.isNullOrBlank()) {
            val uri = result.data?.getStringExtra(RingtonePickerActivity.EXTRA_RESULT_URI)
            val title = result.data?.getStringExtra(RingtonePickerActivity.EXTRA_RESULT_TITLE)
            if (uri.isNullOrBlank()) {
                ContactRingtoneStore.clear(this, phone)
                tts.speak("$name mostantól az alapértelmezett csengőhanggal szól.")
            } else {
                val label = title ?: "kiválasztott hang"
                if (ContactRingtoneStore.set(this, phone, uri, label)) {
                    tts.speak("$name mostantól ezzel szól: $label.")
                } else {
                    tts.speak("A csengőhangot nem sikerült elmenteni.")
                }
            }
        } else {
            tts.speak("A csengőhang nem változott.")
        }
    }

    private val qrScanLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode != RESULT_OK) {
            if (voiceAssistantReturnPending) resumeVoiceAssistantListening()
            return@registerForActivityResult
        }
        val data = result.data ?: run {
            if (voiceAssistantReturnPending) resumeVoiceAssistantListening()
            return@registerForActivityResult
        }
        val actionName = data.getStringExtra(QrScanActivity.EXTRA_ACTION) ?: run {
            if (voiceAssistantReturnPending) resumeVoiceAssistantListening()
            return@registerForActivityResult
        }
        val payload = data.getStringExtra(QrScanActivity.EXTRA_PAYLOAD).orEmpty()
        if (QrActionType.valueOf(actionName) == QrActionType.FINISH) {
            if (voiceAssistantReturnPending) resumeVoiceAssistantListening()
            return@registerForActivityResult
        }
        handleQrFollowUp(QrActionType.valueOf(actionName), payload)
    }


    private val SOS_COUNTDOWN_SECONDS = 5
    private val PERM_REQUEST = 100
    private val REQUIRED_PERMISSIONS: Array<String> = buildList {
        add(Manifest.permission.CALL_PHONE)
        add(Manifest.permission.ANSWER_PHONE_CALLS)
        add(Manifest.permission.READ_PHONE_STATE)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            add(Manifest.permission.READ_PHONE_NUMBERS)
        }
        add(Manifest.permission.READ_CONTACTS)
        add(Manifest.permission.WRITE_CONTACTS)
        add(Manifest.permission.READ_CALL_LOG)
        add(Manifest.permission.SEND_SMS)
        add(Manifest.permission.READ_SMS)
        add(Manifest.permission.RECEIVE_SMS)
        add(Manifest.permission.ACCESS_FINE_LOCATION)
        add(Manifest.permission.CAMERA)
        add(Manifest.permission.RECORD_AUDIO)
        add(Manifest.permission.READ_CALENDAR)
        add(Manifest.permission.WRITE_CALENDAR)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            add(Manifest.permission.POST_NOTIFICATIONS)
            add(Manifest.permission.READ_MEDIA_AUDIO)
            add(Manifest.permission.NEARBY_WIFI_DEVICES)
        }
        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.P) {
            add(Manifest.permission.GET_ACCOUNTS)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            add(Manifest.permission.BLUETOOTH_CONNECT)
        }
        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.S_V2) {
            add(Manifest.permission.READ_EXTERNAL_STORAGE)
        }
    }.toTypedArray()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        )

        vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            (getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            getSystemService(VIBRATOR_SERVICE) as Vibrator
        }

        tvItem = findViewById(R.id.tvItem)
        tvHint = findViewById(R.id.tvHint)
        tvPosition = findViewById(R.id.tvPosition)

        tts = TtsManager(this)
        sounds = SoundFeedback(this)
        voiceInput = VoiceInput(this)
        bookReader = BookReader(
            context = this,
            tts = tts,
            onProgress = { chunkIndex, totalChunks, _ ->
                val book = (activeFlow as? AppFlow.BookReading)?.book ?: return@BookReader
                activeFlow = AppFlow.BookReading(
                    book = book,
                    chunkIndex = chunkIndex,
                    totalChunks = totalChunks,
                    percent = bookReader.progressPercent(),
                    paused = bookReader.isPaused
                )
                updateFlowDisplay()
            },
            onFinished = { finishBookReading("A könyv elolvasva.") },
            onError = { message -> exitBookReading(message) }
        )
        articleReader = BookReader(
            context = this,
            tts = tts,
            onProgress = { chunkIndex, totalChunks, _ ->
                val flow = activeFlow as? AppFlow.SearchArticleReading ?: return@BookReader
                activeFlow = flow.copy(
                    chunkIndex = chunkIndex,
                    totalChunks = totalChunks,
                    percent = articleReader.progressPercent()
                )
                updateFlowDisplay()
            },
            onFinished = { finishSearchArticleReading("Cikk vége.") },
            onError = { message -> exitSearchArticleReading(message) }
        )
        noteReader = BookReader(
            context = this,
            tts = tts,
            onProgress = { chunkIndex, totalChunks, _ ->
                val flow = activeFlow as? AppFlow.NoteReading ?: return@BookReader
                activeFlow = flow.copy(
                    chunkIndex = chunkIndex,
                    totalChunks = totalChunks,
                    percent = noteReader.progressPercent()
                )
                updateFlowDisplay()
            },
            onFinished = { finishNoteReading("Jegyzet vége.") },
            onError = { message -> exitNoteReading(message) }
        )

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = ::handleSwipeUp,
            onSwipeDown = ::handleSwipeDown,
            onSwipeRight = ::handleSwipeRight,
            onSwipeLeft = ::handleSwipeLeft
        )

        findViewById<View>(R.id.rootLayout).setOnTouchListener { _, event ->
            gestureListener.detector.onTouchEvent(event)
            true
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = handleSwipeLeft()
        })

        requestPermissionsIfNeeded()
        BatteryPatrolManager.start(this)
        DeviceStateSoundManager.start(this)
        GestureSoundHelper.restorePhoneRingerIfNeeded(this)
        TimerManager.resumeIfNeeded(this)
        CalendarReminderScheduler.rescheduleUpcoming(this)
        MedicationScheduler.rescheduleAll(this)
        ContactSyncScheduler.reschedule(this)
        Thread { ContactSyncHelper.syncIfNeeded(this) }.start()
        syncElenaWakeListenService()
        updateDisplay()
        val pendingCalendarAlarm = intent?.action == CalendarAlarmReceiver.ACTION_CALENDAR_ALARM
        handleCalendarAlarmIntent(intent)

        queueVoiceAssistantLaunchIfNeeded(intent)
        handleDialIntent(intent)

        if (!pendingCalendarAlarm && LockSession.needsUnlock(this) && !pendingAssistantLaunch) {
            showLockScreen()
        } else if (pendingVoiceAction != null) {
            mainHandler.postDelayed({ runPendingVoiceActionIfReady() }, 200)
        } else {
            sounds.play(SoundType.STARTUP)
            Handler(Looper.getMainLooper()).postDelayed({
                if (LockSession.needsUnlock(this)) {
                    showLockScreen()
                    return@postDelayed
                }
                if (pendingVoiceAction != null) {
                    runPendingVoiceActionIfReady()
                    return@postDelayed
                }
                if (activeFlow is AppFlow.Menu) {
                    tts.speak("${LegalTexts.APP_FULL_NAME}, ${LegalTexts.APP_SHORT_NAME} betöltve. ${speakMenuItemLabel(currentMenu[currentIndex])}")
                    if (DayGreetingStore.shouldGreetOnStartup(this)) {
                        Handler(Looper.getMainLooper()).postDelayed({ speakDayGreeting(onlyIfIdle = true) }, 2500)
                    }
                }
            }, 1500)
        }
    }

    // ==================== GESZTUSOK ====================

    private fun feedbackSwipeUp() {
        sounds.play(SoundType.SWIPE_UP)
        vibrate(30)
    }

    private fun feedbackSwipeDown() {
        sounds.play(SoundType.SWIPE_DOWN)
        vibrate(30)
    }

    private fun feedbackSwipeLeft() {
        sounds.play(SoundType.SWIPE_LEFT)
        vibrate(40)
    }

    private fun feedbackSwipeRight() {
        sounds.play(SoundType.SWIPE_RIGHT)
        vibrate(60)
    }

    private fun feedbackSuccess() = sounds.play(SoundType.ACTION_OK)

    private fun feedbackError() = sounds.play(SoundType.ACTION_ERROR)

    private fun handleSwipeUp() {
        feedbackSwipeUp()
        when (val flow = activeFlow) {
            is AppFlow.TrainingPlayground -> handleTrainingNavigate(flow, -1)
            is AppFlow.Menu -> navigateUp()
            is AppFlow.SmsPickContact -> {
                val next = (flow.index - 1 + flow.matches.size) % flow.matches.size
                activeFlow = flow.copy(index = next)
                updateFlowDisplay()
                speakContactMatch(flow.matches[next])
            }
            is AppFlow.EmailPickRecipient -> navigateEmailPick(flow, -1)
            is AppFlow.EmailBrowseRecipients -> navigateEmailList(flow, -1)
            is AppFlow.EmailRecipientConfirm -> repeatEmailRecipientConfirm(flow.recipient)
            is AppFlow.EmailConfirm -> repeatEmailConfirm(flow.recipient, flow.subject, flow.body)
            is AppFlow.SmsInbox -> {
                val next = (flow.index - 1 + flow.messages.size) % flow.messages.size
                activeFlow = flow.copy(index = next)
                updateFlowDisplay()
                speakSmsPreview(flow.messages[next])
            }
            is AppFlow.SmsContextMenu -> navigateSmsContextMenu(flow, -1)
            is AppFlow.SmsDeleteConfirm -> repeatSmsDeleteConfirm(flow)
            is AppFlow.CallLogContextMenu -> navigateCallLogContextMenu(flow, -1)
            is AppFlow.FavoritesBrowse -> navigateFavoritesList(flow, -1)
            is AppFlow.FavoriteDeleteConfirm -> repeatFavoriteDeleteConfirm(flow.favorite)
            is AppFlow.CallPickContact -> {
                val next = (flow.index - 1 + flow.matches.size) % flow.matches.size
                activeFlow = flow.copy(index = next)
                updateFlowDisplay()
                speakContactMatch(flow.matches[next])
            }
            is AppFlow.ContactBookBrowse -> navigateContactBook(flow, -1)
            is AppFlow.ContactLetterBrowse -> navigateContactLetter(flow, -1)
            is AppFlow.ContactContextMenu -> navigateContactContextMenu(flow, -1)
            is AppFlow.ContactDeleteConfirm -> repeatContactDeleteConfirm(flow.contact)
            is AppFlow.SmsRecipientConfirm -> repeatSmsRecipientConfirm(flow.recipient)
            is AppFlow.SmsConfirm -> repeatSmsConfirm(flow.recipient, flow.message)
            is AppFlow.CallConfirm -> repeatCallConfirm(flow.contact)
            is AppFlow.CalendarConfirm -> repeatCalendarConfirm(flow)
            is AppFlow.CalendarRecurrenceBrowse -> navigateCalendarRecurrence(flow, -1)
            is AppFlow.AlarmListBrowse -> navigateAlarmList(flow, -1)
            is AppFlow.AlarmRepeatBrowse -> navigateAlarmRepeat(flow, -1)
            is AppFlow.CalendarBrowse -> navigateCalendar(flow, -1)
            is AppFlow.CatalogBrowse -> navigateCatalog(flow, -1)
            is AppFlow.CalendarTargetPick -> navigateCalendarTargetPick(flow, -1)
            is AppFlow.AlarmSkipPick -> navigateAlarmSkipPick(flow, -1)
            is AppFlow.AlarmSkipCount -> navigateAlarmSkipCount(flow, +1)
            is AppFlow.CalendarPick -> navigateCalendarPick(flow, -1)
            is AppFlow.CalendarContextMenu -> navigateCalendarContextMenu(flow, -1)
            is AppFlow.CalendarAlarmContextMenu -> navigateCalendarAlarmContextMenu(flow, -1)
            is AppFlow.CalendarDeleteConfirm -> repeatCalendarDeleteConfirm(flow.event)
            is AppFlow.CalendarWeekBrowse -> navigateCalendarWeek(flow, -1)
            is AppFlow.CallLogBrowse -> navigateCallLog(flow, -1)
            is AppFlow.MusicBrowse -> navigateMusicList(flow, -1)
            is AppFlow.RadioBrowse -> navigateRadioList(flow, -1)
            is AppFlow.AlarmDeleteConfirm -> repeatAlarmDeleteConfirm(flow.alarm)
            is AppFlow.MedicationCycleBrowse -> navigateMedicationCycle(flow, -1)
            is AppFlow.MedicationTimeOfDayBrowse -> navigateMedicationTimeOfDay(flow, -1)
            is AppFlow.MedicationWeekdayBrowse -> navigateMedicationWeekday(flow, -1)
            is AppFlow.MedicationListBrowse -> navigateMedicationList(flow, -1)
            is AppFlow.MedicationDeleteConfirm -> repeatMedicationDeleteConfirm(flow.reminder)
            is AppFlow.MedicationConfirm -> repeatMedicationConfirm(flow)
            is AppFlow.SetupWizardBrowse -> navigateSetupWizard(flow, -1)
            is AppFlow.SetupWizardAwaitReturn -> returnToSetupWizard()
            is AppFlow.TimerUnitBrowse -> navigateTimerUnit(flow, -1)
            is AppFlow.TimerIntervalBrowse -> navigateTimerInterval(flow, -1)
            is AppFlow.TimerListBrowse -> navigateTimerList(flow, -1)
            is AppFlow.TimerDeleteConfirm -> repeatTimerDeleteConfirm(flow.timer)
            is AppFlow.TimerConfirm -> repeatTimerConfirm(flow)
            is AppFlow.GpsRadarBrowse -> navigateGpsRadarList(flow, -1)
            is AppFlow.GpsRadarContextMenu -> navigateGpsRadarContextMenu(flow, -1)
            is AppFlow.GpsRadarGuiding -> speakGpsRadarTarget(flow)
            is AppFlow.GpsSavedPoiBrowse -> navigateGpsSavedPoiList(flow, -1)
            is AppFlow.SavedPoiContextMenu -> navigateSavedPoiContextMenu(flow, -1)
            is AppFlow.NavWhereResult -> speakNavWhereResult(flow)
            AppFlow.GpsRouteRecordingActive -> speakGpsRouteStatus()
            is AppFlow.GpsRouteBrowse -> navigateGpsRouteList(flow, -1)
            is AppFlow.GpsRouteDeleteConfirm -> repeatGpsRouteDeleteConfirm(flow.route)
            is AppFlow.GpsRouteGuidingActive -> speakGpsRoutePreview(flow.route)
            is AppFlow.LocationProfileBrowse -> navigateLocationProfileList(flow, -1)
            is AppFlow.LocationProfileActions -> navigateLocationProfileActions(flow, -1)
            is AppFlow.LocationProfileDeleteConfirm -> repeatLocationProfileDeleteConfirm(flow.profile)
            is AppFlow.CardBrowse -> navigateCardList(flow, -1)
            is AppFlow.CardDeleteConfirm -> repeatCardDeleteConfirm(flow.card)
            is AppFlow.NewsFeedManageBrowse -> navigateNewsFeedManageList(flow, -1)
            is AppFlow.GpsArrivalLocationPrompt -> navigateGpsArrivalPrompt(flow, -1)
            is AppFlow.CameraQualityBrowse -> navigateCameraQuality(flow, -1)
            AppFlow.DictaphoneRecording -> speakDictaphoneElapsed()
            is AppFlow.DictaphoneSettingsBrowse -> navigateDictaphoneSettings(flow, -1)
            is AppFlow.DictaphoneFormatBrowse -> navigateDictaphoneFormat(flow, -1)
            is AppFlow.DictaphoneSampleRateBrowse -> navigateDictaphoneSampleRate(flow, -1)
            is AppFlow.DictaphoneBitrateBrowse -> navigateDictaphoneBitrate(flow, -1)
            is AppFlow.DictaphoneChannelsBrowse -> navigateDictaphoneChannels(flow, -1)

            is AppFlow.DictaphoneRecordingsBrowse -> navigateDictaphoneRecordings(flow, -1)
            is AppFlow.DictaphoneRecordingContextMenu -> navigateDictaphoneRecordingContextMenu(flow, -1)
            is AppFlow.DictaphoneShareEmailPickRecipient -> navigateDictaphoneShareEmailPick(flow, -1)
            is AppFlow.DictaphoneShareEmailConfirm -> repeatDictaphoneShareEmailConfirm(flow.entry, flow.recipient)
            is AppFlow.DictaphoneRecordingDeleteConfirm -> repeatDictaphoneRecordingDeleteConfirm(flow)
            is AppFlow.NotificationBrowse -> navigateNotificationList(flow, -1)
            is AppFlow.NewsFeedBrowse -> navigateNewsFeedList(flow, -1)
            is AppFlow.NewsBrowse -> navigateNewsList(flow, -1)
            is AppFlow.SearchResultBrowse -> navigateSearchResults(flow, +1)
            is AppFlow.SearchArticleReading -> articleReader.repeatChunk()
            is AppFlow.MedicationSearchResult -> articleReader.repeatChunk()
            is AppFlow.NewsArticleReading -> articleReader.repeatChunk()
            is AppFlow.NoteListBrowse -> navigateNoteList(flow, -1)
            is AppFlow.NoteReading -> noteReader.repeatChunk()
            is AppFlow.EmailInboxBrowse -> navigateEmailInbox(flow, -1)
            is AppFlow.EmailReadBody -> speakEmailBody(flow)
            is AppFlow.ShoppingListPick -> navigateShoppingListPick(flow, -1)
            is AppFlow.ShoppingListBrowse -> navigateShoppingList(flow, -1)
            is AppFlow.ShoppingItemContextMenu -> navigateShoppingItemContextMenu(flow, -1)
            is AppFlow.ShoppingListContextMenu -> navigateShoppingListContextMenu(flow, -1)
            is AppFlow.ShoppingDeleteItemConfirm -> repeatShoppingDeleteItemConfirm(flow.item)
            is AppFlow.ShoppingDeleteListConfirm -> repeatShoppingDeleteListConfirm(flow.listName)
            is AppFlow.EmailSmtpPickAccount -> navigateEmailSmtpPickAccount(flow, -1)
            AppFlow.EmailSmtpAwaitUsername,
            AppFlow.EmailSmtpAwaitPassword,
            AppFlow.EmailSmtpAwaitFromName -> repeatSmtpPrompt(flow)
            is AppFlow.YoutubeBrowse -> navigateYoutubeList(flow, -1)
            is AppFlow.YoutubePlayConfirm -> repeatYoutubePlayConfirm(flow.video)
            is AppFlow.LegalBrowse -> navigateLegalList(flow, -1)
            is AppFlow.GuideBrowse -> navigateGuideList(flow, -1)
            is AppFlow.TransitBrowse -> navigateTransitList(flow, -1)
            is AppFlow.TransitContextMenu -> navigateTransitContextMenu(flow, -1)
            is AppFlow.TransitRouteBrowse -> navigateTransitRouteList(flow, -1)
            is AppFlow.TrainBrowse -> navigateTrainList(flow, -1)
            is AppFlow.TrainContextMenu -> navigateTrainContextMenu(flow, -1)
            is AppFlow.NavPlaceBrowse -> navigateNavPlaceList(flow, -1)
            is AppFlow.BookLibraryBrowse -> navigateBookList(flow, -1)
            is AppFlow.BookRecentBrowse -> navigateRecentBookList(flow, -1)
            is AppFlow.BookBookmarkBrowse -> navigateBookmarkList(flow, -1)
            is AppFlow.BookBookmarkDeleteConfirm -> repeatBookmarkDeleteConfirm(flow.bookmark)
            is AppFlow.BookReading -> bookReader.repeatChunk()
            is AppFlow.TtsVoiceBrowse -> navigateTtsVoiceList(flow, -1)
            is AppFlow.FavoriteAppsBrowse -> navigateFavoriteAppsList(flow, -1)
            is AppFlow.FavoriteAppsCandidateBrowse -> navigateFavoriteAppsCandidates(flow, -1)
            is AppFlow.FavoriteContactCandidateBrowse -> navigateFavoriteContactCandidates(flow, -1)
            is AppFlow.SosSetupMethodPick -> navigateSosSetupMethodPick(flow, -1)
            is AppFlow.SosContactCandidateBrowse -> navigateSosContactCandidates(flow, -1)
            is AppFlow.SoundTrainingBrowse -> navigateSoundTraining(flow, -1)
            is AppFlow.SoundThemeBrowse -> navigateSoundTheme(flow, -1)
            is AppFlow.AlertSoundPresetBrowse -> navigateAlertSoundPreset(flow, -1)
            is AppFlow.NumberPadInput -> navigateNumberPad(flow, -1)
            is AppFlow.NumericDictationAwait -> pasteOrRepeatNumericIntro(flow)
            is AppFlow.ExternalAppBrowse -> navigateExternalApps(flow, -1)
            else -> {
                feedbackError()
                tts.speak("Ebben a lépésben fel-le navigáció nem elérhető.")
            }
        }
    }

    private fun handleSwipeDown() {
        feedbackSwipeDown()
        when (val flow = activeFlow) {
            is AppFlow.TrainingPlayground -> handleTrainingNavigate(flow, +1)
            is AppFlow.Menu -> navigateDown()
            is AppFlow.SmsPickContact -> {
                val next = (flow.index + 1) % flow.matches.size
                activeFlow = flow.copy(index = next)
                updateFlowDisplay()
                speakContactMatch(flow.matches[next])
            }
            is AppFlow.EmailPickRecipient -> navigateEmailPick(flow, +1)
            is AppFlow.EmailBrowseRecipients -> navigateEmailList(flow, +1)
            is AppFlow.EmailRecipientConfirm -> repeatEmailRecipientConfirm(flow.recipient)
            is AppFlow.EmailConfirm -> repeatEmailConfirm(flow.recipient, flow.subject, flow.body)
            is AppFlow.SmsInbox -> {
                val next = (flow.index + 1) % flow.messages.size
                activeFlow = flow.copy(index = next)
                updateFlowDisplay()
                speakSmsPreview(flow.messages[next])
            }
            is AppFlow.SmsContextMenu -> navigateSmsContextMenu(flow, +1)
            is AppFlow.SmsDeleteConfirm -> repeatSmsDeleteConfirm(flow)
            is AppFlow.CallLogContextMenu -> navigateCallLogContextMenu(flow, +1)
            is AppFlow.FavoritesBrowse -> navigateFavoritesList(flow, +1)
            is AppFlow.FavoriteDeleteConfirm -> repeatFavoriteDeleteConfirm(flow.favorite)
            is AppFlow.CallPickContact -> {
                val next = (flow.index + 1) % flow.matches.size
                activeFlow = flow.copy(index = next)
                updateFlowDisplay()
                speakContactMatch(flow.matches[next])
            }
            is AppFlow.ContactBookBrowse -> navigateContactBook(flow, +1)
            is AppFlow.ContactLetterBrowse -> navigateContactLetter(flow, +1)
            is AppFlow.ContactContextMenu -> navigateContactContextMenu(flow, +1)
            is AppFlow.ContactDeleteConfirm -> repeatContactDeleteConfirm(flow.contact)
            is AppFlow.SmsRecipientConfirm -> repeatSmsRecipientConfirm(flow.recipient)
            is AppFlow.SmsConfirm -> repeatSmsConfirm(flow.recipient, flow.message)
            is AppFlow.CallConfirm -> repeatCallConfirm(flow.contact)
            is AppFlow.CalendarConfirm -> repeatCalendarConfirm(flow)
            is AppFlow.CalendarRecurrenceBrowse -> navigateCalendarRecurrence(flow, +1)
            is AppFlow.AlarmListBrowse -> navigateAlarmList(flow, +1)
            is AppFlow.AlarmRepeatBrowse -> navigateAlarmRepeat(flow, +1)
            is AppFlow.CalendarBrowse -> navigateCalendar(flow, +1)
            is AppFlow.CatalogBrowse -> navigateCatalog(flow, +1)
            is AppFlow.CalendarTargetPick -> navigateCalendarTargetPick(flow, +1)
            is AppFlow.AlarmSkipPick -> navigateAlarmSkipPick(flow, +1)
            is AppFlow.AlarmSkipCount -> navigateAlarmSkipCount(flow, -1)
            is AppFlow.CalendarPick -> navigateCalendarPick(flow, +1)
            is AppFlow.CalendarContextMenu -> navigateCalendarContextMenu(flow, +1)
            is AppFlow.CalendarAlarmContextMenu -> navigateCalendarAlarmContextMenu(flow, +1)
            is AppFlow.CalendarDeleteConfirm -> repeatCalendarDeleteConfirm(flow.event)
            is AppFlow.CalendarWeekBrowse -> navigateCalendarWeek(flow, +1)
            is AppFlow.CallLogBrowse -> navigateCallLog(flow, +1)
            is AppFlow.MusicBrowse -> navigateMusicList(flow, +1)
            is AppFlow.RadioBrowse -> navigateRadioList(flow, +1)
            is AppFlow.AlarmDeleteConfirm -> repeatAlarmDeleteConfirm(flow.alarm)
            is AppFlow.MedicationCycleBrowse -> navigateMedicationCycle(flow, +1)
            is AppFlow.MedicationTimeOfDayBrowse -> navigateMedicationTimeOfDay(flow, +1)
            is AppFlow.MedicationWeekdayBrowse -> navigateMedicationWeekday(flow, +1)
            is AppFlow.MedicationListBrowse -> navigateMedicationList(flow, +1)
            is AppFlow.MedicationDeleteConfirm -> repeatMedicationDeleteConfirm(flow.reminder)
            is AppFlow.MedicationConfirm -> repeatMedicationConfirm(flow)
            is AppFlow.SetupWizardBrowse -> navigateSetupWizard(flow, +1)
            is AppFlow.SetupWizardAwaitReturn -> returnToSetupWizard()
            is AppFlow.TimerUnitBrowse -> navigateTimerUnit(flow, +1)
            is AppFlow.TimerIntervalBrowse -> navigateTimerInterval(flow, +1)
            is AppFlow.TimerListBrowse -> navigateTimerList(flow, +1)
            is AppFlow.TimerDeleteConfirm -> repeatTimerDeleteConfirm(flow.timer)
            is AppFlow.TimerConfirm -> repeatTimerConfirm(flow)
            is AppFlow.GpsRadarBrowse -> navigateGpsRadarList(flow, +1)
            is AppFlow.GpsRadarContextMenu -> navigateGpsRadarContextMenu(flow, +1)
            is AppFlow.GpsRadarGuiding -> startGpsSaveOwnLocation(returnGuiding = flow)
            is AppFlow.GpsSavedPoiBrowse -> navigateGpsSavedPoiList(flow, +1)
            is AppFlow.SavedPoiContextMenu -> navigateSavedPoiContextMenu(flow, +1)
            is AppFlow.NavWhereResult -> beginNavWhereRefining()
            AppFlow.GpsRouteRecordingActive -> speakGpsRouteStatus()
            is AppFlow.GpsRouteBrowse -> navigateGpsRouteList(flow, +1)
            is AppFlow.GpsRouteDeleteConfirm -> repeatGpsRouteDeleteConfirm(flow.route)
            is AppFlow.GpsRouteGuidingActive -> speakGpsRoutePreview(flow.route)
            is AppFlow.LocationProfileBrowse -> navigateLocationProfileList(flow, +1)
            is AppFlow.LocationProfileActions -> navigateLocationProfileActions(flow, +1)
            is AppFlow.LocationProfileDeleteConfirm -> repeatLocationProfileDeleteConfirm(flow.profile)
            is AppFlow.CardBrowse -> navigateCardList(flow, +1)
            is AppFlow.CardDeleteConfirm -> repeatCardDeleteConfirm(flow.card)
            is AppFlow.NewsFeedManageBrowse -> navigateNewsFeedManageList(flow, +1)
            is AppFlow.GpsArrivalLocationPrompt -> navigateGpsArrivalPrompt(flow, +1)
            is AppFlow.CameraQualityBrowse -> navigateCameraQuality(flow, +1)
            AppFlow.DictaphoneRecording -> speakDictaphoneElapsed()
            is AppFlow.DictaphoneSettingsBrowse -> navigateDictaphoneSettings(flow, +1)
            is AppFlow.DictaphoneFormatBrowse -> navigateDictaphoneFormat(flow, +1)
            is AppFlow.DictaphoneSampleRateBrowse -> navigateDictaphoneSampleRate(flow, +1)
            is AppFlow.DictaphoneBitrateBrowse -> navigateDictaphoneBitrate(flow, +1)
            is AppFlow.DictaphoneChannelsBrowse -> navigateDictaphoneChannels(flow, +1)

            is AppFlow.DictaphoneRecordingsBrowse -> navigateDictaphoneRecordings(flow, +1)
            is AppFlow.DictaphoneRecordingContextMenu -> navigateDictaphoneRecordingContextMenu(flow, +1)
            is AppFlow.DictaphoneShareEmailPickRecipient -> navigateDictaphoneShareEmailPick(flow, +1)
            is AppFlow.DictaphoneShareEmailConfirm -> repeatDictaphoneShareEmailConfirm(flow.entry, flow.recipient)
            is AppFlow.DictaphoneRecordingDeleteConfirm -> repeatDictaphoneRecordingDeleteConfirm(flow)
            is AppFlow.NotificationBrowse -> navigateNotificationList(flow, +1)
            is AppFlow.NewsFeedBrowse -> navigateNewsFeedList(flow, +1)
            is AppFlow.NewsBrowse -> navigateNewsList(flow, +1)
            is AppFlow.SearchResultBrowse -> saveSearchResultAsNote(flow)
            is AppFlow.SearchArticleReading -> saveSearchArticleAsNote(flow)
            is AppFlow.NewsArticleReading -> articleReader.nextChunk()
            is AppFlow.MedicationSearchResult -> articleReader.nextChunk()
            is AppFlow.NoteListBrowse -> navigateNoteList(flow, +1)
            is AppFlow.NoteReading -> noteReader.nextChunk()
            is AppFlow.CalendarAwaitDate -> openCalendarDatePad(flow.title)
            is AppFlow.CalendarAwaitStartTime -> openCalendarStartTimePad(flow.title, flow.dayStartMs)
            is AppFlow.CalendarAwaitEndTime -> openCalendarEndTimePad(
                flow.title, flow.dayStartMs, flow.startHour, flow.startMinute
            )
            is AppFlow.EmailInboxBrowse -> navigateEmailInbox(flow, +1)
            is AppFlow.EmailReadBody -> speakEmailBody(flow)
            is AppFlow.ShoppingListPick -> enterShoppingListContextMenu(flow)
            is AppFlow.ShoppingListBrowse -> navigateShoppingList(flow, +1)
            is AppFlow.ShoppingItemContextMenu -> navigateShoppingItemContextMenu(flow, +1)
            is AppFlow.ShoppingListContextMenu -> navigateShoppingListContextMenu(flow, +1)
            is AppFlow.ShoppingDeleteItemConfirm -> repeatShoppingDeleteItemConfirm(flow.item)
            is AppFlow.ShoppingDeleteListConfirm -> repeatShoppingDeleteListConfirm(flow.listName)
            is AppFlow.EmailSmtpPickAccount -> navigateEmailSmtpPickAccount(flow, +1)
            AppFlow.EmailSmtpAwaitUsername,
            AppFlow.EmailSmtpAwaitPassword,
            AppFlow.EmailSmtpAwaitFromName -> repeatSmtpPrompt(flow)
            is AppFlow.YoutubeBrowse -> navigateYoutubeList(flow, +1)
            is AppFlow.YoutubePlayConfirm -> repeatYoutubePlayConfirm(flow.video)
            is AppFlow.LegalBrowse -> navigateLegalList(flow, +1)
            is AppFlow.GuideBrowse -> navigateGuideList(flow, +1)
            is AppFlow.TransitBrowse -> navigateTransitList(flow, +1)
            is AppFlow.TransitContextMenu -> navigateTransitContextMenu(flow, +1)
            is AppFlow.TransitRouteBrowse -> navigateTransitRouteList(flow, +1)
            is AppFlow.TrainBrowse -> navigateTrainList(flow, +1)
            is AppFlow.TrainContextMenu -> navigateTrainContextMenu(flow, +1)
            is AppFlow.NavPlaceBrowse -> navigateNavPlaceList(flow, +1)
            is AppFlow.BookLibraryBrowse -> navigateBookList(flow, +1)
            is AppFlow.BookRecentBrowse -> navigateRecentBookList(flow, +1)
            is AppFlow.BookBookmarkBrowse -> navigateBookmarkList(flow, +1)
            is AppFlow.BookBookmarkDeleteConfirm -> repeatBookmarkDeleteConfirm(flow.bookmark)
            is AppFlow.BookReading -> bookReader.nextChunk()
            is AppFlow.TtsVoiceBrowse -> navigateTtsVoiceList(flow, +1)
            is AppFlow.FavoriteAppsBrowse -> navigateFavoriteAppsList(flow, +1)
            is AppFlow.FavoriteAppsCandidateBrowse -> navigateFavoriteAppsCandidates(flow, +1)
            is AppFlow.FavoriteContactCandidateBrowse -> navigateFavoriteContactCandidates(flow, +1)
            is AppFlow.SosSetupMethodPick -> navigateSosSetupMethodPick(flow, +1)
            is AppFlow.SosContactCandidateBrowse -> navigateSosContactCandidates(flow, +1)
            is AppFlow.SoundTrainingBrowse -> navigateSoundTraining(flow, +1)
            is AppFlow.SoundThemeBrowse -> navigateSoundTheme(flow, +1)
            is AppFlow.AlertSoundPresetBrowse -> navigateAlertSoundPreset(flow, +1)
            is AppFlow.NumberPadInput -> navigateNumberPad(flow, +1)
            is AppFlow.NumericDictationAwait -> openNumberPadFromAwait(flow)
            AppFlow.CalculatorVoiceInput -> {
                voiceInput.cancel()
                startNumberPadFlow(NumberPadPurpose.CALCULATOR)
            }
            is AppFlow.ExternalAppBrowse -> navigateExternalApps(flow, +1)
            else -> {
                feedbackError()
                tts.speak("Ebben a lépésben fel-le navigáció nem elérhető.")
            }
        }
    }

    private fun handleSwipeRight() {
        feedbackSwipeRight()
        when (val flow = activeFlow) {
            is AppFlow.TrainingPlayground -> handleTrainingActivate(flow)
            is AppFlow.Menu -> activateMenuItem()
            is AppFlow.SmsPickContact -> {
                val contact = flow.matches[flow.index]
                enterSmsRecipientConfirm(Recipient(contact.phone, contact.name))
            }
            is AppFlow.EmailPickRecipient -> enterEmailRecipientConfirm(flow.matches[flow.index])
            is AppFlow.EmailRecipientConfirm -> proceedToEmailSubject(flow.recipient)
            is AppFlow.EmailConfirm -> sendEmail(flow.recipient, flow.subject, flow.body)
            is AppFlow.EmailBrowseRecipients -> tts.speak(flow.recipients[flow.index].speakFull())
            is AppFlow.SmsRecipientConfirm -> proceedToSmsMessage(flow.recipient)
            is AppFlow.SmsConfirm -> sendSms(flow.recipient, flow.message)
            is AppFlow.SmsInbox -> enterSmsContextMenu(flow)
            is AppFlow.SmsContextMenu -> onSmsContextActivate(flow)
            is AppFlow.SmsDeleteConfirm -> deleteSmsMessage(flow)
            is AppFlow.CallPickContact -> enterCallConfirm(flow.matches[flow.index])
            is AppFlow.CallConfirm -> placeCall(flow.contact.phone, flow.contact.name)
            is AppFlow.ContactBookBrowse -> onContactBookActivate(flow)
            is AppFlow.ContactLetterBrowse -> enterContactLetter(flow)
            is AppFlow.ContactContextMenu -> onContactContextActivate(flow)
            is AppFlow.ContactDeleteConfirm -> deleteContactFromBook(flow)
            is AppFlow.SosCountdown -> tts.speak("Visszaszámlálás folyamatban. Söpörj balra a leállításhoz.")
            is AppFlow.AlarmListBrowse -> onAlarmListActivate(flow)
            is AppFlow.AlarmRepeatBrowse -> onAlarmRepeatActivate(flow)
            is AppFlow.AlarmConfirm -> saveAlarm(flow.hour, flow.minute, flow.label)
            is AppFlow.CalendarConfirm -> saveCalendarEvent(flow)
            is AppFlow.CalendarRecurrenceBrowse -> applyCalendarRecurrence(flow)
            is AppFlow.CalendarContextMenu -> onCalendarContextActivate(flow)
            is AppFlow.CalendarAlarmContextMenu -> onCalendarAlarmContextActivate(flow)
            is AppFlow.CalendarDeleteConfirm -> deleteCalendarEvent(flow)
            is AppFlow.AlarmDeleteConfirm -> deleteAlarm(flow.alarm)
            is AppFlow.MedicationCycleBrowse -> onMedicationCycleActivate(flow)
            is AppFlow.MedicationTimeOfDayBrowse -> toggleMedicationTimeOfDay(flow)
            is AppFlow.MedicationWeekdayBrowse -> onMedicationWeekdayActivate(flow)
            is AppFlow.MedicationListBrowse -> onMedicationListActivate(flow)
            is AppFlow.MedicationDeleteConfirm -> deleteMedication(flow.reminder)
            is AppFlow.MedicationConfirm -> saveMedication(flow)
            is AppFlow.SetupWizardBrowse -> activateSetupRequirement(flow)
            is AppFlow.SetupWizardAwaitReturn -> returnToSetupWizard()
            is AppFlow.TimerUnitBrowse -> onTimerUnitActivate(flow)
            is AppFlow.TimerIntervalBrowse -> onTimerIntervalActivate(flow)
            is AppFlow.TimerConfirm -> saveTimer(flow)
            is AppFlow.TimerListBrowse -> onTimerListActivate(flow)
            is AppFlow.TimerDeleteConfirm -> deleteTimer(flow.timer)
            is AppFlow.GpsRadarBrowse -> enterGpsRadarContextMenu(flow)
            is AppFlow.GpsRadarContextMenu -> onGpsRadarContextActivate(flow)
            is AppFlow.GpsRadarGuiding -> saveCurrentGpsPoiFromGuiding(flow)
            is AppFlow.GpsSavedPoiBrowse -> enterSavedPoiContextMenu(flow)
            is AppFlow.SavedPoiContextMenu -> onSavedPoiContextActivate(flow)
            is AppFlow.SavedPoiVoiceRecording -> stopAndSaveSavedPoiVoiceRecording(flow)
            is AppFlow.NavWhereResult -> startNavWhereSave(flow)
            AppFlow.GpsRouteRecordingActive -> addGpsRouteWaypoint()
            is AppFlow.GpsRouteBrowse -> onGpsRouteListActivate(flow)
            is AppFlow.GpsRouteDeleteConfirm -> deleteGpsRoute(flow)
            is AppFlow.GpsRouteGuidingActive -> speakGpsRoutePreview(flow.route)
            is AppFlow.LocationProfileBrowse -> onLocationProfileListActivate(flow)
            is AppFlow.LocationProfileActions -> onLocationProfileActionActivate(flow)
            is AppFlow.LocationProfileDeleteConfirm -> deleteLocationProfile(flow)
            is AppFlow.CardBrowse -> onCardListActivate(flow)
            is AppFlow.CardDeleteConfirm -> deleteCard(flow)
            is AppFlow.NewsFeedManageBrowse -> toggleNewsFeed(flow)
            is AppFlow.GpsArrivalLocationPrompt -> activateGpsArrivalPrompt(flow)
            is AppFlow.CameraQualityBrowse -> applyCameraQuality(flow)
            AppFlow.DictaphoneRecording -> toggleDictaphonePause()
            is AppFlow.DictaphoneSettingsBrowse -> onDictaphoneSettingsActivate(flow)
            is AppFlow.DictaphoneFormatBrowse -> applyDictaphoneFormat(flow)
            is AppFlow.DictaphoneSampleRateBrowse -> applyDictaphoneSampleRate(flow)
            is AppFlow.DictaphoneBitrateBrowse -> applyDictaphoneBitrate(flow)
            is AppFlow.DictaphoneChannelsBrowse -> applyDictaphoneChannels(flow)

            is AppFlow.DictaphoneRecordingsBrowse -> enterDictaphoneRecordingContextMenu(flow)
            is AppFlow.DictaphoneRecordingContextMenu -> onDictaphoneRecordingContextActivate(flow)
            is AppFlow.DictaphoneShareEmailPickRecipient -> enterDictaphoneShareEmailConfirm(flow.entry, flow.matches[flow.index])
            is AppFlow.DictaphoneShareEmailConfirm -> sendDictaphoneShareEmail(flow.entry, flow.recipient)
            is AppFlow.DictaphoneRecordingDeleteConfirm -> deleteDictaphoneRecording(flow)
            is AppFlow.CalendarBrowse -> enterCalendarContextMenu(flow)
            is AppFlow.CatalogBrowse -> downloadCatalogModule(flow)
            is AppFlow.CalendarTargetPick -> confirmCalendarTarget(flow)
            is AppFlow.AlarmSkipPick -> toggleAlarmSkipSelection(flow)
            is AppFlow.AlarmSkipCount -> confirmAlarmSkip(flow)
            is AppFlow.CalendarPick -> onCalendarPickActivate(flow)
            is AppFlow.CalendarWeekBrowse -> tts.speak(flow.days[flow.index].speakFull())
            is AppFlow.CallLogBrowse -> enterCallLogContextMenu(flow)
            is AppFlow.CallLogContextMenu -> onCallLogContextActivate(flow)
            is AppFlow.FavoritesBrowse -> onFavoritesListActivate(flow)
            is AppFlow.FavoriteDeleteConfirm -> deleteFavorite(flow)
            is AppFlow.MusicBrowse -> playMusicFromList(flow.tracks, flow.index)
            is AppFlow.RadioBrowse -> {
                openRadioPlayer(flow.stations, flow.index)
                exitFlow("Indul: ${flow.stations[flow.index].name}.")
            }
            is AppFlow.NotificationBrowse -> tts.speak(flow.notifications[flow.index].speakFull())
            is AppFlow.NewsFeedBrowse -> loadNewsFromFeed(flow.feeds[flow.index])
            is AppFlow.NewsBrowse -> openNewsArticle(flow)
            is AppFlow.SearchResultBrowse -> openSearchArticle(flow)
            is AppFlow.SearchArticleReading -> articleReader.repeatChunk()
            is AppFlow.MedicationSearchResult -> articleReader.repeatChunk()
            is AppFlow.NewsArticleReading -> articleReader.repeatChunk()
            is AppFlow.NoteListBrowse -> onNoteListActivate(flow)
            is AppFlow.NoteDeleteConfirm -> deleteNote(flow)
            is AppFlow.CalendarAwaitDate -> listenForCalendarDate(flow.title)
            is AppFlow.CalendarAwaitStartTime -> listenForCalendarStartTime(flow.title, flow.dayStartMs)
            is AppFlow.CalendarAwaitEndTime -> listenForCalendarEndTime(
                flow.title, flow.dayStartMs, flow.startHour, flow.startMinute
            )
            is AppFlow.EmailInboxBrowse -> openEmailBody(flow)
            is AppFlow.ShoppingListPick -> onShoppingListPickActivate(flow)
            is AppFlow.ShoppingListBrowse -> enterShoppingItemContextMenu(flow)
            is AppFlow.ShoppingItemContextMenu -> onShoppingItemContextActivate(flow)
            is AppFlow.ShoppingListContextMenu -> onShoppingListContextActivate(flow)
            is AppFlow.ShoppingDeleteItemConfirm -> deleteShoppingItem(flow)
            is AppFlow.ShoppingDeleteListConfirm -> deleteShoppingList(flow)
            is AppFlow.EmailSmtpPickAccount -> onEmailSmtpPickAccountActivate(flow)
            is AppFlow.YoutubeBrowse -> enterYoutubePlayConfirm(flow.videos, flow.index)
            is AppFlow.YoutubePlayConfirm -> playYoutubeVideo(flow.video)
            is AppFlow.LegalBrowse -> tts.speak(flow.sections[flow.index].speakFull())
            is AppFlow.GuideBrowse -> tts.speak(flow.sections[flow.index].speakFull())
            is AppFlow.TransitBrowse -> enterTransitContextMenu(flow)
            is AppFlow.TransitContextMenu -> onTransitContextActivate(flow)
            is AppFlow.TransitRouteBrowse -> tts.speak(flow.route.steps[flow.index].speakPreview())
            is AppFlow.TrainBrowse -> enterTrainContextMenu(flow)
            is AppFlow.TrainContextMenu -> onTrainContextActivate(flow)
            is AppFlow.NavPlaceBrowse -> openNavPlaceInMaps(flow.places[flow.index])
            is AppFlow.BookLibraryBrowse -> openBook(flow.books[flow.index])
            is AppFlow.BookRecentBrowse -> openBook(flow.books[flow.index], resume = true)
            is AppFlow.BookBookmarkBrowse -> onBookmarkListActivate(flow)
            is AppFlow.BookBookmarkDeleteConfirm -> deleteBookmark(flow.bookmark)
            is AppFlow.BookReading -> addBookBookmark()
            is AppFlow.TtsVoiceBrowse -> selectTtsVoice(flow.options[flow.index])
            is AppFlow.FavoriteAppsBrowse -> onFavoriteAppsActivate(flow)
            is AppFlow.FavoriteAppsCandidateBrowse -> addFavoriteAppCandidate(flow)
            is AppFlow.FavoriteContactCandidateBrowse -> addFavoriteContactCandidate(flow)
            is AppFlow.SosSetupMethodPick -> onSosSetupMethodActivate(flow)
            is AppFlow.SosContactCandidateBrowse -> saveSosNumberFromContact(flow.slot, flow.contacts[flow.index])
            is AppFlow.SoundTrainingBrowse -> playSoundTrainingItem(flow.items[flow.index])
            is AppFlow.SoundThemeBrowse -> selectSoundTheme(flow)
            is AppFlow.AlertSoundPresetBrowse -> selectAlertSoundPreset(flow)
            is AppFlow.NumberPadInput -> onNumberPadActivate(flow)
            is AppFlow.NumericDictationAwait -> startNumericDictation(flow)
            is AppFlow.ExternalAppBrowse -> launchExternalApp(flow.apps[flow.index])
            AppFlow.LauncherExitConfirm -> openLauncherExitSettings()
            AppFlow.VoiceAssistantAwaitQuestion,
            AppFlow.VoiceAssistantChat -> resumeVoiceAssistantListening()
            AppFlow.BookLoading -> tts.speak("A könyv betöltése folyamatban. Várj.")
            else -> {
                feedbackError()
                tts.speak("Várd meg a diktálást, vagy söprés balra a mégse gombhoz.")
            }
        }
    }

    private fun handleSwipeLeft() {
        feedbackSwipeLeft()
        voiceInput.cancel()
        tts.stop()
        when (val flow = activeFlow) {
            is AppFlow.TrainingPlayground -> {
                val now = System.currentTimeMillis()
                if (now - lastLeftSwipeAt < TRAINING_DOUBLE_SWIPE_MS) {
                    lastLeftSwipeAt = 0L
                    exitFlow("Tanuló mód bezárva.")
                    return
                }
                lastLeftSwipeAt = now
                tts.speak("Kilépéshez söprés balra még egyszer gyorsan.")
                return
            }
            is AppFlow.SosCountdown -> cancelSosCountdown()
            is AppFlow.AlarmDeleteConfirm -> {
                activeFlow = AppFlow.AlarmListBrowse(flow.alarms, flow.index, deleteMode = true)
                updateFlowDisplay()
                tts.speak("Törlés megszakítva.")
            }
            is AppFlow.AlarmListBrowse -> exitFlow("Ébresztők bezárva.")
            is AppFlow.MedicationDeleteConfirm -> {
                activeFlow = AppFlow.MedicationListBrowse(flow.reminders, flow.index, deleteMode = true)
                updateFlowDisplay()
                tts.speak("Törlés megszakítva.")
            }
            AppFlow.MedicationAwaitName -> {
                medicationDraftName = null
                exitFlow("Gyógyszer rögzítés megszakítva.")
            }
            is AppFlow.MedicationTimeOfDayBrowse -> proceedFromMedicationTimeOfDay(flow)
            AppFlow.MedicationAwaitCourseDays -> {
                voiceInput.cancel()
                medicationDraftName = null
                medicationDraftTimes = emptyList()
                medicationDraftCourseEndMillis = null
                exitFlow("Gyógyszer rögzítés megszakítva.")
            }
            is AppFlow.MedicationWeekdayBrowse -> {
                if (flow.cycleType == MedicationCycleType.CUSTOM) {
                    proceedMedicationWeekdayIfReady(flow)
                } else {
                    medicationDraftName = null
                    exitFlow("Gyógyszer rögzítés megszakítva.")
                }
            }
            is AppFlow.MedicationCycleBrowse,
            is AppFlow.MedicationConfirm -> {
                medicationDraftName = null
                exitFlow("Gyógyszer rögzítés megszakítva.")
            }
            is AppFlow.MedicationListBrowse -> exitFlow("Patika Őrangyal bezárva.")
            is AppFlow.SetupWizardBrowse -> exitFlow("Beállítás varázsló bezárva.")
            // Visszatérés a rendszerképernyőről: nem kilépünk, hanem újramérünk.
            is AppFlow.SetupWizardAwaitReturn -> returnToSetupWizard()
            is AppFlow.SmsContextMenu -> returnToSmsInbox(flow.messages, flow.messageIndex, flow.folder)
            is AppFlow.SmsDeleteConfirm -> {
                activeFlow = AppFlow.SmsContextMenu(
                    flow.messages,
                    flow.messageIndex,
                    SmsContextAction.all,
                    SmsContextAction.DELETE.ordinal,
                    flow.folder
                )
                updateFlowDisplay()
                tts.speak("Törlés megszakítva.")
            }
            is AppFlow.CallLogContextMenu -> returnToCallLogBrowse(flow.entries, flow.entryIndex)
            is AppFlow.CallLogSaveContactAwaitName -> returnToCallLogBrowse(flow.entries, flow.entryIndex)
            is AppFlow.ContactBookBrowse -> openContactLetterBrowse()
            is AppFlow.ContactLetterBrowse -> exitFlow("Névjegyzék bezárva.")
            is AppFlow.ContactContextMenu -> returnToContactBook(flow.items, flow.contactIndex)
            is AppFlow.ContactEditAwaitName -> returnToContactBookFromEdit(flow.contact)
            is AppFlow.ContactEditAwaitPhone -> returnToContactBookFromEdit(flow.contact)
            is AppFlow.ContactDeleteConfirm -> enterContactContextMenu(flow.items, flow.index)
            is AppFlow.ContactCreateAwaitName -> exitFlow("Névjegy létrehozás megszakítva.")
            is AppFlow.FavoriteDeleteConfirm -> {
                activeFlow = AppFlow.FavoritesBrowse(flow.favorites, flow.index, FavoritesListMode.DELETE)
                updateFlowDisplay()
                tts.speak("Törlés megszakítva.")
            }
            is AppFlow.FavoritesBrowse -> exitFlow("Kedvencek bezárva.")
            is AppFlow.TimerDeleteConfirm -> {
                activeFlow = AppFlow.TimerListBrowse(flow.timers, flow.index, TimerListMode.DELETE)
                updateFlowDisplay()
                tts.speak("Törlés megszakítva.")
            }
            is AppFlow.TimerAwaitAmount,
            is AppFlow.TimerAwaitLabel -> exitFlow("Időzítő beállítás megszakítva.")
            is AppFlow.TimerUnitBrowse,
            is AppFlow.TimerIntervalBrowse,
            is AppFlow.TimerConfirm -> exitFlow("Időzítő beállítás megszakítva.")
            is AppFlow.TimerListBrowse -> exitFlow("Időzítők bezárva.")
            is AppFlow.GpsRadarBrowse -> exitFlow("G P S kitekintő bezárva.")
            is AppFlow.GpsRadarContextMenu -> returnToGpsRadarBrowse(flow)
            is AppFlow.TransitBrowse -> {
                stopTransitCompass()
                exitFlow("Megállók bezárva.")
            }
            is AppFlow.TransitContextMenu -> returnToTransitBrowse(flow)
            AppFlow.TrainAwaitStation -> exitFlow("Állomás keresés megszakítva.")
            is AppFlow.TrainBrowse -> {
                stopTransitCompass()
                exitFlow("Vonat állomások bezárva.")
            }
            is AppFlow.TrainContextMenu -> returnToTrainBrowse(flow)
            is AppFlow.GpsRadarGuiding -> unlockGpsRadarTarget(flow)
            is AppFlow.GpsRadarAwaitSaveName -> cancelGpsSaveOwnLocation(flow)
            is AppFlow.GpsSavedPoiBrowse -> exitFlow("Egyéni helyek bezárva.")
            is AppFlow.SavedPoiContextMenu -> returnToSavedPoiBrowse(flow.saved, flow.poiIndex)
            is AppFlow.SavedPoiVoiceRecording -> cancelSavedPoiVoiceRecording(flow)
            AppFlow.GpsRadarLoading -> exitFlow("G P S kitekintő megszakítva.")
            AppFlow.NavWhereLoading -> cancelNavWhereRefining()
            is AppFlow.NavWhereResult -> exitFlow("Hol vagyok bezárva.")
            is AppFlow.GpsSaveRefining -> cancelGpsSaveRefining(flow)
            AppFlow.GpsRouteRecordingActive -> stopGpsRouteRecordingAndSave()
            is AppFlow.GpsRouteAwaitName -> {
                val route = flow.route
                val saved = GpsRouteStore.save(this, route)
                exitFlow("Útvonal mentve alapértelmezett névvel: ${saved.speakPreview()}.")
            }
            is AppFlow.GpsRouteBrowse -> exitFlow("Mentett útvonalak bezárva.")
            is AppFlow.GpsRouteDeleteConfirm -> {
                activeFlow = AppFlow.GpsRouteBrowse(flow.routes, flow.index, deleteMode = true, guideMode = false)
                updateFlowDisplay()
                tts.speak("Törlés megszakítva.")
            }
            is AppFlow.GpsRouteGuidingActive -> stopGpsRouteGuidance()
            is AppFlow.LocationProfileBrowse -> exitFlow("Mentett helyszínek bezárva.")
            is AppFlow.LocationProfileActions -> {
                activeFlow = AppFlow.LocationProfileBrowse(flow.profiles, flow.profileIndex, deleteMode = false)
                updateFlowDisplay()
                tts.speak(flow.profile.speakPreview())
            }
            is AppFlow.CardBrowse -> exitFlow("Kártyák bezárva.")
            is AppFlow.CardDeleteConfirm -> {
                activeFlow = AppFlow.CardBrowse(flow.cards, flow.index, deleteMode = true)
                updateFlowDisplay()
                tts.speak("Törlés megszakítva.")
            }
            is AppFlow.NewsFeedManageBrowse -> exitFlow("Hírforrások kezelése bezárva.")
            is AppFlow.GpsArrivalLocationPrompt -> {
                activeFlow = AppFlow.Menu
                updateDisplay()
                tts.speak("Helyszín felismerő kihagyva.")
            }
            is AppFlow.LocationProfileDeleteConfirm -> {
                activeFlow = AppFlow.LocationProfileBrowse(flow.profiles, flow.index, deleteMode = true)
                updateFlowDisplay()
                tts.speak("Törlés megszakítva.")
            }
            is AppFlow.CameraQualityBrowse -> exitFlow("Kamera minőség beállítás megszakítva.")
            AppFlow.DictaphoneRecording -> stopDictaphoneRecording(save = true)
            is AppFlow.DictaphoneSettingsBrowse -> exitFlow("Diktafon beállítások bezárva.")
            is AppFlow.DictaphoneFormatBrowse,
            is AppFlow.DictaphoneSampleRateBrowse,
            is AppFlow.DictaphoneBitrateBrowse,
            is AppFlow.DictaphoneChannelsBrowse -> returnToDictaphoneSettings()
            is AppFlow.DictaphoneRecordingsBrowse -> {
                DictaphonePlayback.stop()
                exitFlow("Mentett felvételek bezárva.")
            }
            is AppFlow.DictaphoneRecordingContextMenu -> {
                DictaphonePlayback.stop()
                returnToDictaphoneRecordingsBrowse(flow)
            }
            is AppFlow.DictaphoneShareEmailAwaitRecipient,
            is AppFlow.DictaphoneShareEmailPickRecipient,
            is AppFlow.DictaphoneShareEmailConfirm -> cancelDictaphoneShareEmail()
            is AppFlow.DictaphoneRecordingDeleteConfirm -> {
                val actions = DictaphoneRecordingContextAction.all
                activeFlow = AppFlow.DictaphoneRecordingContextMenu(
                    flow.recordings,
                    flow.recordingIndex,
                    actions,
                    actions.indexOf(DictaphoneRecordingContextAction.DELETE).coerceAtLeast(0)
                )
                updateFlowDisplay()
                tts.speak("Törlés megszakítva.")
            }
            is AppFlow.YoutubePlayConfirm -> {
                activeFlow = AppFlow.YoutubeBrowse(flow.videos, flow.index)
                updateFlowDisplay()
                tts.speak("Lejátszás megszakítva. ${flow.video.title}")
            }
            is AppFlow.Menu -> goBack()
            AppFlow.LauncherExitConfirm -> {
                activeFlow = AppFlow.Menu
                updateDisplay()
                tts.speak("Mégse. Vissza a beállításokban.")
            }
            is AppFlow.GuideBrowse -> {
                activeFlow = AppFlow.Menu
                updateDisplay()
                tts.speak("Útmutató bezárva. Vissza a menüben.")
            }
            is AppFlow.NotificationBrowse -> {
                activeFlow = AppFlow.Menu
                updateDisplay()
                tts.speak("Értesítések bezárva. Vissza a menüben.")
            }
            is AppFlow.BookReading -> finishBookReading("Olvasás leállítva.")
            is AppFlow.BookBookmarkDeleteConfirm -> {
                activeFlow = AppFlow.BookBookmarkBrowse(flow.bookmarks, flow.index, deleteMode = true)
                updateFlowDisplay()
                tts.speak("Törlés megszakítva.")
            }
            AppFlow.BookLoading -> exitFlow("Betöltés megszakítva.")
            AppFlow.BookSearchAwaitQuery -> exitFlow("Keresés megszakítva.")
            AppFlow.CalculatorAwaitInput -> exitFlow("Számológép bezárva.")
            AppFlow.CalculatorVoiceInput -> {
                voiceInput.cancel()
                enterNumericDictationAwait(AppFlow.NumericDictationAwait(purpose = NumberPadPurpose.CALCULATOR))
            }
            is AppFlow.NumericDictationAwait -> exitNumericDictationAwait(flow)
            is AppFlow.NumberPadInput -> onNumberPadBackspace(flow)
            is AppFlow.ExternalAppBrowse -> exitFlow("Külső alkalmazások bezárva.")
            is AppFlow.FavoriteAppsBrowse -> exitFlow("Kedvenc alkalmazások bezárva.")
            is AppFlow.FavoriteAppsCandidateBrowse -> exitFlow("Kedvenc hozzáadása megszakítva.")
            is AppFlow.FavoriteContactCandidateBrowse -> exitFlow("Kedvenc hozzáadása megszakítva.")
            is AppFlow.SosSetupMethodPick -> exitFlow("S.O.S. szám beállítás megszakítva.")
            is AppFlow.SosContactCandidateBrowse -> startSosNumberSetup(flow.slot)
            AppFlow.WeatherAwaitCity -> exitFlow("Időjárás keresés megszakítva.")
            is AppFlow.EmailSmtpPickAccount -> exitFlow("E-mail küldő beállítás megszakítva.")
            AppFlow.EmailSmtpAwaitUsername,
            AppFlow.EmailSmtpAwaitPassword,
            AppFlow.EmailSmtpAwaitFromName -> exitFlow("E-mail küldő beállítás megszakítva.")
            AppFlow.SearchAwaitQuery,
            AppFlow.SearchLoading -> exitFlow("Keresés megszakítva.")
            is AppFlow.SearchResultBrowse -> exitFlow("Internet kereső bezárva.")
            is AppFlow.SearchArticleReading -> {
                articleReader.stop()
                activeFlow = AppFlow.SearchResultBrowse(flow.results, flow.resultIndex, flow.query)
                updateFlowDisplay()
                speakSearchResult(flow.results[flow.resultIndex], flow.resultIndex + 1, flow.results.size)
            }
            is AppFlow.NewsArticleReading -> {
                articleReader.stop()
                activeFlow = flow.newsFlow
                updateFlowDisplay()
                tts.speak(flow.newsFlow.items[flow.newsFlow.index].speakPreview())
            }
            is AppFlow.MedicationSearchResult -> {
                articleReader.stop()
                exitFlow("Gyógyszerkereső bezárva.")
            }
            AppFlow.MedicationSearchAwaitName -> {
                voiceInput.cancel()
                exitFlow("Gyógyszerkereső megszakítva.")
            }
            AppFlow.MedicationSearchLoading -> exitFlow("Gyógyszerkereső megszakítva.")
            AppFlow.EmailInboxLoading -> exitFlow("E-mail olvasás megszakítva.")
            is AppFlow.EmailInboxBrowse -> exitFlow("E-mailek bezárva.")
            is AppFlow.EmailReadBody -> {
                activeFlow = AppFlow.EmailInboxBrowse(flow.mails, flow.index)
                updateFlowDisplay()
                speakEmailHeader(flow.mails[flow.index], flow.index + 1, flow.mails.size)
            }
            is AppFlow.ShoppingListPick -> exitFlow("Bevásárlólista bezárva.")
            is AppFlow.ShoppingListBrowse -> exitFlow("Bevásárlólista bezárva.")
            is AppFlow.ShoppingItemContextMenu -> returnToShoppingBrowse(flow.listName, flow.items, flow.itemIndex)
            is AppFlow.ShoppingListContextMenu -> {
                activeFlow = AppFlow.ShoppingListPick(flow.names, flow.listIndex)
                updateFlowDisplay()
                tts.speak("Vissza a listákhoz.")
            }
            is AppFlow.ShoppingDeleteItemConfirm -> returnToShoppingBrowse(flow.listName, flow.items, flow.index)
            is AppFlow.ShoppingDeleteListConfirm -> {
                activeFlow = AppFlow.ShoppingListPick(flow.names, flow.index)
                updateFlowDisplay()
                tts.speak("Törlés megszakítva.")
            }
            AppFlow.ShoppingListAwaitName,
            AppFlow.ShoppingListAwaitItem -> exitFlow("Bevásárlólista megszakítva.")
            is AppFlow.ShoppingListAwaitMore -> finishShoppingListCreation(flow.listName)
            is AppFlow.ShoppingEditItemAwaitName -> returnToShoppingBrowse(flow.listName, flow.items, flow.index)
            is AppFlow.ShoppingRenameListAwaitName -> {
                activeFlow = AppFlow.ShoppingListPick(flow.names, flow.index)
                updateFlowDisplay()
                tts.speak("Átnevezés megszakítva.")
            }
            AppFlow.VoiceAssistantAwaitQuestion,
            AppFlow.VoiceAssistantChat -> {
                voiceAssistantReturnPending = false
                voiceInput.cancel()
                resumeElenaWakeListening()
                exitFlow("${ElenaWakeHelper.ASSISTANT_NAME} bezárva.")
            }
            AppFlow.ElenaWakeTrainAwaitPhrase -> exitFlow("Elena tanítás megszakítva.")
            is AppFlow.NewsBrowse -> exitFlow("Hírek bezárva.")
            is AppFlow.NewsFeedBrowse -> exitFlow("Hírek bezárva.")
            is AppFlow.CalendarContextMenu -> returnToCalendarBrowse(flow.events, flow.eventIndex)
            is AppFlow.CalendarDeleteConfirm -> returnToCalendarBrowse(flow.events, flow.index)
            is AppFlow.CalendarAlarmContextMenu -> dismissCalendarAlarm()
            is AppFlow.AlertSoundPresetBrowse -> exitFlow("Hangbeállítás megszakítva.")
            is AppFlow.CalendarRecurrenceBrowse -> exitFlow("Program beállítás megszakítva.")
            AppFlow.CalendarAwaitTitle,
            is AppFlow.CalendarAwaitDate,
            is AppFlow.CalendarAwaitStartTime,
            is AppFlow.CalendarAwaitEndTime,
            is AppFlow.CalendarConfirm -> exitFlow("Program beállítás megszakítva.")
            is AppFlow.NoteListBrowse -> exitFlow("Jegyzetek bezárva.")
            is AppFlow.NoteDeleteConfirm -> {
                activeFlow = AppFlow.NoteListBrowse(flow.notes, flow.index, deleteMode = true)
                updateFlowDisplay()
                tts.speak("Törlés megszakítva.")
            }
            is AppFlow.NoteReading -> {
                noteReader.stop()
                activeFlow = AppFlow.NoteListBrowse(flow.notes, flow.noteIndex)
                updateFlowDisplay()
                speakNoteListItem(flow.notes[flow.noteIndex], flow.noteIndex + 1, flow.notes.size)
            }
            AppFlow.NoteAwaitTitle,
            is AppFlow.NoteAwaitBody -> exitFlow("Jegyzet létrehozás megszakítva.")
            is AppFlow.CalendarBrowse -> exitFlow("Naptár bezárva.")
            is AppFlow.CatalogBrowse -> exitFlow("Katalógus bezárva.")
            is AppFlow.CalendarTargetPick -> exitFlow("Naptár-választás megszakítva.")
            is AppFlow.AlarmSkipPick -> finishAlarmSkipSelection(flow)
            is AppFlow.AlarmSkipCount -> {
                activeFlow = AppFlow.AlarmSkipPick(flow.alarms, 0, flow.selected)
                updateFlowDisplay()
                tts.speak("Vissza a kijelöléshez.")
            }
            is AppFlow.CalendarPick -> exitFlow("Naptár bezárva.")
            is AppFlow.CalendarWeekBrowse -> exitFlow("Heti program bezárva.")
            AppFlow.PatrolNightAwaitStart,
            AppFlow.PatrolNightAwaitEnd -> exitFlow("Éjszakai csend beállítás megszakítva.")
            AppFlow.EmailAwaitRecipient,
            is AppFlow.EmailAwaitSubject,
            is AppFlow.EmailAwaitBody,
            is AppFlow.EmailPickRecipient,
            is AppFlow.EmailRecipientConfirm,
            is AppFlow.EmailConfirm,
            is AppFlow.CallPickContact,
            is AppFlow.CallConfirm,
            AppFlow.AlarmAwaitTime,
            is AppFlow.AlarmAwaitLabel,
            is AppFlow.AlarmRepeatBrowse,
            is AppFlow.AlarmConfirm,
            AppFlow.TransitAwaitStop,
            AppFlow.TransitAwaitDestination,
            AppFlow.NavAwaitWalkDestination,
            AppFlow.NavAwaitPlaceQuery,
            AppFlow.YoutubeAwaitQuery -> exitFlow("Diktálás megszakítva.")
            AppFlow.SmsAwaitRecipient,
            is AppFlow.SmsPickContact,
            is AppFlow.SmsRecipientConfirm,
            is AppFlow.SmsAwaitMessage,
            is AppFlow.SmsConfirm -> {
                val restore = smsInboxRestore
                pendingSmsForwardBody = null
                smsInboxRestore = null
                voiceInput.cancel()
                if (restore != null) {
                    returnToSmsInbox(restore.messages, restore.index, restore.folder)
                } else {
                    exitFlow("Mégse.")
                }
            }
            else -> exitFlow("Mégse.")
        }
    }

    // ==================== NAVIGÁCIÓ ====================

    private fun navigateUp() {
        if (currentIndex <= 0) {
            feedbackError()
            tts.speak("Lista eleje.")
            return
        }
        lastExitConfirmSwipeAt = 0L
        currentIndex--
        announceMenuItem(currentMenu[currentIndex])
    }

    private fun navigateDown() {
        if (currentIndex >= currentMenu.size - 1) {
            feedbackError()
            tts.speak("Lista vége.")
            return
        }
        lastExitConfirmSwipeAt = 0L
        currentIndex++
        announceMenuItem(currentMenu[currentIndex])
    }

    private fun announceMenuItem(item: MenuItem) {
        sounds.play(SoundType.MENU_NAV)
        updateDisplay()
        // A felhasználó navigál: a késleltetett köszöntő már ne szóljon bele.
        userStartedNavigating = true
        tts.speak(speakMenuItemLabel(item))
    }

    private fun speakMenuItemLabel(item: MenuItem): String {
        return runCatching {
            when {
                item.action == MenuAction.EXIT_LAUNCHER ->
                    "Figyelem! ${item.label}. Dupla jobbra söprés szükséges a megerősítéshez."
                item.id == "launcher_switch" ->
                    "${item.label}. Almenü. Csak jobbra söprés nyitja meg, fel-le továbblép."
                item.action == MenuAction.WIFI_TOGGLE ->
                    "${item.label}. ${ConnectivityHelper.wifiStatus(this)}"
                item.action == MenuAction.HOTSPOT_TOGGLE ->
                    "${item.label}. ${ConnectivityHelper.hotspotStatus(this)}"
                item.action == MenuAction.BT_TOGGLE ->
                    "${item.label}. ${ConnectivityHelper.bluetoothStatus(this)}"
                item.action == MenuAction.CALL_FILTER_MODE_CYCLE ->
                    "${item.label}. Jelenlegi mód: ${CallFilterStore.getMode(this).menuLabel}."
                ToggleAnnouncement.isToggle(item.action) ->
                    ToggleAnnouncement.speakFocused(this, item.label, item.action)
                else -> item.label
            }
        }.getOrElse { item.label }
    }

    private fun activateMenuItem() {
        val item = currentMenu[currentIndex]
        if (item.action == MenuAction.EXIT_LAUNCHER) {
            confirmExitLauncherActivation()
            return
        }
        lastExitConfirmSwipeAt = 0L
        handleAction(item)
    }

    private fun confirmExitLauncherActivation() {
        val now = System.currentTimeMillis()
        if (now - lastExitConfirmSwipeAt < EXIT_DOUBLE_SWIPE_MS) {
            lastExitConfirmSwipeAt = 0L
            handleAction(currentMenu[currentIndex])
        } else {
            lastExitConfirmSwipeAt = now
            feedbackError()
            tts.speak("Figyelem! Kezdőképernyő váltás. Ismét jobbra söprés a megerősítéshez.")
        }
    }

    private fun goBack() {
        if (menuStack.isEmpty()) {
            tts.speak("Már a főmenüben vagy. ${InfoHelper.mainMenuStatusLine(this)}")
            return
        }
        currentMenu = menuStack.removeLast()
        // Oda térünk vissza, ahonnan beléptünk az almenübe (nem a lista tetejére).
        currentIndex = (menuIndexStack.removeLastOrNull() ?: 0)
            .coerceIn(0, (currentMenu.size - 1).coerceAtLeast(0))
        updateDisplay()
        tts.speak("Vissza. ${speakMenuItemLabel(currentMenu[currentIndex])}")
    }

    private fun enterSubMenu(item: MenuItem) {
        lastExitConfirmSwipeAt = 0L
        menuStack.addLast(currentMenu)
        menuIndexStack.addLast(currentIndex)
        currentMenu = item.children
        currentIndex = 0
        updateDisplay()
        tts.speak(item.label + ". Almenü megnyitva. " + speakMenuItemLabel(currentMenu[currentIndex]))
    }

    private fun exitFlow(message: String, success: Boolean = false, error: Boolean = false) {
        when {
            error -> feedbackError()
            success -> feedbackSuccess()
        }
        if (activeFlow is AppFlow.GpsRadarBrowse ||
            activeFlow is AppFlow.GpsRadarGuiding ||
            activeFlow is AppFlow.GpsRadarLoading
        ) {
            stopRadarSession(stopGuidance = GpsRadarManager.isGuiding())
        }
        voiceInput.cancel()
        lastLeftSwipeAt = 0L
        pendingSmsForwardBody = null
        smsInboxRestore = null
        calendarEditEventId = null
        if (bookReader.isActive) bookReader.stop()
        if (::articleReader.isInitialized && articleReader.isActive) articleReader.stop()
        if (::noteReader.isInitialized && noteReader.isActive) noteReader.stop()
        tts.stop()
        if (voiceAssistantReturnPending) {
            activeFlow = AppFlow.VoiceAssistantChat
            updateFlowDisplay()
            tts.speakThen(message) { resumeVoiceAssistantListening() }
            return
        }
        activeFlow = AppFlow.Menu
        updateDisplay()
        tts.speak("$message Vissza a menüben.")
    }

    private fun startSubFlowFromAssistant(start: () -> Unit) {
        voiceAssistantReturnPending = true
        start()
    }

    // ==================== AKCIÓK ====================

    private fun handleAction(item: MenuItem) {
        when (item.action) {
            MenuAction.SUBMENU -> {
                if (item.children.isNotEmpty()) enterSubMenu(item) else goBack()
            }
            MenuAction.CONTACTS -> startContactCallFlow()
            MenuAction.CONTACT_BOOK -> startContactBookFlow()
            MenuAction.CONTACT_SYNC -> runContactSync(manual = true)
            MenuAction.CALL_LOG -> startCallLogFlow()
            MenuAction.FAVORITES_ADD -> startFavoritesAddFlow()
            MenuAction.FAVORITES_CALL -> startFavoritesFlow(FavoritesListMode.CALL)
            MenuAction.FAVORITES_DELETE -> startFavoritesFlow(FavoritesListMode.DELETE)
            MenuAction.SMS_DEFAULT_SETUP -> startSmsDefaultSetupFlow()
            MenuAction.SMS_DEFAULT_STATUS -> tts.speak(SmsRoleHelper.speakStatus(this))
            MenuAction.CONTACT_CREATE -> startContactCreateFlow()
            MenuAction.DIAL -> startDialFlow()
            MenuAction.SMS_READ -> startSmsInboxFlow()
            MenuAction.SMS_SENT_READ -> startSmsSentFlow()
            MenuAction.SMS_WRITE -> startSmsComposeFlow()
            MenuAction.EMAIL_WRITE -> startEmailComposeFlow()
            MenuAction.EMAIL_IMPORT -> startEmailImportFlow()
            MenuAction.EMAIL_ADD -> startEmailAddFlow()
            MenuAction.EMAIL_LIST -> startEmailListFlow()
            MenuAction.EMAIL_SMTP_SETUP -> startEmailSmtpSetupFlow()
            MenuAction.EMAIL_SMTP_READ -> readEmailSmtpConfig()
            MenuAction.EMAIL_SMTP_CLEAR -> clearEmailSmtpConfig()
            MenuAction.SOS -> activateSos()
            MenuAction.SETUP_WIZARD -> startSetupWizard()
            MenuAction.SETUP_STATUS -> readSetupStatus()
            MenuAction.DIAGNOSTICS -> readDiagnostics()
            MenuAction.BATTERY_OPT_REQUEST -> requestBatteryOptimizationExemption()
            MenuAction.AUTOSTART_SETUP -> openAutostartSettings()
            MenuAction.SOS_SET_1 -> startSosNumberSetup(1)
            MenuAction.SOS_SET_2 -> startSosNumberSetup(2)
            MenuAction.SOS_SET_3 -> startSosNumberSetup(3)
            MenuAction.SOS_SET_4 -> startSosNumberSetup(4)
            MenuAction.SOS_READ_ALL -> readAllSosNumbers()
            MenuAction.TIME_NOW -> tts.speak(InfoHelper.speakDateTime())
            MenuAction.ALARM_SET -> startAlarmSetFlow()
            MenuAction.ALARM_READ_NEXT -> speakNextAlarm()
            MenuAction.ALARM_LIST -> startAlarmListFlow(deleteMode = false)
            MenuAction.ALARM_DELETE -> startAlarmListFlow(deleteMode = true)
            MenuAction.KEYBOARD_MATRIX_CELL -> {
                val name = com.superdl.launcher.keyboard.MatrixKeyboardPrefs.nextCellStep(this)
                tts.speak("Gombok távolsága: $name.")
            }
            MenuAction.KEYBOARD_MATRIX_SPEED -> {
                val name = com.superdl.launcher.keyboard.MatrixKeyboardPrefs.nextSpeedStep(this)
                tts.speak("Pörgetés sebessége: $name.")
            }
            MenuAction.KEYBOARD_MATRIX_HELP -> {
                tts.speak(com.superdl.launcher.keyboard.MatrixKeyboardService.speakGestureHelp())
            }
            MenuAction.CATALOG_UPDATE -> checkForUpdate(manual = true)
            MenuAction.CATALOG_BROWSE -> startCatalogBrowse()
            MenuAction.CATALOG_INSTALLED -> speakInstalledModules()
            MenuAction.KEYBOARD_TEXT_BANK -> {
                tts.speak(com.superdl.launcher.keyboard.MatrixTextBank.speakAll(this))
            }
            MenuAction.KEYBOARD_PICKER -> {
                // A rendszer választója CSAK aktív beviteli mezőből működik,
                // ezért egy próbapadot nyitunk: ott a billentyűzet előjön, a
                // váltó működik, és rögtön ki is lehet próbálni az írást.
                try {
                    startActivity(
                        Intent(this, com.superdl.launcher.keyboard.KeyboardTestActivity::class.java)
                    )
                } catch (_: Exception) {
                    tts.speak("A billentyűzet próba nem nyitható meg.")
                }
            }
            MenuAction.KEYBOARD_SETTINGS -> {
                // A billentyűzeteket ELŐBB engedélyezni kell a rendszerben,
                // csak utána jelennek meg a választóban.
                tts.speak(
                    "Billentyűzetek engedélyezése. Keresd meg a Super DL Braille és a " +
                        "Super DL mátrix billentyűzetet, és kapcsold be őket."
                )
                try {
                    startActivity(Intent(android.provider.Settings.ACTION_INPUT_METHOD_SETTINGS))
                } catch (_: Exception) {
                    tts.speak("A beállítás nem nyitható meg.")
                }
            }
            MenuAction.SCREEN_CURTAIN_TOGGLE -> toggleScreenCurtain()
            MenuAction.SCREEN_READER_TOGGLE -> {
                val next = !ScreenReaderPrefs.isEnabled(this)
                ScreenReaderPrefs.setEnabled(this, next)
                if (next) {
                    tts.speak(
                        "Képernyőolvasó bekapcsolva. Csak külső alkalmazásokban működik: " +
                            "fel-le lépkedés, jobbra megnyomás, balra vissza."
                    )
                    if (!isScreenReaderServiceEnabled()) {
                        tts.speakAdd(
                            "Ahhoz, hogy működjön, engedélyezned kell a kisegítő lehetőségeknél. " +
                                "Válaszd az Engedélyezés a rendszerben pontot."
                        )
                    }
                } else {
                    tts.speak("Képernyőolvasó kikapcsolva.")
                }
            }
            MenuAction.SCREEN_READER_SETUP -> {
                tts.speak("Megnyitom a kisegítő lehetőségeket. Keresd meg a Super DL képernyőolvasót, és kapcsold be.")
                try {
                    startActivity(Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS))
                } catch (_: Exception) {
                    tts.speak("A beállítások nem nyithatók meg.")
                }
            }
            MenuAction.SCREEN_READER_STATUS -> {
                tts.speak(ScreenReaderPrefs.speakStatus(this))
                tts.speakAdd(
                    if (isScreenReaderServiceEnabled()) "A rendszerben engedélyezve van."
                    else "A rendszerben MÉG NINCS engedélyezve."
                )
            }
            MenuAction.SCREEN_READER_HELP -> {
                tts.speak(com.superdl.launcher.screenreader.ScreenReaderService.speakGestureHelp())
            }
            MenuAction.SCREEN_READER_COUNTER -> {
                val on = ScreenReaderPrefs.toggleSpeakCounter(this)
                tts.speak(
                    if (on) "Pozíció bemondása bekapcsolva. Minden elemnél elhangzik, hányadiknál tartasz."
                    else "Pozíció bemondása kikapcsolva. Gyorsabb lesz a felolvasás."
                )
            }
            MenuAction.SCREEN_READER_PHONETIC -> {
                val on = ScreenReaderPrefs.togglePhonetic(this)
                tts.speak(
                    if (on) "Betűző ábécé bekapcsolva. Betűnkénti olvasásnál Aladár, Béla, Cecil."
                    else "Betűző ábécé kikapcsolva. Betűnkénti olvasásnál a betűk hangzanak el."
                )
            }
            MenuAction.SCREEN_READER_AUTOREAD -> {
                val on = ScreenReaderPrefs.toggleAutoRead(this)
                tts.speak(
                    if (on) "Automatikus felolvasás bekapcsolva. Új képernyőre lépve elmondja, mi van rajta."
                    else "Automatikus felolvasás kikapcsolva."
                )
            }
            MenuAction.SCREEN_READER_PANIC -> {
                // BIZTONSÁGI RETESZ: azonnali, teljes leállítás.
                ScreenReaderPrefs.emergencyStop(this, "felhasználói vészleállítás")
                tts.speak(
                    "Képernyőolvasó azonnal leállítva. A telefon érintés-kezelése visszaáll a megszokottra. " +
                        "Újraindításhoz kapcsold be a Képernyőolvasó ki és be pontban."
                )
            }
            MenuAction.ALARM_SKIP -> startAlarmSkipFlow()
            MenuAction.ASSISTANT_CONTINUOUS -> {
                val next = !AssistantPrefs.isContinuousMode(this)
                AssistantPrefs.setContinuousMode(this, next)
                if (next) {
                    tts.speak(
                        "Folyamatos beszélgetés bekapcsolva. A parancs után Elena tovább hallgat, " +
                            "és újabb utasítást vár."
                    )
                } else {
                    tts.speak(
                        "Folyamatos beszélgetés kikapcsolva. Elena a parancs végrehajtása után " +
                            "visszalép a menübe."
                    )
                }
            }
            MenuAction.CALENDAR_READ -> startCalendarReadFlow()
            MenuAction.CALENDAR_TOMORROW -> startCalendarTomorrowFlow()
            MenuAction.CALENDAR_WEEK -> startCalendarWeekFlow()
            MenuAction.CALENDAR_ADD -> startCalendarAddFlow()
            MenuAction.CALENDAR_CHOOSE_TARGET -> startCalendarTargetPick()
            MenuAction.CALENDAR_STATUS -> speakCalendarStatus()
            MenuAction.CALENDAR_EDIT_PICK -> startCalendarPickFlow(CalendarPickPurpose.EDIT)
            MenuAction.CALENDAR_DELETE_PICK -> startCalendarPickFlow(CalendarPickPurpose.DELETE)
            MenuAction.NOTE_LIST -> startNoteListFlow(deleteMode = false)
            MenuAction.NOTE_CREATE -> startNoteCreateFlow()
            MenuAction.NOTE_DELETE -> startNoteListFlow(deleteMode = true)
            MenuAction.TIMER_CREATE -> startTimerCreateFlow()
            MenuAction.TIMER_LIST -> startTimerListFlow(TimerListMode.VIEW)
            MenuAction.TIMER_START -> startTimerListFlow(TimerListMode.START)
            MenuAction.TIMER_STOP -> stopActiveTimer()
            MenuAction.TIMER_EDIT -> startTimerListFlow(TimerListMode.EDIT)
            MenuAction.TIMER_DELETE -> startTimerListFlow(TimerListMode.DELETE)
            MenuAction.MUSIC -> startMusicLibraryFlow()
            MenuAction.MUSIC_RESUME_LAST -> resumeLastMusic()
            MenuAction.USB_FILE_TRANSFER -> openUsbFileTransfer()
            MenuAction.FILE_MANAGER -> openFileManager()
            MenuAction.WIFI_PORTAL -> toggleWifiPortal()
            MenuAction.PODCAST_TOP -> startPodcastTopFlow()
            MenuAction.PODCAST_SEARCH -> startPodcastSearchFlow()
            MenuAction.PODCAST_SUBSCRIPTIONS -> startPodcastSubscriptionsFlow()
            MenuAction.PODCAST_DOWNLOADS -> startPodcastDownloadsFlow()
            MenuAction.PODCAST_COUNTRY -> startPodcastCountryFlow()
            MenuAction.PODCAST_OPML_IMPORT -> startPodcastOpmlImport()
            MenuAction.PODCAST_OPML_EXPORT -> startPodcastOpmlExport()
            MenuAction.MUSIC_PLAY_MODE -> cycleMusicPlayMode()
            MenuAction.MUSIC_SEEK_STEP -> cycleMusicSeekStep()
            MenuAction.MUSIC_EQ_PROFILE -> cycleMusicEqProfile()
            MenuAction.MUSIC_SPEECH_ENABLED -> toggleMusicSpeechMaster()
            MenuAction.MUSIC_SPEAK_SKIP -> toggleMusicSpeak("skip")
            MenuAction.MUSIC_SPEAK_STOP -> toggleMusicSpeak("stop")
            MenuAction.MUSIC_SPEAK_SEEK -> toggleMusicSpeak("seek")
            MenuAction.YOUTUBE -> startYoutubeFlow()
            MenuAction.RADIO_HUNGARIAN -> startRadioHungarianFlow()
            MenuAction.RADIO_FAVORITES -> startRadioFavoritesFlow()
            MenuAction.RADIO_SEARCH -> startRadioSearchFlow()
            MenuAction.RADIO_RECORDINGS -> startRadioRecordingsFlow()
            MenuAction.RADIO_SCHEDULE -> startRadioScheduleFlow()
            MenuAction.WEATHER -> startWeatherFlow()
            MenuAction.WEATHER_CITY -> startWeatherCityFlow()
            MenuAction.DAY_GREETING -> speakDayGreeting()
            MenuAction.DAY_SUMMARY -> startDaySummaryFlow()
            MenuAction.STATUS_REPORT -> tts.speak(StatusReportHelper.buildReport(this))
            MenuAction.NEWS_READ -> startNewsReadFlow()
            MenuAction.SHOPPING_LIST -> startShoppingListFlow()
            MenuAction.SHOPPING_NEW_LIST -> listenForShoppingListName()
            MenuAction.EMAIL_IMAP_READ -> startEmailInboxFlow()
            MenuAction.EMAIL_DIAGNOSTICS -> startEmailDiagnosticsFlow()
            MenuAction.WEB_SEARCH -> startWebSearchFlow()
            MenuAction.NAV_WHERE -> startNavWhereFlow()
            MenuAction.NAV_WALK -> startNavWalkFlow()
            MenuAction.NAV_SEARCH -> startNavSearchFlow()
            MenuAction.GPS_RADAR -> startGpsRadarFlow()
            MenuAction.COMPASS_SCAN -> startCompassScan()
            MenuAction.COMPASS_SCAN_STOP -> stopCompassScan()
            MenuAction.GPS_RADAR_SAVED_LIST -> startGpsSavedPoiFlow()
            MenuAction.GPS_RADAR_SAVE_OWN -> requestGpsSaveOwnLocation()
            MenuAction.GPS_RADAR_SAVE_POI -> requestGpsSaveCurrentPoi()
            MenuAction.TRANSIT -> startTransitNearbyFlow()
            MenuAction.TRANSIT_STOP -> startTransitStopFlow()
            MenuAction.TRANSIT_FAVORITES -> startTransitFavoritesFlow()
            MenuAction.TRANSIT_ROUTE -> startTransitRouteFlow()
            MenuAction.TRAIN_NEARBY -> startTrainNearbyFlow()
            MenuAction.TRAIN_STATION_SEARCH -> startTrainStationFlow()
            MenuAction.TRAIN_FAVORITES -> startTrainFavoritesFlow()
            MenuAction.NOTIFICATIONS_READ -> startNotificationReadFlow()
            MenuAction.BATTERY -> {
                tts.speak(InfoHelper.batteryAndSignalReport(this))
            }
            MenuAction.BATTERY_PATROL_TOGGLE -> toggleBatteryPatrol()
            MenuAction.PATROL_BATTERY_TOGGLE -> togglePatrolBattery()
            MenuAction.PATROL_CALL_ALERT_TOGGLE -> togglePatrolCallAlert()
            MenuAction.PATROL_SMS_ALERT_TOGGLE -> togglePatrolSmsAlert()
            MenuAction.PATROL_NOTIFICATION_ALERT_TOGGLE -> togglePatrolNotificationAlert()
            MenuAction.PATROL_TIME_ANNOUNCE_TOGGLE -> togglePatrolTimeAnnounce()
            MenuAction.PATROL_TIME_INTERVAL_CYCLE -> cyclePatrolTimeInterval()
            MenuAction.PATROL_NIGHT_MODE_TOGGLE -> togglePatrolNightMode()
            MenuAction.PATROL_NIGHT_START_SET -> startPatrolNightStartFlow()
            MenuAction.PATROL_NIGHT_END_SET -> startPatrolNightEndFlow()
            MenuAction.PATROL_POWER_BUTTON_TIME_TOGGLE -> togglePatrolPowerButtonTime()
            MenuAction.FLASHLIGHT -> toggleFlashlight()
            MenuAction.QR_SCAN -> {
                tts.speak("Beépített Q R olvasó indítása.")
                qrScanLauncher.launch(Intent(this, QrScanActivity::class.java))
            }
            MenuAction.LIGHT_DETECTOR -> {
                tts.speak("Fénydetektor indítása. A síp magassága mutatja a fény erősségét.")
                startActivity(Intent(this, LightDetectorActivity::class.java))
            }
            MenuAction.COLOR_DETECTOR -> {
                tts.speak("Színfelismerő indítása. Mutasd a kamerának a felületet.")
                startActivity(Intent(this, ColorDetectorActivity::class.java))
            }
            MenuAction.ENV_SCANNER -> {
                tts.speak("Környezeti kitekintő indítása. A kamera felismeri a tárgyakat.")
                startActivity(Intent(this, EnvironmentScannerActivity::class.java))
            }
            MenuAction.ENV_SNAPSHOT -> {
                startActivity(
                    Intent(this, EnvironmentScannerActivity::class.java)
                        .putExtra(EnvironmentScannerActivity.EXTRA_SNAPSHOT_MODE, true)
                )
            }
            MenuAction.CURRENCY_RECOGNIZER -> {
                tts.speak("Super DL Pénzfelismerő indítása. Mutasd a kamerának a bankjegyet.")
                startActivity(Intent(this, CurrencyRecognizerActivity::class.java))
            }
            MenuAction.MEDICATION_READER -> {
                tts.speak("Gyógyszerdoboz olvasó indítása.")
                startActivity(textReaderIntent(TextReaderMode.MEDICATION_BOX))
            }
            MenuAction.LABEL_READER -> {
                tts.speak("Címke olvasó indítása.")
                startActivity(textReaderIntent(TextReaderMode.PRODUCT_LABEL))
            }
            MenuAction.TEXT_READER -> {
                tts.speak("Szöveg olvasó indítása.")
                startActivity(textReaderIntent(TextReaderMode.GENERAL_TEXT))
            }
            MenuAction.CONTINUOUS_OCR -> {
                tts.speak("Folyamatos szövegolvasó indítása.")
                startActivity(textReaderIntent(TextReaderMode.CONTINUOUS))
            }
            MenuAction.SOUND_TRAINING -> startSoundTrainingFlow()
            MenuAction.SOUND_THEME_SELECT -> startSoundThemeFlow()
            MenuAction.RINGTONE_SELECT -> {
                tts.speak("Csengőhang választása. Söpörj fel-le a hangok között, jobbra a kiválasztáshoz.")
                ringtonePickerLauncher.launch(
                    Intent(this, RingtonePickerActivity::class.java).apply {
                        putExtra(RingtonePickerActivity.EXTRA_TONE_TYPE, RingtonePickerActivity.TONE_RINGTONE)
                        putExtra(
                            RingtonePickerActivity.EXTRA_CURRENT_URI,
                            RingtonePreferenceStore.getRingtoneUri(this@MainActivity)?.toString()
                        )
                    }
                )
            }
            MenuAction.ALERT_SOUND_VOLUME_CYCLE -> cycleAlertSoundVolume()
            MenuAction.ALERT_SILENT_MODE_TOGGLE -> toggleAlertSilentMode()
            MenuAction.ALERT_SOUND_CALENDAR -> startAlertSoundPresetFlow(AlertSoundCategory.CALENDAR)
            MenuAction.ALERT_SOUND_MEDICATION -> startAlertSoundPresetFlow(AlertSoundCategory.MEDICATION)
            MenuAction.ALERT_SOUND_ALARM -> startAlertSoundPresetFlow(AlertSoundCategory.ALARM_CLOCK)
            MenuAction.ALERT_SOUND_SMS -> startAlertSoundPresetFlow(AlertSoundCategory.SMS)
            MenuAction.ALERT_SOUND_EMAIL -> startAlertSoundPresetFlow(AlertSoundCategory.EMAIL)
            MenuAction.ALERT_SOUND_NOTIFICATION -> startAlertSoundPresetFlow(AlertSoundCategory.GENERAL_NOTIFICATION)
            MenuAction.TRAINING_PLAYGROUND -> startTrainingPlaygroundFlow()
            MenuAction.BOOK_LIBRARY -> startBookLibraryFlow()
            MenuAction.BOOK_SEARCH -> startBookSearchFlow()
            MenuAction.BOOK_RECENT -> startBookRecentFlow()
            MenuAction.BOOK_BOOKMARKS -> startBookBookmarkFlow(deleteMode = false)
            MenuAction.BOOK_BOOKMARK_DELETE -> startBookBookmarkFlow(deleteMode = true)
            MenuAction.BOOK_RESUME -> resumeLastBook()
            MenuAction.BOOK_FOLDER_SET -> startBookFolderSetFlow()
            MenuAction.BOOK_FOLDER_READ -> readBookFolders()
            MenuAction.BOOK_FOLDER_CLEAR -> clearBookFolders()
            MenuAction.HEARING_AID -> {
                tts.speak("Hallás erősítő indítása. Bluetooth fejhallgatóval is működik.")
                startActivity(Intent(this, HearingAidActivity::class.java))
            }
            MenuAction.GAME_UNO -> {
                tts.speak("UNO kártyajáték indítása.")
                startActivity(Intent(this, UnoActivity::class.java))
            }
            MenuAction.GAME_BLACKJACK -> {
                tts.speak("Blackjack indítása.")
                startActivity(Intent(this, BlackjackActivity::class.java))
            }
            MenuAction.GAME_POKER -> {
                tts.speak("Póker indítása.")
                startActivity(Intent(this, PokerActivity::class.java))
            }
            MenuAction.GAME_SLOT -> {
                tts.speak("Félkarú rabló indítása.")
                startActivity(Intent(this, com.superdl.launcher.games.slot.SlotActivity::class.java))
            }
            MenuAction.GAME_MILLE_BORNES -> {
                tts.speak("Mille Bornes indítása.")
                startActivity(Intent(this, MilleBornesActivity::class.java))
            }
            MenuAction.CALCULATOR -> startCalculatorFlow()
            MenuAction.WIFI_TOGGLE -> toggleWifi()
            MenuAction.HOTSPOT_TOGGLE -> toggleHotspot()
            MenuAction.BT_TOGGLE -> toggleBluetooth()
            MenuAction.CALL_FILTER_BLOCK_PRIVATE_TOGGLE -> cycleCallFilterMode()
            MenuAction.CALL_FILTER_MODE_CYCLE -> cycleCallFilterMode()
            MenuAction.CALL_FILTER_MODE_STATUS -> tts.speak(CallFilterStore.speakMode(this))

            MenuAction.VOICE_ASSISTANT -> startVoiceAssistantFlow()
            MenuAction.ELENA_WAKE_LISTEN_TOGGLE -> toggleElenaWakeListen()
            MenuAction.ELENA_WAKE_LISTEN_ON -> setElenaWakeListen(true)
            MenuAction.ELENA_WAKE_LISTEN_OFF -> setElenaWakeListen(false)
            MenuAction.ELENA_WAKE_TRAIN -> startElenaWakeTrainFlow()
            MenuAction.ELENA_WAKE_CUSTOM_LIST -> tts.speak(ElenaWakeHelper.speakCustomPhrases(this))
            MenuAction.ASSISTANT_DEFAULT_SETUP -> startAssistantDefaultSetupFlow()
            MenuAction.ASSISTANT_DEFAULT_STATUS -> tts.speak(AssistantRoleHelper.speakStatus(this))
            MenuAction.DIALER_DEFAULT_SETUP -> startDialerDefaultSetupFlow()
            MenuAction.DIALER_DEFAULT_STATUS -> tts.speak(DialerRoleHelper.speakStatus(this))
            MenuAction.BT_ASSISTANT_TOGGLE -> toggleBluetoothAssistant()
            MenuAction.VOLUME_UP -> {
                val am = getSystemService(AUDIO_SERVICE) as AudioManager
                am.adjustVolume(AudioManager.ADJUST_RAISE, AudioManager.FLAG_PLAY_SOUND)
                tts.speak("Hangerő növelve.")
            }
            MenuAction.VOLUME_DOWN -> {
                val am = getSystemService(AUDIO_SERVICE) as AudioManager
                am.adjustVolume(AudioManager.ADJUST_LOWER, AudioManager.FLAG_PLAY_SOUND)
                tts.speak("Hangerő csökkentve.")
            }
            MenuAction.TTS_SPEED_UP -> tts.speedUp()
            MenuAction.TTS_SPEED_DOWN -> tts.speedDown()
            MenuAction.TTS_ENGINE_SELECT -> startTtsEngineFlow()
            MenuAction.TTS_ENGINE_READ -> readCurrentTtsEngine()
            MenuAction.ABOUT_APP -> tts.speak(LegalTexts.aboutApp())
            MenuAction.ABOUT_DEVELOPER -> tts.speak(LegalTexts.aboutDeveloper())
            MenuAction.CONTACT_EMAIL -> contactDeveloperByEmailInternal()
            MenuAction.PRIVACY_POLICY -> startLegalBrowseFlow(LegalTexts.privacyPolicy(), "Adatvédelmi tájékoztató")
            MenuAction.TERMS_OF_USE -> startLegalBrowseFlow(LegalTexts.termsOfUse(), "Felhasználási feltételek")
            MenuAction.LEGAL_NOTICE -> startLegalBrowseFlow(LegalTexts.legalNotice(), "Jogi nyilatkozat")
            MenuAction.EXTERNAL_APPS -> startExternalAppsFlow()
            MenuAction.FAVORITE_APPS_LAUNCH -> startFavoriteAppsFlow(AppFlow.FavoriteAppsMode.LAUNCH)
            MenuAction.FAVORITE_APPS_ADD -> startFavoriteAppsAddFlow()
            MenuAction.FAVORITE_APPS_REMOVE -> startFavoriteAppsFlow(AppFlow.FavoriteAppsMode.REMOVE)
            MenuAction.LOCK_PIN_TOGGLE -> toggleLockPin()
            MenuAction.LOCK_PIN_SET -> startLockPinSetupFlow()
            MenuAction.LOCK_PIN_STATUS -> tts.speak(LockPinStore.speakStatus(this))
            MenuAction.KEYGUARD_PIN_ASSIST_TOGGLE -> toggleKeyguardPinAssist()
            MenuAction.KEYGUARD_PIN_ASSIST_SETUP -> setupKeyguardPinAssist()
            MenuAction.KEYGUARD_PIN_ASSIST_STATUS -> tts.speak(KeyguardPinSettings.speakStatus(this))
            MenuAction.DICTAPHONE_RECORD -> startDictaphoneRecordingFlow()
            MenuAction.DICTAPHONE_SETTINGS -> startDictaphoneSettingsFlow()
            MenuAction.DICTAPHONE_RAW_TOGGLE -> {
                val next = DictaphoneSettingsStore.toggleRawCapture(this)
                if (next) {
                    tts.speak(
                        "Teljesen nyers felvétel bekapcsolva. Semmilyen zajszűrés és " +
                            "hangerő-kiegyenlítés nem fut, pontosan azt rögzíti, amit a mikrofon hall."
                    )
                    tts.speakAdd(DictaphoneAudioSource.speakCapability(this))
                } else {
                    tts.speak("Teljesen nyers felvétel kikapcsolva. A készülék szokásos mikrofon-feldolgozása működik.")
                }
            }
            MenuAction.DICTAPHONE_CAPABILITIES -> {
                tts.speak("Mikrofon vizsgálata.")
                Thread {
                    val summary = DictaphoneCapabilities.speak(this)
                    postWhenAlive { tts.speak(summary) }
                }.start()
            }
            MenuAction.DICTAPHONE_LIBRARY -> startDictaphoneLibraryFlow()
            MenuAction.MEDICATION_READ -> readMedicationReminders()
            MenuAction.MEDICATION_ADD -> startMedicationAddFlow()
            MenuAction.MEDICATION_SEARCH -> startMedicationSearchFlow()
            MenuAction.MEDICATION_DELETE -> startMedicationListFlow(deleteMode = true)
            MenuAction.LOCATION_TRAIN -> startLocationTrainFlow()
            MenuAction.LOCATION_WATCH_START -> startLocationWatchFlow()
            MenuAction.LOCATION_WATCH_TEXT -> startLocationWatchTextFlow()
            MenuAction.LOCATION_PROFILE_LIST -> startLocationProfileListFlow(deleteMode = false)
            MenuAction.LOCATION_WATCH_STOP -> stopLocationWatchFlow()
            MenuAction.FACE_CAMERA -> startFaceCameraFlow(selfie = false)
            MenuAction.FACE_CAMERA_SELFIE -> startFaceCameraFlow(selfie = true)
            MenuAction.FACE_CAMERA_QUALITY -> startCameraQualityFlow()
            MenuAction.GPS_ROUTE_RECORD -> startGpsRouteRecordFlow()
            MenuAction.GPS_ROUTE_STOP -> stopGpsRouteOrGuidanceFlow()
            MenuAction.GPS_ROUTE_LIST -> startGpsRouteListFlow(deleteMode = false)
            MenuAction.GPS_ROUTE_GUIDE -> startGpsRouteListFlow(deleteMode = false, guideMode = true)
            MenuAction.GPS_ROUTE_DELETE -> startGpsRouteListFlow(deleteMode = true)
            MenuAction.CARD_TRAIN -> startCardTrainFlow()
            MenuAction.CARD_RECOGNIZE -> startCardRecognizeFlow()
            MenuAction.CARD_LIST -> startCardListFlow(deleteMode = false)
            MenuAction.CARD_DELETE -> startCardListFlow(deleteMode = true)
            MenuAction.NEWS_FEED_MANAGE -> startNewsFeedManageFlow()
            MenuAction.NEWS_FEED_IMPORT_OPML -> startNewsOpmlImportFlow()
            MenuAction.EXIT_LAUNCHER -> startLauncherExitConfirmFlow()
        }
    }

    // ==================== SMS KÜLDÉS ====================

    private fun startSmsComposeFlow() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.SEND_SMS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("SMS küldés engedély szükséges.")
            return
        }
        ensureMicAndRun {
            activeFlow = AppFlow.SmsAwaitRecipient
            updateFlowDisplay()
            listenForSmsRecipient()
        }
    }

    private fun listenForSmsRecipient() {
        voiceInput.listen(
            prompt = "Mondd a címzett nevét vagy telefonszámát.",
            speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
            onResult = { spoken -> resolveSmsRecipient(spoken) },
            onError = { exitFlow("Nem értettem a címzettet.") }
        )
    }

    private fun resolveSmsRecipient(spoken: String) {
        val contacts = ContactHelper.searchByName(this, spoken)
        val resolved = SmsHelper.resolveRecipient(spoken, contacts)
        when {
            resolved != null -> enterSmsRecipientConfirm(resolved)
            contacts.isEmpty() -> exitFlow("Nem található címzett.")
            else -> {
                activeFlow = AppFlow.SmsPickContact(contacts, 0)
                updateFlowDisplay()
                tts.speak("Több találat. ${contacts.size} névjegy. Söpörj fel-le választás, jobbra kiválasztás.")
                speakContactMatch(contacts.first())
            }
        }
    }

    private fun listenForSmsMessage(recipientLabel: String) {
        voiceInput.listen(
            prompt = "Mondd az üzenetet $recipientLabel részére. " +
                "Kimondhatod az írásjeleket is: vessző, pont, kérdőjel.",
            speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
            onResult = { message ->
                val trimmed = SpeechPunctuation.apply(message)
                if (trimmed.isBlank()) {
                    exitFlow("Az üzenet üres.")
                    return@listen
                }
                val flow = activeFlow as? AppFlow.SmsAwaitMessage ?: return@listen
                enterSmsConfirm(flow.recipient, trimmed)
            },
            onError = { exitFlow("Nem értettem az üzenetet.") }
        )
    }

    private fun enterSmsRecipientConfirm(recipient: Recipient) {
        activeFlow = AppFlow.SmsRecipientConfirm(recipient)
        updateFlowDisplay()
        repeatSmsRecipientConfirm(recipient)
    }

    private fun repeatSmsRecipientConfirm(recipient: Recipient) {
        val readback = buildRecipientReadback(recipient)
        tts.speak("$readback Jó a címzett? Söpörj jobbra a folytatáshoz, söprés balra a mégsehez. Ismétlés: söprés fel.")
    }

    private fun proceedToSmsMessage(recipient: Recipient) {
        voiceInput.cancel()
        val forwardBody = pendingSmsForwardBody
        if (!forwardBody.isNullOrBlank()) {
            enterSmsConfirm(recipient, forwardBody)
            return
        }
        activeFlow = AppFlow.SmsAwaitMessage(recipient)
        updateFlowDisplay()
        listenForSmsMessage(recipient.label)
    }

    private fun enterSmsConfirm(recipient: Recipient, message: String) {
        activeFlow = AppFlow.SmsConfirm(recipient, message)
        updateFlowDisplay()
        repeatSmsConfirm(recipient, message)
    }

    private fun repeatSmsConfirm(recipient: Recipient, message: String) {
        val readback = buildSmsReadback(recipient, message)
        tts.speak("$readback Elküldjem? Söpörj jobbra az elküldéshez, söprés balra a mégsehez. Ismétlés: söprés fel.")
    }

    private fun buildRecipientReadback(recipient: Recipient): String {
        val phoneHint = ContactHelper.maskPhone(recipient.phone)
        return "Címzett: ${recipient.label}. Telefonszám $phoneHint."
    }

    private fun buildSmsReadback(recipient: Recipient, message: String): String {
        return "${buildRecipientReadback(recipient)} Üzenet: $message."
    }

    private fun sendSms(recipient: Recipient, message: String) {
        val ok = SmsHelper.send(this, recipient.phone, message)
        pendingSmsForwardBody = null
        val restore = smsInboxRestore
        smsInboxRestore = null
        if (restore != null && ok) {
            feedbackSuccess()
            activeFlow = restore
            updateFlowDisplay()
            tts.speak("Üzenet elküldve ${recipient.label} részére. Vissza az üzenetlistában.")
            speakSmsPreview(restore.messages[restore.index])
            return
        }
        exitFlow(
            if (ok) "Üzenet elküldve ${recipient.label} részére." else "Üzenet küldése sikertelen.",
            success = ok,
            error = !ok
        )
    }

    private fun startSmsToPhone(phone: String, name: String) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.SEND_SMS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("SMS küldés engedély szükséges.")
            return
        }
        val trimmedPhone = phone.trim()
        if (trimmedPhone.isBlank()) {
            tts.speak("Nincs telefonszám.")
            return
        }
        voiceInput.cancel()
        val label = name.trim().ifBlank { trimmedPhone }
        enterSmsRecipientConfirm(Recipient(trimmedPhone, label))
    }

    // ==================== SMS OLVASÁS ====================

    private fun ensureReadSmsPermission(folder: SmsFolder, onGranted: () -> Unit) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_SMS)
            == PackageManager.PERMISSION_GRANTED
        ) {
            pendingSmsFolderRead = null
            onGranted()
            return
        }
        pendingSmsFolderRead = folder
        ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.READ_SMS), PERM_REQUEST)
        tts.speak("SMS olvasás engedély szükséges.")
    }

    private fun startSmsInboxFlow() {
        ensureReadSmsPermission(SmsFolder.INBOX) { openSmsFolderFlow(SmsFolder.INBOX) }
    }

    private fun startSmsSentFlow() {
        ensureReadSmsPermission(SmsFolder.SENT) { openSmsFolderFlow(SmsFolder.SENT) }
    }

    private fun openSmsFolderFlow(folder: SmsFolder) {
        val messages = SmsHelper.getRecentMessages(this, folder)
        if (messages.isEmpty()) {
            tts.speak(
                when (folder) {
                    SmsFolder.INBOX -> {
                        if (SmsRoleHelper.isDefaultSmsApp(this)) {
                            "Nincs bejövő üzenet. Ha most érkezett SMS, várj pár másodpercet, majd próbáld újra."
                        } else {
                            "Nincs bejövő üzenet."
                        }
                    }
                    SmsFolder.SENT -> "Nincs kimenő üzenet."
                }
            )
            return
        }
        showSmsFolder(folder, messages, 0, announceCount = true)
    }

    private fun showSmsFolder(
        folder: SmsFolder,
        messages: List<SmsMessage>,
        index: Int,
        announceCount: Boolean
    ) {
        if (messages.isEmpty()) return
        val safeIndex = index.coerceIn(0, messages.lastIndex)
        activeFlow = AppFlow.SmsInbox(messages, safeIndex, folder)
        updateFlowDisplay()
        if (announceCount) {
            val folderLabel = folder.label.lowercase()
            tts.speak("${messages.size} $folderLabel üzenet. Söpörj fel-le navigálás, jobbra műveletek, balra vissza.")
        }
        speakSmsPreview(messages[safeIndex], folder)
    }

    private fun refreshSmsInboxIfVisible() {
        val flow = activeFlow as? AppFlow.SmsInbox ?: return
        if (flow.folder != SmsFolder.INBOX) return
        val messages = SmsHelper.getRecentMessages(this, SmsFolder.INBOX)
        if (messages.isEmpty()) return
        val previousId = flow.messages.getOrNull(flow.index)?.id
        val newIndex = messages.indexOfFirst { it.id == previousId }.let { found ->
            if (found >= 0) found else 0
        }
        activeFlow = AppFlow.SmsInbox(messages, newIndex, SmsFolder.INBOX)
        updateFlowDisplay()
        if (newIndex == 0 && previousId != messages.first().id) {
            speakSmsPreview(messages.first(), SmsFolder.INBOX)
        }
    }

    private fun speakSmsPreview(message: SmsMessage, folder: SmsFolder = message.folder) {
        val label = SmsHelper.resolveSenderLabel(this, message.address)
        val previewBody = message.body.ifBlank { "üres üzenet" }
        val preview = if (previewBody.length > 60) previewBody.take(60) + "…" else previewBody
        val prefix = when (folder) {
            SmsFolder.INBOX -> "Feladó: $label."
            SmsFolder.SENT -> "Címzett: $label."
        }
        tts.speak("$prefix $preview")
    }

    private fun enterSmsContextMenu(flow: AppFlow.SmsInbox) {
        val actions = SmsContextAction.all
        activeFlow = AppFlow.SmsContextMenu(flow.messages, flow.index, actions, 0, flow.folder)
        updateFlowDisplay()
        tts.speak("Üzenet műveletek. ${actions.first().label}. Söpörj fel-le választás, jobbra végrehajtás, balra vissza.")
    }

    private fun navigateSmsContextMenu(flow: AppFlow.SmsContextMenu, delta: Int) {
        val next = (flow.actionIndex + delta + flow.actions.size) % flow.actions.size
        activeFlow = flow.copy(actionIndex = next)
        updateFlowDisplay()
        tts.speak(flow.actions[next].label)
    }

    private fun onSmsContextActivate(flow: AppFlow.SmsContextMenu) {
        val message = flow.messages[flow.messageIndex]
        when (flow.actions[flow.actionIndex]) {
            SmsContextAction.READ -> tts.speak(message.body.ifBlank { "Üres üzenet." })
            SmsContextAction.REPLY -> startSmsReplyTo(message, flow.messages, flow.messageIndex, flow.folder)
            SmsContextAction.FORWARD -> startSmsForward(message, flow.messages, flow.messageIndex, flow.folder)
            SmsContextAction.DELETE -> enterSmsDeleteConfirm(flow.messages, flow.messageIndex, flow.folder)
        }
    }

    private fun returnToSmsInbox(messages: List<SmsMessage>, index: Int, folder: SmsFolder) {
        activeFlow = AppFlow.SmsInbox(messages, index, folder)
        updateFlowDisplay()
        tts.speak("Vissza az üzenetlistában.")
        speakSmsPreview(messages[index], folder)
    }

    private fun startSmsReplyTo(
        message: SmsMessage,
        messages: List<SmsMessage>,
        index: Int,
        folder: SmsFolder
    ) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.SEND_SMS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("SMS küldés engedély szükséges.")
            return
        }
        smsInboxRestore = AppFlow.SmsInbox(messages, index, folder)
        pendingSmsForwardBody = null
        val label = SmsHelper.resolveSenderLabel(this, message.address)
        ensureMicAndRun {
            proceedToSmsMessage(Recipient(message.address, label))
        }
    }

    private fun startSmsForward(
        message: SmsMessage,
        messages: List<SmsMessage>,
        index: Int,
        folder: SmsFolder
    ) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.SEND_SMS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("SMS küldés engedély szükséges.")
            return
        }
        smsInboxRestore = AppFlow.SmsInbox(messages, index, folder)
        pendingSmsForwardBody = message.body
        ensureMicAndRun {
            activeFlow = AppFlow.SmsAwaitRecipient
            updateFlowDisplay()
            listenForSmsRecipient()
        }
    }

    private fun enterSmsDeleteConfirm(messages: List<SmsMessage>, index: Int, folder: SmsFolder) {
        activeFlow = AppFlow.SmsDeleteConfirm(messages, index, folder)
        updateFlowDisplay()
        repeatSmsDeleteConfirm(AppFlow.SmsDeleteConfirm(messages, index, folder))
    }

    private fun repeatSmsDeleteConfirm(flow: AppFlow.SmsDeleteConfirm) {
        val label = SmsHelper.resolveSenderLabel(this, flow.messages[flow.messageIndex].address)
        val prompt = when (flow.folder) {
            SmsFolder.INBOX -> "Biztosan törlöd $label üzenetét?"
            SmsFolder.SENT -> "Biztosan törlöd a $label részére küldött üzenetet?"
        }
        tts.speak("$prompt Söpörj jobbra a törléshez, söprés balra a mégsehez. Ismétlés: söprés fel.")
    }

    private fun deleteSmsMessage(flow: AppFlow.SmsDeleteConfirm) {
        val message = flow.messages[flow.messageIndex]
        val ok = SmsHelper.deleteMessage(this, message.id)
        if (!ok) {
            exitFlow("Üzenet törlése sikertelen.", error = true)
            return
        }
        feedbackSuccess()
        val updated = SmsHelper.getRecentMessages(this, flow.folder)
        if (updated.isEmpty()) {
            val emptyText = when (flow.folder) {
                SmsFolder.INBOX -> "Üzenet törölve. Nincs több bejövő üzenet."
                SmsFolder.SENT -> "Üzenet törölve. Nincs több kimenő üzenet."
            }
            exitFlow(emptyText, success = true)
            return
        }
        val newIndex = flow.messageIndex.coerceAtMost(updated.lastIndex)
        activeFlow = AppFlow.SmsInbox(updated, newIndex, flow.folder)
        updateFlowDisplay()
        tts.speak("Üzenet törölve.")
        speakSmsPreview(updated[newIndex], flow.folder)
    }

    // ==================== E-MAIL ====================

    private fun startEmailComposeFlow() {
        if (!EmailHelper.isConfigured(this)) {
            tts.speakThen(
                "Előbb állítsd be az e-mail küldőt a menüben: E-mail küldő beállítása. " +
                    "Gmail esetén alkalmazásjelszó szükséges."
            ) {
                startEmailSmtpSetupFlow()
            }
            return
        }
        ensureMicAndRun {
            activeFlow = AppFlow.EmailAwaitRecipient
            updateFlowDisplay()
            listenForEmailRecipient()
        }
    }

    private fun listenForEmailRecipient() {
        voiceInput.listen(
            prompt = "Mondd a címzett nevét vagy e-mail címét.",
            speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
            onResult = { spoken -> resolveEmailRecipient(spoken) },
            onError = { exitFlow("Nem értettem a címzettet.") }
        )
    }

    private fun resolveEmailRecipient(spoken: String) {
        val matches = EmailHelper.searchRecipients(this, spoken)
        val resolved = EmailHelper.resolveRecipient(spoken, matches)
        when {
            resolved != null -> enterEmailRecipientConfirm(resolved)
            matches.isEmpty() -> exitFlow("Nem található e-mail címzett.")
            else -> {
                activeFlow = AppFlow.EmailPickRecipient(matches, 0)
                updateFlowDisplay()
                tts.speak("Több találat. ${matches.size} cím. Söpörj fel-le választás, jobbra kiválasztás.")
                speakEmailRecipient(matches.first())
            }
        }
    }

    private fun speakEmailRecipient(recipient: EmailRecipient) {
        tts.speak(recipient.speakPreview())
    }

    private fun navigateEmailPick(flow: AppFlow.EmailPickRecipient, delta: Int) {
        val next = (flow.index + delta + flow.matches.size) % flow.matches.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        speakEmailRecipient(flow.matches[next])
    }

    private fun enterEmailRecipientConfirm(recipient: EmailRecipient) {
        activeFlow = AppFlow.EmailRecipientConfirm(recipient)
        updateFlowDisplay()
        repeatEmailRecipientConfirm(recipient)
    }

    private fun repeatEmailRecipientConfirm(recipient: EmailRecipient) {
        tts.speak(
            "Címzett: ${recipient.label}. E-mail: ${EmailHelper.speakAddress(recipient.email)}. " +
                "Jó a címzett? Söpörj jobbra a folytatáshoz, söprés balra a mégsehez."
        )
    }

    private fun proceedToEmailSubject(recipient: EmailRecipient) {
        voiceInput.cancel()
        activeFlow = AppFlow.EmailAwaitSubject(recipient)
        updateFlowDisplay()
        listenForEmailSubject(recipient)
    }

    private fun listenForEmailSubject(recipient: EmailRecipient) {
        voiceInput.listen(
            prompt = "Mondd az e-mail tárgyát, vagy mondd: névtelen.",
            speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
            onResult = { spoken ->
                val subject = parseEmailSubject(spoken)
                proceedToEmailBody(recipient, subject)
            },
            onError = { exitFlow("Nem értettem a tárgyat.") }
        )
    }

    private fun parseEmailSubject(spoken: String): String {
        val trimmed = spoken.trim()
        if (trimmed.isBlank()) return ""
        val lower = trimmed.lowercase()
        return if (lower in listOf("névtelen", "nevtelen", "tárgy nélkül", "targy nelkul", "nincs tárgy", "nincs targy")) {
            ""
        } else {
            trimmed
        }
    }

    private fun proceedToEmailBody(recipient: EmailRecipient, subject: String) {
        voiceInput.cancel()
        activeFlow = AppFlow.EmailAwaitBody(recipient, subject)
        updateFlowDisplay()
        listenForEmailBody(recipient, subject)
    }

    private fun listenForEmailBody(recipient: EmailRecipient, subject: String) {
        voiceInput.listen(
            prompt = "Mondd az e-mail szövegét ${recipient.label} részére. " +
                "Kimondhatod az írásjeleket is: vessző, pont, kérdőjel, új sor.",
            speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
            onResult = { spoken ->
                // A diktált szabad szöveg központozása és szépítése.
                val body = SpeechPunctuation.apply(spoken)
                if (body.isBlank()) {
                    exitFlow("Az e-mail szövege üres.")
                    return@listen
                }
                enterEmailConfirm(recipient, subject, body)
            },
            onError = { exitFlow("Nem értettem az e-mail szövegét.") }
        )
    }

    private fun enterEmailConfirm(recipient: EmailRecipient, subject: String, body: String) {
        activeFlow = AppFlow.EmailConfirm(recipient, subject, body)
        updateFlowDisplay()
        repeatEmailConfirm(recipient, subject, body)
    }

    private fun repeatEmailConfirm(recipient: EmailRecipient, subject: String, body: String) {
        val subjectText = subject.ifBlank { "névtelen tárgy" }
        tts.speak(
            "Címzett: ${recipient.label}. Tárgy: $subjectText. Szöveg: $body. " +
                "Elküldjem? Söpörj jobbra az elküldéshez, söprés balra a mégsehez."
        )
    }

    private fun sendEmail(recipient: EmailRecipient, subject: String, body: String) {
        voiceInput.cancel()
        tts.speak("E-mail küldése. Várj egy pillanatot.")
        Thread {
            val ok = EmailHelper.send(this, recipient, subject, body)
            postWhenAlive {
                exitFlow(
                    if (ok) "E-mail elküldve ${recipient.label} részére."
                    else "E-mail küldés sikertelen. Ellenőrizd az e-mail küldő beállításait.",
                    success = ok,
                    error = !ok
                )
            }
        }.start()
    }

    private fun startEmailSmtpSetupFlow() {
        smtpDraftUsername = ""
        smtpDraftPassword = ""
        val accounts = EmailAccountHelper.getSmtpCandidates(this)
        when {
            accounts.size == 1 -> {
                smtpDraftUsername = accounts.first()
                tts.speakThen(
                    "${EmailAccountHelper.speakAccount(accounts.first())} " +
                        "Most mondd a Gmail alkalmazásjelszavadat. Ez nem a sima jelszavad."
                ) {
                    listenForSmtpPassword()
                }
            }
            accounts.size > 1 -> {
                activeFlow = AppFlow.EmailSmtpPickAccount(accounts, 0)
                updateFlowDisplay()
                tts.speak(
                    "${accounts.size} e-mail fiók a telefonon. Söpörj fel-le választás, " +
                        "jobbra kiválasztás. ${EmailAccountHelper.speakAccount(accounts.first())}"
                )
            }
            else -> listenForSmtpUsernameManual()
        }
    }

    private fun listenForSmtpUsernameManual() {
        ensureMicAndRun {
            activeFlow = AppFlow.EmailSmtpAwaitUsername
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Nem találtam e-mail fiókot a telefonon. Mondd a Gmail címedet.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val email = EmailHelper.parseSpokenAddress(spoken) ?: spoken.trim()
                    if (!EmailHelper.isValidEmail(email)) {
                        tts.speakThen("Nem értettem az e-mail címet. Próbáld újra.") {
                            listenForSmtpUsernameManual()
                        }
                        return@listen
                    }
                    smtpDraftUsername = email
                    listenForSmtpPassword()
                },
                onError = { exitFlow("E-mail küldő beállítás megszakítva.") }
            )
        }
    }

    private fun navigateEmailSmtpPickAccount(flow: AppFlow.EmailSmtpPickAccount, delta: Int) {
        val next = (flow.index + delta + flow.accounts.size) % flow.accounts.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(EmailAccountHelper.speakAccount(flow.accounts[next]))
    }

    private fun onEmailSmtpPickAccountActivate(flow: AppFlow.EmailSmtpPickAccount) {
        smtpDraftUsername = flow.accounts[flow.index]
        tts.speakThen(
            "${EmailAccountHelper.speakAccount(smtpDraftUsername)} " +
                "Most mondd a Gmail alkalmazásjelszavadat."
        ) {
            listenForSmtpPassword()
        }
    }

    private fun repeatSmtpPrompt(flow: AppFlow) {
        when (flow) {
            is AppFlow.EmailSmtpPickAccount -> tts.speak(EmailAccountHelper.speakAccount(flow.accounts[flow.index]))
            AppFlow.EmailSmtpAwaitUsername -> listenForSmtpUsernameManual()
            AppFlow.EmailSmtpAwaitPassword -> listenForSmtpPassword()
            AppFlow.EmailSmtpAwaitFromName -> listenForSmtpFromName()
            else -> Unit
        }
    }

    private fun listenForSmtpPassword() {
        activeFlow = AppFlow.EmailSmtpAwaitPassword
        updateFlowDisplay()
        // A Gmail app-jelszót gyakorlatilag lehetetlen bediktálni (16 véletlen
        // karakter), ezért felajánljuk a fájlból olvasást: a felhasználó a
        // WiFi fájlportálon feltölt egy txt-t, és abból vesszük ki.
        val fileHint = findPasswordFile()
        if (fileHint != null && readPasswordFromFile(fileHint)) {
            // Sikerült a fájlból beolvasni – nem kell diktálni a 16 karaktert.
            val masked = smtpDraftPassword.take(2) + " és további " +
                (smtpDraftPassword.length - 2).coerceAtLeast(0) + " karakter"
            tts.speakThen(
                "A jelszót beolvastam a feltöltött fájlból: ${fileHint.name}. " +
                    "A jelszó $masked. Folytatom a beállítást."
            ) {
                listenForSmtpFromName()
            }
            return
        }
        listenForSmtpPasswordSpoken()
    }

    /** A feltöltött jelszó-fájl megkeresése a portál mappájában. */
    private fun findPasswordFile(): java.io.File? = try {
        val dir = FileManagerHelper.portalDir()
        dir.listFiles()
            ?.filter { f -> f.isFile && f.name.lowercase().endsWith(".txt") }
            ?.sortedByDescending { f -> f.lastModified() }
            ?.firstOrNull { f ->
                val n = f.name.lowercase()
                n.contains("jelszo") || n.contains("jelszó") ||
                    n.contains("password") || n.contains("pass") ||
                    n.contains("gmail") || n.contains("app")
            }
    } catch (_: Exception) {
        null
    }

    /** A jelszó beolvasása a feltöltött fájlból. */
    private fun readPasswordFromFile(file: java.io.File): Boolean {
        val content = FileManagerHelper.readTextFile(file, 500) ?: return false
        val password = content.lineSequence()
            .map { line -> line.trim() }
            .firstOrNull { line -> line.isNotBlank() }
            ?: return false
        smtpDraftPassword = password
        return true
    }

    private fun listenForSmtpPasswordSpoken() {
        voiceInput.listen(
            prompt = "Mondd a Gmail alkalmazásjelszavadat. Ez nem a sima jelszavad.",
            speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
            onResult = { spoken ->
                val password = spoken.trim().replace(" ", "")
                if (password.isBlank()) {
                    tts.speak("A jelszó nem lehet üres.")
                    listenForSmtpPasswordSpoken()
                    return@listen
                }
                smtpDraftPassword = password
                listenForSmtpFromName()
            },
            onError = { exitFlow("E-mail küldő beállítás megszakítva.") }
        )
    }

    private fun listenForSmtpFromName() {
        activeFlow = AppFlow.EmailSmtpAwaitFromName
        updateFlowDisplay()
        voiceInput.listen(
            prompt = "Mondd a nevedet a küldőmezőhöz, vagy mondd: névtelen.",
            speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
            onResult = { spoken ->
                val name = parseEmailSubject(spoken)
                val config = SmtpConfigStore.gmailPreset(smtpDraftUsername, smtpDraftPassword, name)
                SmtpConfigStore.save(this, config)
                smtpDraftUsername = ""
                smtpDraftPassword = ""
                activeFlow = AppFlow.Menu
                updateFlowDisplay()
                tts.speak("E-mail küldő mentve. ${config.speakSummary()}")
            },
            onError = { exitFlow("E-mail küldő beállítás megszakítva.") }
        )
    }

    private fun readEmailSmtpConfig() {
        val config = SmtpConfigStore.get(this)
        if (config == null) {
            tts.speak("Nincs beállított e-mail küldő.")
            return
        }
        tts.speak(config.speakSummary())
    }

    private fun clearEmailSmtpConfig() {
        SmtpConfigStore.clear(this)
        tts.speak("E-mail küldő törölve.")
    }

    private fun startEmailImportFlow() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CONTACTS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("Névjegy engedély szükséges az importáláshoz.")
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.READ_CONTACTS), PERM_REQUEST)
            return
        }
        val result = EmailHelper.importFromPhone(this)
        when {
            result.added > 0 -> tts.speak(
                "Import kész. ${result.added} új cím mentve. " +
                    "Összesen ${result.totalCandidates} cím található a névjegyekben és fiókokban."
            )
            result.totalCandidates > 0 -> tts.speak("Minden elérhető e-mail cím már mentve van.")
            else -> tts.speak("Nem találtam importálható e-mail címet a névjegyekben vagy a telefon fiókjaiban.")
        }
    }

    private fun startEmailAddFlow() {
        ensureMicAndRun {
            voiceInput.listen(
                prompt = "Mondd az e-mail címet. Előtte nevet is mondhatsz, például: Anna kukac gmail pont com.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val email = EmailHelper.parseSpokenAddress(spoken)
                    if (email == null) {
                        tts.speak("Nem értettem az e-mail címet. Próbáld újra.")
                        return@listen
                    }
                    val label = spoken.replace(email, "", ignoreCase = true)
                        .replace("kukac", "", ignoreCase = true)
                        .replace("pont", "", ignoreCase = true)
                        .trim()
                        .ifBlank { email }
                    val saved = EmailStore.add(this, EmailRecipient(email, label))
                    tts.speak(
                        if (saved) "E-mail cím mentve: $label."
                        else "Az e-mail cím nem menthető. Lehet, hogy a lista megtelt."
                    )
                },
                onError = { tts.speak("Nem értettem. Próbáld újra.") }
            )
        }
    }

    private fun startEmailListFlow() {
        val recipients = EmailStore.getAll(this)
        if (recipients.isEmpty()) {
            tts.speak("Nincs mentett e-mail cím. Használd az importálást vagy adj hozzá címet.")
            return
        }
        activeFlow = AppFlow.EmailBrowseRecipients(recipients, 0)
        updateFlowDisplay()
        tts.speak("${recipients.size} mentett cím. Söpörj fel-le navigálás, jobbra felolvasás, balra vissza.")
        speakEmailRecipient(recipients.first())
    }

    private fun navigateEmailList(flow: AppFlow.EmailBrowseRecipients, delta: Int) {
        val next = (flow.index + delta + flow.recipients.size) % flow.recipients.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        speakEmailRecipient(flow.recipients[next])
    }

    // ==================== NÉVJEGY HÍVÁS ====================

    private fun startContactCallFlow() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("Hívás engedély szükséges.")
            return
        }
        ensureMicAndRun {
            voiceInput.listen(
                prompt = "Mondd a névjegy nevét.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken -> resolveCallContact(spoken) },
                onError = { tts.speak("Nem értettem a nevet.") }
            )
        }
    }

    private fun resolveCallContact(spoken: String) {
        val contacts = ContactHelper.searchByName(this, spoken)
        when {
            contacts.isEmpty() -> tts.speak("Nem található névjegy: $spoken")
            contacts.size == 1 -> enterCallConfirm(contacts.first())
            else -> {
                activeFlow = AppFlow.CallPickContact(contacts, 0)
                updateFlowDisplay()
                tts.speak("Több találat. ${contacts.size} névjegy. Söpörj fel-le választás, jobbra kiválasztás és megerősítés.")
                speakContactMatch(contacts.first())
            }
        }
    }

    private fun startDialFlow() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("Hívás engedély szükséges.")
            return
        }
        if (!DialerRoleHelper.isDefaultDialer(this)) {
            tts.speakAdd("Tipp: állítsd be a Super DL-t alapértelmezett telefon alkalmazásként a bejövő hívások azonosításához.")
        }
        enterNumericDictationAwait(AppFlow.NumericDictationAwait(purpose = NumberPadPurpose.PHONE))
    }

    private fun enterCallConfirm(contact: ContactMatch) {
        activeFlow = AppFlow.CallConfirm(contact)
        updateFlowDisplay()
        repeatCallConfirm(contact)
    }

    private fun repeatCallConfirm(contact: ContactMatch) {
        val readback = "Hívás: ${contact.name}. Telefonszám ${ContactHelper.maskPhone(contact.phone)}."
        tts.speak("$readback Biztos hívod? Söpörj jobbra a híváshoz, söprés balra a mégsehez. Ismétlés: söprés fel.")
    }

    private fun placeCall(phone: String, name: String) {
        voiceInput.cancel()
        activeFlow = AppFlow.Menu
        updateDisplay()
        CallHelper.launchInCall(this, phone, name)
        tts.speak("Hívás: $name.")
    }

    private fun speakContactMatch(contact: ContactMatch) {
        tts.speak("${contact.name}, ${ContactHelper.maskPhone(contact.phone)}")
    }

    // ==================== NÉVJEGYZÉK ====================

    private fun buildContactBookItems(contacts: List<ContactMatch>): List<ContactBookItem> =
        listOf(ContactBookItem.SyncAction) + contacts.map { ContactBookItem.Entry(it) }

    private fun reloadContactCache() {
        val contacts = ContactHelper.listAllWithPhone(this)
        ContactStore.save(this, contacts)
    }

    private fun startContactBookFlow() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CONTACTS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("Névjegy olvasás engedély szükséges.")
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.READ_CONTACTS), PERM_REQUEST)
            return
        }
        val cached = ContactStore.getCached(this)
        if (cached.isEmpty()) {
            tts.speak("Névjegyzék betöltése. Várj egy pillanatot.")
            Thread {
                ContactSyncHelper.sync(this)
                postWhenAlive { openContactBookBrowse() }
            }.start()
            return
        }
        openContactBookBrowse()
    }

    private fun openContactBookBrowse(index: Int = 0) {
        // Belépéskor a betű-szint jön, hogy gyorsan a kívánt kezdőbetűhöz lehessen ugrani.
        openContactLetterBrowse(index)
    }

    private fun openContactLetterBrowse(index: Int = 0) {
        val contacts = ContactStore.getCached(this)
        val groups = ContactLetterIndex.buildGroups(contacts)
        if (groups.isEmpty()) {
            // Nincs névjegy: a régi teljes lista jön (a szinkron opcióval).
            openContactFullList(0)
            return
        }
        val safeIndex = index.coerceIn(0, groups.lastIndex)
        activeFlow = AppFlow.ContactLetterBrowse(groups, safeIndex)
        updateFlowDisplay()
        val total = contacts.size
        tts.speak("$total névjegy. Söpörj fel-le a kezdőbetűk között, jobbra belépés a betűbe, balra vissza.")
        tts.speakAdd(groups[safeIndex].speakLabel())
    }

    private fun navigateContactLetter(flow: AppFlow.ContactLetterBrowse, delta: Int) {
        val next = (flow.index + delta + flow.groups.size) % flow.groups.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.groups[next].speakLabel())
    }

    private fun enterContactLetter(flow: AppFlow.ContactLetterBrowse) {
        val group = flow.groups[flow.index]
        val items = group.contacts.map { ContactBookItem.Entry(it) }
        if (items.isEmpty()) {
            tts.speak("Nincs névjegy ennél a betűnél.")
            return
        }
        activeFlow = AppFlow.ContactBookBrowse(items, 0)
        updateFlowDisplay()
        val letterName = if (group.letter == "#") "szám vagy egyéb" else group.letter
        tts.speak("$letterName betű, ${items.size} névjegy. Söpörj fel-le navigálás, jobbra művelet, balra vissza a betűkhöz.")
        speakContactBookItem(items[0])
    }

    /** A régi teljes lista (szinkron opcióval), ha nincs betű-csoport vagy külön kérik. */
    private fun openContactFullList(index: Int = 0) {
        val items = buildContactBookItems(ContactStore.getCached(this))
        val safeIndex = index.coerceIn(0, items.lastIndex.coerceAtLeast(0))
        activeFlow = AppFlow.ContactBookBrowse(items, safeIndex)
        updateFlowDisplay()
        val contactCount = (items.size - 1).coerceAtLeast(0)
        val intro = if (contactCount == 0) {
            "Nincs telefonszámmal rendelkező névjegy. A lista tetején szinkronizálás. Söpörj jobbra a szinkronhoz, balra vissza."
        } else {
            "$contactCount névjegy. A lista tetején szinkronizálás. Söpörj fel-le navigálás, jobbra művelet vagy szinkron, balra vissza."
        }
        tts.speak(intro)
        speakContactBookItem(items[safeIndex])
    }

    private fun speakContactBookItem(item: ContactBookItem) {
        tts.speak(item.speakLabel())
    }

    private fun navigateContactBook(flow: AppFlow.ContactBookBrowse, delta: Int) {
        val next = (flow.index + delta + flow.items.size) % flow.items.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        speakContactBookItem(flow.items[next])
    }

    private fun onContactBookActivate(flow: AppFlow.ContactBookBrowse) {
        when (flow.items[flow.index]) {
            ContactBookItem.SyncAction -> runContactSync(manual = true)
            is ContactBookItem.Entry -> enterContactContextMenu(flow.items, flow.index)
        }
    }

    private fun runContactSync(manual: Boolean) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CONTACTS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("Névjegy olvasás engedély szükséges.")
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.READ_CONTACTS), PERM_REQUEST)
            return
        }
        if (manual) {
            tts.speak("Szinkronizálás a telefon névjegyzékével. Várj egy pillanatot.")
        }
        Thread {
            val result = ContactSyncHelper.sync(this)
            postWhenAlive {
                val items = buildContactBookItems(ContactStore.getCached(this))
                when (val flow = activeFlow) {
                    is AppFlow.ContactBookBrowse -> {
                        val newIndex = flow.index.coerceAtMost(items.lastIndex.coerceAtLeast(0))
                        activeFlow = AppFlow.ContactBookBrowse(items, newIndex)
                        updateFlowDisplay()
                        feedbackSuccess()
                        tts.speak(result.speakSummary())
                        speakContactBookItem(items[newIndex])
                    }
                    else -> {
                        feedbackSuccess()
                        tts.speak("${result.speakSummary()} ${ContactStore.speakLastSync(this)}")
                    }
                }
            }
        }.start()
    }

    private fun returnToContactBook(items: List<ContactBookItem>, index: Int) {
        val safeIndex = index.coerceIn(0, items.lastIndex.coerceAtLeast(0))
        activeFlow = AppFlow.ContactBookBrowse(items, safeIndex)
        updateFlowDisplay()
        tts.speak("Vissza a névjegyzékben.")
        speakContactBookItem(items[safeIndex])
    }

    private fun returnToContactBookFromEdit(contact: ContactMatch) {
        val items = buildContactBookItems(ContactStore.getCached(this))
        val index = items.indexOfFirst {
            it is ContactBookItem.Entry && it.contact.id == contact.id
        }.takeIf { it >= 0 } ?: 1.coerceAtMost(items.lastIndex)
        returnToContactBook(items, index)
    }

    private fun enterContactContextMenu(items: List<ContactBookItem>, contactIndex: Int) {
        val entry = items.getOrNull(contactIndex) as? ContactBookItem.Entry ?: return
        val actions = ContactContextAction.browseActions
        activeFlow = AppFlow.ContactContextMenu(items, contactIndex, actions, 0)
        updateFlowDisplay()
        tts.speak(
            "Névjegy műveletek: ${entry.contact.name}. ${actions.first().label}. " +
                "Söpörj fel-le választás, jobbra végrehajtás, balra vissza."
        )
    }

    private fun navigateContactContextMenu(flow: AppFlow.ContactContextMenu, delta: Int) {
        val next = (flow.actionIndex + delta + flow.actions.size) % flow.actions.size
        activeFlow = flow.copy(actionIndex = next)
        updateFlowDisplay()
        tts.speak(flow.actions[next].label)
    }

    private fun onContactContextActivate(flow: AppFlow.ContactContextMenu) {
        val entry = flow.items.getOrNull(flow.contactIndex) as? ContactBookItem.Entry ?: return
        val contact = entry.contact
        when (flow.actions[flow.actionIndex]) {
            ContactContextAction.CALL -> placeCall(contact.phone, contact.name)
            ContactContextAction.SEND_SMS -> startSmsToPhone(contact.phone, contact.name)
            ContactContextAction.RINGTONE -> openContactRingtonePicker(contact)
            ContactContextAction.EDIT -> startContactEditFlow(contact)
            ContactContextAction.DELETE -> enterContactDeleteConfirm(contact, flow.items, flow.contactIndex)
        }
    }

    private fun startContactEditFlow(contact: ContactMatch) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_CONTACTS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("Névjegy szerkesztés engedély szükséges.")
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.WRITE_CONTACTS), PERM_REQUEST)
            return
        }
        activeFlow = AppFlow.ContactEditAwaitName(contact)
        updateFlowDisplay()
        listenForContactEditName(contact)
    }

    private fun listenForContactEditName(contact: ContactMatch) {
        ensureMicAndRun {
            voiceInput.listen(
                prompt = "Mondd az új nevet. Jelenleg: ${contact.name}.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    if (activeFlow !is AppFlow.ContactEditAwaitName) return@listen
                    val name = spoken.trim()
                    if (name.isBlank()) {
                        tts.speak("A név üres. Mondd újra.")
                        listenForContactEditName(contact)
                        return@listen
                    }
                    activeFlow = AppFlow.ContactEditAwaitPhone(contact, name)
                    updateFlowDisplay()
                    listenForContactEditPhone(contact, name)
                },
                onError = { returnToContactBookFromEdit(contact) }
            )
        }
    }

    private fun listenForContactEditPhone(contact: ContactMatch, newName: String) {
        ensureMicAndRun {
            voiceInput.listen(
                prompt = "Mondd az új telefonszámot. Jelenleg: ${ContactHelper.maskPhone(contact.phone)}.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    if (activeFlow !is AppFlow.ContactEditAwaitPhone) return@listen
                    val phone = spoken.replace(" ", "").trim()
                    if (phone.isBlank()) {
                        tts.speak("A szám üres. Mondd újra.")
                        listenForContactEditPhone(contact, newName)
                        return@listen
                    }
                    val ok = ContactHelper.updateContact(this, contact.id, newName, phone)
                    if (!ok) {
                        exitFlow("Névjegy szerkesztése sikertelen.", error = true)
                        return@listen
                    }
                    feedbackSuccess()
                    reloadContactCache()
                    returnToContactBookFromEdit(contact.copy(name = newName, phone = phone))
                    tts.speakAdd("$newName frissítve.")
                },
                onError = { returnToContactBookFromEdit(contact) }
            )
        }
    }

    private fun enterContactDeleteConfirm(
        contact: ContactMatch,
        items: List<ContactBookItem>,
        index: Int
    ) {
        activeFlow = AppFlow.ContactDeleteConfirm(contact, items, index)
        updateFlowDisplay()
        repeatContactDeleteConfirm(contact)
    }

    private fun repeatContactDeleteConfirm(contact: ContactMatch) {
        tts.speak(
            "Biztosan törlöd ${contact.name} névjegyet? " +
                "Söpörj jobbra a törléshez, söprés balra a mégsehez. Ismétlés: söprés fel."
        )
    }

    private fun deleteContactFromBook(flow: AppFlow.ContactDeleteConfirm) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_CONTACTS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("Névjegy törlés engedély szükséges.")
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.WRITE_CONTACTS), PERM_REQUEST)
            return
        }
        val ok = ContactHelper.deleteContact(this, flow.contact.id)
        if (!ok) {
            exitFlow("Névjegy törlése sikertelen.", error = true)
            return
        }
        feedbackSuccess()
        reloadContactCache()
        val items = buildContactBookItems(ContactStore.getCached(this))
        if (items.size <= 1) {
            activeFlow = AppFlow.ContactBookBrowse(items, 0)
            updateFlowDisplay()
            tts.speak("${flow.contact.name} törölve. Nincs több névjegy.")
            return
        }
        val newIndex = flow.index.coerceAtMost(items.lastIndex).coerceAtLeast(1)
        returnToContactBook(items, newIndex)
        tts.speakAdd("${flow.contact.name} törölve.")
    }

    // ==================== ÉBRESZTŐ & NAPTÁR (M3) ====================

    private fun ensureExactAlarmOrSpeak(): Boolean {
        if (!AlarmScheduler.canScheduleExact(this)) {
            startPermissionGuideFlow(PermissionGuideType.EXACT_ALARM, "Pontos ébresztő engedély")
            return false
        }
        return true
    }

    private fun startAlarmSetFlow() {
        if (!ensureExactAlarmOrSpeak()) return
        enterNumericDictationAwait(
            AppFlow.NumericDictationAwait(
                purpose = NumberPadPurpose.TIME,
                alarmDraft = true
            )
        )
    }

    private fun listenForAlarmLabel(hour: Int, minute: Int) {
        voiceInput.listen(
            prompt = "Mondd az ébresztő nevét, vagy mondd: névtelen.",
            speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
            onResult = { spoken ->
                val label = when {
                    spoken.trim().equals("névtelen", ignoreCase = true) -> ""
                    spoken.trim().equals("nevnelen", ignoreCase = true) -> ""
                    else -> spoken.trim()
                }
                startAlarmRepeatSelect(hour, minute, label)
            },
            onError = { startAlarmRepeatSelect(hour, minute, "") }
        )
    }

    private fun startAlarmRepeatSelect(hour: Int, minute: Int, label: String) {
        alarmDraftRepeat = AlarmRepeatType.ONCE
        alarmDraftWeekDays = mutableSetOf()
        val options = listOf(
            AlarmRepeatType.ONCE,
            AlarmRepeatType.DAILY,
            AlarmRepeatType.WEEKDAYS,
            AlarmRepeatType.WEEKEND
        )
        activeFlow = AppFlow.AlarmRepeatBrowse(hour, minute, label, options, 0)
        updateFlowDisplay()
        tts.speak(
            "Milyen gyakran ismétlődjön? Söpörj fel-le a lehetőségek között, jobbra a kiválasztáshoz. " +
                options.first().speakLabel()
        )
    }

    private fun navigateAlarmRepeat(flow: AppFlow.AlarmRepeatBrowse, delta: Int) {
        val next = (flow.index + delta + flow.options.size) % flow.options.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.options[next].speakLabel())
    }

    private fun onAlarmRepeatActivate(flow: AppFlow.AlarmRepeatBrowse) {
        alarmDraftRepeat = flow.options[flow.index]
        alarmDraftWeekDays = mutableSetOf()
        enterAlarmConfirm(flow.hour, flow.minute, flow.label)
    }

    private fun enterAlarmConfirm(hour: Int, minute: Int, label: String) {
        activeFlow = AppFlow.AlarmConfirm(hour, minute, label)
        updateFlowDisplay()
        repeatAlarmConfirm(hour, minute, label)
    }

    private fun repeatAlarmConfirm(hour: Int, minute: Int, label: String) {
        val name = label.ifBlank { "Névtelen ébresztő" }
        val timeText = "${hour.toString().padStart(2, '0')} óra ${minute.toString().padStart(2, '0')} perc"
        tts.speak(
            "Ébresztő: $name, $timeText. Beállítod? Söpörj jobbra a beállításhoz, söprés balra a mégsehez. Ismétlés: söprés fel."
        )
    }

    private fun saveAlarm(hour: Int, minute: Int, label: String) {
        voiceInput.cancel()
        val entry = AlarmStore.add(
            context = this,
            hour = hour,
            minute = minute,
            label = label,
            repeatType = alarmDraftRepeat,
            weekDays = alarmDraftWeekDays.toSet()
        )
        if (entry == null) {
            exitFlow("Elérted a maximum ébresztőszámot.", error = true)
            return
        }
        AlarmScheduler.schedule(this, entry)
        val mins = AlarmScheduler.millisUntil(entry) / 60_000
        exitFlow(
            "Ébresztő beállítva: ${entry.speakSummary()}. Hátralévő idő kb. $mins perc.",
            success = true
        )
    }

    private fun speakNextAlarm() {
        val next = AlarmStore.getNextAlarm(this)
        if (next == null) {
            tts.speak("Nincs beállított ébresztő.")
            return
        }
        val mins = AlarmScheduler.millisUntil(next) / 60_000
        tts.speak("Következő ébresztő: ${next.speakSummary()}. Hátralévő idő kb. $mins perc.")
    }

    /**
     * SÖTÉT MÓD váltása.
     *
     * A képernyő teljes elfüggönyözése: senki nem látja, mit csinálsz, és a
     * kijelző jóval kevesebbet fogyaszt. Az érintések ÁTMENNEK a fekete rétegen,
     * tehát a telefon alatta ugyanúgy kezelhető.
     */
    private fun toggleScreenCurtain() {
        if (!ScreenCurtain.hasPermission(this)) {
            tts.speak(
                "A sötét módhoz engedély kell a más alkalmazások fölé rajzoláshoz. " +
                    "Megnyitom a beállítást, keresd meg a Super DL-t, és kapcsold be."
            )
            try {
                startActivity(
                    Intent(
                        android.provider.Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        android.net.Uri.parse("package:$packageName")
                    )
                )
            } catch (_: Exception) {
                tts.speak("A beállítás nem nyitható meg.")
            }
            return
        }
        val nowOn = ScreenCurtain.toggle(this)
        if (nowOn) {
            tts.speak("Sötét mód bekapcsolva. A képernyő fekete, de a telefon ugyanúgy kezelhető.")
        } else {
            tts.speak("Sötét mód kikapcsolva.")
        }
    }

    /** Engedélyezve van-e a képernyőolvasó a rendszer kisegítő beállításaiban? */
    private fun isScreenReaderServiceEnabled(): Boolean {
        val expected = com.superdl.launcher.screenreader.ScreenReaderService::class.java.name
        return try {
            val enabled = android.provider.Settings.Secure.getString(
                contentResolver,
                android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            ).orEmpty()
            enabled.split(':').any { it.substringAfter('/', it).trim() == expected }
        } catch (_: Exception) {
            false
        }
    }

    /**
     * ÉBRESZTÉSEK KIHAGYÁSA — 1. lépés: melyik ébresztőket érintse.
     *
     * Nem napokat számol, hanem ÉBRESZTÉSEKET: ha 2-t állítasz be, a kijelölt
     * ébresztők a következő két alkalommal nem szólalnak meg, utána maguktól
     * visszatérnek. Így nem kell este kikapcsolni, majd később visszakapcsolni
     * őket (pl. ha pénteken és hétfőn nem kell dolgozni).
     */
    private fun startAlarmSkipFlow() {
        val alarms = AlarmStore.getEnabled(this)
        if (alarms.isEmpty()) {
            tts.speak("Nincs bekapcsolt ébresztő, amit ki lehetne hagyni.")
            return
        }
        val active = alarms.count { it.isSkipping }
        activeFlow = AppFlow.AlarmSkipPick(alarms, 0, emptySet())
        updateFlowDisplay()
        if (active > 0) {
            tts.speak("$active ébresztőn van érvényben kihagyás.")
            tts.speakAdd("Jelöld ki jobbra söpréssel, melyeket érintse, majd balra a folytatáshoz.")
        } else {
            tts.speak("Jelöld ki jobbra söpréssel, mely ébresztéseket hagyja ki, majd balra a folytatáshoz.")
        }
        tts.speakAdd(speakAlarmSkipEntry(alarms[0], false))
    }

    /** Egy ébresztő bemondása a kihagyás-listában (kijelölés és állapot együtt). */
    private fun speakAlarmSkipEntry(alarm: AlarmEntry, selected: Boolean): String {
        val mark = if (selected) "Kijelölve. " else ""
        val state = if (alarm.isSkipping) {
            " Jelenleg ${alarm.skipRemaining} alkalmat hagy ki."
        } else ""
        return "$mark${alarm.speakSummary()}$state"
    }

    private fun navigateAlarmSkipPick(flow: AppFlow.AlarmSkipPick, delta: Int) {
        val next = (flow.index + delta + flow.alarms.size) % flow.alarms.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        val alarm = flow.alarms[next]
        tts.speak(speakAlarmSkipEntry(alarm, alarm.id in flow.selected))
    }

    /** Jobbra söprés: kijelölés be/ki. */
    private fun toggleAlarmSkipSelection(flow: AppFlow.AlarmSkipPick) {
        val alarm = flow.alarms[flow.index]
        val newSelection = if (alarm.id in flow.selected) {
            flow.selected - alarm.id
        } else {
            flow.selected + alarm.id
        }
        activeFlow = flow.copy(selected = newSelection)
        updateFlowDisplay()
        tts.speak(
            if (alarm.id in newSelection) "Kijelölve: ${alarm.speakSummary()}."
            else "Kijelölés törölve."
        )
    }

    /** Balra söprés a kijelölésnél: tovább a darabszámhoz, vagy kilépés. */
    private fun finishAlarmSkipSelection(flow: AppFlow.AlarmSkipPick) {
        if (flow.selected.isEmpty()) {
            exitFlow("Kihagyás megszakítva.")
            return
        }
        activeFlow = AppFlow.AlarmSkipCount(flow.alarms, flow.selected, 1)
        updateFlowDisplay()
        tts.speak(
            "${flow.selected.size} ébresztő kijelölve. Hány ébresztést hagyjon ki? " +
                "Fel-le a szám állítása, jobbra a mentés."
        )
        tts.speakAdd("1 ébresztés.")
    }

    private fun navigateAlarmSkipCount(flow: AppFlow.AlarmSkipCount, delta: Int) {
        // 0 = a kihagyás megszüntetése, felfelé 30-ig
        val next = (flow.count + delta).coerceIn(0, 30)
        activeFlow = flow.copy(count = next)
        updateFlowDisplay()
        tts.speak(
            if (next == 0) "Kihagyás kikapcsolása."
            else "$next ébresztés."
        )
    }

    /** Jobbra söprés a darabszámnál: mentés. */
    private fun confirmAlarmSkip(flow: AppFlow.AlarmSkipCount) {
        AlarmStore.setSkip(this, flow.selected, flow.count)
        val names = flow.alarms.filter { it.id in flow.selected }
            .joinToString(", ") { if (it.label.isBlank()) it.speakTime() else it.label }
        if (flow.count == 0) {
            exitFlow("Kihagyás kikapcsolva: $names.")
        } else {
            exitFlow(
                "Beállítva: $names a következő ${flow.count} ébresztést kihagyja, " +
                    "utána magától visszatér."
            )
        }
    }

    private fun startAlarmListFlow(deleteMode: Boolean) {
        val alarms = AlarmStore.getAll(this)
        if (alarms.isEmpty()) {
            tts.speak("Nincs beállított ébresztő.")
            return
        }
        activeFlow = AppFlow.AlarmListBrowse(alarms, 0, deleteMode)
        updateFlowDisplay()
        val intro = if (deleteMode) {
            "${alarms.size} ébresztő. Törlés mód. Söpörj fel-le választás, jobbra törlés megerősítése."
        } else {
            "${alarms.size} ébresztő. Söpörj fel-le választás, jobbra felolvasás."
        }
        tts.speak(intro)
        speakAlarmEntry(alarms.first())
    }

    private fun navigateAlarmList(flow: AppFlow.AlarmListBrowse, delta: Int) {
        val next = (flow.index + delta + flow.alarms.size) % flow.alarms.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        speakAlarmEntry(flow.alarms[next])
    }

    private fun onAlarmListActivate(flow: AppFlow.AlarmListBrowse) {
        val alarm = flow.alarms[flow.index]
        if (flow.deleteMode) {
            enterAlarmDeleteConfirm(alarm, flow.alarms, flow.index)
        } else {
            // A listában jobbra söprés: ehhez az ébresztőhöz gyári hangot választunk.
            openAlarmTonePicker(alarm)
        }
    }

    private var alarmToneEditId: Int = -1

    /** Melyik követelményre vár a varázsló a rendszer engedély-kérdése alatt. */
    private var setupWizardPending: String? = null

    private fun openAlarmTonePicker(alarm: AlarmEntry) {
        alarmToneEditId = alarm.id
        tts.speak("Hang választása ehhez: ${alarm.speakSummary()}. Söpörj fel-le a hangok között, jobbra a kiválasztáshoz.")
        alarmTonePickerLauncher.launch(
            Intent(this, RingtonePickerActivity::class.java).apply {
                putExtra(RingtonePickerActivity.EXTRA_TONE_TYPE, RingtonePickerActivity.TONE_ALARM)
                putExtra(RingtonePickerActivity.EXTRA_CURRENT_URI, alarm.toneUri)
            }
        )
    }

    private fun openContactRingtonePicker(contact: ContactMatch) {
        if (contact.phone.isBlank()) {
            tts.speak("Ehhez a névjegyhez nincs telefonszám, így nem lehet egyéni csengőhangot adni.")
            return
        }
        contactRingtoneEditPhone = contact.phone
        contactRingtoneEditName = contact.name
        val current = ContactRingtoneStore.getForPhone(this, contact.phone)
        val currentLabel = if (current != null) {
            "Jelenleg: ${current.title}. "
        } else {
            "Jelenleg az alapértelmezett szól. "
        }
        tts.speak(
            "Egyéni csengőhang ehhez: ${contact.name}. " + currentLabel +
                "Söpörj fel-le a hangok között, jobbra a kiválasztáshoz."
        )
        contactRingtonePickerLauncher.launch(
            Intent(this, RingtonePickerActivity::class.java).apply {
                putExtra(RingtonePickerActivity.EXTRA_TONE_TYPE, RingtonePickerActivity.TONE_RINGTONE)
                putExtra(RingtonePickerActivity.EXTRA_CURRENT_URI, current?.uri)
            }
        )
    }

    private fun enterAlarmDeleteConfirm(alarm: AlarmEntry, alarms: List<AlarmEntry>, index: Int) {
        activeFlow = AppFlow.AlarmDeleteConfirm(alarm, alarms, index)
        updateFlowDisplay()
        repeatAlarmDeleteConfirm(alarm)
    }

    private fun repeatAlarmDeleteConfirm(alarm: AlarmEntry) {
        tts.speak(
            "Törlöd ezt az ébresztőt? ${alarm.speakSummary()}. Söpörj jobbra a törléshez, söprés balra a mégsehez."
        )
    }

    private fun deleteAlarm(alarm: AlarmEntry) {
        voiceInput.cancel()
        AlarmScheduler.cancel(this, alarm.id)
        AlarmStore.delete(this, alarm.id)
        exitFlow("Ébresztő törölve: ${alarm.speakSummary()}.")
    }

    private fun speakAlarmEntry(alarm: AlarmEntry) {
        tts.speak(alarm.speakSummary())
    }

    // ==================== PATIKA ŐRANGYAL ====================

    private fun readMedicationReminders() {
        tts.speak(MedicationSpeech.readAll(MedicationStore.getAll(this)))
    }

    // ==================== GYÓGYSZERKERESŐ ====================

    private fun startMedicationSearchFlow() {
        ensureMicAndRun {
            activeFlow = AppFlow.MedicationSearchAwaitName
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Gyógyszerkereső. Fontos: az itt elhangzó adatok tájékoztató jellegűek, " +
                    "változhatnak, és nem gyógyszerészeti tanácsok. A kölcsönhatásokért és a biztos " +
                    "információért mindig kérdezd meg a gyógyszerészt. Most mondd a gyógyszer nevét.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val name = spoken.trim()
                    if (name.isBlank()) {
                        tts.speak("Nem értettem a gyógyszer nevét. Próbáld újra.")
                        startMedicationSearchFlow()
                        return@listen
                    }
                    runMedicationSearch(name)
                },
                onError = { exitFlow("Gyógyszerkereső megszakítva.") }
            )
        }
    }

    private fun runMedicationSearch(query: String) {
        activeFlow = AppFlow.MedicationSearchLoading
        updateFlowDisplay()
        tts.speak("Keresés: $query. Egy pillanat.")
        Thread {
            val result = MedicationSearchHelper.search(query)
            postWhenAlive {
                if (activeFlow !is AppFlow.MedicationSearchLoading) return@postWhenAlive
                if (result == null) {
                    exitFlow(
                        "Erről a gyógyszerről nem találtam megbízható leírást. " +
                            "Kérdezd meg a gyógyszerészed. Próbálkozhatsz a hatóanyag nevével is.",
                        error = true
                    )
                    return@postWhenAlive
                }
                startMedicationSearchReading(result)
            }
        }.start()
    }

    private fun startMedicationSearchReading(result: MedicationSearchHelper.Result) {
        val fullText = result.speakText()
        if (::articleReader.isInitialized && articleReader.isActive) articleReader.stop()
        articleReader.startWithText(searchArticleBook, result.title, fullText, 0)
        activeFlow = AppFlow.MedicationSearchResult(result.title, fullText)
        updateFlowDisplay()
    }

    private fun startMedicationAddFlow() {
        if (!ensureExactAlarmOrSpeak()) return
        medicationDraftName = null
        ensureMicAndRun {
            activeFlow = AppFlow.MedicationAwaitName
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd a gyógyszer nevét. Például: Dedaxin, Anti-pukitin, Fosadin, Leteperin.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val name = spoken.trim()
                    if (name.isBlank()) {
                        tts.speak("Nem értettem a gyógyszer nevét. Próbáld újra.")
                        startMedicationAddFlow()
                        return@listen
                    }
                    medicationDraftName = name
                    medicationDraftTimes = emptyList()
                    medicationDraftCourseEndMillis = null
                    startMedicationTimeOfDaySelect()
                },
                onError = { exitFlow("Gyógyszer rögzítés megszakítva.") }
            )
        }
    }

    private fun startMedicationTimeOfDaySelect() {
        val name = medicationDraftName ?: return
        val options = MedicationTimeOfDay.entries.toList()
        activeFlow = AppFlow.MedicationTimeOfDayBrowse(name, options, emptySet(), 0)
        updateFlowDisplay()
        tts.speak(
            "$name. Válaszd ki mikor kell bevenni. Söpörj fel-le a napszakok között, " +
                "jobbra pipáld ki vagy vedd le. Több is választható. Balra a végén tovább a beállításhoz. " +
                options.first().speakLabel()
        )
    }

    private fun navigateMedicationTimeOfDay(flow: AppFlow.MedicationTimeOfDayBrowse, delta: Int) {
        val next = (flow.index + delta + flow.options.size) % flow.options.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        val option = flow.options[next]
        val checked = if (option in flow.selected) "kipipálva" else "nincs kipipálva"
        tts.speak("${option.speakLabel()}, $checked")
    }

    private fun toggleMedicationTimeOfDay(flow: AppFlow.MedicationTimeOfDayBrowse) {
        val option = flow.options[flow.index]
        val newSelected = if (option in flow.selected) flow.selected - option else flow.selected + option
        activeFlow = flow.copy(selected = newSelected)
        updateFlowDisplay()
        val checked = if (option in newSelected) "kipipálva" else "levéve"
        tts.speak("${option.label}, $checked")
    }

    /** A napszak-választóból tovább a ciklushoz (napi/heti), a kiválasztott időpontokkal. */
    private fun proceedFromMedicationTimeOfDay(flow: AppFlow.MedicationTimeOfDayBrowse) {
        if (flow.selected.isEmpty()) {
            tts.speak("Legalább egy napszakot pipálj ki. Söpörj jobbra a kijelöléshez.")
            return
        }
        // A kiválasztott napszakok időpontjai, napszak-sorrendben.
        medicationDraftTimes = flow.options
            .filter { it in flow.selected }
            .map { it.hour to it.minute }
        val name = flow.name
        val options = MedicationCycleType.entries.toList()
        // A ciklus-választóhoz az első időpontot adjuk (a mentésnél úgyis mind felhasználjuk).
        val first = medicationDraftTimes.first()
        activeFlow = AppFlow.MedicationCycleBrowse(name, first.first, first.second, options, 0)
        updateFlowDisplay()
        val times = medicationDraftTimes.size
        tts.speak(
            "$times időpont kiválasztva. Válaszd ki az ismétlés típusát. ${options.first().label}."
        )
    }

    private fun startMedicationTimePad() {
        val name = medicationDraftName ?: return
        enterNumericDictationAwait(AppFlow.NumericDictationAwait(purpose = NumberPadPurpose.TIME))
        tts.speakAdd("Gyógyszer: $name.")
    }

    private fun onMedicationTimeEntered(hour: Int, minute: Int) {
        val name = medicationDraftName ?: return
        val options = MedicationCycleType.entries.toList()
        activeFlow = AppFlow.MedicationCycleBrowse(name, hour, minute, options, 0)
        updateFlowDisplay()
        tts.speak(
            "Időpont: ${hour.toString().padStart(2, '0')} óra ${minute.toString().padStart(2, '0')} perc. " +
                "Válaszd ki az ismétlés típusát. ${options.first().label}."
        )
    }

    private fun navigateMedicationCycle(flow: AppFlow.MedicationCycleBrowse, delta: Int) {
        val next = (flow.index + delta + flow.options.size) % flow.options.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.options[next].label)
    }

    private fun onMedicationCycleActivate(flow: AppFlow.MedicationCycleBrowse) {
        when (flow.options[flow.index]) {
            MedicationCycleType.DAILY -> enterMedicationConfirm(
                flow.name, flow.hour, flow.minute, MedicationCycleType.DAILY, emptySet()
            )
            MedicationCycleType.WEEKLY,
            MedicationCycleType.CUSTOM -> {
                activeFlow = AppFlow.MedicationWeekdayBrowse(
                    flow.name,
                    flow.hour,
                    flow.minute,
                    flow.options[flow.index],
                    emptySet(),
                    0
                )
                updateFlowDisplay()
                val hint = if (flow.options[flow.index] == MedicationCycleType.WEEKLY) {
                    "Válaszd ki a hetente ismétlődő napot."
                } else {
                    "Válaszd ki az egyéni napokat. Jobbra be-kikapcsol, balra tovább ha kész."
                }
                tts.speak("$hint ${MedicationWeekdays.all.first().label}.")
            }
        }
    }

    private fun navigateMedicationWeekday(flow: AppFlow.MedicationWeekdayBrowse, delta: Int) {
        val next = (flow.index + delta + MedicationWeekdays.all.size) % MedicationWeekdays.all.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        speakMedicationWeekday(flow.copy(index = next))
    }

    private fun speakMedicationWeekday(flow: AppFlow.MedicationWeekdayBrowse) {
        val day = MedicationWeekdays.all[flow.index]
        val selected = if (day.dayOfWeek in flow.selectedDays) "kiválasztva" else "nincs kiválasztva"
        tts.speak("${day.label}, $selected.")
    }

    private fun onMedicationWeekdayActivate(flow: AppFlow.MedicationWeekdayBrowse) {
        val day = MedicationWeekdays.all[flow.index]
        when (flow.cycleType) {
            MedicationCycleType.WEEKLY -> enterMedicationConfirm(
                flow.name, flow.hour, flow.minute, flow.cycleType, setOf(day.dayOfWeek)
            )
            MedicationCycleType.CUSTOM -> {
                val updated = flow.selectedDays.toMutableSet()
                if (day.dayOfWeek in updated) updated.remove(day.dayOfWeek) else updated.add(day.dayOfWeek)
                activeFlow = flow.copy(selectedDays = updated)
                updateFlowDisplay()
                val state = if (day.dayOfWeek in updated) "kiválasztva" else "kikapcsolva"
                tts.speak("${day.label} $state.")
            }
            MedicationCycleType.DAILY -> Unit
        }
    }

    private fun proceedMedicationWeekdayIfReady(flow: AppFlow.MedicationWeekdayBrowse) {
        if (flow.cycleType != MedicationCycleType.CUSTOM) return
        if (flow.selectedDays.isEmpty()) {
            tts.speak("Legalább egy napot válassz ki.")
            return
        }
        enterMedicationConfirm(flow.name, flow.hour, flow.minute, flow.cycleType, flow.selectedDays)
    }

    private fun enterMedicationConfirm(
        name: String,
        hour: Int,
        minute: Int,
        cycleType: MedicationCycleType,
        weekDays: Set<Int>
    ) {
        // A megerősítés előtt megkérdezzük a kúra hosszát (hány napig).
        askMedicationCourseDays(name, hour, minute, cycleType, weekDays)
    }

    private var medicationConfirmPending: AppFlow.MedicationConfirm? = null

    private fun askMedicationCourseDays(
        name: String,
        hour: Int,
        minute: Int,
        cycleType: MedicationCycleType,
        weekDays: Set<Int>
    ) {
        medicationConfirmPending = AppFlow.MedicationConfirm(name, hour, minute, cycleType, weekDays)
        activeFlow = AppFlow.MedicationAwaitCourseDays
        updateFlowDisplay()
        voiceInput.listen(
            prompt = "Hány napig kell szedni? Mondd a napok számát, például hét. " +
                "Ha folyamatos, mondd azt hogy folyamatos, vagy nulla.",
            speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
            onResult = { spoken ->
                medicationDraftCourseEndMillis = parseCourseDays(spoken)
                val pending = medicationConfirmPending
                if (pending != null) {
                    activeFlow = pending
                    updateFlowDisplay()
                    repeatMedicationConfirm(pending)
                }
            },
            onError = { exitFlow("Gyógyszer rögzítés megszakítva.") }
        )
    }

    /** A bemondott napok számából kiszámolja a kúra záró időpontját (nap vége). Null = folyamatos. */
    private fun parseCourseDays(spoken: String): Long? {
        val text = spoken.trim().lowercase()
        if (text.isBlank() || text.contains("folyamatos") || text.contains("nincs")) return null
        val number = VoiceDurationParser.parseAmount(text)
        if (number == null || number <= 0) return null
        // A kúra vége: a mai naptól number nap múlva, aznap végén (23:59).
        val cal = java.util.Calendar.getInstance().apply {
            add(java.util.Calendar.DAY_OF_YEAR, number - 1)
            set(java.util.Calendar.HOUR_OF_DAY, 23)
            set(java.util.Calendar.MINUTE, 59)
            set(java.util.Calendar.SECOND, 59)
            set(java.util.Calendar.MILLISECOND, 0)
        }
        return cal.timeInMillis
    }

    private fun repeatMedicationConfirm(flow: AppFlow.MedicationConfirm) {
        val summary = MedicationSpeech.confirmSummary(
            flow.name, flow.hour, flow.minute, flow.cycleType, flow.weekDays
        )
        tts.speak(
            "Gyógyszer emlékeztető: $summary. Elmented? Söpörj jobbra a mentéshez, söprés balra a mégsehez. Ismétlés: söprés fel."
        )
    }

    private fun saveMedication(flow: AppFlow.MedicationConfirm) {
        voiceInput.cancel()
        // A kiválasztott napszakok időpontjai; ha valamiért üres, a flow egyetlen időpontja.
        val times = medicationDraftTimes.ifEmpty { listOf(flow.hour to flow.minute) }
        val courseEnd = medicationDraftCourseEndMillis
        val added = MedicationStore.addMultipleTimes(
            context = this,
            name = flow.name,
            times = times,
            cycleType = flow.cycleType,
            weekDays = flow.weekDays,
            courseEndMillis = courseEnd
        )
        if (added.isEmpty()) {
            medicationDraftName = null
            medicationDraftTimes = emptyList()
            medicationDraftCourseEndMillis = null
            val message = if (flow.cycleType != MedicationCycleType.DAILY && flow.weekDays.isEmpty()) {
                "Legalább egy napot ki kell választani."
            } else {
                "Elérted a maximum gyógyszer emlékeztető számot."
            }
            exitFlow(message, error = true)
            return
        }
        // Minden felvett napszakot beütemezünk.
        var anyScheduled = false
        added.forEach { if (MedicationScheduler.scheduleAndReport(this, it)) anyScheduled = true }
        medicationDraftName = null
        medicationDraftTimes = emptyList()
        medicationDraftCourseEndMillis = null

        val timesText = added.joinToString(", ") { it.speakTime() }
        val courseText = if (courseEnd != null) {
            " Kúra: ${added.first().speakCourse()}."
        } else {
            ""
        }
        val scheduleNote = if (anyScheduled) {
            ""
        } else {
            " Figyelem: pontos ébresztő engedély hiányzik, az emlékeztető késhet."
        }
        exitFlow(
            "Gyógyszer emlékeztető mentve: ${flow.name}, ${added.size} időpont: $timesText.$courseText$scheduleNote",
            success = true
        )
    }

    private fun startMedicationListFlow(deleteMode: Boolean) {
        val reminders = MedicationStore.getAll(this)
        if (reminders.isEmpty()) {
            tts.speak("Nincs beállított gyógyszer emlékeztető.")
            return
        }
        activeFlow = AppFlow.MedicationListBrowse(reminders, 0, deleteMode)
        updateFlowDisplay()
        val intro = if (deleteMode) {
            "${reminders.size} gyógyszer emlékeztető. Törlés mód. Söpörj fel-le választás, jobbra törlés megerősítése."
        } else {
            "${reminders.size} gyógyszer emlékeztető. Söpörj fel-le választás, jobbra felolvasás."
        }
        tts.speak(intro)
        speakMedicationEntry(reminders.first())
    }

    private fun navigateMedicationList(flow: AppFlow.MedicationListBrowse, delta: Int) {
        val next = (flow.index + delta + flow.reminders.size) % flow.reminders.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        speakMedicationEntry(flow.reminders[next])
    }

    private fun onMedicationListActivate(flow: AppFlow.MedicationListBrowse) {
        val reminder = flow.reminders[flow.index]
        if (flow.deleteMode) {
            enterMedicationDeleteConfirm(reminder, flow.reminders, flow.index)
        } else {
            speakMedicationEntry(reminder)
        }
    }

    private fun enterMedicationDeleteConfirm(
        reminder: MedicationReminder,
        reminders: List<MedicationReminder>,
        index: Int
    ) {
        activeFlow = AppFlow.MedicationDeleteConfirm(reminder, reminders, index)
        updateFlowDisplay()
        repeatMedicationDeleteConfirm(reminder)
    }

    private fun repeatMedicationDeleteConfirm(reminder: MedicationReminder) {
        tts.speak(
            "Törlöd ezt a gyógyszer emlékeztetőt? ${reminder.speakSummary()}. Söpörj jobbra a törléshez, söprés balra a mégsehez."
        )
    }

    // ==================== Beállítás varázsló ====================

    /**
     * Végigvezet a hiányzó engedélyeken.
     *
     * MIÉRT KELL: 24 service, mindegyik más rendszerképernyőn kér jogot. Aki
     * most kapja kézbe a telefont, egyedül nem jut át rajta — és ha egy engedély
     * hiányzik, a funkció CSENDBEN nem megy. Ez a varázsló kimondja, mi hiányzik,
     * mi nem fog menni emiatt, és odaviszi, ahol megadható.
     */
    private fun startSetupWizard() {
        voiceInput.cancel()
        val missing = SetupRequirements.missing(this)
        if (missing.isEmpty()) {
            exitFlow("Minden engedély megvan. A SuperDL teljes egészében működik.")
            return
        }
        activeFlow = AppFlow.SetupWizardBrowse(missing, 0)
        updateFlowDisplay()
        val first = missing.first()
        tts.speak(
            "Beállítás varázsló. ${SetupRequirements.speakSummary(this)} " +
                "Söpörj fel-le a tételek között, jobbra a megadáshoz, balra a kilépéshez. " +
                "${first.index1Of(missing)} ${first.speakDetail()}"
        )
    }

    private fun readSetupStatus() {
        tts.speak(SetupRequirements.speakSummary(this))
    }

    /**
     * Diagnosztika: mi NEM működik, és miért.
     *
     * MIÉRT NEM FLOW: itt nincs mit választani, csak meghallgatni. A részletes
     * lista a portálon van; a telefonon a lényeg kell, egyben.
     */
    private fun readDiagnostics() {
        tts.speak("Diagnosztika fut. Várj.")
        // A tárhely- és akku-lekérdezés lassú lehet, ezért háttérszálon.
        Thread {
            val summary = try {
                DiagnosticsReport.speakSummary(this)
            } catch (e: Exception) {
                "A diagnosztika nem futott le."
            }
            postWhenAlive { tts.speak(summary) }
        }.start()
    }

    /**
     * Korlátlan háttérfutás kérése.
     *
     * MIÉRT KÜLÖN MENÜPONT: ez a némaság leggyakoribb oka, és a rendszer
     * párbeszéde egy kattintás — nem kell hozzá varázsló.
     */
    private fun requestBatteryOptimizationExemption() {
        val check = DiagnosticsReport.batteryOptimization(this)
        if (check.level == DiagnosticsReport.Level.OK) {
            tts.speak("A korlátlan háttérfutás már engedélyezve van. ${check.detail}")
            return
        }
        val intent = DiagnosticsReport.batteryOptimizationIntent(this)
        if (intent == null) {
            tts.speak("Ezen az Android verzión ez nem állítható.")
            return
        }
        tts.speakThen(
            "Most megnyílik a rendszer kérdése. Válaszd az engedélyezést, " +
                "hogy a gyógyszer emlékeztető és az ébresztő időben szóljon."
        ) {
            try {
                startActivity(intent)
            } catch (e: Exception) {
                tts.speak(
                    "Ezt a képernyőt nem sikerült megnyitni. Keresd a rendszer " +
                        "beállításaiban: Alkalmazások, SuperDL, Akkumulátor."
                )
            }
        }
    }

    /**
     * Gyártói automatikus indítás.
     *
     * MIÉRT KÜLÖN AZ AKKU-OPTIMALIZÁLÁSTÓL: több gyártó (Xiaomi, Huawei, Oppo)
     * saját háttérvédelmet is futtat az Android fölött. Attól, hogy az Android
     * akku-optimalizálása alól felmentetted az appot, a GYÁRTÓ még megölheti.
     *
     * ŐSZINTESÉG: erre nincs szabványos API, és azt sem tudjuk lekérdezni, hogy
     * be van-e kapcsolva. Ezért ha nem találunk megnyitható képernyőt, NEM
     * hazudunk, hanem elmondjuk, hol keresse — vagy hogy nincs is ilyen.
     */
    private fun openAutostartSettings() {
        val intent = AutostartHelper.findIntent(this)
        if (intent == null) {
            // Nincs ismert gyártói képernyő: ez sokszor jó hír (Pixel, Ulefone).
            tts.speak(AutostartHelper.speakStatus(this))
            return
        }
        tts.speakThen(
            "Most megnyílik a ${AutostartHelper.manufacturerLabel()} automatikus indítás " +
                "beállítása. Keresd meg a SuperDL-t a listában, és kapcsold be. " +
                "Ez azért kell, hogy a gyógyszer emlékeztető a háttérből is megszólaljon. " +
                "Utána nyomd meg a vissza gombot."
        ) {
            try {
                startActivity(intent)
            } catch (e: Exception) {
                tts.speak(
                    "Ezt a képernyőt nem sikerült megnyitni. Keresd a telefon " +
                        "beállításaiban: alkalmazáskezelő vagy akkumulátor, " +
                        "automatikus indítás."
                )
            }
        }
    }

    private fun navigateSetupWizard(flow: AppFlow.SetupWizardBrowse, delta: Int) {
        if (flow.requirements.isEmpty()) return
        val next = (flow.index + delta + flow.requirements.size) % flow.requirements.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        val req = flow.requirements[next]
        tts.speak("${req.index1Of(flow.requirements, next)} ${req.speakDetail()}")
    }

    private fun repeatSetupWizard(flow: AppFlow.SetupWizardBrowse) {
        val req = flow.requirements.getOrNull(flow.index) ?: return
        tts.speak("${req.index1Of(flow.requirements, flow.index)} ${req.speakDetail()}")
    }

    /**
     * A kiválasztott engedély megadása.
     *
     * Háromféle út van, és mindhárom másképp működik:
     *  - RUNTIME: requestPermissions() – a rendszer felugró kérdése
     *  - ROLE / SYSTEM_SCREEN: másik Activity nyílik meg, oda csak elnavigálni tudunk
     */
    private fun activateSetupRequirement(flow: AppFlow.SetupWizardBrowse) {
        val req = flow.requirements.getOrNull(flow.index) ?: return

        if (req.kind == SetupRequirements.RequestKind.RUNTIME) {
            if (req.permissions.isEmpty()) {
                tts.speak("Ezen az Android verzión ehhez nem kell külön engedély.")
                return
            }
            // A rendszer kérdése után az onRequestPermissionsResult újramér.
            setupWizardPending = req.id
            ActivityCompat.requestPermissions(this, req.permissions.toTypedArray(), PERM_REQUEST)
            return
        }

        val intent = SetupRequirements.systemIntentFor(this, req)
            ?: SetupRequirements.appSettingsIntent(this)
        activeFlow = AppFlow.SetupWizardAwaitReturn(req)
        updateFlowDisplay()
        // MIÉRT MONDJUK EL ELŐRE: a rendszerképernyő NEM a SuperDL, ott a
        // TalkBack szólal meg. Ha nem mondjuk meg előre, mit keressen, a
        // felhasználó egy idegen képernyőn találja magát kapaszkodó nélkül.
        tts.speakThen(
            "Most megnyílik a rendszer beállítás képernyője: ${req.title}. " +
                "Keresd meg a SuperDL-t, és kapcsold be. Utána nyomd meg a vissza gombot, " +
                "és ide visszatérve ellenőrizzük."
        ) {
            try {
                startActivity(intent)
            } catch (e: Exception) {
                // A MainActivity nem naplóz (nincs Log import) — és itt nem is
                // a napló a fontos: a felhasználónak kell megtudnia, hogy ez az
                // út nem járható, és mi a másik lehetőség.
                tts.speak(
                    "Ezt a képernyőt nem sikerült megnyitni ezen a telefonon. " +
                        "Próbáld a rendszer beállításaiban kézzel: ${req.title}."
                )
                returnToSetupWizard()
            }
        }
    }

    /**
     * Visszatérés a rendszerképernyőről: ÚJRAMÉRÜNK.
     *
     * MIÉRT: a felmérés pillanatfelvétel. Ha nem mérnénk újra, a varázsló azt
     * hinné, hogy a most megadott engedély még mindig hiányzik.
     */
    private fun returnToSetupWizard() {
        val missing = SetupRequirements.missing(this)
        if (missing.isEmpty()) {
            exitFlow("Kész. Minden engedély megvan, a SuperDL teljes egészében működik.")
            return
        }
        activeFlow = AppFlow.SetupWizardBrowse(missing, 0)
        updateFlowDisplay()
        val first = missing.first()
        tts.speak("${SetupRequirements.speakSummary(this)} ${first.index1Of(missing)} ${first.speakDetail()}")
    }

    private fun deleteMedication(reminder: MedicationReminder) {
        voiceInput.cancel()
        MedicationScheduler.cancel(this, reminder.id)
        MedicationStore.delete(this, reminder.id)
        exitFlow("Gyógyszer emlékeztető törölve: ${reminder.speakSummary()}.")
    }

    private fun speakMedicationEntry(reminder: MedicationReminder) {
        tts.speak(reminder.speakSummary())
    }

    // ==================== IDŐZÍTŐK ====================

    private fun startTimerCreateFlow(editTimerId: Int? = null) {
        val units = TimerStore.UNIT_OPTIONS
        activeFlow = AppFlow.TimerUnitBrowse(units, 0, editTimerId)
        updateFlowDisplay()
        val intro = if (editTimerId != null) {
            val existing = TimerStore.getById(this, editTimerId)
            if (existing != null) {
                "Időzítő módosítása: ${existing.speakSummary()}. Válaszd ki az időtartam egységét."
            } else {
                "Új időzítő beállítása. Válaszd ki az időtartam egységét."
            }
        } else {
            "Új időzítő beállítása. Válaszd ki az időtartam egységét: perc vagy óra."
        }
        tts.speak(intro)
        tts.speakAdd(units.first().label)
    }

    private fun navigateTimerUnit(flow: AppFlow.TimerUnitBrowse, delta: Int) {
        val next = (flow.index + delta + flow.units.size) % flow.units.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.units[next].label)
    }

    private fun onTimerUnitActivate(flow: AppFlow.TimerUnitBrowse) {
        val unit = flow.units[flow.index]
        enterNumericDictationAwait(
            AppFlow.NumericDictationAwait(
                purpose = NumberPadPurpose.AMOUNT,
                timerUnit = unit,
                editTimerId = flow.editTimerId
            )
        )
    }

    private fun onTimerAmountSpoken(unit: TimerUnitOption, spoken: String, editTimerId: Int?) {
        val amount = VoiceDurationParser.parseAmount(spoken)
        if (amount == null) {
            tts.speak("Nem értettem a számot. Próbáld újra.")
            activeFlow = AppFlow.TimerAwaitAmount(unit, editTimerId)
            updateFlowDisplay()
            ensureMicAndRun {
                voiceInput.listen(
                    prompt = "Mondd az időtartamot ${unit.label.lowercase()}ben.",
                    speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                    onResult = { retry -> onTimerAmountSpoken(unit, retry, editTimerId) },
                    onError = { exitFlow("Nem értettem az időtartamot.") }
                )
            }
            return
        }
        val durationMinutes = TimerStore.normalizeDuration(amount * unit.multiplierMinutes)
        val intervals = TimerStore.intervalOptionsFor(durationMinutes)
        activeFlow = AppFlow.TimerIntervalBrowse(durationMinutes, intervals, 0, editTimerId)
        updateFlowDisplay()
        tts.speak(
            "Időtartam: ${TimerSpeech.speakMinutes(durationMinutes)}. " +
                "Válaszd ki a jelzés gyakoriságát. ${intervals.first()} perc."
        )
    }

    private fun navigateTimerInterval(flow: AppFlow.TimerIntervalBrowse, delta: Int) {
        val next = (flow.index + delta + flow.intervals.size) % flow.intervals.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak("${flow.intervals[next]} perc")
    }

    private fun onTimerIntervalActivate(flow: AppFlow.TimerIntervalBrowse) {
        val interval = flow.intervals[flow.index]
        activeFlow = AppFlow.TimerAwaitLabel(flow.durationMinutes, interval, flow.editTimerId)
        updateFlowDisplay()
        ensureMicAndRun {
            voiceInput.listen(
                prompt = "Mondd az időzítő nevét. Például: előadás időzítő, ebéd szünet.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val label = spoken.trim()
                    enterTimerConfirm(flow.durationMinutes, interval, label, flow.editTimerId)
                },
                onError = { enterTimerConfirm(flow.durationMinutes, interval, "", flow.editTimerId) }
            )
        }
    }

    private fun enterTimerConfirm(
        durationMinutes: Int,
        announceIntervalMinutes: Int,
        label: String,
        editTimerId: Int?
    ) {
        activeFlow = AppFlow.TimerConfirm(durationMinutes, announceIntervalMinutes, label, editTimerId)
        updateFlowDisplay()
        repeatTimerConfirm(activeFlow as AppFlow.TimerConfirm)
    }

    private fun repeatTimerConfirm(flow: AppFlow.TimerConfirm) {
        val name = flow.label.ifBlank { "Névtelen időzítő" }
        val action = if (flow.editTimerId != null) "Mentem a módosítást?" else "Elmented?"
        tts.speak(
            "Időzítő: $name, ${TimerSpeech.speakMinutes(flow.durationMinutes)}, " +
                "jelzés ${TimerSpeech.speakMinutes(flow.announceIntervalMinutes)}enként. $action " +
                "Söpörj jobbra a mentéshez, söprés balra a mégsehez. Ismétlés: söprés fel."
        )
    }

    private fun saveTimer(flow: AppFlow.TimerConfirm) {
        voiceInput.cancel()
        val duration = TimerStore.normalizeDuration(flow.durationMinutes)
        val interval = TimerStore.normalizeInterval(duration, flow.announceIntervalMinutes)
        val label = flow.label.trim()
        val entry = if (flow.editTimerId != null) {
            TimerStore.update(this, flow.editTimerId, label, duration, interval)
        } else {
            TimerStore.add(this, label, duration, interval)
        }
        if (entry == null) {
            exitFlow(
                if (flow.editTimerId != null) "Az időzítő nem található."
                else "Elérted a maximum időzítőszámot.",
                error = true
            )
            return
        }
        val verb = if (flow.editTimerId != null) "módosítva" else "mentve"
        exitFlow("Időzítő $verb: ${entry.speakSummary()}.", success = true)
    }

    private fun startTimerListFlow(mode: TimerListMode) {
        val timers = TimerStore.getAll(this)
        if (timers.isEmpty()) {
            tts.speak("Nincs mentett időzítő. Először hozz létre egyet.")
            return
        }
        activeFlow = AppFlow.TimerListBrowse(timers, 0, mode)
        updateFlowDisplay()
        val intro = when (mode) {
            TimerListMode.VIEW -> "${timers.size} időzítő. Söpörj fel-le választás, jobbra felolvasás."
            TimerListMode.START -> "${timers.size} időzítő. Söpörj fel-le választás, jobbra indítás."
            TimerListMode.EDIT -> "${timers.size} időzítő. Söpörj fel-le választás, jobbra módosítás."
            TimerListMode.DELETE -> "${timers.size} időzítő. Törlés mód. Söpörj fel-le választás, jobbra törlés."
        }
        tts.speak(intro)
        speakTimerEntry(timers.first())
    }

    private fun navigateTimerList(flow: AppFlow.TimerListBrowse, delta: Int) {
        val next = (flow.index + delta + flow.timers.size) % flow.timers.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        speakTimerEntry(flow.timers[next])
    }

    private fun onTimerListActivate(flow: AppFlow.TimerListBrowse) {
        val timer = flow.timers[flow.index]
        when (flow.mode) {
            TimerListMode.VIEW -> tts.speak(timer.speakSummary())
            TimerListMode.START -> startSavedTimer(timer)
            TimerListMode.EDIT -> startTimerCreateFlow(editTimerId = timer.id)
            TimerListMode.DELETE -> enterTimerDeleteConfirm(timer, flow.timers, flow.index)
        }
    }

    private fun startSavedTimer(timer: TimerEntry) {
        if (TimerManager.isRunning(this)) {
            TimerManager.stop(this)
            tts.speakAdd("Előző időzítő leállítva.")
        }
        TimerManager.start(this, timer)
        exitFlow("Időzítő elindítva: ${timer.speakSummary()}.", success = true)
    }

    private fun stopActiveTimer() {
        if (!TimerManager.isRunning(this)) {
            tts.speak("Nincs futó időzítő.")
            return
        }
        val session = TimerStore.getActiveSession(this)
        TimerManager.stop(this)
        val name = session?.label?.ifBlank { "Időzítő" } ?: "Időzítő"
        tts.speak("$name leállítva.")
    }

    private fun enterTimerDeleteConfirm(
        timer: TimerEntry,
        timers: List<TimerEntry>,
        index: Int
    ) {
        activeFlow = AppFlow.TimerDeleteConfirm(timer, timers, index)
        updateFlowDisplay()
        repeatTimerDeleteConfirm(timer)
    }

    private fun repeatTimerDeleteConfirm(timer: TimerEntry) {
        tts.speak(
            "Törlöd ezt az időzítőt? ${timer.speakSummary()}. Söpörj jobbra a törléshez, söprés balra a mégsehez."
        )
    }

    private fun deleteTimer(timer: TimerEntry) {
        voiceInput.cancel()
        val active = TimerStore.getActiveSession(this)
        if (active?.timerId == timer.id) {
            TimerManager.stop(this)
        }
        TimerStore.delete(this, timer.id)
        exitFlow("Időzítő törölve: ${timer.speakSummary()}.")
    }

    private fun speakTimerEntry(timer: TimerEntry) {
        tts.speakAdd(timer.speakSummary())
    }

    /**
     * NAPTÁR-VÁLASZTÓ: melyik naptárba kerüljenek a felvett programok.
     *
     * Ez azért fontos, mert sok telefonon van egy HELYI naptár (pl. "PC Sync"),
     * ami sehova nem szinkronizál — ha oda kerülnek a programok, nem jelennek
     * meg a Google Naptárban, se a gépen, se más eszközön.
     */
    /**
     * KATALÓGUS: az elérhető modulok böngészése és letöltése.
     *
     * A katalógus adat-modulokat kínál (kvíz, szójáték, rádiócsomag, útmutató),
     * amiket a SuperDL saját motorjai értelmeznek. Így egy új játékhoz NEM kell
     * új alkalmazás-verzió, és az app sem hízik feleslegesen.
     */
    /**
     * FRISSÍTÉS-KERESÉS.
     *
     * Ha a SuperDL nem a Google Play-ről érkezik, nincs automatikus frissítés —
     * ezért az alkalmazás maga néz rá naponta kétszer, és SZÓL, ha új verzió van.
     * A letöltést és a telepítést mindig a FELHASZNÁLÓ indítja, tudatosan.
     *
     * @param manual igaz, ha a felhasználó kérte (ilyenkor akkor is szólunk,
     *               ha nincs újdonság — hogy tudja, megtörtént az ellenőrzés)
     */
    private fun checkForUpdate(manual: Boolean) {
        if (manual) tts.speak("Frissítés keresése.")
        Thread {
            val info = com.superdl.launcher.catalog.UpdateChecker.check(this, force = manual)
            postWhenAlive {
                if (info == null) {
                    if (manual) {
                        tts.speak(
                            "Nincs újabb verzió. A jelenlegi: " +
                                com.superdl.launcher.catalog.UpdateChecker.currentVersion(this)
                        )
                    }
                    return@postWhenAlive
                }
                // Automatikus ellenőrzésnél csak EGYSZER szólunk egy verzióról,
                // hogy ne nyaggassuk a felhasználót minden indításnál.
                if (!manual &&
                    com.superdl.launcher.catalog.UpdateChecker.alreadyAnnounced(this, info.version)
                ) return@postWhenAlive

                com.superdl.launcher.catalog.UpdateChecker.markAnnounced(this, info.version)
                tts.speak(info.speak())
                if (info.downloadUrl.isNotBlank()) {
                    tts.speakAdd(
                        "A letöltéshez nyisd meg a Katalógus menüben a Frissítés keresése pontot, " +
                            "vagy látogasd meg a super-dl.com oldalt."
                    )
                }
            }
        }.start()
    }

    private fun startCatalogBrowse() {
        tts.speak("Katalógus betöltése.")
        Thread {
            val result = com.superdl.launcher.catalog.CatalogClient.fetchCatalog()
            postWhenAlive {
                if (result.error != null || result.modules.isEmpty()) {
                    tts.speak(result.error ?: "A katalógus most üres.")
                    return@postWhenAlive
                }
                activeFlow = AppFlow.CatalogBrowse(result.modules, 0)
                updateFlowDisplay()
                tts.speak(
                    "${result.modules.size} modul. Fel-le válogatás, jobbra letöltés, balra vissza."
                )
                tts.speakAdd(speakCatalogEntry(result.modules[0]))
            }
        }.start()
    }

    private fun speakCatalogEntry(module: com.superdl.launcher.catalog.CatalogModule): String {
        val installed = com.superdl.launcher.catalog.CatalogStore.installedVersion(this, module.id)
        return module.speakSummary(installed)
    }

    private fun navigateCatalog(flow: AppFlow.CatalogBrowse, delta: Int) {
        val next = (flow.index + delta + flow.modules.size) % flow.modules.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(speakCatalogEntry(flow.modules[next]))
    }

    /** Jobbra: letöltés (vagy leírás felolvasása, ha már megvan). */
    private fun downloadCatalogModule(flow: AppFlow.CatalogBrowse) {
        val module = flow.modules[flow.index]
        val installed = com.superdl.launcher.catalog.CatalogStore.installedVersion(this, module.id)
        if (installed != null && installed >= module.version) {
            tts.speak("Ez már letöltve van. ${module.description}")
            return
        }
        tts.speak("Letöltés: ${module.name}.")
        Thread {
            val error = com.superdl.launcher.catalog.CatalogClient.downloadModule(this, module)
            postWhenAlive {
                if (error != null) {
                    tts.speak(error)
                } else {
                    tts.speak("Letöltve: ${module.name}. ${module.description}")
                }
            }
        }.start()
    }

    /** A letöltött modulok felsorolása. */
    private fun speakInstalledModules() {
        val ids = com.superdl.launcher.catalog.CatalogStore.installedIds(this)
        if (ids.isEmpty()) {
            tts.speak(
                "Még nincs letöltött modul. Az Elérhető modulok pontban válogathatsz."
            )
            return
        }
        tts.speak("${ids.size} letöltött modul: ${ids.joinToString(", ")}")
    }

    private fun startCalendarTargetPick() {
        if (!ensureCalendarPermission()) return
        val calendars = CalendarHelper.getWritableCalendars(this)
        if (calendars.isEmpty()) {
            tts.speak("Nincs írható naptár a telefonon.")
            return
        }
        val currentId = CalendarHelper.getWritableCalendarId(this)
        val start = calendars.indexOfFirst { it.id == currentId }.coerceAtLeast(0)
        activeFlow = AppFlow.CalendarTargetPick(calendars, start)
        updateFlowDisplay()
        tts.speak(
            "${calendars.size} naptár. Fel-le válogatás, jobbra kiválasztás, balra vissza. " +
                "A szinkronizáló naptárak vannak elöl."
        )
        tts.speakAdd(speakCalendarEntry(calendars[start], currentId))
    }

    private fun speakCalendarEntry(
        info: CalendarHelper.CalendarInfo,
        currentId: Long?
    ): String {
        val mark = if (info.id == currentId) "Jelenleg ez van kiválasztva. " else ""
        return "$mark${info.speakSummary()}"
    }

    private fun navigateCalendarTargetPick(flow: AppFlow.CalendarTargetPick, delta: Int) {
        val next = (flow.index + delta + flow.calendars.size) % flow.calendars.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        val currentId = CalendarHelper.getWritableCalendarId(this)
        tts.speak(speakCalendarEntry(flow.calendars[next], currentId))
    }

    private fun confirmCalendarTarget(flow: AppFlow.CalendarTargetPick) {
        val chosen = flow.calendars[flow.index]
        CalendarPreferenceStore.setChosenCalendarId(this, chosen.id)
        if (chosen.syncs) {
            exitFlow(
                "Mostantól ide kerülnek a programjaid: ${chosen.displayName}. " +
                    "Ez szinkronizál, tehát a gépen és a weben is látni fogod őket."
            )
        } else {
            exitFlow(
                "Mostantól ide kerülnek a programjaid: ${chosen.displayName}. " +
                    "Figyelem: ez a naptár NEM szinkronizál, csak ezen a telefonon lesznek meg."
            )
        }
    }

    /** Naptárak állapota: mi van, mi szinkronizál, hova írunk. */
    private fun speakCalendarStatus() {
        if (!ensureCalendarPermission()) return
        val calendars = CalendarHelper.getWritableCalendars(this)
        if (calendars.isEmpty()) {
            tts.speak("Nincs írható naptár a telefonon.")
            return
        }
        val targetId = CalendarHelper.getWritableCalendarId(this)
        val target = calendars.firstOrNull { it.id == targetId }
        val syncing = calendars.count { it.syncs }
        tts.speak(
            "${calendars.size} írható naptár, ebből $syncing szinkronizál. " +
                "A programjaid ide kerülnek: ${target?.speakSummary() ?: "ismeretlen"}."
        )
        if (target != null && !target.syncs) {
            tts.speakAdd(
                "Ez a naptár nem szinkronizál. Ha azt szeretnéd, hogy a gépen is lásd a " +
                    "programjaidat, válassz másikat a Melyik naptárba írjunk pontban."
            )
        }
    }

    private fun startCalendarReadFlow() {
        if (!ensureCalendarPermission()) return
        val events = CalendarHelper.getTodayEvents(this)
        if (events.isEmpty()) {
            tts.speak(CalendarHelper.speakAllEvents(events))
            return
        }
        activeFlow = AppFlow.CalendarBrowse(events, 0)
        updateFlowDisplay()
        tts.speak("${events.size} mai program. Söpörj fel-le választás, jobbra műveletek, balra vissza.")
        tts.speakAdd(CalendarHelper.speakEvent(events.first()))
    }

    /**
     * Program kiválasztása közvetlen szerkesztésre vagy törlésre. A mai (ha üres,
     * a heti) programlistát nyitja, és a kiválasztott programon jobbra söpréskor
     * egyből a kért műveletet indítja — nem a teljes művelet-menüt.
     */
    private fun startCalendarPickFlow(purpose: CalendarPickPurpose) {
        if (!ensureCalendarWritePermission()) return
        val events = CalendarHelper.getTodayEvents(this)
        if (events.isEmpty()) {
            tts.speak("Ma nincs program a naptárban. A heti áttekintőben találod a többi napot.")
            return
        }
        calendarPickPurpose = purpose
        activeFlow = AppFlow.CalendarPick(events, 0, purpose)
        updateFlowDisplay()
        val verb = if (purpose == CalendarPickPurpose.EDIT) "szerkesztéshez" else "törléshez"
        tts.speak("${events.size} mai program. Söpörj fel-le, jobbra a kiválasztott $verb, balra vissza.")
        tts.speakAdd(CalendarHelper.speakEvent(events.first()))
    }

    private fun navigateCalendarPick(flow: AppFlow.CalendarPick, delta: Int) {
        val next = (flow.index + delta + flow.events.size) % flow.events.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(CalendarHelper.speakEvent(flow.events[next]))
    }

    private fun onCalendarPickActivate(flow: AppFlow.CalendarPick) {
        val event = flow.events[flow.index]
        when (flow.purpose) {
            CalendarPickPurpose.EDIT -> startCalendarEditFlow(event)
            CalendarPickPurpose.DELETE -> enterCalendarDeleteConfirm(event, flow.events, flow.index)
        }
    }

    private fun navigateCalendar(flow: AppFlow.CalendarBrowse, delta: Int) {
        val next = (flow.index + delta + flow.events.size) % flow.events.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(CalendarHelper.speakEvent(flow.events[next]))
    }

    private fun startCalendarTomorrowFlow() {
        if (!ensureCalendarPermission()) return
        val events = CalendarHelper.getTomorrowEvents(this)
        if (events.isEmpty()) {
            tts.speak("Holnap nincs bejegyzés a naptárban.")
            return
        }
        activeFlow = AppFlow.CalendarBrowse(events, 0)
        updateFlowDisplay()
        tts.speak("${events.size} holnapi program. Söpörj fel-le választás, jobbra műveletek, balra vissza.")
        tts.speakAdd(CalendarHelper.speakEvent(events.first()))
    }

    private fun startCalendarWeekFlow() {
        if (!ensureCalendarPermission()) return
        val days = CalendarHelper.getWeekEvents(this)
        if (days.isEmpty()) {
            tts.speak("A következő héten nincs bejegyzés a naptárban.")
            return
        }
        activeFlow = AppFlow.CalendarWeekBrowse(days, 0)
        updateFlowDisplay()
        tts.speak("${days.size} nap programmal. Söpörj fel-le navigálás, jobbra részletes felolvasás, balra vissza.")
        tts.speakAdd(days.first().speakPreview())
    }

    private fun navigateCalendarWeek(flow: AppFlow.CalendarWeekBrowse, delta: Int) {
        val next = (flow.index + delta + flow.days.size) % flow.days.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.days[next].speakPreview())
    }

    private fun ensureCalendarPermission(): Boolean {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CALENDAR)
            == PackageManager.PERMISSION_GRANTED
        ) return true
        tts.speak("Naptár olvasás engedély szükséges.")
        ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.READ_CALENDAR), PERM_REQUEST)
        return false
    }

    private fun ensureCalendarWritePermission(): Boolean {
        val hasRead = ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CALENDAR) ==
            PackageManager.PERMISSION_GRANTED
        val hasWrite = ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_CALENDAR) ==
            PackageManager.PERMISSION_GRANTED
        if (hasRead && hasWrite) return true
        if (!hasRead && !hasWrite) {
            tts.speak("Naptár olvasás és írás engedély szükséges.")
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.READ_CALENDAR, Manifest.permission.WRITE_CALENDAR),
                PERM_REQUEST
            )
            return false
        }
        startPermissionGuideFlow(PermissionGuideType.CALENDAR_WRITE, "Naptár írás engedély")
        return false
    }

    private fun startCalendarAddFlow() {
        if (!ensureCalendarWritePermission()) return
        if (!ensureExactAlarmOrSpeak()) return
        calendarEditEventId = null
        startCalendarTitleFlow("Mondd a program nevét. Például: orvos, találkozó, edzés.")
    }

    private fun startCalendarEditFlow(event: CalendarEvent) {
        if (!ensureCalendarWritePermission()) return
        calendarEditEventId = event.eventId
        startCalendarTitleFlow("Jelenlegi név: ${event.title}. Mondd az új program nevét.")
    }

    private fun startCalendarTitleFlow(prompt: String) {
        ensureMicAndRun {
            activeFlow = AppFlow.CalendarAwaitTitle
            updateFlowDisplay()
            voiceInput.listen(
                prompt = prompt,
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val title = spoken.trim()
                    if (title.isBlank()) {
                        exitFlow("A program neve üres.")
                        return@listen
                    }
                    activeFlow = AppFlow.CalendarAwaitDate(title)
                    updateFlowDisplay()
                    listenForCalendarDate(title)
                },
                onError = { exitFlow("Nem értettem a program nevét.") }
            )
        }
    }

    private fun listenForCalendarDate(title: String) {
        ensureMicAndRun {
            activeFlow = AppFlow.CalendarAwaitDate(title)
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd a dátumot. Például: ma, holnap, péntek, március tizenöt.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val dayStart = VoiceDateParser.parseDayStartMs(spoken)
                    if (dayStart == null) {
                        tts.speakThen(
                            "Nem értettem a dátumot. Próbáld újra, vagy söprés le az offline bevitelhez."
                        ) { listenForCalendarDate(title) }
                        return@listen
                    }
                    activeFlow = AppFlow.CalendarAwaitStartTime(title, dayStart)
                    updateFlowDisplay()
                    listenForCalendarStartTime(title, dayStart)
                },
                onError = {
                    tts.speakThen("Nem értettem a dátumot. Próbáld újra.") { listenForCalendarDate(title) }
                }
            )
        }
    }

    private fun listenForCalendarStartTime(title: String, dayStartMs: Long) {
        ensureMicAndRun {
            activeFlow = AppFlow.CalendarAwaitStartTime(title, dayStartMs)
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd a kezdési időt. Például: nyolc óra harminc, délután három.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val time = VoiceTimeParser.parse(spoken)
                    if (time == null) {
                        tts.speakThen(
                            "Nem értettem az időt. Próbáld újra, vagy söprés le az offline bevitelhez."
                        ) { listenForCalendarStartTime(title, dayStartMs) }
                        return@listen
                    }
                    activeFlow = AppFlow.CalendarAwaitEndTime(title, dayStartMs, time.first, time.second)
                    updateFlowDisplay()
                    listenForCalendarEndTime(title, dayStartMs, time.first, time.second)
                },
                onError = {
                    tts.speakThen("Nem értettem az időt. Próbáld újra.") {
                        listenForCalendarStartTime(title, dayStartMs)
                    }
                }
            )
        }
    }

    private fun openCalendarDatePad(title: String) {
        voiceInput.cancel()
        activeFlow = AppFlow.NumberPadInput(
            purpose = NumberPadPurpose.DATE,
            items = NumberPadHelper.itemsFor(NumberPadPurpose.DATE),
            index = 0,
            buffer = "",
            calendarTitle = title
        )
        updateFlowDisplay()
        tts.speak("Dátum bevitele. Nyolc számjegy: év, hónap, nap.")
    }

    private fun openCalendarStartTimePad(title: String, dayStartMs: Long) {
        voiceInput.cancel()
        activeFlow = AppFlow.NumberPadInput(
            purpose = NumberPadPurpose.TIME,
            items = NumberPadHelper.itemsFor(NumberPadPurpose.TIME),
            index = 0,
            buffer = "",
            calendarTitle = title,
            calendarDayStartMs = dayStartMs
        )
        updateFlowDisplay()
        tts.speak("Kezdési idő bevitele. Négy számjegy: óra, óra, perc, perc.")
    }

    private fun openCalendarEndTimePad(
        title: String,
        dayStartMs: Long,
        startHour: Int,
        startMinute: Int
    ) {
        voiceInput.cancel()
        activeFlow = AppFlow.NumberPadInput(
            purpose = NumberPadPurpose.TIME,
            items = NumberPadHelper.itemsFor(NumberPadPurpose.TIME),
            index = 0,
            buffer = "",
            calendarTitle = title,
            calendarDayStartMs = dayStartMs,
            calendarAwaitEnd = true,
            calendarStartHour = startHour,
            calendarStartMinute = startMinute
        )
        updateFlowDisplay()
        tts.speak("Befejezési idő bevitele. Négy számjegy: óra, óra, perc, perc. Balra üresen hagyva egy órás program lesz.")
    }

    private fun listenForCalendarEndTime(
        title: String,
        dayStartMs: Long,
        startHour: Int,
        startMinute: Int
    ) {
        activeFlow = AppFlow.CalendarAwaitEndTime(title, dayStartMs, startHour, startMinute)
        updateFlowDisplay()
        voiceInput.listen(
            prompt = "Mondd a befejezési időt, vagy mondd: egy óra. Ha nem mondod, egy órás program lesz.",
            speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
            onResult = { spoken ->
                resolveCalendarEndTime(title, dayStartMs, startHour, startMinute, spoken)
            },
            onError = {
                applyCalendarDefaultDuration(title, dayStartMs, startHour, startMinute)
            }
        )
    }

    private fun resolveCalendarEndTime(
        title: String,
        dayStartMs: Long,
        startHour: Int,
        startMinute: Int,
        spoken: String
    ) {
        val duration = VoiceDateParser.parseDurationMinutes(spoken)
        if (duration != null) {
            val times = CalendarHelper.buildEventTimesWithDuration(
                dayStartMs, startHour, startMinute, duration
            )
            enterCalendarRecurrenceBrowse(title, times.first, times.second)
            return
        }
        val endTime = VoiceTimeParser.parse(spoken)
        if (endTime == null) {
            tts.speakThen("Nem értettem a befejezési időt. Próbáld újra, vagy mondd: egy óra.") {
                listenForCalendarEndTime(title, dayStartMs, startHour, startMinute)
            }
            return
        }
        val times = CalendarHelper.buildEventTimes(
            dayStartMs, startHour, startMinute, endTime.first, endTime.second
        )
        enterCalendarRecurrenceBrowse(title, times.first, times.second)
    }

    private fun applyCalendarDefaultDuration(
        title: String,
        dayStartMs: Long,
        startHour: Int,
        startMinute: Int
    ) {
        val times = CalendarHelper.buildEventTimesWithDuration(dayStartMs, startHour, startMinute, 60)
        enterCalendarRecurrenceBrowse(title, times.first, times.second)
    }

    private fun enterCalendarRecurrenceBrowse(title: String, beginMs: Long, endMs: Long) {
        val options = CalendarRecurrence.selectable
        val defaultIndex = calendarEditEventId?.let { id ->
            CalendarHelper.getEventById(this, id)?.recurrence?.let { recurrence ->
                options.indexOf(recurrence).coerceAtLeast(0)
            }
        } ?: 0
        activeFlow = AppFlow.CalendarRecurrenceBrowse(
            title = title,
            beginMs = beginMs,
            endMs = endMs,
            options = options,
            index = defaultIndex,
            editEventId = calendarEditEventId
        )
        updateFlowDisplay()
        tts.speak("Ismétlés beállítása. ${options[defaultIndex].speakSummary()}. Söpörj fel-le választás, jobbra megerősítés.")
    }

    private fun navigateCalendarRecurrence(flow: AppFlow.CalendarRecurrenceBrowse, delta: Int) {
        val next = (flow.index + delta + flow.options.size) % flow.options.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.options[next].speakSummary())
    }

    private fun applyCalendarRecurrence(flow: AppFlow.CalendarRecurrenceBrowse) {
        enterCalendarConfirm(
            title = flow.title,
            beginMs = flow.beginMs,
            endMs = flow.endMs,
            recurrence = flow.options[flow.index],
            editEventId = flow.editEventId
        )
    }

    private fun enterCalendarConfirm(
        title: String,
        beginMs: Long,
        endMs: Long,
        recurrence: CalendarRecurrence,
        editEventId: Long? = calendarEditEventId
    ) {
        activeFlow = AppFlow.CalendarConfirm(title, beginMs, endMs, recurrence, editEventId)
        updateFlowDisplay()
        repeatCalendarConfirm(activeFlow as AppFlow.CalendarConfirm)
    }

    private fun repeatCalendarConfirm(flow: AppFlow.CalendarConfirm) {
        val message = if (flow.editEventId != null) {
            CalendarHelper.speakEditEventConfirm(flow.title, flow.beginMs, flow.endMs, flow.recurrence)
        } else {
            CalendarHelper.speakEventConfirm(flow.title, flow.beginMs, flow.endMs, flow.recurrence)
        }
        tts.speak(message)
    }

    private fun saveCalendarEvent(flow: AppFlow.CalendarConfirm) {
        if (!ensureCalendarWritePermission()) return
        val ok = if (flow.editEventId != null) {
            CalendarHelper.updateEvent(
                this,
                flow.editEventId,
                flow.title,
                flow.beginMs,
                flow.endMs,
                flow.recurrence
            )
        } else {
            CalendarHelper.insertEvent(
                this,
                flow.title,
                flow.beginMs,
                flow.endMs,
                flow.recurrence
            ) != null
        }
        calendarEditEventId = null
        val scheduleNote = if (ok && flow.beginMs > System.currentTimeMillis() && !AlarmScheduler.canScheduleExact(this)) {
            " Figyelem: pontos ébresztő engedély hiányzik, az emlékeztető késhet."
        } else {
            ""
        }
        exitFlow(
            if (ok) {
                if (flow.editEventId != null) "Program módosítva: ${flow.title}.$scheduleNote"
                else "Program mentve a naptárba: ${flow.title}. Emlékeztető beállítva az indulási időpontra.$scheduleNote"
            } else {
                "Program mentése sikertelen. Ellenőrizd a naptár írás engedélyt."
            },
            success = ok,
            error = !ok
        )
    }

    // ==================== SAJÁT JEGYZETEK ====================

    private fun startNoteListFlow(deleteMode: Boolean = false) {
        val notes = NoteStore.getAll(this)
        if (notes.isEmpty()) {
            tts.speak("Nincs mentett jegyzet.")
            return
        }
        activeFlow = AppFlow.NoteListBrowse(notes, 0, deleteMode)
        updateFlowDisplay()
        val intro = if (deleteMode) {
            "${notes.size} jegyzet. Törlés mód. Söpörj fel-le választás, jobbra törlés megerősítése."
        } else {
            "${notes.size} jegyzet. Söpörj fel-le választás, jobbra megnyitás."
        }
        tts.speak(intro)
        speakNoteListItem(notes.first(), 1, notes.size)
    }

    private fun speakNoteListItem(note: NoteEntry, index: Int, total: Int) {
        tts.speak(note.speakListItem(index, total))
    }

    private fun navigateNoteList(flow: AppFlow.NoteListBrowse, delta: Int) {
        val next = (flow.index + delta + flow.notes.size) % flow.notes.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        speakNoteListItem(flow.notes[next], next + 1, flow.notes.size)
    }

    private fun onNoteListActivate(flow: AppFlow.NoteListBrowse) {
        val note = flow.notes[flow.index]
        if (flow.deleteMode) {
            enterNoteDeleteConfirm(note, flow.notes, flow.index)
        } else {
            openNoteReading(note, flow.notes, flow.index)
        }
    }

    private fun enterNoteDeleteConfirm(note: NoteEntry, notes: List<NoteEntry>, index: Int) {
        activeFlow = AppFlow.NoteDeleteConfirm(note, notes, index)
        updateFlowDisplay()
        repeatNoteDeleteConfirm(note)
    }

    private fun repeatNoteDeleteConfirm(note: NoteEntry) {
        tts.speak(
            "Törlöd ezt a jegyzetet? ${note.title}. Söpörj jobbra a törléshez, söprés balra a mégsehez."
        )
    }

    private fun deleteNote(flow: AppFlow.NoteDeleteConfirm) {
        val removed = NoteStore.delete(this, flow.note.id)
        if (removed == null) {
            tts.speak("A jegyzet törlése sikertelen.")
            return
        }
        val remaining = NoteStore.getAll(this)
        if (remaining.isEmpty()) {
            exitFlow("Jegyzet törölve: ${removed.title}. Nincs több jegyzet.")
            return
        }
        val nextIndex = flow.index.coerceAtMost(remaining.lastIndex)
        activeFlow = AppFlow.NoteListBrowse(remaining, nextIndex, deleteMode = true)
        updateFlowDisplay()
        tts.speak("Jegyzet törölve: ${removed.title}.")
        speakNoteListItem(remaining[nextIndex], nextIndex + 1, remaining.size)
    }

    private fun startNoteCreateFlow() {
        ensureMicAndRun {
            activeFlow = AppFlow.NoteAwaitTitle
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd a jegyzet címét. Például: bevásárló ötletek, recept, fontos telefonszám.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val title = spoken.trim()
                    if (title.isBlank()) {
                        tts.speakThen("A cím üres. Próbáld újra.") { startNoteCreateFlow() }
                        return@listen
                    }
                    listenForNoteBody(title)
                },
                onError = { exitFlow("Jegyzet létrehozás megszakítva.") }
            )
        }
    }

    private fun listenForNoteBody(title: String) {
        ensureMicAndRun {
            activeFlow = AppFlow.NoteAwaitBody(title)
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd a jegyzet szövegét. Bármilyen hosszúságú lehet. " +
                    "Kimondhatod az írásjeleket is: vessző, pont, új sor.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val body = SpeechPunctuation.apply(spoken)
                    if (body.isBlank()) {
                        tts.speakThen("A jegyzet szövege üres. Próbáld újra.") { listenForNoteBody(title) }
                        return@listen
                    }
                    saveNoteFromDictation(title, body)
                },
                onError = { exitFlow("Jegyzet létrehozás megszakítva.") }
            )
        }
    }

    private fun saveNoteFromDictation(title: String, body: String, sourceUrl: String? = null) {
        val entry = NoteStore.add(this, title, body, sourceUrl)
        if (entry == null) {
            exitFlow("Nem sikerült menteni a jegyzetet. Lehet, hogy üres, vagy elérted a ${NoteStore.MAX_NOTES} jegyzet limitet.")
            return
        }
        exitFlow("Jegyzet mentve: ${entry.title}.")
    }

    private fun openNoteReading(note: NoteEntry, notes: List<NoteEntry>, noteIndex: Int) {
        if (::noteReader.isInitialized && noteReader.isActive) noteReader.stop()
        noteReader.startWithText(noteReadingBook, note.title, note.body, 0)
        activeFlow = AppFlow.NoteReading(
            note = note,
            chunkIndex = 0,
            totalChunks = 1,
            percent = 0,
            notes = notes,
            noteIndex = noteIndex
        )
        updateFlowDisplay()
        tts.speak(
            "Jegyzet: ${note.title}. Söpörj lefelé: következő rész, felfelé: ismétlés, balra: vissza a listához."
        )
    }

    private fun finishNoteReading(message: String) {
        noteReader.stop()
        val flow = activeFlow as? AppFlow.NoteReading
        if (flow != null) {
            activeFlow = AppFlow.NoteListBrowse(flow.notes, flow.noteIndex)
            updateFlowDisplay()
            tts.speak("$message Vissza a jegyzeteknél.")
            return
        }
        exitFlow(message)
    }

    private fun exitNoteReading(message: String) {
        if (::noteReader.isInitialized && noteReader.isActive) noteReader.stop()
        exitFlow(message)
    }

    private fun enterCalendarContextMenu(flow: AppFlow.CalendarBrowse) {
        val actions = CalendarContextAction.browseActions
        activeFlow = AppFlow.CalendarContextMenu(flow.events, flow.index, actions, 0)
        updateFlowDisplay()
        tts.speak("Program műveletek. ${actions.first().label}. Söpörj fel-le választás, jobbra végrehajtás, balra vissza.")
    }

    private fun navigateCalendarContextMenu(flow: AppFlow.CalendarContextMenu, delta: Int) {
        val next = (flow.actionIndex + delta + flow.actions.size) % flow.actions.size
        activeFlow = flow.copy(actionIndex = next)
        updateFlowDisplay()
        tts.speak(flow.actions[next].label)
    }

    private fun onCalendarContextActivate(flow: AppFlow.CalendarContextMenu) {
        val event = flow.events[flow.eventIndex]
        when (flow.actions[flow.actionIndex]) {
            CalendarContextAction.READ -> tts.speak(CalendarHelper.speakEvent(event))
            CalendarContextAction.EDIT -> startCalendarEditFlow(event)
            CalendarContextAction.DELETE -> enterCalendarDeleteConfirm(event, flow.events, flow.eventIndex)
        }
    }

    private fun returnToCalendarBrowse(events: List<CalendarEvent>, index: Int) {
        activeFlow = AppFlow.CalendarBrowse(events, index)
        updateFlowDisplay()
        tts.speak("Vissza a naptárban.")
        tts.speakAdd(CalendarHelper.speakEvent(events[index]))
    }

    private fun enterCalendarDeleteConfirm(event: CalendarEvent, events: List<CalendarEvent>, index: Int) {
        activeFlow = AppFlow.CalendarDeleteConfirm(event, events, index)
        updateFlowDisplay()
        repeatCalendarDeleteConfirm(event)
    }

    private fun repeatCalendarDeleteConfirm(event: CalendarEvent) {
        tts.speak("Biztosan törlöd a ${event.title} programot? Söpörj jobbra a törléshez, söprés balra a mégsehez.")
    }

    private fun deleteCalendarEvent(flow: AppFlow.CalendarDeleteConfirm) {
        val ok = CalendarHelper.deleteEvent(this, flow.event.eventId)
        if (!ok) {
            exitFlow("Program törlése sikertelen.", error = true)
            return
        }
        val updated = flow.events.filterNot { it.eventId == flow.event.eventId }
        if (updated.isEmpty()) {
            exitFlow("Program törölve: ${flow.event.title}.", success = true)
            return
        }
        val newIndex = flow.index.coerceAtMost(updated.lastIndex)
        returnToCalendarBrowse(updated, newIndex)
        tts.speakAdd("Program törölve: ${flow.event.title}.")
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleCalendarAlarmIntent(intent)

        queueVoiceAssistantLaunchIfNeeded(intent)
        handleDialIntent(intent)
        if (pendingAssistantLaunch) {
            if (LockSession.lockScreenVisible) {
                LockSession.lockScreenVisible = false
                activeFlow = AppFlow.Menu
                updateDisplay()
            }
            runPendingVoiceActionIfReady()
        }
    }

    private fun handleDialIntent(intent: Intent?) {
        val number = intent?.getStringExtra(DialActivity.EXTRA_DIAL_NUMBER).orEmpty().trim()
        if (number.isBlank()) return
        intent?.removeExtra(DialActivity.EXTRA_DIAL_NUMBER)
        mainHandler.postDelayed({
            if (LockSession.needsUnlock(this)) return@postDelayed
            enterCallConfirm(ContactMatch("dial", "Tárcsázás", number))
        }, 300)
    }

    private fun handleCalendarAlarmIntent(intent: Intent?) {
        if (intent?.action != CalendarAlarmReceiver.ACTION_CALENDAR_ALARM) return
        val eventId = intent.getLongExtra(CalendarAlarmReceiver.EXTRA_EVENT_ID, -1L)
        if (eventId < 0L) return
        val title = intent.getStringExtra(CalendarAlarmReceiver.EXTRA_TITLE).orEmpty()
        val beginMs = intent.getLongExtra(CalendarAlarmReceiver.EXTRA_BEGIN_MS, 0L)
        val endMs = intent.getLongExtra(CalendarAlarmReceiver.EXTRA_END_MS, 0L)
        try {
            startActivity(
                Intent(this, CalendarAlertActivity::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
                    putExtra(CalendarAlarmReceiver.EXTRA_EVENT_ID, eventId)
                    putExtra(CalendarAlarmReceiver.EXTRA_TITLE, title)
                    putExtra(CalendarAlarmReceiver.EXTRA_BEGIN_MS, beginMs)
                    putExtra(CalendarAlarmReceiver.EXTRA_END_MS, endMs)
                }
            )
        } catch (_: Exception) {
            val event = CalendarEvent(eventId, title, beginMs, endMs)
            enterCalendarAlarmContextMenu(event)
        }
    }

    private fun enterCalendarAlarmContextMenu(event: CalendarEvent) {
        voiceInput.cancel()
        val actions = CalendarAlarmAction.entries.toList()
        activeFlow = AppFlow.CalendarAlarmContextMenu(event, actions, 0)
        updateFlowDisplay()
        tts.speak(CalendarHelper.speakAlarmPrompt(event))
        tts.speakAdd("${actions.first().label}. Söpörj fel-le választás, jobbra végrehajtás.")
    }

    private fun navigateCalendarAlarmContextMenu(flow: AppFlow.CalendarAlarmContextMenu, delta: Int) {
        val next = (flow.actionIndex + delta + flow.actions.size) % flow.actions.size
        activeFlow = flow.copy(actionIndex = next)
        updateFlowDisplay()
        tts.speak(flow.actions[next].label)
    }

    private fun onCalendarAlarmContextActivate(flow: AppFlow.CalendarAlarmContextMenu) {
        when (flow.actions[flow.actionIndex]) {
            CalendarAlarmAction.REMIND_ONE_HOUR -> {
                CalendarAlarmService.stop(this)
                CalendarReminderScheduler.scheduleSnoozeOneHour(
                    this,
                    flow.event.eventId,
                    flow.event.title,
                    flow.event.begin,
                    flow.event.end
                )
                exitFlow("Emlékeztető egy óra múlva: ${flow.event.title}.", success = true)
            }
            CalendarAlarmAction.MARK_COMPLETE -> {
                CalendarAlarmService.stop(this)
                CalendarReminderScheduler.cancelInstance(this, flow.event.eventId, flow.event.begin)
                CalendarReminderStore.markCompleted(this, flow.event.eventId, flow.event.begin)
                exitFlow("${flow.event.title} teljesítettként megjelölve.", success = true)
            }
        }
    }

    private fun dismissCalendarAlarm() {
        CalendarAlarmService.stop(this)
        exitFlow("Program emlékeztető bezárva.")
    }

    // ==================== HÍVÁSNAPLÓ ====================

    private fun startCallLogFlow() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CALL_LOG)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("Hívásnapló olvasás engedély szükséges.")
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.READ_CALL_LOG), PERM_REQUEST)
            return
        }
        val entries = CallLogHelper.getRecentCalls(this)
        if (entries.isEmpty()) {
            tts.speak("A hívásnapló üres.")
            return
        }
        activeFlow = AppFlow.CallLogBrowse(entries, 0)
        updateFlowDisplay()
        tts.speak("${entries.size} hívás. Söpörj fel-le navigálás, jobbra műveletek, balra vissza.")
        tts.speakAdd(entries.first().speakPreview())
    }

    private fun navigateCallLog(flow: AppFlow.CallLogBrowse, delta: Int) {
        val next = (flow.index + delta + flow.entries.size) % flow.entries.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.entries[next].speakPreview())
    }

    private fun enterCallLogContextMenu(flow: AppFlow.CallLogBrowse) {
        val entry = flow.entries[flow.index]
        val actions = CallLogContextAction.forEntry(this, entry)
        activeFlow = AppFlow.CallLogContextMenu(flow.entries, flow.index, actions, 0)
        updateFlowDisplay()
        tts.speak("Hívás műveletek. ${actions.first().label}. Söpörj fel-le választás, jobbra végrehajtás, balra vissza.")
    }

    private fun navigateCallLogContextMenu(flow: AppFlow.CallLogContextMenu, delta: Int) {
        val next = (flow.actionIndex + delta + flow.actions.size) % flow.actions.size
        activeFlow = flow.copy(actionIndex = next)
        updateFlowDisplay()
        tts.speak(flow.actions[next].label)
    }

    private fun onCallLogContextActivate(flow: AppFlow.CallLogContextMenu) {
        val entry = flow.entries[flow.entryIndex]
        when (flow.actions[flow.actionIndex]) {
            CallLogContextAction.CALL -> placeCall(entry.number, entry.name.ifBlank { entry.number })
            CallLogContextAction.SEND_SMS -> startSmsToPhone(entry.number, entry.name.ifBlank { entry.number })
            CallLogContextAction.COPY_NUMBER -> copyPhoneNumber(entry.number)
            CallLogContextAction.SAVE_CONTACT -> startCallLogSaveContact(flow)
            CallLogContextAction.ADD_FAVORITE -> addCallLogToFavorites(entry, flow.entries, flow.entryIndex)
            CallLogContextAction.BLOCK_NUMBER -> blockCallLogNumber(entry)
        }
    }

    private fun blockCallLogNumber(entry: com.superdl.launcher.calllog.CallLogEntry) {
        if (entry.number.isBlank()) {
            tts.speak("Nincs letiltandó szám.")
            return
        }
        if (CallFilterStore.isBlacklisted(this, entry.number)) {
            tts.speak("Ez a szám már a tiltólistán van: ${ContactHelper.maskPhone(entry.number)}.")
            return
        }
        val added = CallFilterStore.addToBlacklist(this, entry.number)
        if (!added) {
            tts.speak("A szám letiltása sikertelen.")
            return
        }
        feedbackSuccess()
        val masked = ContactHelper.maskPhone(entry.number)
        tts.speak("A $masked szám letiltva. A jövőbeni hívásai automatikusan elutasításra kerülnek.")
        ensureCallScreeningRole(promptIfMissing = true)
    }

    private fun returnToCallLogBrowse(entries: List<com.superdl.launcher.calllog.CallLogEntry>, index: Int) {
        activeFlow = AppFlow.CallLogBrowse(entries, index)
        updateFlowDisplay()
        tts.speak("Vissza a hívásnaplóban.")
        tts.speakAdd(entries[index].speakPreview())
    }

    private fun copyPhoneNumber(number: String) {
        val clipboard = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("phone", number))
        feedbackSuccess()
        tts.speak("Szám a vágólapra másolva: ${ContactHelper.maskPhone(number)}.")
    }

    private fun startContactCreateFlow() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_CONTACTS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("Névjegy mentés engedély szükséges.")
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.WRITE_CONTACTS), PERM_REQUEST)
            return
        }
        enterNumericDictationAwait(AppFlow.NumericDictationAwait(purpose = NumberPadPurpose.CONTACT))
    }

    private fun proceedContactCreateName(phone: String) {
        val trimmedPhone = phone.trim()
        if (trimmedPhone.isBlank()) {
            tts.speak("Üres szám. Írj be legalább egy számjegyet.")
            return
        }
        activeFlow = AppFlow.ContactCreateAwaitName(trimmedPhone)
        updateFlowDisplay()
        listenForContactCreateName(trimmedPhone)
    }

    private fun listenForContactCreateName(phone: String) {
        if (activeFlow !is AppFlow.ContactCreateAwaitName) return
        ensureMicAndRun {
            voiceInput.listen(
                prompt = "Mondd az új névjegy nevét a ${ContactHelper.maskPhone(phone)} számhoz.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    if (activeFlow !is AppFlow.ContactCreateAwaitName) return@listen
                    val name = spoken.trim()
                    if (name.isBlank()) {
                        tts.speak("A név üres. Mondd újra a nevet.")
                        listenForContactCreateName(phone)
                        return@listen
                    }
                    val ok = ContactHelper.insertContact(this, name, phone)
                    if (ok) {
                        exitFlow("$name mentve a névjegyek közé.", success = true)
                    } else {
                        exitFlow("Névjegy mentése sikertelen.", error = true)
                    }
                },
                onError = {
                    if (activeFlow is AppFlow.ContactCreateAwaitName) {
                        exitFlow("Névjegy létrehozás megszakítva.")
                    }
                }
            )
        }
    }

    private fun resolveAssistantCallContact(query: String) {
        val contacts = ContactHelper.searchByName(this, query)
        when {
            contacts.size == 1 -> {
                val contact = contacts.first()
                if (assistantLockedMode) {
                    // ZÁRT KÉPERNYŐN NINCS MEGERŐSÍTŐ GESZTUS.
                    // A zárt képernyős parancs lényege, hogy NE kelljen elővenni
                    // a telefont — ha jobbra kellene söpörni a hívás indításához,
                    // az értelmetlenné tenné az egészet. Ezért bemondjuk, kit
                    // hívunk, és rögtön tárcsázunk.
                    tts.speakThen("Hívom: ${contact.name}.") {
                        placeCall(contact.phone, contact.name)
                    }
                } else {
                    voiceAssistantReturnPending = true
                    enterCallConfirm(contact)
                }
            }
            contacts.isEmpty() -> {
                tts.speakThen("Nem található névjegy: $query.") { resumeVoiceAssistantListening() }
            }
            assistantLockedMode -> {
                // Több találat zárt képernyőn: választani nem tudunk gesztus
                // nélkül, ezért kérünk pontosítást, nem hívunk vaktában.
                tts.speakThen(
                    "${contacts.size} névjegyet találtam erre: $query. " +
                        "Mondd a teljes nevet."
                ) { resumeVoiceAssistantListening() }
            }
            else -> {
                voiceAssistantReturnPending = true
                activeFlow = AppFlow.CallPickContact(contacts, 0)
                updateFlowDisplay()
                tts.speakThen("Több találat. ${contacts.size} névjegy. Söpörj fel-le választás, jobbra hívás.") {
                    speakContactMatch(contacts.first())
                }
            }
        }
    }

    private fun startCallLogSaveContact(flow: AppFlow.CallLogContextMenu) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_CONTACTS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("Névjegy mentés engedély szükséges.")
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.WRITE_CONTACTS), PERM_REQUEST)
            return
        }
        ensureMicAndRun {
            activeFlow = AppFlow.CallLogSaveContactAwaitName(flow.entries, flow.entryIndex)
            updateFlowDisplay()
            val entry = flow.entries[flow.entryIndex]
            voiceInput.listen(
                prompt = "Mondd a névjegy nevét a ${ContactHelper.maskPhone(entry.number)} számhoz.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val name = spoken.trim()
                    if (name.isBlank()) {
                        tts.speak("A név üres. Próbáld újra.")
                        startCallLogSaveContact(flow)
                        return@listen
                    }
                    val ok = ContactHelper.insertContact(this, name, entry.number)
                    if (ok) {
                        feedbackSuccess()
                        returnToCallLogBrowse(flow.entries, flow.entryIndex)
                        tts.speakAdd("$name mentve a névjegyek közé.")
                    } else {
                        exitFlow("Névjegy mentése sikertelen.", error = true)
                    }
                },
                onError = {
                    if (activeFlow is AppFlow.CallLogSaveContactAwaitName) {
                        returnToCallLogBrowse(flow.entries, flow.entryIndex)
                        tts.speak("Névjegy mentés megszakítva.")
                    }
                }
            )
        }
    }

    private fun addCallLogToFavorites(
        entry: com.superdl.launcher.calllog.CallLogEntry,
        entries: List<com.superdl.launcher.calllog.CallLogEntry>,
        index: Int
    ) {
        val name = entry.name.ifBlank { entry.number }
        if (FavoritesStore.contains(this, entry.number)) {
            tts.speak("Ez a szám már a kedvencek között van.")
            returnToCallLogBrowse(entries, index)
            return
        }
        val added = FavoritesStore.add(this, name, entry.number)
        if (added) {
            feedbackSuccess()
            tts.speak("$name hozzáadva a kedvencekhez.")
        } else {
            feedbackError()
            tts.speak("Kedvenc mentése sikertelen.")
        }
        returnToCallLogBrowse(entries, index)
    }

    // ==================== KEDVENCEK ====================

    private fun startFavoritesFlow(mode: FavoritesListMode) {
        val favorites = FavoritesStore.getAll(this)
        if (favorites.isEmpty()) {
            tts.speak("Nincs mentett kedvenc.")
            return
        }
        activeFlow = AppFlow.FavoritesBrowse(favorites, 0, mode)
        updateFlowDisplay()
        val intro = when (mode) {
            FavoritesListMode.CALL -> "${favorites.size} kedvenc. Söpörj fel-le választás, jobbra hívás, balra vissza."
            FavoritesListMode.DELETE -> "${favorites.size} kedvenc. Söpörj fel-le választás, jobbra törlés, balra vissza."
        }
        tts.speak(intro)
        tts.speakAdd(favorites.first().speakPreview())
    }

    private fun navigateFavoritesList(flow: AppFlow.FavoritesBrowse, delta: Int) {
        val next = (flow.index + delta + flow.favorites.size) % flow.favorites.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.favorites[next].speakPreview())
    }

    private fun onFavoritesListActivate(flow: AppFlow.FavoritesBrowse) {
        val favorite = flow.favorites[flow.index]
        when (flow.mode) {
            FavoritesListMode.CALL -> placeCall(favorite.phone, favorite.name)
            FavoritesListMode.DELETE -> enterFavoriteDeleteConfirm(favorite, flow.favorites, flow.index)
        }
    }

    private fun enterFavoriteDeleteConfirm(
        favorite: FavoriteEntry,
        favorites: List<FavoriteEntry>,
        index: Int
    ) {
        activeFlow = AppFlow.FavoriteDeleteConfirm(favorite, favorites, index)
        updateFlowDisplay()
        repeatFavoriteDeleteConfirm(favorite)
    }

    private fun repeatFavoriteDeleteConfirm(favorite: FavoriteEntry) {
        tts.speak("Biztosan törlöd ${favorite.speakPreview()} kedvencet? Söpörj jobbra a törléshez, söprés balra a mégsehez. Ismétlés: söprés fel.")
    }

    private fun deleteFavorite(flow: AppFlow.FavoriteDeleteConfirm) {
        val ok = FavoritesStore.remove(this, flow.favorite.phone)
        if (!ok) {
            exitFlow("Kedvenc törlése sikertelen.", error = true)
            return
        }
        feedbackSuccess()
        val updated = FavoritesStore.getAll(this)
        if (updated.isEmpty()) {
            exitFlow("Kedvenc törölve. Nincs több mentett kedvenc.", success = true)
            return
        }
        val newIndex = flow.index.coerceAtMost(updated.lastIndex)
        activeFlow = AppFlow.FavoritesBrowse(updated, newIndex, FavoritesListMode.DELETE)
        updateFlowDisplay()
        tts.speak("Kedvenc törölve.")
        tts.speakAdd(updated[newIndex].speakPreview())
    }

    // ==================== IDŐJÁRÁS ====================

    private fun startWeatherFlow() {
        tts.speak("Időjárás betöltése. Várj egy pillanatot.")
        WeatherHelper.fetch(
            onResult = { info -> postWhenAlive { tts.speak(info.speakSummary()) } },
            onError = { message -> postWhenAlive { tts.speak(message) } }
        )
    }

    private fun startWeatherCityFlow() {
        ensureMicAndRun {
            activeFlow = AppFlow.WeatherAwaitCity
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd melyik város időjárását szeretnéd.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val city = spoken.trim()
                    if (city.isBlank()) {
                        exitFlow("Nem értettem a várost.")
                        return@listen
                    }
                    fetchWeatherForCity(city)
                },
                onError = { exitFlow("Nem értettem a várost.") }
            )
        }
    }

    private fun fetchWeatherForCity(city: String) {
        voiceInput.cancel()
        WeatherCityStore.save(this, city)
        tts.speak("Időjárás betöltése: $city. Várj egy pillanatot.")
        WeatherHelper.fetch(
            city = city,
            onResult = { info ->
                postWhenAlive {
                    activeFlow = AppFlow.Menu
                    updateFlowDisplay()
                    tts.speak(info.speakSummary())
                }
            },
            onError = { message -> postWhenAlive { exitFlow(message, error = true) } }
        )
    }

    // ==================== FÁJLOK, PORTÁL, ZENE ====================

    /**
     * WiFi fájlportál be/ki. Bekapcsoláskor bemondja a böngészőbe írandó
     * címet (számjegyenként, hogy vakon is leírható legyen).
     */
    private fun openFileManager() {
        tts.speak("Fájlkezelő indítása.")
        startActivity(Intent(this, FileManagerActivity::class.java))
    }

    private fun toggleWifiPortal() {
        if (WifiPortalService.isRunning) {
            WifiPortalService.stop(this)
            tts.speak("Fájlportál kikapcsolva.")
            return
        }
        val probe = WifiPortalServer(this)
        val ip = probe.localIpAddress()
        if (ip == null) {
            tts.speak(
                "Nincs WiFi kapcsolat. A portálhoz a telefonnak és a gépnek " +
                    "ugyanarra a WiFi hálózatra kell csatlakoznia."
            )
            return
        }
        WifiPortalService.start(this)
        // Egy pillanat, míg a szerver elindul, aztán bemondjuk a címet és a PIN-t.
        window.decorView.postDelayed({
            val spoken = WifiPortalService.currentSpokenUrl() ?: probe.speakUrl()
            val pin = WifiPortalService.currentSpokenPin()
            val pinPart = if (pin != null) {
                "A belépéshez szükséges PIN kód: $pin . Ismétlem: $pin . "
            } else {
                ""
            }
            tts.speak(
                "Fájlportál bekapcsolva. A gépeden nyisd meg a böngészőt, és írd be: " +
                    "$spoken . Ismétlem: $spoken . " +
                    pinPart +
                    "Ott feltölthetsz fájlokat a telefonra, azok a SuperDL, Portal mappába kerülnek. " +
                    "Ha végeztél, kapcsold ki ezt a menüpontot."
            )
        }, 900L)
    }

    private fun openUsbFileTransfer() {
        val status = UsbTransferHelper.speakStatus(this)
        if (!UsbTransferHelper.isUsbConnected(this)) {
            tts.speak(status)
            return
        }
        tts.speakThen(status) {
            if (!UsbTransferHelper.openUsbSettings(this)) {
                tts.speak(
                    "Nem sikerült megnyitni az USB beállításokat ezen a telefonon. " +
                        "Húzd le az értesítéseket, és ott találod az USB beállítás lehetőséget."
                )
            }
        }
    }

    private fun cycleMusicPlayMode() {
        val modes = MusicPlayerActivity.PlayMode.entries
        val current = MusicPlayerPrefs.getPlayMode(this)
        val next = modes[(current.ordinal + 1) % modes.size]
        MusicPlayerPrefs.setPlayMode(this, next)
        val label = when (next) {
            MusicPlayerActivity.PlayMode.SEQUENTIAL -> "sorban lejátszás"
            MusicPlayerActivity.PlayMode.REPEAT_ONE -> "egy szám ismétlése"
            MusicPlayerActivity.PlayMode.REPEAT_ALL -> "teljes lista ismétlése"
            MusicPlayerActivity.PlayMode.SHUFFLE -> "véletlen sorrend"
        }
        tts.speak("Lejátszási mód: $label. Söpörj fel-le a menüben a többi beállításhoz.")
    }

    private fun cycleMusicSeekStep() {
        val steps = MusicPlayerPrefs.SEEK_STEPS
        val current = MusicPlayerPrefs.getSeekStep(this)
        val idx = steps.indexOf(current).let { if (it < 0) 0 else it }
        val next = steps[(idx + 1) % steps.size]
        MusicPlayerPrefs.setSeekStep(this, next)
        tts.speak("Tekerés egység: $next másodperc.")
    }

    /** A zenelejátszó beszéd-visszajelzésének ki/be kapcsolása (számváltás, leállítás, tekerés). */
    /**
     * FŐKAPCSOLÓ a zenelejátszó beszédéhez. Kikapcsolva a lejátszó nem mond
     * semmit magától (szám címe, szünet, folytatás) — a zene zavartalanul szól.
     * A vezérlők bemondása és a hibaüzenetek ilyenkor is megmaradnak, különben
     * a lejátszó kezelhetetlen lenne.
     */
    private fun toggleMusicSpeechMaster() {
        val next = !MusicPlayerPrefs.isSpeechEnabled(this)
        MusicPlayerPrefs.setSpeechEnabled(this, next)
        if (next) {
            tts.speak("Beszéd a lejátszás alatt: bekapcsolva. A lejátszó újra bemondja a számokat.")
        } else {
            tts.speak(
                "Beszéd a lejátszás alatt: kikapcsolva. A zene zavartalanul szól, " +
                    "a lejátszó nem mond semmit magától. A vezérlők és a hibajelzések továbbra is hallhatók."
            )
        }
    }

    private fun toggleMusicSpeak(which: String) {
        val (current, label) = when (which) {
            "skip" -> MusicPlayerPrefs.getSpeakOnSkipRaw(this) to "Számváltásnál beszéd"
            "stop" -> MusicPlayerPrefs.getSpeakOnStopRaw(this) to "Leállításnál beszéd"
            else -> MusicPlayerPrefs.getSpeakOnSeekRaw(this) to "Tekerésnél beszéd"
        }
        val next = !current
        when (which) {
            "skip" -> MusicPlayerPrefs.setSpeakOnSkip(this, next)
            "stop" -> MusicPlayerPrefs.setSpeakOnStop(this, next)
            else -> MusicPlayerPrefs.setSpeakOnSeek(this, next)
        }
        tts.speak("$label: ${if (next) "bekapcsolva" else "kikapcsolva"}.")
        // Ha a főkapcsoló ki van kapcsolva, ez a beállítás most nem hallatszik —
        // jobb szólni, mint hagyni a felhasználót értetlenkedni.
        if (next && !MusicPlayerPrefs.isSpeechEnabled(this)) {
            tts.speakAdd(
                "Megjegyzés: a Beszéd a lejátszás alatt kapcsoló ki van kapcsolva, " +
                    "ezért ez egyelőre nem hallatszik."
            )
        }
    }

    private fun cycleMusicEqProfile() {
        val eq = MusicEqualizer(this)
        val profiles = eq.availableProfiles()
        eq.release()
        if (profiles.size <= 1) {
            tts.speak("Ezen az eszközön nincs elérhető hangszínprofil.")
            return
        }
        val current = MusicPlayerPrefs.getEqProfile(this)
        val idx = profiles.indexOf(current).let { if (it < 0) 0 else it }
        val next = profiles[(idx + 1) % profiles.size]
        MusicPlayerPrefs.setEqProfile(this, next)
        tts.speak("Hangszínprofil: $next.")
    }

    // ==================== PODCAST ====================

    private fun startPodcastTopFlow() {
        activeFlow = AppFlow.PodcastLoading
        updateFlowDisplay()
        val country = PodcastStore.getCountry(this)
        tts.speak("Népszerű podcastok betöltése. ${PodcastStore.countryName(country)}.")
        Thread {
            val list = PodcastHelper.topPodcasts(country)
            postWhenAlive {
                if (activeFlow !is AppFlow.PodcastLoading) return@postWhenAlive
                if (list.isEmpty()) {
                    exitFlow("Nem sikerült betölteni a listát. Ellenőrizd az internetet.", error = true)
                    return@postWhenAlive
                }
                enterPodcastList(list, "Népszerű podcastok")
            }
        }.start()
    }

    private fun startPodcastSearchFlow() {
        ensureMicAndRun {
            activeFlow = AppFlow.PodcastSearchAwaitQuery
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Milyen podcastot keresel? Mondd a nevét vagy a témát.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val query = spoken.trim()
                    if (query.isBlank()) {
                        exitFlow("Nem értettem. Próbáld újra.")
                        return@listen
                    }
                    runPodcastSearch(query)
                },
                onError = { exitFlow("Podcast keresés megszakítva.") }
            )
        }
    }

    private fun runPodcastSearch(query: String) {
        activeFlow = AppFlow.PodcastLoading
        updateFlowDisplay()
        tts.speak("Keresés: $query.")
        val country = PodcastStore.getCountry(this).uppercase()
        Thread {
            val list = PodcastHelper.search(query, country)
            postWhenAlive {
                if (activeFlow !is AppFlow.PodcastLoading) return@postWhenAlive
                if (list.isEmpty()) {
                    exitFlow("Nincs találat erre: $query.", error = true)
                    return@postWhenAlive
                }
                enterPodcastList(list, "Találatok: $query")
            }
        }.start()
    }

    private fun startPodcastSubscriptionsFlow() {
        val subs = PodcastStore.getSubscriptions(this)
        if (subs.isEmpty()) {
            tts.speak("Még nincs feliratkozásod. A népszerű listából vagy keresésből tudsz feliratkozni.")
            return
        }
        enterPodcastList(subs, "Feliratkozásaim")
    }

    private fun startPodcastDownloadsFlow() {
        val episodes = PodcastDownloadHelper.downloadedEpisodes(this)
        if (episodes.isEmpty()) {
            tts.speak("Még nincs letöltött adásod.")
            return
        }
        // A letöltéseket ugyanazzal az epizód-böngészővel mutatjuk.
        val virtualPodcast = Podcast(id = "downloads", title = "Letöltéseim", author = "", feedUrl = "")
        activeFlow = AppFlow.PodcastEpisodeBrowse(virtualPodcast, episodes, 0)
        updateFlowDisplay()
        tts.speak("Letöltéseim. ${episodes.size} adás. ${episodes.first().speakPreview()}")
    }

    private fun startPodcastCountryFlow() {
        val current = PodcastStore.getCountry(this)
        val idx = PodcastStore.COUNTRIES.indexOfFirst { it.first == current }.coerceAtLeast(0)
        activeFlow = AppFlow.PodcastCountryBrowse(idx)
        updateFlowDisplay()
        tts.speak(
            "Ország választása. Jelenlegi: ${PodcastStore.countryName(current)}. " +
                "Söpörj fel-le, jobbra a kiválasztáshoz."
        )
    }

    private fun startPodcastOpmlImport() {
        tts.speak("Válaszd ki az OPML fájlt a feliratkozásaiddal.")
        podcastOpmlLauncher.launch(arrayOf("*/*"))
    }

    private fun startPodcastOpmlExport() {
        val subs = PodcastStore.getSubscriptions(this)
        if (subs.isEmpty()) {
            tts.speak("Nincs mit exportálni, még nincs feliratkozásod.")
            return
        }
        val file = PodcastOpml.export(this, subs)
        if (file != null) {
            tts.speak("${subs.size} feliratkozás mentve. A fájl neve: superdl feliratkozasok pont opml.")
        } else {
            tts.speak("A mentés nem sikerült.")
        }
    }

    private fun enterPodcastList(list: List<Podcast>, title: String) {
        activeFlow = AppFlow.PodcastListBrowse(list, 0, title)
        updateFlowDisplay()
        tts.speak("$title. ${list.size} műsor. ${list.first().speakPreview()}")
    }

    private fun navigatePodcastList(flow: AppFlow.PodcastListBrowse, delta: Int) {
        val next = (flow.index + delta + flow.podcasts.size) % flow.podcasts.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.podcasts[next].speakPreview())
    }

    /** Belépés egy podcastba: betölti az epizódokat (ha kell, előbb a feed URL-t). */
    private fun openPodcast(podcast: Podcast) {
        activeFlow = AppFlow.PodcastLoading
        updateFlowDisplay()
        tts.speak("${podcast.title}. Adások betöltése.")
        Thread {
            // A toplistából jövő podcastnak nincs feed URL-je, ezért lekérjük.
            val resolved = if (podcast.feedUrl.isBlank()) {
                PodcastHelper.lookup(podcast.id, PodcastStore.getCountry(this).uppercase()) ?: podcast
            } else {
                podcast
            }
            val episodes = if (resolved.feedUrl.isNotBlank()) {
                PodcastHelper.episodes(resolved.feedUrl, resolved.title)
            } else {
                emptyList()
            }
            postWhenAlive {
                if (activeFlow !is AppFlow.PodcastLoading) return@postWhenAlive
                if (episodes.isEmpty()) {
                    exitFlow("Ennek a műsornak nem sikerült betölteni az adásait.", error = true)
                    return@postWhenAlive
                }
                // Új adások jelzése a feliratkozásoknál.
                val seen = PodcastStore.getSeenCount(this, resolved.feedUrl)
                val newCount = (episodes.size - seen).coerceAtLeast(0)
                PodcastStore.setSeenCount(this, resolved.feedUrl, episodes.size)

                activeFlow = AppFlow.PodcastEpisodeBrowse(resolved, episodes, 0)
                updateFlowDisplay()
                val newPart = if (seen > 0 && newCount > 0) " $newCount új adás." else ""
                tts.speak("${resolved.title}. ${episodes.size} adás.$newPart ${episodes.first().speakPreview()}")
            }
        }.start()
    }

    private fun navigatePodcastEpisodes(flow: AppFlow.PodcastEpisodeBrowse, delta: Int) {
        val next = (flow.index + delta + flow.episodes.size) % flow.episodes.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.episodes[next].speakPreview())
    }

    /** Egy epizódra lépve a művelet-menü nyílik (lejátszás, letöltés, feliratkozás, leírás). */
    private fun enterPodcastEpisodeMenu(flow: AppFlow.PodcastEpisodeBrowse) {
        activeFlow = AppFlow.PodcastEpisodeMenu(flow.podcast, flow.episodes, flow.index, 0)
        updateFlowDisplay()
        val ep = flow.episodes[flow.index]
        tts.speak("${ep.title}. ${podcastEpisodeActions(flow.podcast).first()}")
    }

    private fun podcastEpisodeActions(podcast: Podcast): List<String> {
        val subscribed = if (podcast.feedUrl.isNotBlank() && PodcastStore.isSubscribed(this, podcast)) {
            "Leiratkozás"
        } else {
            "Feliratkozás"
        }
        return listOf("Lejátszás", "Letöltés offline hallgatáshoz", subscribed, "Leírás felolvasása")
    }

    private fun navigatePodcastEpisodeMenu(flow: AppFlow.PodcastEpisodeMenu, delta: Int) {
        val actions = podcastEpisodeActions(flow.podcast)
        val next = (flow.actionIndex + delta + actions.size) % actions.size
        activeFlow = flow.copy(actionIndex = next)
        updateFlowDisplay()
        tts.speak(actions[next])
    }

    private fun onPodcastEpisodeMenuActivate(flow: AppFlow.PodcastEpisodeMenu) {
        val ep = flow.episodes[flow.episodeIndex]
        when (flow.actionIndex) {
            0 -> {
                PodcastEpisodeHolder.current = ep
                startActivity(Intent(this, PodcastPlayerActivity::class.java))
                exitFlow("Lejátszás: ${ep.title}")
            }
            1 -> downloadPodcastEpisode(ep)
            2 -> {
                if (flow.podcast.feedUrl.isBlank()) {
                    tts.speak("Ehhez a listához nem lehet feliratkozni.")
                    return
                }
                val subscribed = PodcastStore.toggleSubscription(this, flow.podcast)
                tts.speak(
                    if (subscribed) "Feliratkozva: ${flow.podcast.title}."
                    else "Leiratkozva: ${flow.podcast.title}."
                )
            }
            3 -> {
                val desc = ep.description.trim()
                if (desc.isBlank()) tts.speak("Ehhez az adáshoz nincs leírás.")
                else tts.speak(desc.take(900))
            }
        }
    }

    private fun downloadPodcastEpisode(ep: PodcastEpisode) {
        if (PodcastDownloadHelper.isDownloaded(this, ep)) {
            tts.speak("Ez az adás már le van töltve.")
            return
        }
        tts.speak("Letöltés indul: ${ep.title}. Ez percekbe telhet, a háttérben fut.")
        Thread {
            val ok = PodcastDownloadHelper.download(this, ep)
            postWhenAlive {
                if (ok) {
                    tts.speak("Letöltés kész: ${ep.title}. Megtalálod a Letöltéseim alatt.")
                } else {
                    tts.speak("A letöltés nem sikerült: ${ep.title}.")
                }
            }
        }.start()
    }

    private fun navigatePodcastCountry(flow: AppFlow.PodcastCountryBrowse, delta: Int) {
        val countries = PodcastStore.COUNTRIES
        val next = (flow.index + delta + countries.size) % countries.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(countries[next].second)
    }

    private fun onPodcastCountryActivate(flow: AppFlow.PodcastCountryBrowse) {
        val (code, name) = PodcastStore.COUNTRIES[flow.index]
        PodcastStore.setCountry(this, code)
        exitFlow("Ország beállítva: $name.", success = true)
    }

    private fun startMusicLibraryFlow() {
        val tracks = MusicHelper.getTracks(this)
        if (tracks.isEmpty()) {
            tts.speak("Nem találtam zenét a telefonon.")
            return
        }
        activeFlow = AppFlow.MusicBrowse(tracks, 0)
        updateFlowDisplay()
        tts.speak("${tracks.size} zeneszám. Söpörj fel-le választás, jobbra lejátszás, balra vissza.")
        tts.speakAdd(tracks.first().speakPreview())
    }

    private fun navigateMusicList(flow: AppFlow.MusicBrowse, delta: Int) {
        val next = (flow.index + delta + flow.tracks.size) % flow.tracks.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.tracks[next].speakPreview())
    }

    private fun playMusicFromList(tracks: List<MusicTrack>, index: Int) {
        MusicPlaylistHolder.tracks = tracks
        val intent = Intent(this, MusicPlayerActivity::class.java).apply {
            putExtra(MusicPlayerActivity.EXTRA_INDEX, index)
        }
        startActivity(intent)
        exitFlow("Lejátszás: ${tracks[index].title}.")
    }

    /**
     * Az utoljára hallgatott szám folytatása a mentett pozíciótól — egyetlen
     * menüponttal, keresgélés nélkül. Megkeresi a mentett szám azonosítóját a
     * zenetárban, és onnan indítja; a lejátszó a mentett pozíciótól folytatja.
     */
    private fun resumeLastMusic() {
        val lastId = MusicPlayerPrefs.getLastTrackId(this)
        if (lastId < 0) {
            tts.speak("Nincs mentett zene, amit folytathatnék. Előbb hallgass valamit.")
            return
        }
        val tracks = MusicHelper.getTracks(this)
        val index = tracks.indexOfFirst { it.id == lastId }
        if (index < 0) {
            tts.speak("A legutóbbi szám már nem található a telefonon.")
            MusicPlayerPrefs.clearPosition(this)
            return
        }
        // A lejátszó a setOnPreparedListener-ben a mentett pozíciótól folytatja.
        playMusicFromList(tracks, index)
    }

    // ==================== INTERNETES RÁDIÓ ====================

    /** Megnyitja a rádió-lejátszót a megadott állomás-listával. */
    private fun openRadioPlayer(stations: List<RadioStation>, index: Int = 0) {
        if (stations.isEmpty()) {
            tts.speak("Nincs lejátszható állomás.")
            return
        }
        RadioPlaylistHolder.stations = stations
        RadioPlaylistHolder.startIndex = index.coerceIn(0, stations.size - 1)
        startActivity(Intent(this, RadioPlayerActivity::class.java))
    }

    private fun startRadioHungarianFlow() {
        tts.speak("Magyar rádióállomások betöltése.")
        Thread {
            val online = RadioBrowserClient.hungarianStations()
            postWhenAlive {
                if (online.isNotEmpty()) {
                    openRadioBrowse(online)
                } else {
                    // Nincs net vagy nem elérhető az API → beépített állomások.
                    tts.speak("Az internetes lista nem elérhető, a beépített állomások jönnek.")
                    openRadioBrowse(RadioStore.BUILTIN)
                }
            }
        }.start()
    }

    /**
     * Rádióállomás-böngésző: a találatokat NEM indítja rögtön, hanem listázza.
     * Fel-le lépkedés, jobbra söprés indítja a kiválasztott állomást. (A
     * MusicBrowse mintájára.)
     */
    private fun openRadioBrowse(stations: List<RadioStation>) {
        if (stations.isEmpty()) {
            tts.speak("Nincs megjeleníthető állomás.")
            return
        }
        activeFlow = AppFlow.RadioBrowse(stations, 0)
        updateFlowDisplay()
        tts.speak("${stations.size} állomás. Söpörj fel-le a válogatáshoz, jobbra a kiválasztott indításához, balra vissza.")
        tts.speakAdd(stations.first().name)
    }

    private fun navigateRadioList(flow: AppFlow.RadioBrowse, delta: Int) {
        val next = (flow.index + delta + flow.stations.size) % flow.stations.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.stations[next].name)
    }

    private fun startRadioFavoritesFlow() {
        val favorites = RadioStore.getStations(this)
        if (favorites.isEmpty()) {
            tts.speak("Még nincs mentett kedvenc állomásod. A rádió lejátszóban a Mentés ponttal tehetsz hozzá.")
            return
        }
        openRadioBrowse(favorites)
    }

    private fun startRadioSearchFlow() {
        ensureMicAndRun {
            voiceInput.listen(
                prompt = "Milyen rádiót keresel? Mondd a nevét.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val query = spoken.trim()
                    if (query.isBlank()) {
                        tts.speak("Nem értettem. Próbáld újra.")
                        return@listen
                    }
                    tts.speak("Keresés: $query.")
                    Thread {
                        val list = RadioBrowserClient.searchByName(query)
                        postWhenAlive {
                            if (list.isEmpty()) {
                                tts.speak("Nincs találat erre: $query.")
                            } else {
                                openRadioBrowse(list)
                            }
                        }
                    }.start()
                },
                onError = { tts.speak("Rádió keresés megszakítva.") }
            )
        }
    }

    private fun startRadioRecordingsFlow() {
        val dir = RadioRecorder.dir(this)
        val files = dir.listFiles()?.filter { it.isFile }?.sortedByDescending { it.lastModified() } ?: emptyList()
        if (files.isEmpty()) {
            tts.speak("Még nincs rádiófelvételed. A rádió lejátszóban a Felvétel ponttal rögzíthetsz.")
            return
        }
        val names = files.take(10).joinToString(". ") { it.name }
        tts.speak("${files.size} felvételed van. A legutóbbiak: $names. A fájlkezelőben találod meg őket.")
    }

    private fun startRadioScheduleFlow() {
        tts.speak("Az időzített felvétel hamarosan érkezik. Ezzel majd beállíthatod, hogy egy adott állomást adott időben automatikusan felvegyen.")
    }

    // ==================== OFFLINE SZÁMBILLENTYŰZET ====================

    private fun speakNumericInputIntro(purpose: NumberPadPurpose) {
        val subject = when (purpose) {
            NumberPadPurpose.PHONE -> "Telefonszám megadása"
            NumberPadPurpose.SOS -> "S.O.S. szám megadása"
            NumberPadPurpose.CONTACT -> "Névjegy telefonszáma"
            NumberPadPurpose.CALCULATOR -> "Számológép"
            NumberPadPurpose.TIME -> "Idő megadása"
            NumberPadPurpose.AMOUNT -> "Szám megadása"
            NumberPadPurpose.DATE -> "Dátum megadása"
            NumberPadPurpose.PRICE -> "Ár megadása"
            NumberPadPurpose.PIN -> "PIN megadása"
        }
        // Ha van használható szám a vágólapon (pl. Hívásnapló → Szám másolása),
        // azt felajánljuk harmadik lehetőségként – így értelme lesz a másolásnak.
        val clip = clipboardNumberOrNull(purpose)
        val clipPart = if (clip != null) {
            " Vágólapon: ${ContactHelper.maskPhone(clip)}. Beillesztés: söprés fel."
        } else {
            ""
        }
        tts.speak(
            "$subject. Először diktálás: söprés jobbra. Offline számbillentyűzet: söprés le.$clipPart Mégse: söprés balra."
        )
    }

    /**
     * A vágólap tartalma, ha az számnak tűnik és illik a célhoz.
     * Így a Hívásnapló "Szám másolása" funkciója végre használható:
     * kimásolod, aztán bárhol beilleszted.
     */
    private fun clipboardNumberOrNull(purpose: NumberPadPurpose): String? {
        // Csak ott ajánljuk, ahol számot várunk.
        if (purpose !in setOf(
                NumberPadPurpose.PHONE,
                NumberPadPurpose.CONTACT,
                NumberPadPurpose.SOS
            )
        ) {
            return null
        }
        return try {
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            val text = clipboard.primaryClip
                ?.takeIf { it.itemCount > 0 }
                ?.getItemAt(0)
                ?.coerceToText(this)
                ?.toString()
                ?.trim()
                ?: return null
            // Csak a számjegyeket és a plusz jelet tartjuk meg.
            val cleaned = text.filter { it.isDigit() || it == '+' }
            if (cleaned.count { it.isDigit() } in 6..15) cleaned else null
        } catch (_: Exception) {
            null
        }
    }

    /**
     * Fel-söprés a szám-bekérésnél: ha van használható szám a vágólapon,
     * beillesztjük; ha nincs, megismételjük az útmutatót.
     */
    private fun pasteOrRepeatNumericIntro(flow: AppFlow.NumericDictationAwait) {
        val clip = clipboardNumberOrNull(flow.purpose)
        if (clip == null) {
            speakNumericInputIntro(flow.purpose)
            return
        }
        voiceInput.cancel()
        tts.speak("Beillesztve: ${ContactHelper.maskPhone(clip)}")
        // Ugyanaz az út, mint a diktált számnál – a számjegyeket egyesével
        // adjuk át, hogy a meglévő feldolgozó helyesen értelmezze.
        handleNumericDictationResult(flow, clip)
    }

    private fun enterNumericDictationAwait(flow: AppFlow.NumericDictationAwait) {
        activeFlow = flow
        updateFlowDisplay()
        speakNumericInputIntro(flow.purpose)
    }

    private fun openNumberPadFromAwait(await: AppFlow.NumericDictationAwait) {
        voiceInput.cancel()
        val items = NumberPadHelper.itemsFor(await.purpose)
        activeFlow = AppFlow.NumberPadInput(
            purpose = await.purpose,
            items = items,
            index = 0,
            buffer = "",
            sosSlot = await.sosSlot,
            alarmDraft = await.alarmDraft,
            timerUnit = await.timerUnit,
            editTimerId = await.editTimerId,
            calendarTitle = await.calendarTitle,
            calendarDayStartMs = await.calendarDayStartMs,
            calendarAwaitEnd = await.calendarAwaitEnd,
            calendarStartHour = await.calendarStartHour,
            calendarStartMinute = await.calendarStartMinute,
            shoppingListName = await.shoppingListName,
            shoppingItemName = await.shoppingItemName,
            shoppingEditItemId = await.shoppingEditItemId,
            shoppingEditPriceOnly = await.shoppingEditPriceOnly
        )
        updateFlowDisplay()
        val padIntro = when (await.purpose) {
            NumberPadPurpose.TIME -> when {
                await.alarmDraft ->
                    "Ébresztő idő bevitele. Négy számjegy: óra, óra, perc, perc."
                await.calendarTitle != null && await.calendarAwaitEnd ->
                    "Befejezési idő bevitele. Négy számjegy: óra, óra, perc, perc."
                await.calendarTitle != null ->
                    "Kezdési idő bevitele. Négy számjegy: óra, óra, perc, perc."
                else ->
                    "Időpont bevitele. Négy számjegy: óra, óra, perc, perc."
            }
            NumberPadPurpose.AMOUNT ->
                "Időtartam bevitele ${await.timerUnit?.label?.lowercase() ?: ""}ben."
            NumberPadPurpose.DATE ->
                "Dátum bevitele. Nyolc számjegy: év, év, év, év, hónap, hónap, nap, nap."
            NumberPadPurpose.PRICE -> "Ár bevitele forintban."
            NumberPadPurpose.PHONE ->
                "Offline számbillentyűzet. Fel-le választás, jobbra beírás, balra törlés, Kész a tárcsázáshoz."
            NumberPadPurpose.SOS ->
                "S.O.S. szám ${await.sosSlot} offline bevitele. Fel-le választás, jobbra beírás, balra törlés, Kész a mentéshez."
            NumberPadPurpose.CONTACT ->
                "Telefonszám offline bevitele. Fel-le választás, jobbra beírás, balra törlés, Kész a továbblépéshez."
            NumberPadPurpose.CALCULATOR ->
                "Offline számológép. Fel-le választás, jobbra beírás, balra törlés. Diktálás vagy Kész alul."
            NumberPadPurpose.PIN -> ""
        }
        if (padIntro.isNotBlank()) {
            tts.speak("$padIntro Fel-le választás, jobbra beírás, balra törlés.")
            tts.speakAdd(items.first().speakLabel())
        }
    }

    private fun startNumericDictation(await: AppFlow.NumericDictationAwait) {
        if (await.purpose == NumberPadPurpose.CALCULATOR) {
            activeFlow = AppFlow.CalculatorVoiceInput
            updateFlowDisplay()
            listenForCalculatorInput()
            return
        }
        ensureMicAndRun {
            val prompt = when (await.purpose) {
                NumberPadPurpose.PHONE -> "Mondd a telefonszámot."
                NumberPadPurpose.SOS -> "Mondd az S.O.S. számot."
                NumberPadPurpose.CONTACT -> "Mondd a telefonszámot."
                NumberPadPurpose.TIME -> when {
                    await.alarmDraft -> "Mondd az ébresztő idejét. Például: hét harminc."
                    await.calendarTitle != null && await.calendarAwaitEnd ->
                        "Mondd a befejezési időt."
                    await.calendarTitle != null -> "Mondd a kezdési időt."
                    else -> "Mondd az időpontot. Például: nyolc óra tizenöt."
                }
                NumberPadPurpose.AMOUNT ->
                    "Mondd az időtartamot ${await.timerUnit?.label?.lowercase() ?: ""}ben."
                NumberPadPurpose.DATE -> "Mondd a dátumot. Például: március tizenötödike."
                NumberPadPurpose.PRICE -> "Mondd az árat forintban."
                NumberPadPurpose.PIN -> "Mondd a PIN kódot."
                NumberPadPurpose.CALCULATOR -> "Mondd a számolást."
            }
            voiceInput.listen(
                prompt = prompt,
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken -> handleNumericDictationResult(await, spoken) },
                onError = {
                    tts.speak("Nem értettem. Söpörj jobbra az újrapróbáláshoz, söprés le az offline bevitelhez.")
                    enterNumericDictationAwait(await)
                }
            )
        }
    }

    private fun handleNumericDictationResult(await: AppFlow.NumericDictationAwait, spoken: String) {
        when (await.purpose) {
            NumberPadPurpose.PHONE -> {
                val phone = NumberPadHelper.parseSpokenPhone(spoken)
                if (phone.isBlank()) {
                    tts.speak("Nem értettem a telefonszámot. Próbáld újra.")
                    enterNumericDictationAwait(await)
                    return
                }
                enterCallConfirm(ContactMatch("dial", "Tárcsázás", phone))
            }
            NumberPadPurpose.SOS -> {
                val phone = NumberPadHelper.parseSpokenPhone(spoken)
                if (phone.isBlank()) {
                    tts.speak("Nem értettem az S.O.S. számot. Próbáld újra.")
                    enterNumericDictationAwait(await)
                    return
                }
                val slot = await.sosSlot ?: return
                saveSosNumberFromPad(slot, phone)
            }
            NumberPadPurpose.CONTACT -> {
                val phone = NumberPadHelper.parseSpokenPhone(spoken)
                if (phone.isBlank()) {
                    tts.speak("Nem értettem a telefonszámot. Próbáld újra.")
                    enterNumericDictationAwait(await)
                    return
                }
                proceedContactCreateName(phone)
            }
            NumberPadPurpose.TIME -> {
                val time = VoiceTimeParser.parse(spoken)
                if (time == null) {
                    tts.speak("Nem értettem az időt. Próbáld újra, vagy söprés le az offline bevitelhez.")
                    enterNumericDictationAwait(await)
                    return
                }
                applyParsedTime(await, time.first, time.second)
            }
            NumberPadPurpose.AMOUNT -> {
                val unit = await.timerUnit ?: return
                onTimerAmountSpoken(unit, spoken, await.editTimerId)
            }
            NumberPadPurpose.DATE -> {
                val title = await.calendarTitle ?: return
                val dayStart = VoiceDateParser.parseDayStartMs(spoken)
                if (dayStart == null) {
                    tts.speak("Nem értettem a dátumot. Próbáld újra, vagy söprés le az offline bevitelhez.")
                    enterNumericDictationAwait(await)
                    return
                }
                enterNumericDictationAwait(
                    AppFlow.NumericDictationAwait(
                        purpose = NumberPadPurpose.TIME,
                        calendarTitle = title,
                        calendarDayStartMs = dayStart
                    )
                )
            }
            NumberPadPurpose.PRICE -> {
                val amount = VoiceDurationParser.parseAmount(spoken)
                if (amount == null) {
                    tts.speak("Nem értettem az árat. Próbáld újra, vagy söprés le az offline bevitelhez.")
                    enterNumericDictationAwait(await)
                    return
                }
                applyShoppingPrice(await, amount)
            }
            NumberPadPurpose.CALCULATOR -> listenForCalculatorInput()
            NumberPadPurpose.PIN -> Unit
        }
    }

    private fun applyParsedTime(await: AppFlow.NumericDictationAwait, hour: Int, minute: Int) {
        when {
            await.alarmDraft -> {
                activeFlow = AppFlow.AlarmAwaitLabel(hour, minute)
                updateFlowDisplay()
                listenForAlarmLabel(hour, minute)
            }
            await.calendarTitle != null && await.calendarDayStartMs != null -> {
                if (await.calendarAwaitEnd) {
                    val startHour = await.calendarStartHour ?: return
                    val startMinute = await.calendarStartMinute ?: return
                    val times = CalendarHelper.buildEventTimes(
                        await.calendarDayStartMs,
                        startHour,
                        startMinute,
                        hour,
                        minute
                    )
                    enterCalendarRecurrenceBrowse(await.calendarTitle, times.first, times.second)
                } else {
                    listenForCalendarEndTime(
                        await.calendarTitle,
                        await.calendarDayStartMs,
                        hour,
                        minute
                    )
                }
            }
            else -> onMedicationTimeEntered(hour, minute)
        }
    }

    private fun exitNumericDictationAwait(flow: AppFlow.NumericDictationAwait) {
        voiceInput.cancel()
        val message = when (flow.purpose) {
            NumberPadPurpose.PHONE -> "Tárcsázás megszakítva."
            NumberPadPurpose.SOS -> "S.O.S. szám beállítás megszakítva."
            NumberPadPurpose.CONTACT -> "Névjegy létrehozás megszakítva."
            NumberPadPurpose.CALCULATOR -> "Számológép bezárva."
            NumberPadPurpose.TIME -> when {
                flow.alarmDraft -> "Ébresztő beállítás megszakítva."
                flow.calendarTitle != null -> "Naptár bejegyzés megszakítva."
                medicationDraftName != null -> "Gyógyszer rögzítés megszakítva."
                else -> "Időbevitel megszakítva."
            }
            NumberPadPurpose.AMOUNT -> "Időzítő beállítás megszakítva."
            NumberPadPurpose.DATE -> "Naptár bejegyzés megszakítva."
            NumberPadPurpose.PRICE -> "Bevásárlólista megszakítva."
            NumberPadPurpose.PIN -> "PIN bevitel megszakítva."
        }
        if (flow.purpose == NumberPadPurpose.TIME && medicationDraftName != null && flow.calendarTitle == null && !flow.alarmDraft) {
            medicationDraftName = null
        }
        exitFlow(message)
    }

    private fun applyShoppingPrice(await: AppFlow.NumericDictationAwait, amount: Int) {
        val listName = await.shoppingListName ?: return
        val itemName = await.shoppingItemName ?: return
        if (await.shoppingEditPriceOnly && await.shoppingEditItemId != null) {
            ShoppingListStore.updateItemPrice(this, listName, await.shoppingEditItemId, amount)
            exitFlow("Ár frissítve: $amount forint.")
            return
        }
        ShoppingListStore.addItem(this, listName, itemName, amount)
        tts.speak("$itemName hozzáadva, $amount forint.")
        listenForShoppingListMore(listName)
    }

    private fun startNumberPadFlow(purpose: NumberPadPurpose, sosSlot: Int? = null) {
        val items = NumberPadHelper.itemsFor(purpose)
        activeFlow = AppFlow.NumberPadInput(purpose, items, 0, "", sosSlot)
        updateFlowDisplay()
        val intro = when (purpose) {
            NumberPadPurpose.PHONE ->
                "Offline számbillentyűzet. Egyestől nulláig, alul a Kész gomb. " +
                    "Söpörj fel-le választás, jobbra beírás, balra egy szám törlése."
            NumberPadPurpose.SOS ->
                "S.O.S. szám $sosSlot offline bevitele. Fel-le választás, jobbra beírás, balra törlés, Kész a mentéshez."
            NumberPadPurpose.CALCULATOR ->
                "Offline számológép. Számok és műveletek fel-le választással, jobbra beírás, balra törlés. " +
                    "Diktálás vagy Kész alul."
            NumberPadPurpose.CONTACT ->
                "Új névjegy telefonszáma. Egyestől nulláig, alul a Kész gomb. " +
                    "Söpörj fel-le választás, jobbra beírás, balra egy szám törlése."
            NumberPadPurpose.PIN -> ""
            NumberPadPurpose.TIME -> ""
            NumberPadPurpose.AMOUNT -> ""
            NumberPadPurpose.DATE -> ""
            NumberPadPurpose.PRICE -> ""
        }
        if (intro.isNotBlank()) {
            tts.speak(intro)
            tts.speakAdd(items.first().speakLabel())
        }
    }

    private fun startPinPadFlow(mode: PinPadMode, setupPin: String? = null) {
        val items = NumberPadHelper.itemsFor(NumberPadPurpose.PIN)
        activeFlow = AppFlow.NumberPadInput(
            purpose = NumberPadPurpose.PIN,
            items = items,
            index = 0,
            buffer = "",
            pinMode = mode,
            setupPin = setupPin
        )
        updateFlowDisplay()
        val intro = when (mode) {
            PinPadMode.UNLOCK ->
                "Super DL zárolva. Add meg a PIN kódot a feloldáshoz. " +
                    "Egyestől nulláig, alul a Törlés és Megerősítés gomb. " +
                    "Fel-le választás, jobbra beírás, balra egy számjegy törlése."
            PinPadMode.SETUP ->
                "Új PIN kód beállítása. Legalább ${LockPinStore.MIN_PIN_LENGTH} számjegy. " +
                    "Fel-le választás, jobbra beírás, balra törlés, Megerősítés a továbblépéshez."
            PinPadMode.CONFIRM ->
                "Erősítsd meg az új PIN kódot. Megerősítés a mentéshez."
        }
        tts.speak(intro)
        tts.speakAdd(items.first().speakLabel())
    }

    private fun showLockScreen() {
        voiceInput.cancel()
        tts.stop()
        LockSession.lockScreenVisible = true
        startPinPadFlow(PinPadMode.UNLOCK)
    }

    private fun startLockPinSetupFlow() {
        startPinPadFlow(PinPadMode.SETUP)
    }

    private fun toggleLockPin() {
        if (!LockPinStore.hasPinSet(this)) {
            tts.speak("Előbb állíts be PIN kódot.")
            startLockPinSetupFlow()
            return
        }
        val wasEnabled = LockPinStore.isEnabled(this)
        tts.speak(ToggleAnnouncement.speakBinaryToggle("PIN zárolás", wasEnabled))
        val enabling = !wasEnabled
        LockPinStore.setEnabled(this, enabling)
        if (enabling) {
            LockSession.lock()
            showLockScreen()
            tts.speakAdd(ToggleAnnouncement.speakAfterToggle("PIN zárolás", true))
        } else {
            LockSession.unlock()
            LockSession.lockScreenVisible = false
            tts.speak(ToggleAnnouncement.speakAfterToggle("PIN zárolás", false))
        }
    }

    private fun toggleKeyguardPinAssist() {
        val wasEnabled = KeyguardPinSettings.isFeatureEnabled(this)
        tts.speak(ToggleAnnouncement.speakBinaryToggle("Rendszer PIN segéd", wasEnabled))
        val enabling = !wasEnabled
        KeyguardPinSettings.setFeatureEnabled(this, enabling)
        tts.speak(ToggleAnnouncement.speakAfterToggle("Rendszer PIN segéd", enabling))
        if (enabling && !KeyguardPinSettings.isServiceEnabled(this)) {
            tts.speakAdd(
                "A rendszer PIN feloldáshoz engedélyezd a Super DL rendszer PIN segéd szolgáltatást " +
                    "a Kisegítő lehetőségek menüben."
            )
        }
    }

    private fun setupKeyguardPinAssist() {
        KeyguardPinSettings.setFeatureEnabled(this, true)
        if (KeyguardPinSettings.isServiceEnabled(this)) {
            tts.speak("A rendszer PIN segéd már engedélyezve van.")
            return
        }
        tts.speakThen(
            "Megnyitom a Kisegítő lehetőségek menüt. " +
                "Kapcsold be a Super DL rendszer PIN segéd szolgáltatást."
        ) {
            KeyguardPinSettings.openAccessibilitySettings(this)
        }
    }

    private fun navigateNumberPad(flow: AppFlow.NumberPadInput, delta: Int) {
        val next = (flow.index + delta + flow.items.size) % flow.items.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.items[next].speakLabel())
    }

    private fun onNumberPadActivate(flow: AppFlow.NumberPadInput) {
        val item = flow.items[flow.index]
        if (flow.purpose == NumberPadPurpose.PIN) {
            onPinPadActivate(flow, item)
            return
        }
        if (flow.purpose == NumberPadPurpose.TIME && item.key == NumberPadKey.DIGIT) {
            val updated = NumberPadHelper.appendTimeDigit(flow.buffer, item.value) ?: run {
                tts.speak("Négy számjegy elegendő. Nyomd meg a Kész gombot.")
                return
            }
            activeFlow = flow.copy(buffer = updated)
            updateFlowDisplay()
            tts.speak("${item.speakLabel()} beírva. ${NumberPadHelper.speakTimeBuffer(updated)}")
            if (updated.length == 4) {
                submitNumberPad(activeFlow as AppFlow.NumberPadInput)
            }
            return
        }
        if (flow.purpose == NumberPadPurpose.AMOUNT && item.key == NumberPadKey.DIGIT) {
            val updated = NumberPadHelper.appendAmountDigit(flow.buffer, item.value) ?: run {
                tts.speak("Négy számjegy elegendő. Nyomd meg a Kész gombot.")
                return
            }
            activeFlow = flow.copy(buffer = updated)
            updateFlowDisplay()
            tts.speak("${item.speakLabel()} beírva. ${NumberPadHelper.speakAmountBuffer(updated)}")
            return
        }
        if (flow.purpose == NumberPadPurpose.DATE && item.key == NumberPadKey.DIGIT) {
            val updated = NumberPadHelper.appendDateDigit(flow.buffer, item.value) ?: run {
                tts.speak("Nyolc számjegy elegendő. Nyomd meg a Kész gombot.")
                return
            }
            activeFlow = flow.copy(buffer = updated)
            updateFlowDisplay()
            tts.speak("${item.speakLabel()} beírva. ${NumberPadHelper.speakDateBuffer(updated)}")
            if (updated.length == 8) {
                submitNumberPad(activeFlow as AppFlow.NumberPadInput)
            }
            return
        }
        if (flow.purpose == NumberPadPurpose.PRICE && item.key == NumberPadKey.DIGIT) {
            val updated = NumberPadHelper.appendPriceDigit(flow.buffer, item.value) ?: run {
                tts.speak("Maximum hét számjegy. Nyomd meg a Kész gombot.")
                return
            }
            activeFlow = flow.copy(buffer = updated)
            updateFlowDisplay()
            tts.speak("${item.speakLabel()} beírva. ${NumberPadHelper.speakPriceBuffer(updated)}")
            return
        }
        when (item.key) {
            NumberPadKey.DIGIT, NumberPadKey.OPERATOR -> {
                val updated = NumberPadHelper.append(flow.buffer, item) ?: return
                activeFlow = flow.copy(buffer = updated)
                updateFlowDisplay()
                tts.speak("${item.speakLabel()} beírva. ${NumberPadHelper.speakBuffer(updated)}")
            }
            NumberPadKey.VOICE -> startCalculatorVoiceInput()
            NumberPadKey.DONE -> submitNumberPad(flow)
            else -> Unit
        }
    }

    private fun onPinPadActivate(flow: AppFlow.NumberPadInput, item: com.superdl.launcher.input.NumberPadItem) {
        when (item.key) {
            NumberPadKey.DIGIT -> {
                if (flow.buffer.length >= LockPinStore.MAX_PIN_LENGTH) {
                    feedbackError()
                    tts.speak("Maximum ${LockPinStore.MAX_PIN_LENGTH} számjegy.")
                    return
                }
                val updated = flow.buffer + item.value
                activeFlow = flow.copy(buffer = updated)
                updateFlowDisplay()
                sounds.play(SoundType.MENU_NAV)
                vibrate(25)
                tts.speak(NumberPadHelper.speakPinDigitEntered(updated))
            }
            NumberPadKey.CLEAR -> {
                activeFlow = flow.copy(buffer = NumberPadHelper.clear())
                updateFlowDisplay()
                sounds.play(SoundType.ACTION_OK)
                tts.speak("Teljes bevitel törölve.")
            }
            NumberPadKey.CONFIRM -> submitPinPad(flow)
            else -> Unit
        }
    }

    private fun onNumberPadBackspace(flow: AppFlow.NumberPadInput) {
        if (flow.purpose == NumberPadPurpose.PIN) {
            onPinPadBackspace(flow)
            return
        }
        if (flow.buffer.isEmpty()) {
            when (flow.purpose) {
                NumberPadPurpose.PRICE -> {
                    val listName = flow.shoppingListName
                    if (listName == null) {
                        exitFlow("Bevásárlólista megszakítva.")
                        return
                    }
                    if (flow.shoppingEditPriceOnly && flow.shoppingEditItemId != null) {
                        ShoppingListStore.updateItemPrice(this, listName, flow.shoppingEditItemId, null)
                        val items = ShoppingListStore.getItems(this, listName)
                        val index = items.indexOfFirst { it.id == flow.shoppingEditItemId }.coerceAtLeast(0)
                        returnToShoppingBrowse(listName, items, index)
                        tts.speak("Ár törölve.")
                        return
                    }
                    val itemName = flow.shoppingItemName
                    if (itemName != null) {
                        val added = ShoppingListStore.addItem(this, listName, itemName, null)
                        if (added == null) {
                            tts.speak("Nem sikerült hozzáadni.")
                            return
                        }
                        tts.speak("$itemName hozzáadva ár nélkül.")
                        listenForShoppingListMore(listName)
                    } else {
                        exitFlow("Bevásárlólista megszakítva.")
                    }
                    return
                }
                else -> {
                    val message = when (flow.purpose) {
                        NumberPadPurpose.PHONE -> "Tárcsázás megszakítva."
                        NumberPadPurpose.SOS -> "S.O.S. szám beállítás megszakítva."
                        NumberPadPurpose.CONTACT -> "Névjegy létrehozás megszakítva."
                        NumberPadPurpose.CALCULATOR -> "Számológép bezárva."
                        NumberPadPurpose.PIN -> "PIN bevitel megszakítva."
                        NumberPadPurpose.TIME -> when {
                            flow.calendarAwaitEnd && flow.calendarTitle != null && flow.calendarDayStartMs != null -> {
                                val startHour = flow.calendarStartHour
                                val startMinute = flow.calendarStartMinute
                                if (startHour != null && startMinute != null) {
                                    applyCalendarDefaultDuration(
                                        flow.calendarTitle,
                                        flow.calendarDayStartMs,
                                        startHour,
                                        startMinute
                                    )
                                }
                                return
                            }
                            flow.alarmDraft -> "Ébresztő beállítás megszakítva."
                            flow.calendarTitle != null -> "Naptár bejegyzés megszakítva."
                            else -> {
                                medicationDraftName = null
                                "Gyógyszer rögzítés megszakítva."
                            }
                        }
                        NumberPadPurpose.AMOUNT -> "Időzítő beállítás megszakítva."
                        NumberPadPurpose.DATE -> "Naptár bejegyzés megszakítva."
                        NumberPadPurpose.PRICE -> "Bevásárlólista megszakítva."
                    }
                    if (flow.purpose == NumberPadPurpose.TIME && medicationDraftName != null && flow.calendarTitle == null && !flow.alarmDraft) {
                        medicationDraftName = null
                    }
                    exitFlow(message)
                    return
                }
            }
        }
        val updated = NumberPadHelper.backspace(flow.buffer)
        activeFlow = flow.copy(buffer = updated)
        updateFlowDisplay()
        val spoken = when (flow.purpose) {
            NumberPadPurpose.TIME -> NumberPadHelper.speakTimeBuffer(updated)
            NumberPadPurpose.AMOUNT -> NumberPadHelper.speakAmountBuffer(updated)
            NumberPadPurpose.DATE -> NumberPadHelper.speakDateBuffer(updated)
            NumberPadPurpose.PRICE -> NumberPadHelper.speakPriceBuffer(updated)
            else -> NumberPadHelper.speakBuffer(updated)
        }
        tts.speak("Törölve. $spoken")
    }

    private fun onPinPadBackspace(flow: AppFlow.NumberPadInput) {
        if (flow.buffer.isEmpty()) {
            if (flow.pinMode == PinPadMode.UNLOCK) {
                feedbackError()
                tts.speak("Add meg a PIN kódot a feloldáshoz.")
                return
            }
            LockSession.lockScreenVisible = false
            exitFlow("PIN beállítás megszakítva.")
            return
        }
        val updated = NumberPadHelper.backspace(flow.buffer)
        activeFlow = flow.copy(buffer = updated)
        updateFlowDisplay()
        sounds.play(SoundType.SWIPE_LEFT)
        tts.speak(NumberPadHelper.speakPinBackspace(updated))
    }

    private fun submitPinPad(flow: AppFlow.NumberPadInput) {
        val pin = flow.buffer
        if (pin.length < LockPinStore.MIN_PIN_LENGTH) {
            feedbackError()
            tts.speak("Legalább ${LockPinStore.MIN_PIN_LENGTH} számjegy szükséges.")
            return
        }
        when (flow.pinMode) {
            PinPadMode.UNLOCK -> {
                if (LockPinStore.verifyPin(this, pin)) {
                    LockSession.unlock()
                    LockSession.lockScreenVisible = false
                    activeFlow = AppFlow.Menu
                    updateDisplay()
                    feedbackSuccess()
                    tts.speak("PIN helyes. Super DL feloldva.")
                } else {
                    activeFlow = flow.copy(buffer = "", index = 0)
                    updateFlowDisplay()
                    feedbackError()
                    tts.speak("Helytelen PIN. Próbáld újra.")
                    tts.speakAdd(flow.items.first().speakLabel())
                }
            }
            PinPadMode.SETUP -> startPinPadFlow(PinPadMode.CONFIRM, setupPin = pin)
            PinPadMode.CONFIRM -> {
                val expected = flow.setupPin
                if (expected == null || pin != expected) {
                    feedbackError()
                    tts.speak("A két PIN nem egyezik. Kezdd újra.")
                    startLockPinSetupFlow()
                    return
                }
                LockPinStore.savePin(this, pin)
                LockPinStore.setEnabled(this, true)
                LockSession.lock()
                LockSession.lockScreenVisible = false
                activeFlow = AppFlow.Menu
                updateDisplay()
                feedbackSuccess()
                tts.speak("PIN kód mentve és a zárolás bekapcsolva.")
            }
            null -> Unit
        }
    }

    private fun submitNumberPad(flow: AppFlow.NumberPadInput) {
        when (flow.purpose) {
            NumberPadPurpose.PIN -> submitPinPad(flow)
            NumberPadPurpose.PHONE -> {
                val phone = flow.buffer.trim()
                if (phone.isBlank()) {
                    tts.speak("Üres szám. Írj be legalább egy számjegyet.")
                    return
                }
                enterCallConfirm(ContactMatch("dial", "Tárcsázás", phone))
            }
            NumberPadPurpose.CONTACT -> {
                val phone = flow.buffer.trim()
                if (phone.isBlank()) {
                    tts.speak("Üres szám. Írj be legalább egy számjegyet.")
                    return
                }
                proceedContactCreateName(phone)
            }
            NumberPadPurpose.SOS -> {
                val slot = flow.sosSlot ?: return
                saveSosNumberFromPad(slot, flow.buffer.trim())
            }
            NumberPadPurpose.CALCULATOR -> {
                val result = CalculatorHelper.evaluateExpression(flow.buffer)
                if (result == null) {
                    tts.speak("Érvénytelen számolás. Javítsd a bevitelt, vagy válaszd a Diktálást.")
                    return
                }
                activeFlow = AppFlow.Menu
                updateDisplay()
                tts.speak(result.speak())
            }
            NumberPadPurpose.TIME -> submitTimePad(flow)
            NumberPadPurpose.AMOUNT -> {
                val amount = NumberPadHelper.parseAmountBuffer(flow.buffer)
                val unit = flow.timerUnit
                if (amount == null || unit == null) {
                    tts.speak("Érvénytelen szám. Írj be legalább egy számjegyet.")
                    return
                }
                onTimerAmountSpoken(unit, amount.toString(), flow.editTimerId)
            }
            NumberPadPurpose.DATE -> {
                val dayStart = NumberPadHelper.parseDateBuffer(flow.buffer)
                val title = flow.calendarTitle
                if (dayStart == null || title == null) {
                    tts.speak("Érvénytelen dátum. Nyolc számjegy kell: év, hónap, nap.")
                    return
                }
                listenForCalendarStartTime(title, dayStart)
            }
            NumberPadPurpose.PRICE -> {
                val listName = flow.shoppingListName ?: return
                val price = NumberPadHelper.parseAmountBuffer(flow.buffer)
                if (flow.shoppingEditPriceOnly && flow.shoppingEditItemId != null) {
                    val updated = ShoppingListStore.updateItemPrice(
                        this, listName, flow.shoppingEditItemId, price
                    )
                    if (updated == null) {
                        tts.speak("Nem sikerült módosítani az árat.")
                        return
                    }
                    val items = ShoppingListStore.getItems(this, listName)
                    val index = items.indexOfFirst { it.id == flow.shoppingEditItemId }.coerceAtLeast(0)
                    returnToShoppingBrowse(listName, items, index)
                    tts.speak(updated.speakPreview())
                    return
                }
                val itemName = flow.shoppingItemName ?: return
                val added = ShoppingListStore.addItem(this, listName, itemName, price)
                if (added == null) {
                    tts.speak("Nem sikerült hozzáadni.")
                    return
                }
                val priceText = price?.let { ", $it forint" }.orEmpty()
                tts.speak("$itemName hozzáadva$priceText.")
                listenForShoppingListMore(listName)
            }
        }
    }

    private fun submitTimePad(flow: AppFlow.NumberPadInput) {
        val time = NumberPadHelper.parseTimeBuffer(flow.buffer)
        if (time == null) {
            tts.speak("Érvénytelen idő. Négy számjegy kell: óra, óra, perc, perc. Például nulla hét három nulla.")
            return
        }
        when {
            flow.alarmDraft -> {
                activeFlow = AppFlow.AlarmAwaitLabel(time.first, time.second)
                updateFlowDisplay()
                listenForAlarmLabel(time.first, time.second)
            }
            flow.calendarTitle != null && flow.calendarDayStartMs != null -> {
                if (flow.calendarAwaitEnd) {
                    val startHour = flow.calendarStartHour ?: return
                    val startMinute = flow.calendarStartMinute ?: return
                    val times = CalendarHelper.buildEventTimes(
                        flow.calendarDayStartMs,
                        startHour,
                        startMinute,
                        time.first,
                        time.second
                    )
                    enterCalendarRecurrenceBrowse(flow.calendarTitle, times.first, times.second)
                } else {
                    listenForCalendarEndTime(flow.calendarTitle, flow.calendarDayStartMs, time.first, time.second)
                }
            }
            else -> onMedicationTimeEntered(time.first, time.second)
        }
    }

    private fun saveSosNumberFromPad(slot: Int, number: String) {
        SosPreferences.setNumber(this, slot, number)
        activeFlow = AppFlow.Menu
        updateDisplay()
        tts.speak(
            if (number.isBlank()) "S.O.S. szám $slot törölve."
            else "S.O.S. szám $slot mentve: ${NumberPadHelper.speakChars(number)}"
        )
    }

    private fun startCalculatorVoiceInput() {
        ensureMicAndRun {
            activeFlow = AppFlow.CalculatorVoiceInput
            updateFlowDisplay()
            listenForCalculatorInput()
        }
    }

    // ==================== KÜLSŐ ALKALMAZÁSOK ====================

    private fun startExternalAppsFlow() {
        val apps = ExternalAppHelper.getLaunchableApps(this)
        if (apps.isEmpty()) {
            tts.speak("Nem találtam indítható alkalmazást.")
            return
        }
        activeFlow = AppFlow.ExternalAppBrowse(apps, 0)
        updateFlowDisplay()
        tts.speak(ExternalAppHelper.warningMessage())
        tts.speakAdd(apps.first().speakPreview())
    }

    private fun navigateExternalApps(flow: AppFlow.ExternalAppBrowse, delta: Int) {
        val next = (flow.index + delta + flow.apps.size) % flow.apps.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.apps[next].speakPreview())
    }

    /**
     * A képernyőolvasó bekapcsolása külső alkalmazás indításakor.
     *
     * Csak akkor kapcsoljuk be, ha a rendszerben ENGEDÉLYEZVE van — enélkül
     * úgysem működne. Ha a felhasználó a saját megszokott képernyőolvasóját
     * használja, a Super DL beállításaiban kikapcsolhatja ezt.
     */
    private fun enableScreenReaderForExternalApp() {
        if (!ExternalAppHelper.isScreenReaderEnabledInSystem(this)) return
        if (ScreenReaderPrefs.isEmergencyDisabled(this)) return   // vészleállítás tiszteletben
        if (!ScreenReaderPrefs.isEnabled(this)) {
            ScreenReaderPrefs.setEnabled(this, true)
        }
    }

    private fun launchExternalApp(app: com.superdl.launcher.apps.ExternalApp) {
        // Ha a képernyőolvasó engedélyezve van a rendszerben, BEKAPCSOLJUK —
        // így a külső alkalmazás rögtön kezelhető a megszokott gesztusokkal.
        // A beállításokban bármikor kikapcsolható, ha más olvasót használnál.
        enableScreenReaderForExternalApp()
        tts.speakThen(ExternalAppHelper.assistantLaunchWarning(this)) {
            if (!ExternalAppHelper.launch(this, app)) {
                tts.speak("Az alkalmazás nem indítható: ${app.label}")
            } else {
                tts.speak("${app.label} megnyitva.")
            }
        }
    }

    private fun launchExternalAppFromAssistant(query: String) {
        val app = ExternalAppHelper.findByName(this, query)
        if (app == null) {
            tts.speakThen("Nem találom a $query alkalmazást.") { resumeVoiceAssistantListening() }
            return
        }
        // Az asszisztensből indított külső appnál is bekapcsoljuk az olvasót.
        enableScreenReaderForExternalApp()
        tts.speakThen(ExternalAppHelper.assistantLaunchWarning(this)) {
            if (!ExternalAppHelper.launch(this, app)) {
                tts.speakThen("Az alkalmazás nem indítható: ${app.label}.") { resumeVoiceAssistantListening() }
            } else {
                tts.speakThen("${app.label} megnyitva.") { resumeVoiceAssistantListening() }
            }
        }
    }

    // ==================== KEDVENC ALKALMAZÁSOK ====================

    private fun startFavoriteAppsFlow(mode: AppFlow.FavoriteAppsMode) {
        val favorites = FavoriteAppCatalog.getActiveFavorites(this)
        if (favorites.isEmpty()) {
            tts.speak("Nincs mentett kedvenc alkalmazás. Előbb adj hozzá egyet.")
            return
        }
        activeFlow = AppFlow.FavoriteAppsBrowse(favorites, 0, mode)
        updateFlowDisplay()
        val intro = when (mode) {
            AppFlow.FavoriteAppsMode.LAUNCH ->
                "${favorites.size} kedvenc alkalmazás. Söpörj fel-le választás, jobbra indítás, balra vissza."
            AppFlow.FavoriteAppsMode.REMOVE ->
                "${favorites.size} kedvenc alkalmazás. Söpörj fel-le választás, jobbra törlés, balra vissza."
            AppFlow.FavoriteAppsMode.ADD -> ""
        }
        tts.speak(intro)
        tts.speakAdd(favorites.first().speakPreview())
    }

    private fun startFavoriteAppsAddFlow() {
        val candidates = FavoriteAppCatalog.getAddableCandidates(this)
        if (candidates.isEmpty()) {
            tts.speak("Nincs több hozzáadható alkalmazás, vagy minden már kedvenc.")
            return
        }
        activeFlow = AppFlow.FavoriteAppsCandidateBrowse(candidates, 0)
        updateFlowDisplay()
        tts.speak(
            "${candidates.size} választható alkalmazás. " +
                "Super DL funkciók és külső telepített appok. Söpörj fel-le választás, jobbra hozzáadás, balra vissza."
        )
        tts.speakAdd(candidates.first().speakPreview())
    }

    private fun navigateFavoriteAppsList(flow: AppFlow.FavoriteAppsBrowse, delta: Int) {
        val next = (flow.index + delta + flow.favorites.size) % flow.favorites.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.favorites[next].speakPreview())
    }

    private fun navigateFavoriteAppsCandidates(flow: AppFlow.FavoriteAppsCandidateBrowse, delta: Int) {
        val next = (flow.index + delta + flow.candidates.size) % flow.candidates.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.candidates[next].speakPreview())
    }

    private fun onFavoriteAppsActivate(flow: AppFlow.FavoriteAppsBrowse) {
        val favorite = flow.favorites[flow.index]
        when (flow.mode) {
            AppFlow.FavoriteAppsMode.LAUNCH -> launchFavoriteApp(favorite)
            AppFlow.FavoriteAppsMode.REMOVE -> removeFavoriteApp(favorite, flow)
            AppFlow.FavoriteAppsMode.ADD -> Unit
        }
    }

    private fun addFavoriteAppCandidate(flow: AppFlow.FavoriteAppsCandidateBrowse) {
        val candidate = flow.candidates[flow.index]
        val entry = candidate.toEntry()
        if (!FavoriteAppsStore.add(this, entry)) {
            tts.speak("Ez az alkalmazás már kedvenc.")
            return
        }
        feedbackSuccess()
        val updated = FavoriteAppCatalog.getAddableCandidates(this)
        if (updated.isEmpty()) {
            exitFlow("Kedvenc mentve: ${entry.label}. Nincs több hozzáadható alkalmazás.", success = true)
            return
        }
        val nextIndex = flow.index.coerceAtMost(updated.lastIndex)
        activeFlow = AppFlow.FavoriteAppsCandidateBrowse(updated, nextIndex)
        updateFlowDisplay()
        tts.speak("Kedvenc mentve: ${entry.label}.")
        tts.speakAdd(updated[nextIndex].speakPreview())
    }

    private fun removeFavoriteApp(favorite: FavoriteAppEntry, flow: AppFlow.FavoriteAppsBrowse) {
        if (!FavoriteAppsStore.remove(this, favorite)) {
            tts.speak("Kedvenc törlése sikertelen.")
            return
        }
        feedbackSuccess()
        val updated = FavoriteAppCatalog.getActiveFavorites(this)
        if (updated.isEmpty()) {
            exitFlow("Kedvenc törölve. Nincs több mentett kedvenc alkalmazás.", success = true)
            return
        }
        val nextIndex = flow.index.coerceAtMost(updated.lastIndex)
        activeFlow = AppFlow.FavoriteAppsBrowse(updated, nextIndex, flow.mode)
        updateFlowDisplay()
        tts.speak("Kedvenc törölve.")
        tts.speakAdd(updated[nextIndex].speakPreview())
    }

    private fun launchFavoriteApp(favorite: FavoriteAppEntry) {
        when (favorite.type) {
            FavoriteAppType.INTERNAL -> {
                val item = com.superdl.launcher.menu.MenuTree.allItems()
                    .firstOrNull { it.action.name == favorite.id }
                if (item == null) {
                    tts.speak("A kedvenc Super DL funkció már nem érhető el.")
                    return
                }
                tts.speakAndRun("${favorite.label} indítása.") { handleAction(item) }
            }
            FavoriteAppType.EXTERNAL -> {
                // Külső alkalmazásnál a képernyőolvasót is bekapcsoljuk.
                enableScreenReaderForExternalApp()
                tts.speakThen(ExternalAppHelper.assistantLaunchWarning(this)) {
                    val app = com.superdl.launcher.apps.ExternalApp(favorite.id, favorite.label)
                    if (!ExternalAppHelper.launch(this, app)) {
                        tts.speak("A kedvenc alkalmazás nem indítható: ${favorite.label}")
                    } else {
                        tts.speak("${favorite.label} megnyitva.")
                    }
                }
            }
        }
    }

    // ==================== INTERNET KERESŐ ====================

    private fun startWebSearchFlow() {
        ensureMicAndRun {
            activeFlow = AppFlow.SearchAwaitQuery
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Internet kereső. Mondd mit keresel.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val query = spoken.trim()
                    if (query.isBlank()) {
                        exitFlow("Üres keresés.")
                        return@listen
                    }
                    runWebSearch(query)
                },
                onError = { exitFlow("Keresés megszakítva.") }
            )
        }
    }

    private fun runWebSearch(query: String, fromAssistant: Boolean = false) {
        voiceInput.cancel()
        activeFlow = AppFlow.SearchLoading
        updateFlowDisplay()
        tts.speak("Keresés: $query. Várj.")
        Thread {
            val wiki = WikipediaHelper.tryFetch(query)
            if (wiki != null) {
                postWhenAlive {
                    if (activeFlow !is AppFlow.SearchLoading) return@postWhenAlive
                    openWikipediaArticle(query, wiki, fromAssistant)
                }
                return@Thread
            }
            val results = SearchHelper.search(query)
            postWhenAlive {
                if (activeFlow !is AppFlow.SearchLoading) return@postWhenAlive
                if (results.isEmpty()) {
                    val message = "Nem találtam eredményt: $query."
                    if (fromAssistant) tts.speakThen(message) { resumeVoiceAssistantListening() }
                    else exitFlow(message)
                    return@postWhenAlive
                }
                showSearchResults(query, results)
            }
        }.start()
    }

    private fun openWikipediaArticle(
        query: String,
        article: WikipediaHelper.Article,
        fromAssistant: Boolean
    ) {
        val result = SearchResult(article.title, article.extract.take(240), "wikipedia://hu")
        if (fromAssistant) voiceAssistantReturnPending = true
        startSearchArticleReading(result, article.extract, listOf(result), 0, query, "Wikipédia")
    }

    private fun showSearchResults(query: String, results: List<SearchResult>) {
        activeFlow = AppFlow.SearchResultBrowse(results, 0, query)
        updateFlowDisplay()
        tts.speak(
            "${results.size} találat. Söpörj felfelé: következő találat, lefelé: mentés jegyzetként, jobbra: cikk felolvasása, balra: vissza."
        )
        speakSearchResult(results.first(), 1, results.size)
    }

    private fun speakSearchResult(result: SearchResult, index: Int, total: Int) {
        tts.speak(result.speakFull(index, total))
    }

    private fun navigateSearchResults(flow: AppFlow.SearchResultBrowse, delta: Int) {
        val next = (flow.index + delta + flow.results.size) % flow.results.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        speakSearchResult(flow.results[next], next + 1, flow.results.size)
    }

    private fun openNewsArticle(flow: AppFlow.NewsBrowse) {
        val item = flow.items[flow.index]
        val link = item.link
        // Ha nincs link, marad a régi viselkedés: az RSS-kivonat felolvasása.
        if (link.isBlank()) {
            tts.speak(item.speakFull())
            return
        }
        val savedFlow = flow
        activeFlow = AppFlow.SearchLoading
        updateFlowDisplay()
        tts.speak("Cikk betöltése: ${item.title}. Várj.")
        Thread {
            val text = ArticleTextExtractor.fetchText(link)
            postWhenAlive {
                if (activeFlow !is AppFlow.SearchLoading) return@postWhenAlive
                val body = when {
                    !text.isNullOrBlank() -> text
                    item.description.isNotBlank() -> item.description
                    else -> null
                }
                if (body == null) {
                    // Nem sikerült letölteni: visszaesünk a hírlistára és felolvassuk a kivonatot.
                    activeFlow = savedFlow
                    updateFlowDisplay()
                    tts.speak("Nem sikerült letölteni a teljes cikket. ${item.speakFull()}")
                    return@postWhenAlive
                }
                startNewsArticleReading(savedFlow, item, body)
            }
        }.start()
    }

    private fun startNewsArticleReading(
        newsFlow: AppFlow.NewsBrowse,
        item: com.superdl.launcher.news.RssItem,
        body: String
    ) {
        if (::articleReader.isInitialized && articleReader.isActive) articleReader.stop()
        articleReader.startWithText(searchArticleBook, item.title, body, 0)
        activeFlow = AppFlow.NewsArticleReading(newsFlow, item.title, body)
        updateFlowDisplay()
    }

    private fun openSearchArticle(flow: AppFlow.SearchResultBrowse) {
        val result = flow.results[flow.index]
        activeFlow = AppFlow.SearchLoading
        updateFlowDisplay()
        tts.speak("Oldal betöltése: ${result.title}. Várj.")
        Thread {
            val text = ArticleTextExtractor.fetchText(result.url)
            postWhenAlive {
                if (activeFlow !is AppFlow.SearchLoading) return@postWhenAlive
                val body = when {
                    !text.isNullOrBlank() -> text
                    result.snippet.isNotBlank() -> result.snippet
                    else -> null
                }
                if (body == null) {
                    tts.speak("Nem sikerült kinyerni a szöveget. Marad a rövid leírás.")
                    activeFlow = AppFlow.SearchResultBrowse(flow.results, flow.index, flow.query)
                    updateFlowDisplay()
                    speakSearchResult(result, flow.index + 1, flow.results.size)
                    return@postWhenAlive
                }
                startSearchArticleReading(result, body, flow.results, flow.index, flow.query)
            }
        }.start()
    }

    private fun startSearchArticleReading(
        result: SearchResult,
        body: String,
        results: List<SearchResult>,
        resultIndex: Int,
        query: String,
        sourceLabel: String = ""
    ) {
        if (::articleReader.isInitialized && articleReader.isActive) articleReader.stop()
        articleReader.startWithText(searchArticleBook, result.title, body, 0)
        activeFlow = AppFlow.SearchArticleReading(
            result = result,
            chunkIndex = 0,
            totalChunks = 1,
            percent = 0,
            results = results,
            resultIndex = resultIndex,
            query = query,
            sourceLabel = sourceLabel,
            articleBody = body
        )
        updateFlowDisplay()
        val prefix = if (sourceLabel.isNotBlank()) "$sourceLabel: " else "Cikk: "
        tts.speak(
            "${prefix}${result.title}. Söpörj lefelé: következő rész vagy mentés jegyzetként, felfelé: ismétlés, balra: vissza."
        )
    }

    private fun saveSearchResultAsNote(flow: AppFlow.SearchResultBrowse) {
        val result = flow.results[flow.index]
        val query = flow.query
        val results = flow.results
        val index = flow.index
        activeFlow = AppFlow.SearchLoading
        updateFlowDisplay()
        tts.speak("Jegyzet mentése: ${result.title}. Várj.")
        Thread {
            val text = ArticleTextExtractor.fetchText(result.url)
            postWhenAlive {
                val body = when {
                    !text.isNullOrBlank() -> text
                    result.snippet.isNotBlank() -> result.snippet
                    else -> null
                }
                if (body == null) {
                    activeFlow = AppFlow.SearchResultBrowse(results, index, query)
                    updateFlowDisplay()
                    tts.speak("Nem sikerült menteni. Nincs elérhető szöveg.")
                    speakSearchResult(results[index], index + 1, results.size)
                    return@postWhenAlive
                }
                val entry = NoteStore.add(this, result.title, body, result.url)
                activeFlow = AppFlow.SearchResultBrowse(results, index, query)
                updateFlowDisplay()
                if (entry == null) {
                    tts.speak("Nem sikerült menteni a jegyzetet.")
                } else {
                    tts.speak("Jegyzet mentve: ${entry.title}.")
                }
                speakSearchResult(results[index], index + 1, results.size)
            }
        }.start()
    }

    private fun saveSearchArticleAsNote(flow: AppFlow.SearchArticleReading) {
        val body = flow.articleBody.ifBlank { flow.result.snippet }
        if (body.isBlank()) {
            tts.speak("Nincs menthető szöveg.")
            return
        }
        val entry = NoteStore.add(this, flow.result.title, body, flow.result.url)
        if (entry == null) {
            tts.speak("Nem sikerült menteni a jegyzetet.")
            return
        }
        tts.speak("Jegyzet mentve: ${entry.title}.")
    }

    private fun finishSearchArticleReading(message: String) {
        articleReader.stop()
        val flow = activeFlow as? AppFlow.SearchArticleReading
        if (flow != null && flow.results.size > 1) {
            activeFlow = AppFlow.SearchResultBrowse(flow.results, flow.resultIndex, flow.query)
            updateFlowDisplay()
            tts.speak("$message Vissza a találatoknál.")
            return
        }
        if (voiceAssistantReturnPending) {
            tts.speakThen(message) { resumeVoiceAssistantListening() }
            return
        }
        exitFlow(message)
    }

    private fun exitSearchArticleReading(message: String) {
        if (::articleReader.isInitialized && articleReader.isActive) articleReader.stop()
        exitFlow(message)
    }

    // ==================== NAPI ÖSSZEFOGLALÓ ====================

    private fun startDaySummaryFlow() {
        tts.speak("Napi összefoglaló összeállítása. Várj.")
        DaySummaryHelper.fetchAndSpeak(
            context = this,
            onSpeak = { summary -> postWhenAlive { tts.speak(summary) } },
            onError = { message -> postWhenAlive { tts.speak(message) } }
        )
    }

    // ==================== BEVÁSÁRLÓLISTA ====================

    private fun startShoppingListFlow() {
        val names = ShoppingListStore.getListNames(this)
        if (names.isEmpty()) {
            tts.speak("Még nincs bevásárlólistád.")
            listenForShoppingListName()
            return
        }
        val activeName = ShoppingListStore.getActiveListName(this)
        val startIndex = activeName?.let { names.indexOf(it).takeIf { idx -> idx >= 0 } } ?: 0
        activeFlow = AppFlow.ShoppingListPick(names, startIndex)
        updateFlowDisplay()
        // RÖVID bemondás: korábban négy dolgot mondott el egyszerre (söprés,
        // pöccintés, hangparancs), amitől több listánál áttekinthetetlen lett.
        // A művelet-menü a lefelé pöccintéssel továbbra is elérhető, csak nem
        // daráljuk el minden belépéskor.
        tts.speak("${names.size} listád van. Fel-le válogatás, jobbra megnyitás.")
        tts.speakAdd(names[startIndex])
    }

    private fun listenForShoppingListName() {
        ensureMicAndRun {
            activeFlow = AppFlow.ShoppingListAwaitName
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd az új bevásárlólista nevét.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val name = spoken.trim()
                    if (name.isBlank()) {
                        exitFlow("Üres lista név.")
                        return@listen
                    }
                    if (!ShoppingListStore.createList(this, name)) {
                        tts.speak("Nem sikerült létrehozni a listát.")
                        return@listen
                    }
                    listenForShoppingListItem(name)
                },
                onError = { exitFlow("Bevásárlólista megszakítva.") }
            )
        }
    }

    private fun listenForShoppingListItem(listName: String) {
        ensureMicAndRun {
            activeFlow = AppFlow.ShoppingListAwaitItem
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd a tételt a $listName listához.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val item = spoken.trim()
                    if (item.isBlank()) {
                        exitFlow("Üres tétel.")
                        return@listen
                    }
                    listenForShoppingListPrice(listName, item)
                },
                onError = { exitFlow("Bevásárlólista megszakítva.") }
            )
        }
    }

    private fun listenForShoppingListPrice(listName: String, itemName: String) {
        enterNumericDictationAwait(
            AppFlow.NumericDictationAwait(
                purpose = NumberPadPurpose.PRICE,
                shoppingListName = listName,
                shoppingItemName = itemName
            )
        )
        tts.speakAdd("$itemName ára.")
    }

    private fun listenForShoppingListMore(listName: String) {
        ensureMicAndRun {
            activeFlow = AppFlow.ShoppingListAwaitMore(listName)
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd a következő tételt, vagy mondd: kész.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val text = spoken.trim()
                    if (text.equals("kész", ignoreCase = true) || text.equals("kesz", ignoreCase = true)) {
                        finishShoppingListCreation(listName)
                        return@listen
                    }
                    if (text.isBlank()) {
                        tts.speak("Üres tétel. Mondd a következő nevet, vagy mondd: kész.")
                        listenForShoppingListMore(listName)
                        return@listen
                    }
                    listenForShoppingListPrice(listName, text)
                },
                onError = { finishShoppingListCreation(listName) }
            )
        }
    }

    private fun finishShoppingListCreation(listName: String) {
        val items = ShoppingListStore.getItems(this, listName)
        if (items.isEmpty()) {
            exitFlow("A lista üres maradt.")
            return
        }
        enterShoppingBrowse(listName, items, 0)
        tts.speakAdd(ShoppingListStore.speakTotal(items))
    }

    private fun enterShoppingBrowse(listName: String, items: List<ShoppingItem>, index: Int) {
        ShoppingListStore.setActiveListName(this, listName)
        val hasSummary = items.any { it.priceHuf != null }
        val showingSummary = hasSummary && index >= items.size
        activeFlow = AppFlow.ShoppingListBrowse(listName, items, index.coerceAtMost(items.size), showingSummary)
        updateFlowDisplay()
        if (showingSummary) {
            tts.speak(ShoppingListStore.speakTotal(items))
            return
        }
        // RÖVID bemondás — a négy gesztust a felhasználó ismeri, nem kell minden
        // belépéskor felsorolni. A lista neve és a tételszám elég a tájékozódáshoz.
        tts.speak("$listName. ${items.size} tétel.")
        if (hasSummary) {
            tts.speakAdd("Az árösszesítő a lista végén érhető el.")
        }
        tts.speakAdd(items[index.coerceIn(0, items.lastIndex)].speakPreview())
    }

    private fun returnToShoppingBrowse(listName: String, items: List<ShoppingItem>, index: Int) {
        val fresh = ShoppingListStore.getItems(this, listName)
        if (fresh.isEmpty()) {
            exitFlow("A lista üres lett.")
            return
        }
        enterShoppingBrowse(listName, fresh, index.coerceIn(0, fresh.lastIndex))
    }

    private fun navigateShoppingListPick(flow: AppFlow.ShoppingListPick, delta: Int) {
        val next = (flow.index + delta + flow.names.size) % flow.names.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.names[next])
    }

    private fun onShoppingListPickActivate(flow: AppFlow.ShoppingListPick) {
        val name = flow.names[flow.index]
        val items = ShoppingListStore.getItems(this, name)
        if (items.isEmpty()) {
            listenForShoppingListItem(name)
        } else {
            enterShoppingBrowse(name, items, 0)
        }
    }

    private fun enterShoppingListContextMenu(flow: AppFlow.ShoppingListPick) {
        activeFlow = AppFlow.ShoppingListContextMenu(
            names = flow.names,
            listIndex = flow.index,
            actions = ShoppingListContextAction.all,
            actionIndex = 0
        )
        updateFlowDisplay()
        tts.speak(
            "${flow.names[flow.index]} lista műveletei. " +
                "${ShoppingListContextAction.all.first().label}. Söpörj fel-le választás, jobbra végrehajtás."
        )
    }

    private fun navigateShoppingListContextMenu(flow: AppFlow.ShoppingListContextMenu, delta: Int) {
        val next = (flow.actionIndex + delta + flow.actions.size) % flow.actions.size
        activeFlow = flow.copy(actionIndex = next)
        updateFlowDisplay()
        tts.speak(flow.actions[next].label)
    }

    private fun onShoppingListContextActivate(flow: AppFlow.ShoppingListContextMenu) {
        val name = flow.names[flow.listIndex]
        when (flow.actions[flow.actionIndex]) {
            ShoppingListContextAction.OPEN -> onShoppingListPickActivate(
                AppFlow.ShoppingListPick(flow.names, flow.listIndex)
            )
            ShoppingListContextAction.ADD_ITEM -> listenForShoppingListItem(name)
            ShoppingListContextAction.RENAME -> listenForShoppingListRename(name, flow.names, flow.listIndex)
            ShoppingListContextAction.DELETE -> enterShoppingDeleteListConfirm(name, flow.names, flow.listIndex)
        }
    }

    private fun listenForShoppingListRename(oldName: String, names: List<String>, index: Int) {
        ensureMicAndRun {
            activeFlow = AppFlow.ShoppingRenameListAwaitName(oldName, names, index)
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd az új lista nevet. Jelenlegi név: $oldName.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val newName = spoken.trim()
                    if (newName.isBlank()) {
                        tts.speak("Üres név.")
                        return@listen
                    }
                    if (!ShoppingListStore.renameList(this, oldName, newName)) {
                        tts.speak("Nem sikerült átnevezni. Lehet, hogy már létezik ilyen név.")
                        return@listen
                    }
                    val updatedNames = ShoppingListStore.getListNames(this)
                    val newIndex = updatedNames.indexOf(newName).coerceAtLeast(0)
                    activeFlow = AppFlow.ShoppingListPick(updatedNames, newIndex)
                    updateFlowDisplay()
                    tts.speak("Lista átnevezve: $newName.")
                },
                onError = {
                    activeFlow = AppFlow.ShoppingListPick(names, index)
                    updateFlowDisplay()
                    tts.speak("Átnevezés megszakítva.")
                }
            )
        }
    }

    private fun enterShoppingDeleteListConfirm(listName: String, names: List<String>, index: Int) {
        activeFlow = AppFlow.ShoppingDeleteListConfirm(listName, names, index)
        updateFlowDisplay()
        repeatShoppingDeleteListConfirm(listName)
    }

    private fun repeatShoppingDeleteListConfirm(listName: String) {
        tts.speak(
            "Törlöd a $listName bevásárlólistát és minden tételét? " +
                "Söpörj jobbra a törléshez, söprés balra a mégsehez."
        )
    }

    private fun deleteShoppingList(flow: AppFlow.ShoppingDeleteListConfirm) {
        ShoppingListStore.deleteList(this, flow.listName)
        val names = ShoppingListStore.getListNames(this)
        if (names.isEmpty()) {
            exitFlow("Lista törölve. Nincs több bevásárlólista.")
            return
        }
        val nextIndex = flow.index.coerceIn(0, names.lastIndex)
        activeFlow = AppFlow.ShoppingListPick(names, nextIndex)
        updateFlowDisplay()
        tts.speak("Lista törölve. ${names[nextIndex]}.")
    }

    private fun shoppingBrowseSlotCount(items: List<ShoppingItem>): Int {
        val hasSummary = items.any { it.priceHuf != null }
        return items.size + if (hasSummary) 1 else 0
    }

    private fun navigateShoppingList(flow: AppFlow.ShoppingListBrowse, delta: Int) {
        val slots = shoppingBrowseSlotCount(flow.items)
        val next = (flow.index + delta + slots) % slots
        val showingSummary = next >= flow.items.size
        activeFlow = flow.copy(index = next, showingSummary = showingSummary)
        updateFlowDisplay()
        if (showingSummary) {
            tts.speak(ShoppingListStore.speakTotal(flow.items))
        } else {
            tts.speak(flow.items[next].speakPreview())
        }
    }

    private fun enterShoppingItemContextMenu(flow: AppFlow.ShoppingListBrowse) {
        val actions = if (flow.showingSummary) {
            ShoppingContextAction.summaryActions
        } else {
            ShoppingContextAction.itemActions
        }
        activeFlow = AppFlow.ShoppingItemContextMenu(
            listName = flow.listName,
            items = flow.items,
            itemIndex = flow.index.coerceIn(0, flow.items.lastIndex.coerceAtLeast(0)),
            actions = actions,
            actionIndex = 0
        )
        updateFlowDisplay()
        tts.speak(
            "Műveletek. ${actions.first().label}. Söpörj fel-le választás, jobbra végrehajtás, balra vissza."
        )
    }

    private fun navigateShoppingItemContextMenu(flow: AppFlow.ShoppingItemContextMenu, delta: Int) {
        val next = (flow.actionIndex + delta + flow.actions.size) % flow.actions.size
        activeFlow = flow.copy(actionIndex = next)
        updateFlowDisplay()
        tts.speak(flow.actions[next].label)
    }

    private fun onShoppingItemContextActivate(flow: AppFlow.ShoppingItemContextMenu) {
        when (flow.actions[flow.actionIndex]) {
            ShoppingContextAction.TOGGLE_CHECKED -> {
                if (flow.itemIndex >= flow.items.size) {
                    tts.speak(ShoppingListStore.speakTotal(flow.items))
                    return
                }
                val item = flow.items[flow.itemIndex]
                val updated = ShoppingListStore.toggleChecked(this, flow.listName, item.id) ?: return
                sounds.play(SoundType.ACTION_OK)
                val items = ShoppingListStore.getItems(this, flow.listName)
                returnToShoppingBrowse(flow.listName, items, flow.itemIndex)
                tts.speakAdd(updated.speakPreview())
            }
            ShoppingContextAction.ADD_ITEM -> listenForShoppingListItem(flow.listName)
            ShoppingContextAction.EDIT_NAME -> listenForShoppingEditItemName(flow)
            ShoppingContextAction.EDIT_PRICE -> listenForShoppingEditItemPrice(flow)
            ShoppingContextAction.DELETE_ITEM -> {
                if (flow.itemIndex >= flow.items.size) return
                enterShoppingDeleteItemConfirm(
                    flow.listName,
                    flow.items[flow.itemIndex],
                    flow.items,
                    flow.itemIndex
                )
            }
            ShoppingContextAction.DELETE_LIST -> enterShoppingDeleteListConfirm(
                flow.listName,
                ShoppingListStore.getListNames(this),
                ShoppingListStore.getListNames(this).indexOf(flow.listName).coerceAtLeast(0)
            )
        }
    }

    private fun listenForShoppingEditItemName(flow: AppFlow.ShoppingItemContextMenu) {
        val item = flow.items.getOrNull(flow.itemIndex) ?: return
        ensureMicAndRun {
            activeFlow = AppFlow.ShoppingEditItemAwaitName(flow.listName, item, flow.items, flow.itemIndex)
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd az új nevet. Jelenlegi név: ${item.name}.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val name = spoken.trim()
                    if (name.isBlank()) {
                        tts.speak("Üres név.")
                        return@listen
                    }
                    val updated = ShoppingListStore.updateItemName(this, flow.listName, item.id, name)
                    if (updated == null) {
                        tts.speak("Nem sikerült módosítani.")
                        return@listen
                    }
                    val items = ShoppingListStore.getItems(this, flow.listName)
                    returnToShoppingBrowse(flow.listName, items, flow.itemIndex)
                    tts.speakAdd(updated.speakPreview())
                },
                onError = { returnToShoppingBrowse(flow.listName, flow.items, flow.itemIndex) }
            )
        }
    }

    private fun listenForShoppingEditItemPrice(flow: AppFlow.ShoppingItemContextMenu) {
        val item = flow.items.getOrNull(flow.itemIndex) ?: return
        enterNumericDictationAwait(
            AppFlow.NumericDictationAwait(
                purpose = NumberPadPurpose.PRICE,
                shoppingListName = flow.listName,
                shoppingItemName = item.name,
                shoppingEditItemId = item.id,
                shoppingEditPriceOnly = true
            )
        )
        tts.speakAdd("${item.name} új ára.")
    }

    private fun enterShoppingDeleteItemConfirm(
        listName: String,
        item: ShoppingItem,
        items: List<ShoppingItem>,
        index: Int
    ) {
        activeFlow = AppFlow.ShoppingDeleteItemConfirm(listName, item, items, index)
        updateFlowDisplay()
        repeatShoppingDeleteItemConfirm(item)
    }

    private fun repeatShoppingDeleteItemConfirm(item: ShoppingItem) {
        tts.speak(
            "Törlöd ezt a tételt? ${item.name}. Söpörj jobbra a törléshez, söprés balra a mégsehez."
        )
    }

    private fun deleteShoppingItem(flow: AppFlow.ShoppingDeleteItemConfirm) {
        ShoppingListStore.removeItem(this, flow.listName, flow.item.id)
        val items = ShoppingListStore.getItems(this, flow.listName)
        if (items.isEmpty()) {
            exitFlow("Tétel törölve. A lista most üres.")
            return
        }
        val nextIndex = flow.index.coerceIn(0, items.lastIndex)
        returnToShoppingBrowse(flow.listName, items, nextIndex)
        tts.speakAdd("Tétel törölve.")
    }

    // ==================== E-MAIL OLVASÁS (IMAP) ====================

    /**
     * E-mail kapcsolat lépésenkénti vizsgálata. Végigmegy a kapcsolódás összes
     * lépésén (névfeloldás, kapcsolat, titkosítás, bejelentkezés, postafiók),
     * méri az időt, és fájlba írja — így kiderül, hol akad el, ha az olvasás
     * csak "várakozik, majd visszalép".
     */
    private fun startEmailDiagnosticsFlow() {
        tts.speak("E-mail kapcsolat vizsgálata. Ez eltarthat fél percig.")
        Thread {
            val result = EmailDiagnostics.run(this)
            postWhenAlive {
                tts.speak(result.spokenSummary)
                tts.speakAdd("A részletes napló elmentve.")
            }
        }.start()
    }

    private fun startEmailInboxFlow() {
        val config = SmtpConfigStore.get(this)
        if (config == null) {
            tts.speak("Előbb állítsd be az e-mail küldőt.")
            return
        }
        activeFlow = AppFlow.EmailInboxLoading
        updateFlowDisplay()
        tts.speak("E-mailek betöltése. Várj.")
        Thread {
            val mails = ImapReader.fetchInbox(config)
            postWhenAlive {
                if (activeFlow !is AppFlow.EmailInboxLoading) return@postWhenAlive
                if (mails.isEmpty()) {
                    // A konkrét okot mondjuk be (bejelentkezés, hálózat, IMAP tiltva),
                    // nem a régi általános "ellenőrizd az app jelszót" üzenetet.
                    exitFlow(ImapReader.lastError ?: "Nincs e-mail a postafiókban.")
                    return@postWhenAlive
                }
                activeFlow = AppFlow.EmailInboxBrowse(mails, 0)
                updateFlowDisplay()
                tts.speak(
                    "${mails.size} levél. Söpörj fel-le választás, jobbra teljes levél, balra vissza."
                )
                speakEmailHeader(mails.first(), 1, mails.size)
            }
        }.start()
    }

    private fun speakEmailHeader(mail: ImapMail, index: Int, total: Int) {
        tts.speak(mail.speakHeader(index, total))
    }

    private fun navigateEmailInbox(flow: AppFlow.EmailInboxBrowse, delta: Int) {
        val next = (flow.index + delta + flow.mails.size) % flow.mails.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        speakEmailHeader(flow.mails[next], next + 1, flow.mails.size)
    }

    private fun openEmailBody(flow: AppFlow.EmailInboxBrowse) {
        val mail = flow.mails[flow.index]
        // A lista csak a fejléceket tölti le (gyors), a levél TÖRZSE itt jön le —
        // csak arról a levélről, amit tényleg megnyitunk.
        if (mail.body.isBlank()) {
            tts.speak("Levél megnyitása.")
            Thread {
                val config = SmtpConfigStore.get(this)
                val body = if (config != null) ImapReader.fetchBody(config, mail.uid) else null
                postWhenAlive {
                    val loaded = if (body.isNullOrBlank()) mail else mail.copy(body = body)
                    val updated = flow.mails.toMutableList().also { it[flow.index] = loaded }
                    activeFlow = AppFlow.EmailReadBody(loaded, updated, flow.index)
                    updateFlowDisplay()
                    if (body.isNullOrBlank()) {
                        tts.speak(loaded.speakHeader(flow.index + 1, updated.size))
                        tts.speakAdd("A levél tartalma most nem tölthető le.")
                    } else {
                        tts.speak(loaded.speakBodyPreview())
                    }
                }
            }.start()
            return
        }
        activeFlow = AppFlow.EmailReadBody(mail, flow.mails, flow.index)
        updateFlowDisplay()
        tts.speak(mail.speakBodyPreview())
    }

    private fun speakEmailBody(flow: AppFlow.EmailReadBody) {
        tts.speak(flow.mail.speakBodyPreview())
    }

    fun launchVoiceAssistantFromMediaButton() {
        if (!BluetoothAssistantStore.isEnabled(this)) return
        val locked = LockSession.needsUnlock(this)
        pendingAssistantLaunch = true
        pendingAssistantFromKeyguard = locked
        pendingVoiceAction = { startVoiceAssistantFlow(lockedMode = locked) }
        runPendingVoiceActionIfReady()
    }

    private fun toggleBluetoothAssistant() {
        val enabled = BluetoothAssistantStore.toggle(this)
        if (enabled) {
            mediaButtonHandler?.start()
            tts.speak(AssistantMediaButtonHandler.speakStatus(this, true))
        } else {
            mediaButtonHandler?.stop()
            tts.speak(AssistantMediaButtonHandler.speakStatus(this, false))
        }
    }

    // ==================== SZÁMOLÓGÉP ====================

    private fun startCalculatorFlow() {
        enterNumericDictationAwait(AppFlow.NumericDictationAwait(purpose = NumberPadPurpose.CALCULATOR))
    }

    private fun listenForCalculatorInput() {
        if (activeFlow != AppFlow.CalculatorVoiceInput) return
        voiceInput.listen(
            prompt = "Mondd a számolást. Például: kétszer három, vagy tizenkettő osztva néggyel.",
            speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
            onResult = { spoken ->
                if (activeFlow != AppFlow.CalculatorVoiceInput) return@listen
                val result = CalculatorHelper.evaluate(spoken)
                if (result == null) {
                    tts.speakThen("Nem értettem a számolást. Próbáld újra.") {
                        listenForCalculatorInput()
                    }
                } else {
                    tts.speakThen(result.speak()) {
                        listenForCalculatorInput()
                    }
                }
            },
            onError = {
                tts.speak("Mondd a számolást, vagy söprés balra a kilépéshez.")
            }
        )
    }

    // ==================== ÉRTESÍTÉSEK ====================

    private fun startNotificationReadFlow() {
        if (!NotificationHelper.isListenerEnabled(this)) {
            val intent = NotificationHelper.createListenerSettingsIntent(this)
            if (intent != null) {
                activeFlow = AppFlow.Menu
                updateDisplay()
                tts.speakThen(
                    "Az értesítések olvasásához kapcsold be a Super DL-t az értesítés hozzáférés listában."
                ) {
                    try {
                        notificationListenerSettingsLauncher.launch(intent)
                    } catch (_: Exception) {
                        startPermissionGuideFlow(
                            PermissionGuideType.NOTIFICATION_LISTENER,
                            "Értesítés olvasás engedély"
                        )
                    }
                }
            } else {
                startPermissionGuideFlow(
                    PermissionGuideType.NOTIFICATION_LISTENER,
                    "Értesítés olvasás engedély"
                )
            }
            return
        }
        val notifications = NotificationStore.getRecent()
        if (notifications.isEmpty()) {
            tts.speak("Nincs olvasható értesítés.")
            return
        }
        activeFlow = AppFlow.NotificationBrowse(notifications, 0)
        updateFlowDisplay()
        tts.speak("${notifications.size} értesítés. Söpörj fel-le navigálás, jobbra teljes felolvasás, balra vissza.")
        tts.speakAdd(notifications.first().speakPreview())
    }

    private fun navigateNotificationList(flow: AppFlow.NotificationBrowse, delta: Int) {
        val next = (flow.index + delta + flow.notifications.size) % flow.notifications.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.notifications[next].speakPreview())
    }

    // ==================== NAPI ÜDVÖZLÉS ====================

    /**
     * Napi üdvözlés (dátum, névnap, időjárás).
     *
     * @param onlyIfIdle ha igaz, csak akkor szólal meg, ha a felhasználó
     *   közben nem kezdett navigálni. Indításkor ez kell: aki már lapoz a
     *   menüben, azt ne vágja félbe egy hálózatról érkező köszöntő.
     */
    private fun speakDayGreeting(onlyIfIdle: Boolean = false) {
        if (onlyIfIdle && userStartedNavigating) return
        if (!onlyIfIdle) tts.speak("Napi üdvözlés betöltése. Várj egy pillanatot.")
        DayInfoHelper.fetchGreeting(
            onResult = { greeting ->
                postWhenAlive {
                    // Mire megjön a hálózatról, lehet hogy már navigál a felhasználó.
                    if (onlyIfIdle && userStartedNavigating) return@postWhenAlive
                    tts.speak(greeting)
                }
            }
        )
    }

    // ==================== HÍREK (RSS) ====================

    private fun startNewsReadFlow() {
        tts.speak("Hírek betöltése. Várj egy pillanatot.")
        RssHelper.fetchHeadlines(
            context = this,
            page = 0,
            onResult = { page ->
                postWhenAlive {
                    if (page.items.isEmpty()) {
                        tts.speak("Nem találtam híreket. Ellenőrizd az internetkapcsolatot.")
                        return@postWhenAlive
                    }
                    activeFlow = AppFlow.NewsBrowse(page.items, 0, null, page.page, page.hasMore)
                    updateFlowDisplay()
                    val moreHint = if (page.hasMore) " Az utolsó hírnél lefelé söprés a következő 20 hírhez." else ""
                    tts.speak(
                        "${page.items.size} hír betöltve. Söpörj fel-le navigálás, " +
                            "jobbra teljes hír felolvasása, balra vissza a menübe.$moreHint"
                    )
                    tts.speakAdd(page.items.first().speakPreview())
                }
            },
            onError = {
                postWhenAlive {
                    tts.speak("A hírek nem tölthetők. Ellenőrizd az internetkapcsolatot.")
                }
            }
        )
    }

    private fun startNewsFeedManageFlow() {
        val feeds = NewsFeedStore.allDefaultFeeds() + NewsFeedStore.customFeeds(this)
        if (feeds.isEmpty()) {
            tts.speak("Nincs hírforrás.")
            return
        }
        activeFlow = AppFlow.NewsFeedManageBrowse(feeds, 0)
        updateFlowDisplay()
        tts.speak(
            "${feeds.size} hírforrás. Söpörj fel-le választás, jobbra be- vagy kikapcsolás, balra vissza."
        )
        tts.speakAdd(newsFeedManagePreview(feeds.first()))
    }

    private fun newsFeedManagePreview(feed: NewsFeed): String {
        val status = if (NewsFeedStore.isEnabled(this, feed.id)) "bekapcsolva" else "kikapcsolva"
        return "${feed.speakPreview()}. $status."
    }

    private fun navigateNewsFeedManageList(flow: AppFlow.NewsFeedManageBrowse, delta: Int) {
        val next = (flow.index + delta + flow.feeds.size) % flow.feeds.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(newsFeedManagePreview(flow.feeds[next]))
    }

    private fun toggleNewsFeed(flow: AppFlow.NewsFeedManageBrowse) {
        val feed = flow.feeds[flow.index]
        val enabled = !NewsFeedStore.isEnabled(this, feed.id)
        NewsFeedStore.setEnabled(this, feed.id, enabled)
        val status = if (enabled) "bekapcsolva" else "kikapcsolva"
        tts.speak("${feed.name} $status.")
    }

    private fun startNewsOpmlImportFlow() {
        tts.speak("Válaszd ki az OPML hírforrás fájlt.")
        opmlImportLauncher.launch(arrayOf("text/*", "application/xml", "*/*"))
    }

    private fun navigateNewsFeedList(flow: AppFlow.NewsFeedBrowse, delta: Int) {
        val next = (flow.index + delta + flow.feeds.size) % flow.feeds.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.feeds[next].speakPreview())
    }

    private fun loadNewsFromFeed(feed: NewsFeed) {
        tts.speak("${feed.name} hírei betöltése. Várj egy pillanatot.")
        RssHelper.fetchFromFeed(
            context = this,
            feedId = feed.id,
            page = 0,
            onResult = { page ->
                postWhenAlive {
                    activeFlow = AppFlow.NewsBrowse(page.items, 0, feed.id, page.page, page.hasMore)
                    updateFlowDisplay()
                    val moreHint = if (page.hasMore) " Az utolsó hírnél lefelé söprés a következő 20 hírhez." else ""
                    tts.speak(
                        "${page.items.size} hír a ${feed.name} forrásból. Söpörj fel-le navigálás, " +
                            "jobbra teljes cikk felolvasása, balra vissza.$moreHint"
                    )
                    tts.speakAdd(page.items.first().speakPreview())
                }
            },
            onError = {
                postWhenAlive {
                    tts.speak("${feed.name} hírei nem tölthetők. Ellenőrizd az internetkapcsolatot.")
                }
            }
        )
    }

    private fun navigateNewsList(flow: AppFlow.NewsBrowse, delta: Int) {
        if (delta > 0 && flow.index == flow.items.lastIndex && flow.hasMore) {
            loadNextNewsPage(flow)
            return
        }
        val next = (flow.index + delta + flow.items.size) % flow.items.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.items[next].speakPreview())
    }

    private fun loadNextNewsPage(flow: AppFlow.NewsBrowse) {
        tts.speak("Következő hírek betöltése. Várj.")
        val nextPage = flow.page + 1
        val fetch = if (flow.feedId == null) {
            { cb: (com.superdl.launcher.news.RssPage) -> Unit, err: () -> Unit ->
                RssHelper.fetchHeadlines(this, nextPage, cb, err)
            }
        } else {
            { cb: (com.superdl.launcher.news.RssPage) -> Unit, err: () -> Unit ->
                RssHelper.fetchFromFeed(this, flow.feedId, nextPage, cb, err)
            }
        }
        fetch(
            { page ->
                postWhenAlive {
                    if (page.items.isEmpty()) {
                        tts.speak("Nincs több hír.")
                        return@postWhenAlive
                    }
                    activeFlow = AppFlow.NewsBrowse(page.items, 0, flow.feedId, page.page, page.hasMore)
                    updateFlowDisplay()
                    tts.speak("${page.items.size} új hír, ${page.page + 1}. oldal.")
                    tts.speakAdd(page.items.first().speakPreview())
                }
            },
            {
                postWhenAlive { tts.speak("A következő hírek nem tölthetők.") }
            }
        )
    }

    // ==================== BELSŐ NAVIGÁCIÓ ====================

    private fun ensureLocationPermission(): Boolean {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
            == PackageManager.PERMISSION_GRANTED
        ) {
            return true
        }
        tts.speak("Helymeghatározás engedély szükséges. Engedélyezd, majd próbáld újra.")
        ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.ACCESS_FINE_LOCATION), PERM_REQUEST)
        return false
    }

    // ==================== HANG-IRÁNYTŰ (söprő mód) ====================

    private fun startCompassScan() {
        if (!ensureLocationPermission()) return
        if (CompassScanManager.isActive()) {
            tts.speak("A hang-iránytű már fut. Forgasd a telefont a tájékozódáshoz.")
            return
        }
        CompassScanManager.start(this)
        tts.speak("Hang-iránytű indul.")
    }

    private fun stopCompassScan() {
        if (!CompassScanManager.isActive()) {
            tts.speak("A hang-iránytű nem fut.")
            return
        }
        CompassScanManager.stop(this)
        tts.speak("Hang-iránytű leállítva.")
    }

    // ==================== GPS KITEKINTŐ ====================

    private fun startGpsRadarFlow() {
        if (!ensureLocationPermission()) return
        if (GpsRadarManager.isGuiding()) {
            val target = GpsRadarStore.targetPoi
            if (target != null) {
                val pois = GpsRadarStore.nearbyPois
                val index = pois.indexOfFirst { it.id == target.id }.takeIf { it >= 0 } ?: 0
                activeFlow = AppFlow.GpsRadarGuiding(pois, index)
                updateFlowDisplay()
                if (!GpsSurroundingsManager.isRunning()) {
                    startSurroundingsMonitoring()
                }
                tts.speak("Célkövetés folyamatban: ${target.speakRadar()}")
                return
            }
        }
        startRadarSensors()
        activeFlow = AppFlow.GpsRadarLoading
        updateFlowDisplay()
        tts.speak("G P S kitekintő. Közeli helyek, utcák és kereszteződések keresése. Várj.")
        val heading = radarCompass?.heading() ?: 0f
        GpsRadarHelper.loadNearbyPois(
            context = this,
            headingDegrees = heading,
            onResult = { pois ->
                postWhenAlive {
                    if (pois.isEmpty()) {
                        stopRadarSession()
                        exitFlow("Nincs közeli bolt, étterem, utca vagy kereszteződés 300 méteren belül.")
                        return@postWhenAlive
                    }
                    activeFlow = AppFlow.GpsRadarBrowse(pois, 0)
                    updateFlowDisplay()
                    startRadarRefreshLoop()
                    startSurroundingsMonitoring()
                    tts.speak(GpsRadarHelper.speakAllPois(pois))
                }
            },
            onError = { message ->
                postWhenAlive {
                    stopRadarSession()
                    exitFlow(message, error = true)
                }
            }
        )
    }

    private fun startRadarSensors() {
        stopRadarSensorsOnly()
        radarCompass = CompassProvider(this).also { it.start() }
    }

    private fun stopRadarSensorsOnly() {
        radarCompass?.stop()
        radarCompass = null
    }

    private fun stopRadarRefreshLoop() {
        radarRefreshRunnable?.let { mainHandler.removeCallbacks(it) }
        radarRefreshRunnable = null
    }

    private fun startSurroundingsMonitoring() {
        if (!GpsRadarStore.streetMonitoringEnabled) return
        GpsStreetAnnouncer.resetSession()
        GpsSurroundingsManager.start(this)
    }

    private fun stopSurroundingsMonitoring() {
        GpsSurroundingsManager.stop(this)
        GpsStreetAnnouncer.resetSession()
    }

    private fun stopRadarSession(stopGuidance: Boolean = false) {
        stopRadarRefreshLoop()
        stopSurroundingsMonitoring()
        stopRadarSensorsOnly()
        if (stopGuidance) {
            GpsRadarManager.stopGuidance(this)
        }
        GpsRadarStore.clear()
    }

    private fun startRadarRefreshLoop() {
        stopRadarRefreshLoop()
        val runnable = object : Runnable {
            override fun run() {
                if (isFinishing || isDestroyed) return
                val flow = activeFlow
                if (flow !is AppFlow.GpsRadarBrowse) return
                val location = GpsLocationHelper.getLastLocation(this@MainActivity) ?: run {
                    mainHandler.postDelayed(this, 18_000L)
                    return
                }
                val heading = radarCompass?.heading() ?: GpsRadarStore.lastHeading
                GpsRadarHelper.refreshPoisWithLocation(location, heading) { pois ->
                    postWhenAlive {
                        if (pois.isEmpty()) return@postWhenAlive
                        val current = activeFlow as? AppFlow.GpsRadarBrowse ?: return@postWhenAlive
                        val currentId = current.pois.getOrNull(current.index)?.id
                        val newIndex = currentId?.let { id ->
                            pois.indexOfFirst { it.id == id }.takeIf { it >= 0 }
                        } ?: current.index.coerceAtMost(pois.lastIndex)
                        activeFlow = AppFlow.GpsRadarBrowse(pois, newIndex)
                        updateFlowDisplay()
                    }
                }
                mainHandler.postDelayed(this, 18_000L)
            }
        }
        radarRefreshRunnable = runnable
        mainHandler.postDelayed(runnable, 18_000L)
    }

    private fun navigateGpsRadarList(flow: AppFlow.GpsRadarBrowse, delta: Int) {
        val next = (flow.index + delta + flow.pois.size) % flow.pois.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        speakGpsRadarPoi(flow.pois[next])
    }

    private fun speakGpsRadarPoi(poi: GpsPoi) {
        tts.speak(poi.speakRadar())
    }

    private fun speakGpsRadarTarget(flow: AppFlow.GpsRadarGuiding) {
        val poi = flow.pois.getOrNull(flow.index) ?: GpsRadarStore.targetPoi ?: return
        tts.speak("Célzár: ${poi.speakRadar()}")
    }

    private fun lockGpsRadarTarget(flow: AppFlow.GpsRadarBrowse) {
        val poi = flow.pois[flow.index]
        stopRadarRefreshLoop()
        stopRadarSensorsOnly()
        if (!GpsSurroundingsManager.isRunning()) {
            startSurroundingsMonitoring()
        }
        GpsRadarManager.startGuidance(this, poi)
        activeFlow = AppFlow.GpsRadarGuiding(flow.pois, flow.index)
        updateFlowDisplay()
        tts.speak("Cél zárolva: ${poi.speakRadar()} Követés indul.")
    }

    private fun unlockGpsRadarTarget(flow: AppFlow.GpsRadarGuiding) {
        GpsRadarManager.stopGuidance(this)
        activeFlow = AppFlow.GpsRadarBrowse(flow.pois, flow.index)
        updateFlowDisplay()
        startRadarSensors()
        startRadarRefreshLoop()
        if (!GpsSurroundingsManager.isRunning()) {
            startSurroundingsMonitoring()
        }
        tts.speak("Célzárolás feloldva. Vissza a helylistában.")
        speakGpsRadarPoi(flow.pois[flow.index])
    }

    private fun enterGpsRadarContextMenu(flow: AppFlow.GpsRadarBrowse) {
        val actions = GpsRadarContextAction.entries
        activeFlow = AppFlow.GpsRadarContextMenu(flow.pois, flow.index, actions, 0)
        updateFlowDisplay()
        tts.speak("G P S műveletek. ${actions.first().label}. Söpörj fel-le választás, jobbra végrehajtás, balra vissza.")
    }

    private fun navigateGpsRadarContextMenu(flow: AppFlow.GpsRadarContextMenu, delta: Int) {
        val next = (flow.actionIndex + delta + flow.actions.size) % flow.actions.size
        activeFlow = flow.copy(actionIndex = next)
        updateFlowDisplay()
        tts.speak(flow.actions[next].label)
    }

    private fun onGpsRadarContextActivate(flow: AppFlow.GpsRadarContextMenu) {
        when (flow.actions[flow.actionIndex]) {
            GpsRadarContextAction.LOCK_TARGET -> lockGpsRadarTarget(
                AppFlow.GpsRadarBrowse(flow.pois, flow.poiIndex)
            )
            GpsRadarContextAction.HEAR_INTERSECTION_AHEAD -> speakIntersectionAhead()
            GpsRadarContextAction.WHERE_AM_I -> speakGpsWhereAmI()
            GpsRadarContextAction.TOGGLE_STREET_MONITORING -> toggleGpsStreetMonitoring()
            GpsRadarContextAction.SAVE_OWN_LOCATION -> startGpsSaveOwnLocation(
                returnBrowse = AppFlow.GpsRadarBrowse(flow.pois, flow.poiIndex)
            )
            GpsRadarContextAction.SAVE_POI -> saveGpsPoiByIndex(
                flow.pois,
                flow.poiIndex,
                returnBrowse = AppFlow.GpsRadarBrowse(flow.pois, flow.poiIndex)
            )
        }
    }

    private fun speakIntersectionAhead() {
        val heading = radarCompass?.heading() ?: GpsRadarStore.lastHeading
        val context = GpsRadarStore.streetContext
        if (context == null) {
            tts.speak("Nincs elérhető kereszteződés adat. Várj, amíg frissül a környezet.")
            return
        }
        val ahead = GpsStreetHelper.intersectionAhead(context, heading)
        if (ahead == null) {
            tts.speak("Nincs kereszteződés közvetlenül előtted a közelben.")
        } else {
            tts.speak(ahead.speakAhead())
        }
    }

    private fun speakGpsWhereAmI() {
        val heading = radarCompass?.heading() ?: GpsRadarStore.lastHeading
        val context = GpsRadarStore.streetContext
        if (context != null) {
            tts.speak(GpsStreetHelper.speakWhereAmI(context, heading))
            return
        }
        val location = GpsLocationHelper.getLastLocation(this)
        if (location == null) {
            tts.speak("Helymeghatározás nem elérhető.")
            return
        }
        Thread {
            val fetched = try {
                GpsStreetHelper.fetchStreetContext(location.latitude, location.longitude, heading)
            } catch (_: Exception) {
                null
            }
            postWhenAlive {
                if (fetched == null) {
                    tts.speak("Nem sikerült lekérdezni a helyszínt.")
                } else {
                    GpsRadarStore.streetContext = fetched
                    tts.speak(GpsStreetHelper.speakWhereAmI(fetched, heading))
                }
            }
        }.start()
    }

    private fun toggleGpsStreetMonitoring() {
        GpsRadarStore.streetMonitoringEnabled = !GpsRadarStore.streetMonitoringEnabled
        if (GpsRadarStore.streetMonitoringEnabled) {
            if (!GpsSurroundingsManager.isRunning()) {
                startSurroundingsMonitoring()
            }
            tts.speak("Utcabemondás bekapcsolva. ${GpsStreetAnnouncer.introMessage()}")
        } else {
            tts.speak("Utcabemondás kikapcsolva. A környezeti figyelő továbbra is fut, de nem mond be utcaneveket.")
        }
    }

    private fun returnToGpsRadarBrowse(flow: AppFlow.GpsRadarContextMenu) {
        activeFlow = AppFlow.GpsRadarBrowse(flow.pois, flow.poiIndex)
        updateFlowDisplay()
        tts.speak("Vissza a helylistában.")
        speakGpsRadarPoi(flow.pois[flow.poiIndex])
    }

    private fun currentGpsPoiFromFlow(): GpsPoi? = when (val flow = activeFlow) {
        is AppFlow.GpsRadarBrowse -> flow.pois.getOrNull(flow.index)
        is AppFlow.GpsRadarGuiding -> flow.pois.getOrNull(flow.index) ?: GpsRadarStore.targetPoi
        is AppFlow.GpsRadarContextMenu -> flow.pois.getOrNull(flow.poiIndex)
        else -> GpsRadarStore.targetPoi
    }

    private fun requestGpsSaveCurrentPoi(fromAssistant: Boolean = false) {
        val poi = currentGpsPoiFromFlow()
        if (poi == null) {
            val message = "Előbb nyisd meg a G P S kitekintőt, és válassz egy helyet."
            if (fromAssistant) tts.speakThen(message) { resumeVoiceAssistantListening() }
            else tts.speak(message)
            return
        }
        val returnBrowse = (activeFlow as? AppFlow.GpsRadarBrowse)
        val returnGuiding = (activeFlow as? AppFlow.GpsRadarGuiding)
        saveGpsPoi(poi, returnBrowse, returnGuiding, fromAssistant)
    }

    private fun requestGpsSaveOwnLocation(fromAssistant: Boolean = false) {
        if (activeFlow !is AppFlow.GpsRadarBrowse &&
            activeFlow !is AppFlow.GpsRadarGuiding &&
            activeFlow !is AppFlow.GpsRadarContextMenu
        ) {
            val message = "A saját hely mentéséhez előbb nyisd meg a G P S kitekintőt."
            if (fromAssistant) tts.speakThen(message) { resumeVoiceAssistantListening() }
            else tts.speak(message)
            return
        }
        val returnBrowse = when (val flow = activeFlow) {
            is AppFlow.GpsRadarBrowse -> flow
            is AppFlow.GpsRadarContextMenu -> AppFlow.GpsRadarBrowse(flow.pois, flow.poiIndex)
            else -> null
        }
        val returnGuiding = activeFlow as? AppFlow.GpsRadarGuiding
        startGpsSaveOwnLocation(returnBrowse, returnGuiding, fromAssistant)
    }

    private fun saveCurrentGpsPoiFromGuiding(flow: AppFlow.GpsRadarGuiding) {
        val poi = flow.pois.getOrNull(flow.index) ?: GpsRadarStore.targetPoi
        if (poi == null) {
            tts.speak("Nincs menthető célpont.")
            return
        }
        saveGpsPoi(poi, returnBrowse = null, returnGuiding = flow)
    }

    private fun saveGpsPoiByIndex(
        pois: List<GpsPoi>,
        index: Int,
        returnBrowse: AppFlow.GpsRadarBrowse? = null,
        returnGuiding: AppFlow.GpsRadarGuiding? = null
    ) {
        val poi = pois.getOrNull(index) ?: return
        saveGpsPoi(poi, returnBrowse, returnGuiding)
    }

    private fun saveGpsPoi(
        poi: GpsPoi,
        returnBrowse: AppFlow.GpsRadarBrowse? = null,
        returnGuiding: AppFlow.GpsRadarGuiding? = null,
        fromAssistant: Boolean = false
    ) {
        if (SavedPoiStore.containsCoords(this, poi.latitude, poi.longitude)) {
            val message = "${poi.name} már mentve van a mentett helyek között."
            speakAfterGpsAction(message, returnBrowse, returnGuiding, fromAssistant)
            return
        }
        val saved = SavedPoiStore.add(
            this,
            name = poi.name,
            latitude = poi.latitude,
            longitude = poi.longitude,
            category = poi.category
        )
        if (saved == null) {
            speakAfterGpsAction("A hely mentése sikertelen.", returnBrowse, returnGuiding, fromAssistant, error = true)
            return
        }
        speakAfterGpsAction("${saved.name} elmentve a mentett helyek közé.", returnBrowse, returnGuiding, fromAssistant, success = true)
    }

    private fun startGpsSaveOwnLocation(
        returnBrowse: AppFlow.GpsRadarBrowse? = null,
        returnGuiding: AppFlow.GpsRadarGuiding? = null,
        fromAssistant: Boolean = false
    ) {
        if (!ensureLocationPermission()) {
            if (fromAssistant) resumeVoiceAssistantListening()
            return
        }
        voiceInput.cancel()
        cancelGpsRefining()
        activeFlow = AppFlow.GpsSaveRefining(returnBrowse, returnGuiding, fromAssistant)
        updateFlowDisplay()
        tts.speak("Saját hely mentése. Állj egy helyben, pontosság javítása.")
        var lastAnnouncedAccuracy = -1
        gpsRefineCancel = GpsAccuracyRefiner.refine(
            context = this,
            onProgress = { accuracy ->
                if (activeFlow !is AppFlow.GpsSaveRefining) return@refine
                if (accuracy == lastAnnouncedAccuracy) return@refine
                lastAnnouncedAccuracy = accuracy
                tts.speakAdd("Pontosság kb. $accuracy méter.")
            },
            onComplete = { result ->
                gpsRefineCancel = null
                val refining = activeFlow as? AppFlow.GpsSaveRefining ?: return@refine
                if (result == null) {
                    val message = "Helymeghatározás nem elérhető. Kapcsold be a G P S-t."
                    speakAfterGpsAction(message, refining.returnBrowse, refining.returnGuiding, refining.fromAssistant, error = true)
                    return@refine
                }
                if (SavedPoiStore.containsCoords(this, result.location.latitude, result.location.longitude)) {
                    val message = "Ez a hely már mentve van az egyéni helyek között."
                    speakAfterGpsAction(message, refining.returnBrowse, refining.returnGuiding, refining.fromAssistant)
                    return@refine
                }
                activeFlow = AppFlow.GpsRadarAwaitSaveName(
                    latitude = result.location.latitude,
                    longitude = result.location.longitude,
                    accuracyMeters = result.accuracyMeters,
                    category = "egyéni",
                    returnBrowse = refining.returnBrowse,
                    returnGuiding = refining.returnGuiding
                )
                updateFlowDisplay()
                val hint = GpsAccuracyRefiner.accuracyHint(result.accuracyMeters)
                tts.speakThen(hint) {
                    listenForGpsSaveOwnLocationName(activeFlow as AppFlow.GpsRadarAwaitSaveName, refining.fromAssistant)
                }
            }
        )
    }

    private fun listenForGpsSaveOwnLocationName(flow: AppFlow.GpsRadarAwaitSaveName, fromAssistant: Boolean) {
        ensureMicAndRun {
            voiceInput.listen(
                prompt = "Milyen néven mentsem a helyet?",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    if (activeFlow !is AppFlow.GpsRadarAwaitSaveName) return@listen
                    val name = spoken.trim()
                    if (name.isBlank()) {
                        tts.speak("A név üres. Mondd újra, milyen néven mentsem.")
                        listenForGpsSaveOwnLocationName(flow, fromAssistant)
                        return@listen
                    }
                    val saved = SavedPoiStore.add(
                        this,
                        name = name,
                        latitude = flow.latitude,
                        longitude = flow.longitude,
                        category = flow.category
                    )
                    if (saved == null) {
                        speakAfterGpsAction(
                            "A hely mentése sikertelen.",
                            flow.returnBrowse,
                            flow.returnGuiding,
                            fromAssistant,
                            error = true
                        )
                        return@listen
                    }
                    val accuracyNote = flow.accuracyMeters?.let { " Pontosság kb. $it méter." } ?: ""
                    speakAfterGpsAction(
                        "Egyéni hely mentve: ${saved.name}.$accuracyNote Megtalálod az egyéni helyek alatt.",
                        flow.returnBrowse,
                        flow.returnGuiding,
                        fromAssistant,
                        success = true,
                        returnNavWhere = flow.returnNavWhere
                    )
                },
                onError = {
                    if (activeFlow is AppFlow.GpsRadarAwaitSaveName) {
                        cancelGpsSaveOwnLocation(flow)
                    }
                }
            )
        }
    }

    private fun cancelGpsSaveOwnLocation(flow: AppFlow.GpsRadarAwaitSaveName) {
        voiceInput.cancel()
        when {
            flow.returnNavWhere != null -> {
                activeFlow = flow.returnNavWhere
                updateFlowDisplay()
                tts.speak("Mentés megszakítva.")
            }
            flow.returnGuiding != null -> {
                activeFlow = flow.returnGuiding
                updateFlowDisplay()
                tts.speak("Saját hely mentés megszakítva.")
            }
            flow.returnBrowse != null -> {
                activeFlow = flow.returnBrowse
                updateFlowDisplay()
                tts.speak("Saját hely mentés megszakítva.")
                speakGpsRadarPoi(flow.returnBrowse.pois[flow.returnBrowse.index])
            }
            else -> exitFlow("Saját hely mentés megszakítva.")
        }
    }

    private fun speakAfterGpsAction(
        message: String,
        returnBrowse: AppFlow.GpsRadarBrowse?,
        returnGuiding: AppFlow.GpsRadarGuiding?,
        fromAssistant: Boolean,
        success: Boolean = false,
        error: Boolean = false,
        returnNavWhere: AppFlow.NavWhereResult? = null
    ) {
        when {
            error -> feedbackError()
            success -> feedbackSuccess()
        }
        when {
            returnNavWhere != null -> exitFlow(message, success = success, error = error)
            returnGuiding != null -> {
                activeFlow = returnGuiding
                updateFlowDisplay()
                tts.speak(message)
            }
            returnBrowse != null -> {
                activeFlow = returnBrowse
                updateFlowDisplay()
                tts.speak(message)
            }
            fromAssistant -> tts.speakThen(message) { resumeVoiceAssistantListening() }
            else -> tts.speak(message)
        }
    }

    private fun startGpsSavedPoiFlow() {
        if (!ensureLocationPermission()) return
        val saved = SavedPoiStore.getAll(this)
        if (saved.isEmpty()) {
            tts.speak("Nincs egyéni hely. A Hol vagyok menüpontban vagy a G P S kitekintőben menthetsz helyeket.")
            return
        }
        activeFlow = AppFlow.GpsSavedPoiBrowse(saved, 0)
        updateFlowDisplay()
        tts.speak("${saved.size} egyéni hely. Söpörj fel-le választás, jobbra útmutatás, balra vissza.")
        tts.speakAdd(saved.first().speakPreview())
    }

    private fun navigateGpsSavedPoiList(flow: AppFlow.GpsSavedPoiBrowse, delta: Int) {
        val next = (flow.index + delta + flow.saved.size) % flow.saved.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.saved[next].speakPreview())
    }

    // ==================== HANGOS EMLÉKHELY (mentett pont műveletek) ====================

    private fun enterSavedPoiContextMenu(flow: AppFlow.GpsSavedPoiBrowse) {
        val poi = flow.saved[flow.index]
        val actions = SavedPoiContextAction.forPoi(poi.hasVoiceNote())
        activeFlow = AppFlow.SavedPoiContextMenu(flow.saved, flow.index, actions, 0)
        updateFlowDisplay()
        tts.speak("${poi.name} műveletei. Söpörj fel-le választás, jobbra végrehajtás, balra vissza.")
        tts.speakAdd(actions.first().label)
    }

    private fun navigateSavedPoiContextMenu(flow: AppFlow.SavedPoiContextMenu, delta: Int) {
        val next = (flow.actionIndex + delta + flow.actions.size) % flow.actions.size
        activeFlow = flow.copy(actionIndex = next)
        updateFlowDisplay()
        tts.speak(flow.actions[next].label)
    }

    private fun returnToSavedPoiBrowse(saved: List<SavedPoi>, poiIndex: Int) {
        val fresh = SavedPoiStore.getAll(this)
        if (fresh.isEmpty()) {
            exitFlow("Nincs több mentett hely.")
            return
        }
        val safeIndex = poiIndex.coerceIn(0, fresh.lastIndex)
        activeFlow = AppFlow.GpsSavedPoiBrowse(fresh, safeIndex)
        updateFlowDisplay()
        tts.speak(fresh[safeIndex].speakPreview())
    }

    private fun onSavedPoiContextActivate(flow: AppFlow.SavedPoiContextMenu) {
        val poi = flow.saved[flow.poiIndex]
        when (flow.actions[flow.actionIndex]) {
            SavedPoiContextAction.GUIDE -> {
                activeFlow = AppFlow.GpsSavedPoiBrowse(flow.saved, flow.poiIndex)
                startGuidanceToSavedPoi(AppFlow.GpsSavedPoiBrowse(flow.saved, flow.poiIndex))
            }
            SavedPoiContextAction.PLAY_VOICE_NOTE -> {
                val path = poi.voiceNotePath
                if (path.isNullOrBlank()) {
                    tts.speak("Ehhez a helyhez nincs hangjegyzet.")
                    return
                }
                tts.speak("Hangjegyzet lejátszása.")
                VoiceNoteRecorder.play(path) {
                    runOnUiThread { tts.speak("Hangjegyzet vége.") }
                }
            }
            SavedPoiContextAction.RECORD_VOICE_NOTE -> startSavedPoiVoiceRecording(flow)
            SavedPoiContextAction.DELETE_VOICE_NOTE -> {
                VoiceNoteRecorder.deleteFile(poi.voiceNotePath)
                SavedPoiStore.updateVoiceNote(this, poi.id, null)
                tts.speak("Hangjegyzet törölve.")
                returnToSavedPoiBrowse(SavedPoiStore.getAll(this), flow.poiIndex)
            }
            SavedPoiContextAction.DELETE_POI -> {
                VoiceNoteRecorder.deleteFile(poi.voiceNotePath)
                SavedPoiStore.remove(this, poi.id)
                tts.speak("${poi.name} törölve.")
                val remaining = SavedPoiStore.getAll(this)
                if (remaining.isEmpty()) exitFlow("Nincs több mentett hely.")
                else returnToSavedPoiBrowse(remaining, 0)
            }
        }
    }

    private fun startSavedPoiVoiceRecording(flow: AppFlow.SavedPoiContextMenu) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            tts.speak("Mikrofon engedély szükséges a hangjegyzethez.")
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), PERM_REQUEST)
            return
        }
        val poi = flow.saved[flow.poiIndex]
        // FONTOS: NINCS beszéd a felvétel indításakor — a TTS "mondd az
        // eligazítást" szövege rákerült a felvételre. Helyette egyetlen erőteljes
        // bleep jelzi az indulást, ÉS a felvétel csak a bleep UTÁN indul, hogy a
        // jelzőhang se kerüljön rá. A mentés/megszakítás gesztus változatlan.
        playRecordingStartBleep()
        Handler(Looper.getMainLooper()).postDelayed({
            if (!VoiceNoteRecorder.startRecording(this, poi.id)) {
                tts.speak("A hangfelvétel nem indult el.")
                return@postDelayed
            }
            activeFlow = AppFlow.SavedPoiVoiceRecording(flow.saved, flow.poiIndex)
            updateFlowDisplay()
        }, 350L)
    }

    /** Egyetlen erőteljes bleep a hangfelvétel indulásának jelzésére (beszéd nélkül). */
    private fun playRecordingStartBleep() {
        try {
            val tone = android.media.ToneGenerator(
                android.media.AudioManager.STREAM_MUSIC, 100
            )
            tone.startTone(android.media.ToneGenerator.TONE_PROP_BEEP, 200)
            Handler(Looper.getMainLooper()).postDelayed({ tone.release() }, 300L)
        } catch (_: Exception) {
        }
    }

    private fun stopAndSaveSavedPoiVoiceRecording(flow: AppFlow.SavedPoiVoiceRecording) {
        val poi = flow.saved[flow.poiIndex]
        val path = VoiceNoteRecorder.stopRecording()
        if (path == null) {
            tts.speak("A felvétel túl rövid vagy sikertelen volt.")
            returnToSavedPoiBrowse(SavedPoiStore.getAll(this), flow.poiIndex)
            return
        }
        // Régi hangjegyzet törlése, ha volt (felülírás)
        if (poi.hasVoiceNote() && poi.voiceNotePath != path) {
            VoiceNoteRecorder.deleteFile(poi.voiceNotePath)
        }
        SavedPoiStore.updateVoiceNote(this, poi.id, path)
        tts.speak("Hangjegyzet mentve a helyhez: ${poi.name}.")
        returnToSavedPoiBrowse(SavedPoiStore.getAll(this), flow.poiIndex)
    }

    private fun cancelSavedPoiVoiceRecording(flow: AppFlow.SavedPoiVoiceRecording) {
        VoiceNoteRecorder.cancelRecording()
        tts.speak("Felvétel megszakítva.")
        returnToSavedPoiBrowse(SavedPoiStore.getAll(this), flow.poiIndex)
    }

    private fun startGuidanceToSavedPoi(flow: AppFlow.GpsSavedPoiBrowse) {
        if (!ensureLocationPermission()) return
        val saved = flow.saved[flow.index]
        val location = GpsLocationHelper.getLastLocation(this)
        if (location == null) {
            tts.speak("Helymeghatározás nem elérhető.")
            return
        }
        val heading = radarCompass?.heading() ?: GpsRadarStore.lastHeading
        val poi = saved.toGpsPoi(location, heading)
        GpsRadarStore.lastLocation = location
        GpsRadarStore.lastHeading = heading
        GpsRadarStore.nearbyPois = listOf(poi)
        stopRadarRefreshLoop()
        stopRadarSensorsOnly()
        GpsRadarStore.approachSavedPoi = true
        GpsRadarStore.lastApproachThreshold = null
        if (!GpsSurroundingsManager.isRunning()) {
            startSurroundingsMonitoring()
        }
        GpsRadarManager.startGuidance(this, poi)
        activeFlow = AppFlow.GpsRadarGuiding(listOf(poi), 0)
        updateFlowDisplay()
        tts.speak(
            "Útmutatás a mentett helyhez: ${poi.speakRadar()} " +
                "Közeledéskor szólok: 50, 20, 10, 5 méter."
        )
    }

    // ==================== HELYSZÍN FELISMERŐ ====================

    private fun startLocationTrainFlow() {
        tts.speak("Helyszín tanítás indítása. Mutasd a kamerának a feliratot, majd jobbra söprés a rögzítéshez.")
        startActivity(LocationTrainerActivity.intent(this))
    }

    private fun startLocationWatchFlow() {
        val profiles = LocationProfileStore.getAll(this)
        if (profiles.isEmpty()) {
            tts.speak("Nincs mentett helyszín profil. Előbb taníts be egy helyet a Helyszín tanítása menüpontban.")
            return
        }
        tts.speak("Helyszín figyelő indítása. ${profiles.size} mentett profil figyelése.")
        startActivity(LocationWatchActivity.intentForAllProfiles(this))
    }

    private fun startLocationWatchTextFlow() {
        ensureMicAndRun {
            voiceInput.listen(
                prompt = "Mondd a figyelendő szöveget vagy feliratot.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val text = spoken.trim()
                    if (text.length < 4) {
                        tts.speak("A szöveg túl rövid. Mondd újra legalább négy karaktert.")
                        startLocationWatchTextFlow()
                        return@listen
                    }
                    tts.speak("Helyszín figyelő indítása szövegre: $text")
                    startActivity(LocationWatchActivity.intentForFreeText(this, text))
                },
                onError = { tts.speak("Nem értettem a szöveget.") }
            )
        }
    }

    private fun startLocationProfileListFlow(deleteMode: Boolean) {
        val profiles = LocationProfileStore.getAll(this)
        if (profiles.isEmpty()) {
            tts.speak("Nincs mentett helyszín profil.")
            return
        }
        activeFlow = AppFlow.LocationProfileBrowse(profiles, 0, deleteMode)
        updateFlowDisplay()
        val intro = if (deleteMode) {
            "${profiles.size} helyszín profil. Törlés mód. Söpörj fel-le választás, jobbra törlés megerősítése."
        } else {
            "${profiles.size} helyszín profil. Söpörj fel-le választás, jobbra műveletek: figyelő, fotók bővítése, fotók törlése."
        }
        tts.speak(intro)
        tts.speakAdd(profiles.first().speakPreview())
    }

    private fun navigateLocationProfileList(flow: AppFlow.LocationProfileBrowse, delta: Int) {
        val next = (flow.index + delta + flow.profiles.size) % flow.profiles.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.profiles[next].speakPreview())
    }

    private fun onLocationProfileListActivate(flow: AppFlow.LocationProfileBrowse) {
        val profile = flow.profiles[flow.index]
        if (flow.deleteMode) {
            enterLocationProfileDeleteConfirm(profile, flow.profiles, flow.index)
        } else {
            enterLocationProfileActions(profile, flow.profiles, flow.index)
        }
    }

    private fun enterLocationProfileActions(
        profile: LocationProfile,
        profiles: List<LocationProfile>,
        index: Int
    ) {
        activeFlow = AppFlow.LocationProfileActions(profile, profiles, index, 0)
        updateFlowDisplay()
        tts.speak(
            "${profile.speakPreview()}. ${AppFlow.LocationProfileActions.OPTIONS.first()}. " +
                "Söpörj fel-le művelet választás, jobbra végrehajtás, balra vissza."
        )
    }

    private fun navigateLocationProfileActions(flow: AppFlow.LocationProfileActions, delta: Int) {
        val options = AppFlow.LocationProfileActions.OPTIONS
        val next = (flow.actionIndex + delta + options.size) % options.size
        activeFlow = flow.copy(actionIndex = next)
        updateFlowDisplay()
        tts.speak(options[next])
    }

    private fun onLocationProfileActionActivate(flow: AppFlow.LocationProfileActions) {
        when (flow.actionIndex) {
            0 -> startLocationWatchForProfile(flow.profile)
            1 -> {
                tts.speak("Fotók bővítése: ${flow.profile.name}")
                startActivity(LocationTrainerActivity.intentForEdit(this, flow.profile.id))
            }
            2 -> {
                if (flow.profile.referenceImagePaths.isEmpty()) {
                    tts.speak("Ehhez a helyszínhez nincs mentett fotó.")
                } else {
                    tts.speak("Fotók törlése: ${flow.profile.name}")
                    startActivity(LocationProfilePhotosActivity.intent(this, flow.profile.id))
                }
            }
        }
    }

    private fun enterLocationProfileDeleteConfirm(
        profile: LocationProfile,
        profiles: List<LocationProfile>,
        index: Int
    ) {
        activeFlow = AppFlow.LocationProfileDeleteConfirm(profile, profiles, index)
        updateFlowDisplay()
        repeatLocationProfileDeleteConfirm(profile)
    }

    private fun repeatLocationProfileDeleteConfirm(profile: LocationProfile) {
        tts.speak(
            "Törlöd ezt a helyszín profilt? ${profile.speakPreview()}. Söpörj jobbra a törléshez, söprés balra a mégsehez."
        )
    }

    private fun deleteLocationProfile(flow: AppFlow.LocationProfileDeleteConfirm) {
        LocationProfileStore.remove(this, flow.profile.id)
        val updated = LocationProfileStore.getAll(this)
        if (updated.isEmpty()) {
            exitFlow("Helyszín profil törölve: ${flow.profile.speakPreview()}. Nincs több mentett profil.")
            return
        }
        val newIndex = flow.index.coerceAtMost(updated.lastIndex)
        activeFlow = AppFlow.LocationProfileBrowse(updated, newIndex, deleteMode = true)
        updateFlowDisplay()
        tts.speak("Helyszín profil törölve: ${flow.profile.speakPreview()}.")
        tts.speakAdd(updated[newIndex].speakPreview())
    }

    private fun startLocationWatchForProfile(profile: LocationProfile) {
        tts.speak("Helyszín figyelő indítása: ${profile.name}")
        startActivity(LocationWatchActivity.intentForProfile(this, profile.id))
    }

    private fun stopLocationWatchFlow() {
        if (LocationWatchState.isActive()) {
            LocationWatchState.clear()
            tts.speak("Helyszín figyelő leállítva.")
        } else {
            tts.speak("Nincs aktív helyszín figyelő.")
        }
    }

    private fun startGpsArrivalLocationPrompt(destinationName: String) {
        GpsRadarStore.pendingArrivalPrompt = null
        activeFlow = AppFlow.GpsArrivalLocationPrompt(destinationName, 0)
        updateFlowDisplay()
        tts.speak(
            "Megérkeztél: $destinationName. Szeretnéd a helyszín felismerőt használni? " +
                AppFlow.GpsArrivalLocationPrompt.OPTIONS.first() +
                ". Söpörj fel-le választás, jobbra megerősítés, balra kihagyás."
        )
    }

    private fun navigateGpsArrivalPrompt(flow: AppFlow.GpsArrivalLocationPrompt, delta: Int) {
        val options = AppFlow.GpsArrivalLocationPrompt.OPTIONS
        val next = (flow.index + delta + options.size) % options.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(options[next])
    }

    private fun activateGpsArrivalPrompt(flow: AppFlow.GpsArrivalLocationPrompt) {
        when (flow.index) {
            0 -> startLocationWatchFlow()
            1 -> startLocationTrainFlow()
            else -> tts.speak("Rendben, helyszín felismerő nélkül.")
        }
        if (activeFlow is AppFlow.GpsArrivalLocationPrompt) {
            activeFlow = AppFlow.Menu
            updateDisplay()
        }
    }

    // ==================== KÁRTYA RENDSZEREZŐ ====================

    private fun startCardTrainFlow() {
        tts.speak("Kártya hozzáadása. Először fotózd le az elejét, majd a hátulját, végül add meg a nevét.")
        startActivity(CardTrainerActivity.intent(this))
    }

    private fun startCardRecognizeFlow() {
        val cards = CardStore.getAll(this)
        if (cards.isEmpty()) {
            tts.speak("Nincs mentett kártya. Előbb adj hozzá egyet az Új kártya menüpontban.")
            return
        }
        tts.speak("Kártya felismerő indítása. ${cards.size} mentett kártya.")
        startActivity(CardRecognizerActivity.intent(this))
    }

    private fun startCardListFlow(deleteMode: Boolean) {
        val cards = CardStore.getAll(this)
        if (cards.isEmpty()) {
            tts.speak("Nincs mentett kártya.")
            return
        }
        activeFlow = AppFlow.CardBrowse(cards, 0, deleteMode)
        updateFlowDisplay()
        val intro = if (deleteMode) {
            "${cards.size} kártya. Törlés mód. Söpörj fel-le választás, jobbra törlés."
        } else {
            "${cards.size} kártya. Söpörj fel-le böngészés."
        }
        tts.speak(intro)
        tts.speakAdd(cards.first().speakPreview())
    }

    private fun navigateCardList(flow: AppFlow.CardBrowse, delta: Int) {
        val next = (flow.index + delta + flow.cards.size) % flow.cards.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.cards[next].speakPreview())
    }

    private fun onCardListActivate(flow: AppFlow.CardBrowse) {
        val card = flow.cards[flow.index]
        if (flow.deleteMode) {
            enterCardDeleteConfirm(card, flow.cards, flow.index)
        } else {
            tts.speak(card.speakPreview())
        }
    }

    private fun enterCardDeleteConfirm(card: CardProfile, cards: List<CardProfile>, index: Int) {
        activeFlow = AppFlow.CardDeleteConfirm(card, cards, index)
        updateFlowDisplay()
        repeatCardDeleteConfirm(card)
    }

    private fun repeatCardDeleteConfirm(card: CardProfile) {
        tts.speak("Törlöd ezt a kártyát? ${card.speakPreview()}. Söpörj jobbra a törléshez, balra a mégsehez.")
    }

    private fun deleteCard(flow: AppFlow.CardDeleteConfirm) {
        CardStore.remove(this, flow.card.id)
        val updated = CardStore.getAll(this)
        if (updated.isEmpty()) {
            exitFlow("Kártya törölve: ${flow.card.speakPreview()}. Nincs több mentett kártya.")
            return
        }
        val newIndex = flow.index.coerceAtMost(updated.lastIndex)
        activeFlow = AppFlow.CardBrowse(updated, newIndex, deleteMode = true)
        updateFlowDisplay()
        tts.speak("Kártya törölve: ${flow.card.speakPreview()}.")
        tts.speakAdd(updated[newIndex].speakPreview())
    }

    // ==================== ARC KAMERA ====================

    private fun startFaceCameraFlow(selfie: Boolean = false) {
        val message = if (selfie) {
            "Kamera indítása szelfi módban."
        } else {
            "Kamera indítása."
        }
        tts.speak(message)
        startActivity(
            Intent(this, FaceCameraActivity::class.java)
                .putExtra(FaceCameraActivity.EXTRA_SELFIE_MODE, selfie)
        )
    }

    private fun startCameraQualityFlow() {
        val profiles = CameraQualityProfile.entries
        val current = CameraQualityStore.load(this)
        val index = profiles.indexOf(current).coerceAtLeast(0)
        activeFlow = AppFlow.CameraQualityBrowse(profiles, index)
        updateFlowDisplay()
        tts.speak("Kamera minőség beállítás. Söpörj fel-le választás, jobbra mentés, balra vissza.")
        tts.speakAdd(profiles[index].speakSummary())
    }

    private fun navigateCameraQuality(flow: AppFlow.CameraQualityBrowse, delta: Int) {
        val next = (flow.index + delta + flow.profiles.size) % flow.profiles.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.profiles[next].speakSummary())
    }

    private fun applyCameraQuality(flow: AppFlow.CameraQualityBrowse) {
        val profile = flow.profiles[flow.index]
        CameraQualityStore.updateProfile(this, profile)
        exitFlow("Kamera minőség mentve: ${profile.speakSummary()}.", success = true)
    }

    // ==================== GPS ÚTVONAL ====================

    private fun startGpsRouteRecordFlow() {
        if (!ensureLocationPermission()) return
        if (GpsRouteSession.isRecording) {
            activeFlow = AppFlow.GpsRouteRecordingActive
            updateFlowDisplay()
            speakGpsRouteStatus()
            return
        }
        if (GpsRouteSession.isGuiding) {
            tts.speak("Előbb állítsd le az aktív útvonal útmutatást.")
            return
        }
        GpsRouteStore.startRecording(this, "Útvonal")
        activeFlow = AppFlow.GpsRouteRecordingActive
        updateFlowDisplay()
        tts.speak("G P S útvonal rögzítés elindult. Söpörj fel-le állapot, jobbra útpont, balra mentés.")
        speakGpsRouteStatus()
    }

    private fun speakGpsRouteStatus() {
        if (!GpsRouteSession.isRecording) {
            tts.speak("Nincs aktív útvonal rögzítés.")
            return
        }
        val points = GpsRouteSession.points.size
        val waypoints = GpsRouteSession.events.count { it.type == RouteEventType.WAYPOINT }
        val turns = GpsRouteSession.events.count {
            it.type == RouteEventType.TURN_LEFT ||
                it.type == RouteEventType.TURN_RIGHT ||
                it.type == RouteEventType.TURN_SLIGHT ||
                it.type == RouteEventType.U_TURN
        }
        tts.speak(
            "Útvonal rögzítés: $points pont, $waypoints jelölő, $turns kanyar."
        )
    }

    private fun addGpsRouteWaypoint() {
        if (!GpsRouteSession.isRecording) {
            tts.speak("Nincs aktív útvonal rögzítés.")
            return
        }
        val point = GpsRouteSession.points.lastOrNull()
        if (point == null) {
            tts.speak("Még nincs rögzített pont. Menj egy kicsit, majd próbáld újra.")
            return
        }
        val waypointIndex = GpsRouteSession.events.count { it.type == RouteEventType.WAYPOINT } + 1
        GpsRouteSession.events.add(
            RouteEvent(
                type = RouteEventType.WAYPOINT,
                latitude = point.latitude,
                longitude = point.longitude,
                timestampMs = System.currentTimeMillis(),
                label = "út pont $waypointIndex"
            )
        )
        feedbackSuccess()
        tts.speak("Útpont rögzítve: út pont $waypointIndex.")
    }

    private fun stopGpsRouteRecordingAndSave() {
        if (!GpsRouteSession.isRecording) {
            exitFlow("Nincs aktív útvonal rögzítés.")
            return
        }
        val route = GpsRouteStore.stopRecording(this)
        if (route == null) {
            exitFlow("Az útvonal túl rövid, nem menthető.")
            return
        }
        activeFlow = AppFlow.GpsRouteAwaitName(route)
        updateFlowDisplay()
        listenForGpsRouteName(route)
    }

    private fun listenForGpsRouteName(route: GpsRouteRecording) {
        ensureMicAndRun {
            voiceInput.listen(
                prompt = "Mondd az útvonal nevét.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    if (activeFlow !is AppFlow.GpsRouteAwaitName) return@listen
                    val name = spoken.trim().ifBlank { route.name }
                    val saved = GpsRouteStore.save(this, route.copy(name = name))
                    exitFlow(
                        "Útvonal mentve: ${saved.speakPreview()}. Távolság kb. ${saved.totalDistanceMeters()} méter.",
                        success = true
                    )
                },
                onError = {
                    val saved = GpsRouteStore.save(this, route)
                    exitFlow("Útvonal mentve alapértelmezett névvel: ${saved.speakPreview()}.")
                }
            )
        }
    }

    private fun stopGpsRouteOrGuidanceFlow() {
        when {
            GpsRouteSession.isRecording -> stopGpsRouteRecordingAndSave()
            GpsRouteSession.isGuiding -> stopGpsRouteGuidance()
            activeFlow is AppFlow.GpsRouteGuidingActive -> stopGpsRouteGuidance()
            else -> tts.speak("Nincs aktív útvonal rögzítés vagy útmutatás.")
        }
    }

    private fun startGpsRouteListFlow(deleteMode: Boolean, guideMode: Boolean = false) {
        val routes = GpsRouteStore.getAll(this)
        if (routes.isEmpty()) {
            tts.speak("Nincs mentett G P S útvonal.")
            return
        }
        activeFlow = AppFlow.GpsRouteBrowse(routes, 0, deleteMode, guideMode)
        updateFlowDisplay()
        val intro = when {
            deleteMode -> "${routes.size} mentett útvonal. Törlés mód. Söpörj fel-le választás, jobbra törlés megerősítése."
            guideMode -> "${routes.size} mentett útvonal. Útmutatás mód. Söpörj fel-le választás, jobbra útmutatás indítása."
            else -> "${routes.size} mentett útvonal. Söpörj fel-le választás, jobbra felolvasás."
        }
        tts.speak(intro)
        speakGpsRoutePreview(routes.first())
    }

    private fun navigateGpsRouteList(flow: AppFlow.GpsRouteBrowse, delta: Int) {
        val next = (flow.index + delta + flow.routes.size) % flow.routes.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        speakGpsRoutePreview(flow.routes[next])
    }

    private fun speakGpsRoutePreview(route: GpsRouteRecording) {
        val distance = route.totalDistanceMeters()
        tts.speak("${route.speakPreview()}. Távolság kb. $distance méter, ${route.points.size} pont.")
    }

    private fun onGpsRouteListActivate(flow: AppFlow.GpsRouteBrowse) {
        val route = flow.routes[flow.index]
        when {
            flow.deleteMode -> enterGpsRouteDeleteConfirm(route, flow.routes, flow.index)
            flow.guideMode -> startGpsRouteGuide(route)
            else -> speakGpsRoutePreview(route)
        }
    }

    private fun enterGpsRouteDeleteConfirm(
        route: GpsRouteRecording,
        routes: List<GpsRouteRecording>,
        index: Int
    ) {
        activeFlow = AppFlow.GpsRouteDeleteConfirm(route, routes, index)
        updateFlowDisplay()
        repeatGpsRouteDeleteConfirm(route)
    }

    private fun repeatGpsRouteDeleteConfirm(route: GpsRouteRecording) {
        tts.speak(
            "Törlöd ezt az útvonalat? ${route.speakPreview()}. Söpörj jobbra a törléshez, söprés balra a mégsehez."
        )
    }

    private fun deleteGpsRoute(flow: AppFlow.GpsRouteDeleteConfirm) {
        GpsRouteStore.remove(this, flow.route.id)
        val updated = GpsRouteStore.getAll(this)
        if (updated.isEmpty()) {
            exitFlow("Útvonal törölve: ${flow.route.speakPreview()}. Nincs több mentett útvonal.")
            return
        }
        val newIndex = flow.index.coerceAtMost(updated.lastIndex)
        activeFlow = AppFlow.GpsRouteBrowse(updated, newIndex, deleteMode = true, guideMode = false)
        updateFlowDisplay()
        tts.speak("Útvonal törölve: ${flow.route.speakPreview()}.")
        speakGpsRoutePreview(updated[newIndex])
    }

    private fun startGpsRouteGuide(route: GpsRouteRecording) {
        if (!ensureLocationPermission()) return
        if (GpsRouteSession.isRecording) {
            tts.speak("Előbb állítsd le az aktív útvonal rögzítést.")
            return
        }
        if (route.points.size < 2) {
            tts.speak("Az útvonal túl rövid az útmutatáshoz.")
            return
        }
        GpsRouteStore.startGuidance(this, route)
        activeFlow = AppFlow.GpsRouteGuidingActive(route)
        updateFlowDisplay()
        tts.speak("Útvonal útmutatás elindult: ${route.speakPreview()}. Balra söprés a leállításhoz.")
    }

    private fun stopGpsRouteGuidance() {
        val routeName = (activeFlow as? AppFlow.GpsRouteGuidingActive)?.route?.speakPreview()
            ?: GpsRouteSession.activeRoute?.speakPreview()
            ?: "útvonal"
        GpsRouteStore.stopGuidance(this)
        exitFlow("Útvonal útmutatás leállítva: $routeName.")
    }

    // ==================== PROFI DIKTAFON ====================

    private fun startDictaphoneRecordingFlow() {
        if (!ensureMicPermission()) return
        if (DictaphoneManager.isRecording()) {
            activeFlow = AppFlow.DictaphoneRecording
            updateFlowDisplay()
            playDictaphoneRecordingBeep()
            return
        }
        if (!DictaphoneManager.startRecording(this)) {
            feedbackError()
            val detail = DictaphoneManager.lastError()
                ?: "Felvétel indítása sikertelen. Ellenőrizd a mikrofont és a tárhelyet."
            tts.speak(detail)
            return
        }
        activeFlow = AppFlow.DictaphoneRecording
        updateFlowDisplay()
        startDictaphoneElapsedLoop()
        playDictaphoneRecordingBeep()
    }

    private fun playDictaphoneRecordingBeep() {
        sounds.play(SoundType.ACTION_OK, 1f)
    }

    private fun ensureMicPermission(): Boolean {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        ) {
            return true
        }
        tts.speak("Mikrofon engedély szükséges a felvételhez.")
        ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), PERM_REQUEST)
        return false
    }

    private fun startDictaphoneElapsedLoop() {
        stopDictaphoneElapsedLoop()
        val runnable = object : Runnable {
            override fun run() {
                if (activeFlow !is AppFlow.DictaphoneRecording) return
                val failure = DictaphoneManager.consumeRecordingFailure()
                if (failure != null) {
                    stopDictaphoneElapsedLoop()
                    DictaphoneManager.cancelRecording(this@MainActivity)
                    exitFlow(failure, error = true)
                    return
                }
                updateFlowDisplay()
                mainHandler.postDelayed(this, 1_000L)
            }
        }
        dictaphoneElapsedRunnable = runnable
        mainHandler.postDelayed(runnable, 1_000L)
    }

    private fun stopDictaphoneElapsedLoop() {
        dictaphoneElapsedRunnable?.let { mainHandler.removeCallbacks(it) }
        dictaphoneElapsedRunnable = null
    }

    private fun speakDictaphoneElapsed() {
        tts.speak(DictaphoneSpeech.speakElapsed(DictaphoneManager.elapsedMillis(), DictaphoneManager.isPaused()))
    }

    private fun toggleDictaphonePause() {
        if (!DictaphoneManager.isRecording()) return
        DictaphoneManager.togglePause()
        updateFlowDisplay()
        playDictaphoneRecordingBeep()
    }

    private fun stopDictaphoneRecording(save: Boolean) {
        stopDictaphoneElapsedLoop()
        if (!DictaphoneManager.isRecording()) {
            exitFlow("Nincs aktív felvétel.")
            return
        }
        if (!save) {
            DictaphoneManager.cancelRecording(this)
            exitFlow("Felvétel megszakítva.")
            return
        }
        tts.speak("Felvétel mentése. Várj.")
        Thread {
            val entry = DictaphoneManager.stopAndSave(this@MainActivity)
            postWhenAlive {
                if (entry == null) {
                    val detail = DictaphoneManager.lastError() ?: "Felvétel mentése sikertelen."
                    exitFlow(detail, error = true)
                } else {
                    exitFlow(DictaphoneSpeech.speakSaved(entry), success = true)
                }
            }
        }.start()
    }

    private fun startDictaphoneSettingsFlow() {
        val options = DictaphoneSettingsOption.entries
        val config = DictaphoneSettingsStore.load(this)
        activeFlow = AppFlow.DictaphoneSettingsBrowse(options.toList(), 0)
        updateFlowDisplay()
        tts.speak(DictaphoneSpeech.speakSettingsIntro(config))
        speakDictaphoneSettingOption(options.first(), config)
    }

    private fun navigateDictaphoneSettings(flow: AppFlow.DictaphoneSettingsBrowse, delta: Int) {
        val next = (flow.index + delta + flow.options.size) % flow.options.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        val config = DictaphoneSettingsStore.load(this)
        speakDictaphoneSettingOption(flow.options[next], config)
    }

    private fun speakDictaphoneSettingOption(option: DictaphoneSettingsOption, config: com.superdl.launcher.dictaphone.DictaphoneConfig) {
        if (option == DictaphoneSettingsOption.NOISE_SUPPRESSION) {
            tts.speak(ToggleAnnouncement.speakFocusedState("Zajszűrés", config.noiseSuppressionEnabled))
        } else {
            tts.speak("${option.label}. Aktuális: ${option.speakCurrent(config)}")
        }
    }

    private fun onDictaphoneSettingsActivate(flow: AppFlow.DictaphoneSettingsBrowse) {
        val option = flow.options[flow.index]
        val config = DictaphoneSettingsStore.load(this)
        when (option) {
            DictaphoneSettingsOption.FORMAT -> {
                val formats = DictaphoneFormat.entries.toList()
                activeFlow = AppFlow.DictaphoneFormatBrowse(formats, config.format.ordinal.coerceIn(0, formats.lastIndex))
                updateFlowDisplay()
                tts.speak("Formátum választása. ${formats[(activeFlow as AppFlow.DictaphoneFormatBrowse).index].speakSummary()}")
            }
            DictaphoneSettingsOption.SAMPLE_RATE -> {
                val rates = DictaphoneSampleRate.entries.toList()
                activeFlow = AppFlow.DictaphoneSampleRateBrowse(rates, config.sampleRate.ordinal.coerceIn(0, rates.lastIndex))
                updateFlowDisplay()
                tts.speak("Mintavételi frekvencia. ${rates[(activeFlow as AppFlow.DictaphoneSampleRateBrowse).index].speakSummary()}")
            }
            DictaphoneSettingsOption.BITRATE -> {
                if (!config.format.isCompressed()) {
                    tts.speak("Bitráta csak M P 3 és A A C formátumnál állítható.")
                    return
                }
                val bitrates = DictaphoneBitrate.entries.toList()
                activeFlow = AppFlow.DictaphoneBitrateBrowse(bitrates, config.bitrate.ordinal.coerceIn(0, bitrates.lastIndex))
                updateFlowDisplay()
                tts.speak("Bitráta. ${bitrates[(activeFlow as AppFlow.DictaphoneBitrateBrowse).index].speakSummary()}")
            }
            DictaphoneSettingsOption.CHANNELS -> {
                val channels = DictaphoneChannels.entries.toList()
                activeFlow = AppFlow.DictaphoneChannelsBrowse(channels, config.channels.ordinal.coerceIn(0, channels.lastIndex))
                updateFlowDisplay()
                tts.speak("Csatornák. ${channels[(activeFlow as AppFlow.DictaphoneChannelsBrowse).index].speakSummary()}")
            }
            DictaphoneSettingsOption.NOISE_SUPPRESSION -> {
                val label = "Zajszűrés"
                val wasEnabled = config.noiseSuppressionEnabled
                tts.speak(ToggleAnnouncement.speakBinaryToggle(label, wasEnabled))
                val enabled = DictaphoneSettingsStore.toggleNoiseSuppression(this)
                val extra = if (enabled) {
                    "Bekapcsolva. Visszhang- és zajszűrő aktív. ${DictaphoneAudioEffects.speakAvailability()}"
                } else {
                    "Kikapcsolva. Nyers, szűretlen környezeti hang rögzítése."
                }
                tts.speak(ToggleAnnouncement.speakAfterToggle(label, enabled, extra))
                activeFlow = flow
                updateFlowDisplay()
            }
        }
    }

    private fun returnToDictaphoneSettings() {
        val options = DictaphoneSettingsOption.entries.toList()
        val config = DictaphoneSettingsStore.load(this)
        activeFlow = AppFlow.DictaphoneSettingsBrowse(options, 0)
        updateFlowDisplay()
        tts.speak("Vissza a beállításokhoz. ${options.first().label}.")
        speakDictaphoneSettingOption(options.first(), config)
    }

    private fun navigateDictaphoneFormat(flow: AppFlow.DictaphoneFormatBrowse, delta: Int) {
        val next = (flow.index + delta + flow.formats.size) % flow.formats.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.formats[next].speakSummary())
    }

    private fun applyDictaphoneFormat(flow: AppFlow.DictaphoneFormatBrowse) {
        val format = flow.formats[flow.index]
        DictaphoneSettingsStore.updateFormat(this, format)
        tts.speak("Formátum mentve: ${format.speakSummary()}.")
        returnToDictaphoneSettings()
    }

    private fun navigateDictaphoneSampleRate(flow: AppFlow.DictaphoneSampleRateBrowse, delta: Int) {
        val next = (flow.index + delta + flow.rates.size) % flow.rates.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.rates[next].speakSummary())
    }

    private fun applyDictaphoneSampleRate(flow: AppFlow.DictaphoneSampleRateBrowse) {
        val rate = flow.rates[flow.index]
        DictaphoneSettingsStore.updateSampleRate(this, rate)
        tts.speak("Mintavételi frekvencia mentve: ${rate.speakSummary()}.")
        returnToDictaphoneSettings()
    }

    private fun navigateDictaphoneBitrate(flow: AppFlow.DictaphoneBitrateBrowse, delta: Int) {
        val next = (flow.index + delta + flow.bitrates.size) % flow.bitrates.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.bitrates[next].speakSummary())
    }

    private fun applyDictaphoneBitrate(flow: AppFlow.DictaphoneBitrateBrowse) {
        val bitrate = flow.bitrates[flow.index]
        DictaphoneSettingsStore.updateBitrate(this, bitrate)
        tts.speak("Bitráta mentve: ${bitrate.speakSummary()}.")
        returnToDictaphoneSettings()
    }

    private fun navigateDictaphoneChannels(flow: AppFlow.DictaphoneChannelsBrowse, delta: Int) {
        val next = (flow.index + delta + flow.channels.size) % flow.channels.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.channels[next].speakSummary())
    }

    private fun applyDictaphoneChannels(flow: AppFlow.DictaphoneChannelsBrowse) {
        val channels = flow.channels[flow.index]
        DictaphoneSettingsStore.updateChannels(this, channels)
        tts.speak("Csatorna mentve: ${channels.speakSummary()}.")
        returnToDictaphoneSettings()
    }

    private fun startDictaphoneLibraryFlow() {
        val recordings = DictaphoneLibrary.listRecordings(this)
        if (recordings.isEmpty()) {
            tts.speak("Nincs mentett felvétel.")
            return
        }
        activeFlow = AppFlow.DictaphoneRecordingsBrowse(recordings, 0)
        updateFlowDisplay()
        tts.speak("${recordings.size} mentett felvétel. Söpörj fel-le választás, jobbra műveletek, balra vissza.")
        tts.speakAdd(recordings.first().speakSummary())
    }

    private fun navigateDictaphoneRecordings(flow: AppFlow.DictaphoneRecordingsBrowse, delta: Int) {
        val next = (flow.index + delta + flow.recordings.size) % flow.recordings.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.recordings[next].speakSummary())
    }

    private fun playDictaphoneRecording(entry: DictaphoneRecordingEntry) {
        tts.speakThen("Lejátszás: ${entry.displayName()}.") {
            DictaphonePlayback.play(this, entry) {
                postWhenAlive {
                    if (activeFlow is AppFlow.DictaphoneRecordingsBrowse ||
                        activeFlow is AppFlow.DictaphoneRecordingContextMenu
                    ) {
                        tts.speak("Lejátszás vége.")
                    }
                }
            }
        }
    }

    private fun enterDictaphoneRecordingContextMenu(flow: AppFlow.DictaphoneRecordingsBrowse) {
        val actions = DictaphoneRecordingContextAction.all
        activeFlow = AppFlow.DictaphoneRecordingContextMenu(
            flow.recordings,
            flow.index,
            actions,
            0
        )
        updateFlowDisplay()
        val entry = flow.recordings[flow.index]
        tts.speak(
            "Felvétel műveletek: ${entry.displayName()}. ${actions.first().label}. " +
                "Söpörj fel-le választás, jobbra végrehajtás, balra vissza."
        )
    }

    private fun navigateDictaphoneRecordingContextMenu(flow: AppFlow.DictaphoneRecordingContextMenu, delta: Int) {
        val next = (flow.actionIndex + delta + flow.actions.size) % flow.actions.size
        activeFlow = flow.copy(actionIndex = next)
        updateFlowDisplay()
        tts.speak(flow.actions[next].label)
    }

    private fun onDictaphoneRecordingContextActivate(flow: AppFlow.DictaphoneRecordingContextMenu) {
        val entry = flow.recordings[flow.recordingIndex]
        when (flow.actions[flow.actionIndex]) {
            DictaphoneRecordingContextAction.PLAY -> playDictaphoneRecording(entry)
            DictaphoneRecordingContextAction.SHARE_EMAIL -> {
                dictaphoneShareReturnBrowse = AppFlow.DictaphoneRecordingsBrowse(flow.recordings, flow.recordingIndex)
                startDictaphoneShareEmailFlow(entry)
            }
            DictaphoneRecordingContextAction.SHARE_SYSTEM -> shareDictaphoneViaSystem(entry, flow)
            DictaphoneRecordingContextAction.DELETE -> enterDictaphoneRecordingDeleteConfirm(flow.recordings, flow.recordingIndex)
        }
    }

    private fun enterDictaphoneRecordingDeleteConfirm(
        recordings: List<DictaphoneRecordingEntry>,
        index: Int
    ) {
        activeFlow = AppFlow.DictaphoneRecordingDeleteConfirm(recordings, index)
        updateFlowDisplay()
        repeatDictaphoneRecordingDeleteConfirm(AppFlow.DictaphoneRecordingDeleteConfirm(recordings, index))
    }

    private fun repeatDictaphoneRecordingDeleteConfirm(flow: AppFlow.DictaphoneRecordingDeleteConfirm) {
        val entry = flow.recordings[flow.recordingIndex]
        tts.speak(
            "Biztosan törlöd: ${entry.displayName()}? Söpörj jobbra a törléshez, söprés balra a mégsehez."
        )
    }

    private fun deleteDictaphoneRecording(flow: AppFlow.DictaphoneRecordingDeleteConfirm) {
        val entry = flow.recordings[flow.recordingIndex]
        DictaphonePlayback.stop()
        val ok = DictaphoneLibrary.delete(entry)
        if (!ok) {
            tts.speak("Felvétel törlése sikertelen.")
            returnToDictaphoneRecordingsBrowse(
                AppFlow.DictaphoneRecordingContextMenu(
                    flow.recordings,
                    flow.recordingIndex,
                    DictaphoneRecordingContextAction.all,
                    0
                )
            )
            return
        }
        feedbackSuccess()
        val updated = DictaphoneLibrary.listRecordings(this)
        if (updated.isEmpty()) {
            exitFlow("Felvétel törölve. Nincs több mentett felvétel.", success = true)
            return
        }
        val newIndex = flow.recordingIndex.coerceAtMost(updated.lastIndex)
        activeFlow = AppFlow.DictaphoneRecordingsBrowse(updated, newIndex)
        updateFlowDisplay()
        tts.speak("Felvétel törölve.")
        tts.speakAdd(updated[newIndex].speakSummary())
    }

    private fun returnToDictaphoneRecordingsBrowse(flow: AppFlow.DictaphoneRecordingContextMenu) {
        activeFlow = AppFlow.DictaphoneRecordingsBrowse(flow.recordings, flow.recordingIndex)
        updateFlowDisplay()
        tts.speak("Vissza a felvételek között.")
        tts.speakAdd(flow.recordings[flow.recordingIndex].speakSummary())
    }

    private fun shareDictaphoneViaSystem(
        entry: DictaphoneRecordingEntry,
        returnFlow: AppFlow.DictaphoneRecordingContextMenu
    ) {
        val ok = DictaphoneShareHelper.shareViaSystem(this, entry)
        if (!ok) {
            tts.speak("Megosztás sikertelen. A fájl nem elérhető.")
        } else {
            tts.speak("Megosztás indítva. Válaszd ki az alkalmazást, például Bluetooth-ot.")
        }
        returnToDictaphoneRecordingsBrowse(returnFlow)
    }

    private fun startDictaphoneShareEmailFlow(entry: DictaphoneRecordingEntry) {
        if (!EmailHelper.isConfigured(this)) {
            tts.speakThen(
                "Előbb állítsd be az e-mail küldőt a menüben: E-mail küldő beállítása."
            ) {
                startEmailSmtpSetupFlow()
            }
            return
        }
        if (!entry.file.exists() || entry.file.length() <= 0L) {
            tts.speak("A felvétel fájl nem elérhető.")
            cancelDictaphoneShareEmail()
            return
        }
        ensureMicAndRun {
            activeFlow = AppFlow.DictaphoneShareEmailAwaitRecipient(entry)
            updateFlowDisplay()
            listenForDictaphoneShareEmailRecipient(entry)
        }
    }

    private fun listenForDictaphoneShareEmailRecipient(entry: DictaphoneRecordingEntry) {
        voiceInput.listen(
            prompt = "Mondd a címzett nevét vagy e-mail címét a felvétel küldéséhez.",
            speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
            onResult = { spoken -> resolveDictaphoneShareEmailRecipient(entry, spoken) },
            onError = { cancelDictaphoneShareEmail() }
        )
    }

    private fun resolveDictaphoneShareEmailRecipient(entry: DictaphoneRecordingEntry, spoken: String) {
        val matches = EmailHelper.searchRecipients(this, spoken)
        val resolved = EmailHelper.resolveRecipient(spoken, matches)
        when {
            resolved != null -> enterDictaphoneShareEmailConfirm(entry, resolved)
            matches.isEmpty() -> finishDictaphoneShareEmail(false, "Nem található e-mail címzett.")
            else -> {
                activeFlow = AppFlow.DictaphoneShareEmailPickRecipient(entry, matches, 0)
                updateFlowDisplay()
                tts.speak("Több találat. ${matches.size} cím. Söpörj fel-le választás, jobbra kiválasztás.")
                speakEmailRecipient(matches.first())
            }
        }
    }

    private fun navigateDictaphoneShareEmailPick(flow: AppFlow.DictaphoneShareEmailPickRecipient, delta: Int) {
        val next = (flow.index + delta + flow.matches.size) % flow.matches.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        speakEmailRecipient(flow.matches[next])
    }

    private fun enterDictaphoneShareEmailConfirm(entry: DictaphoneRecordingEntry, recipient: EmailRecipient) {
        activeFlow = AppFlow.DictaphoneShareEmailConfirm(entry, recipient)
        updateFlowDisplay()
        repeatDictaphoneShareEmailConfirm(entry, recipient)
    }

    private fun repeatDictaphoneShareEmailConfirm(entry: DictaphoneRecordingEntry, recipient: EmailRecipient) {
        tts.speak(
            "Felvétel küldése e-mailben: ${entry.displayName()}, címzett: ${recipient.label}. " +
                "Elküldjem? Söpörj jobbra az elküldéshez, söprés balra a mégsehez."
        )
    }

    private fun sendDictaphoneShareEmail(entry: DictaphoneRecordingEntry, recipient: EmailRecipient) {
        voiceInput.cancel()
        tts.speak("E-mail küldése melléklettel. Várj egy pillanatot.")
        Thread {
            val subject = "Super DL diktafon: ${entry.displayName()}"
            val body = "Csatolva: ${entry.displayName()}, ${entry.format.label}."
            val ok = EmailHelper.sendWithAttachment(
                context = this@MainActivity,
                recipient = recipient,
                subject = subject,
                body = body,
                attachment = entry.file,
                attachmentMime = entry.format.mimeType,
                attachmentName = entry.file.name
            )
            postWhenAlive {
                finishDictaphoneShareEmail(
                    ok,
                    if (ok) "Felvétel elküldve ${recipient.label} részére."
                    else "E-mail küldés sikertelen. Ellenőrizd az e-mail küldő beállításait."
                )
            }
        }.start()
    }

    private fun cancelDictaphoneShareEmail() {
        val returnBrowse = dictaphoneShareReturnBrowse
        dictaphoneShareReturnBrowse = null
        voiceInput.cancel()
        if (returnBrowse != null) {
            activeFlow = returnBrowse
            updateFlowDisplay()
            tts.speak("Felvétel megosztás megszakítva.")
        } else {
            exitFlow("Felvétel megosztás megszakítva.")
        }
    }

    private fun finishDictaphoneShareEmail(success: Boolean, message: String) {
        val returnBrowse = dictaphoneShareReturnBrowse
        dictaphoneShareReturnBrowse = null
        if (returnBrowse != null) {
            activeFlow = returnBrowse
            updateFlowDisplay()
            if (success) feedbackSuccess() else feedbackError()
            tts.speak(message)
            tts.speakAdd(returnBrowse.recordings[returnBrowse.index].speakSummary())
        } else {
            exitFlow(message, success = success, error = !success)
        }
    }

    private fun startNavWhereFlow() {
        if (!ensureLocationPermission()) return
        if (!ConnectivityHelper.isOnline(this)) {
            val stored = LastLocationStore.get(this)
            if (stored != null) {
                tts.speak(stored.speakSummary())
                return
            }
            tts.speak("Nincs internet, és nincs mentett utolsó hely.")
            return
        }
        beginNavWhereRefining()
    }

    private fun beginNavWhereRefining() {
        voiceInput.cancel()
        cancelGpsRefining()
        cancelGnss()
        activeFlow = AppFlow.NavWhereLoading
        updateFlowDisplay()
        tts.speak("Helymeghatározás. Állj egy helyben, a pontosság javítása folyamatban.")
        var lastAnnouncedAccuracy = -1
        var lastAnnouncedSatellites = -1
        gnssCancel = GnssStatusMonitor.start(this) { count ->
            if (activeFlow !is AppFlow.NavWhereLoading) return@start
            if (count == lastAnnouncedSatellites) return@start
            lastAnnouncedSatellites = count
            tts.speakAdd("$count műhold használatban.")
        }
        gpsRefineCancel = GpsAccuracyRefiner.refine(
            context = this,
            targetAccuracyM = GpsAccuracyRefiner.TARGET_ACCURACY_M,
            onProgress = { accuracy ->
                if (activeFlow !is AppFlow.NavWhereLoading) return@refine
                if (accuracy == lastAnnouncedAccuracy) return@refine
                lastAnnouncedAccuracy = accuracy
                tts.speakAdd("Jelenlegi pontosság kb. $accuracy méter.")
            },
            onComplete = { result ->
                cancelGnss()
                gpsRefineCancel = null
                if (activeFlow !is AppFlow.NavWhereLoading) return@refine
                if (result == null) {
                    exitFlow("Helymeghatározás nem sikerült. Kapcsold be a G P S-t.")
                    return@refine
                }
                Thread {
                    val address = try {
                        OsmHelper.reverseGeocode(result.location.latitude, result.location.longitude)
                    } catch (_: Exception) {
                        null
                    } ?: "ismeretlen cím"
                    postWhenAlive {
                        if (activeFlow !is AppFlow.NavWhereLoading) return@postWhenAlive
                        val flow = AppFlow.NavWhereResult(
                            latitude = result.location.latitude,
                            longitude = result.location.longitude,
                            address = address,
                            accuracyMeters = result.accuracyMeters
                        )
                        LastLocationStore.save(
                            this@MainActivity,
                            flow.latitude,
                            flow.longitude,
                            flow.address,
                            flow.accuracyMeters
                        )
                        activeFlow = flow
                        updateFlowDisplay()
                        speakNavWhereResult(flow, includeHints = true)
                    }
                }.start()
            }
        )
    }

    private fun speakNavWhereResult(flow: AppFlow.NavWhereResult, includeHints: Boolean = false) {
        val hint = GpsAccuracyRefiner.accuracyHint(flow.accuracyMeters)
        val base = "Jelenlegi helyed: ${flow.address}. $hint"
        if (includeHints) {
            tts.speak("$base Jobbra söprés: mentés egyéni helyként. Balra: vissza.")
        } else {
            tts.speak(base)
        }
    }

    private fun startNavWhereSave(flow: AppFlow.NavWhereResult) {
        if (SavedPoiStore.containsCoords(this, flow.latitude, flow.longitude)) {
            tts.speak("Ez a hely már mentve van az egyéni helyek között.")
            return
        }
        voiceInput.cancel()
        activeFlow = AppFlow.GpsRadarAwaitSaveName(
            latitude = flow.latitude,
            longitude = flow.longitude,
            accuracyMeters = flow.accuracyMeters,
            category = "egyéni",
            returnNavWhere = flow
        )
        updateFlowDisplay()
        listenForGpsSaveOwnLocationName(activeFlow as AppFlow.GpsRadarAwaitSaveName, fromAssistant = false)
    }

    private fun cancelNavWhereRefining() {
        cancelGpsRefining()
        cancelGnss()
        exitFlow("Helymeghatározás megszakítva.")
    }

    private fun cancelGpsRefining() {
        gpsRefineCancel?.invoke()
        gpsRefineCancel = null
    }

    private fun cancelGnss() {
        gnssCancel?.invoke()
        gnssCancel = null
    }

    private fun cancelGpsSaveRefining(flow: AppFlow.GpsSaveRefining) {
        cancelGpsRefining()
        when {
            flow.returnGuiding != null -> {
                activeFlow = flow.returnGuiding
                updateFlowDisplay()
                tts.speak("Saját hely mentés megszakítva.")
            }
            flow.returnBrowse != null -> {
                activeFlow = flow.returnBrowse
                updateFlowDisplay()
                tts.speak("Saját hely mentés megszakítva.")
                speakGpsRadarPoi(flow.returnBrowse.pois[flow.returnBrowse.index])
            }
            flow.fromAssistant -> tts.speakThen("Saját hely mentés megszakítva.") { resumeVoiceAssistantListening() }
            else -> exitFlow("Saját hely mentés megszakítva.")
        }
    }

    private fun startNavWalkFlow() {
        if (!ensureLocationPermission()) return
        ensureMicAndRun {
            activeFlow = AppFlow.NavAwaitWalkDestination
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd hová szeretnél menni gyalog.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val destination = spoken.trim()
                    if (destination.isBlank()) {
                        exitFlow("Üres célállomás.")
                        return@listen
                    }
                    voiceInput.cancel()
                    fetchWalkingRoute(destination)
                },
                onError = { exitFlow("Nem értettem a célállomást.") }
            )
        }
    }

    private fun startNavSearchFlow() {
        ensureMicAndRun {
            activeFlow = AppFlow.NavAwaitPlaceQuery
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd a keresett címet vagy helyet.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val query = spoken.trim()
                    if (query.isBlank()) {
                        exitFlow("Üres keresés.")
                        return@listen
                    }
                    voiceInput.cancel()
                    searchNavPlaces(query)
                },
                onError = { exitFlow("Nem értettem a keresést.") }
            )
        }
    }

    private fun fetchWalkingRoute(destination: String) {
        if (!ensureLocationPermission()) return
        tts.speak("Gyalogos útvonal keresése: $destination. Várj egy pillanatot.")
        NavigationHelper.fetchWalkingRoute(
            context = this,
            destination = destination,
            onResult = { route -> postWhenAlive { showTransitRouteBrowse(route) } },
            onError = { message -> postWhenAlive { exitFlow(message) } }
        )
    }

    private fun fetchWalkingRouteFromAssistant(destination: String) {
        if (!ensureLocationPermission()) {
            tts.speakThen("Helymeghatározás engedély szükséges.") { resumeVoiceAssistantListening() }
            return
        }
        voiceAssistantReturnPending = true
        tts.speak("Gyalogos útvonal keresése: $destination. Várj egy pillanatot.")
        NavigationHelper.fetchWalkingRoute(
            context = this,
            destination = destination,
            onResult = { route -> postWhenAlive { showTransitRouteBrowse(route) } },
            onError = { message ->
                postWhenAlive {
                    voiceAssistantReturnPending = false
                    tts.speakThen(message) { resumeVoiceAssistantListening() }
                }
            }
        )
    }

    private fun fetchWalkingRouteFromQr(payload: String) {
        if (!ensureLocationPermission()) return
        val parts = payload.split("|", limit = 2)
        val coords = parts[0].split(",")
        val lat = coords.getOrNull(0)?.trim()?.toDoubleOrNull()
        val lon = coords.getOrNull(1)?.trim()?.toDoubleOrNull()
        if (lat == null || lon == null) {
            tts.speak("Érvénytelen hely koordináta a kódban.")
            return
        }
        val label = parts.getOrNull(1)?.trim().orEmpty().ifBlank { "cél" }
        tts.speak("Gyalogos útvonal keresése: $label. Várj egy pillanatot.")
        NavigationHelper.fetchWalkingRouteToCoords(
            context = this,
            lat = lat,
            lon = lon,
            label = label,
            onResult = { route -> postWhenAlive { showTransitRouteBrowse(route) } },
            onError = { message -> postWhenAlive { tts.speak(message) } }
        )
    }

    private fun searchNavPlaces(query: String) {
        tts.speak("Hely keresése: $query. Várj egy pillanatot.")
        NavigationHelper.searchPlaces(
            context = this,
            query = query,
            onResult = { places -> postWhenAlive { showNavPlaceBrowse(places) } },
            onError = { message -> postWhenAlive { exitFlow(message) } }
        )
    }

    private fun showNavPlaceBrowse(places: List<NavPlace>) {
        activeFlow = AppFlow.NavPlaceBrowse(places, 0)
        updateFlowDisplay()
        tts.speak(
            "${places.size} találat. Söpörj fel-le választás, jobbra megnyitás térképen, balra vissza."
        )
        tts.speakAdd(places.first().speakPreview())
    }

    private fun navigateNavPlaceList(flow: AppFlow.NavPlaceBrowse, delta: Int) {
        val next = (flow.index + delta + flow.places.size) % flow.places.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.places[next].speakPreview())
    }

    private fun openNavPlaceInMaps(place: NavPlace) {
        if (NavigationHelper.openInMaps(this, place)) {
            tts.speak("Megnyitom a térképen: ${place.shortName}")
        } else {
            tts.speak("Nem sikerült megnyitni a térképet. Telepíts egy térképalkalmazást.")
        }
    }

    // ==================== TÖMEGKÖZLEKEDÉS ====================

    private fun startTransitNearbyFlow() {
        if (!ensureLocationPermission()) return
        startTransitCompass()
        tts.speak("Közeli megállók keresése indulási időkkel. Várj egy pillanatot.")
        val heading = transitCompass?.heading() ?: 0f
        TransitHelper.fetchNearbyStops(
            context = this,
            onResult = { places ->
                postWhenAlive {
                    showTransitBrowse(
                        places,
                        title = "Közeli megállók",
                        radiusMode = TransitHelper.StopRadiusMode.NEAR
                    )
                }
            },
            onError = { message -> postWhenAlive { tts.speak(message) } },
            headingDegrees = heading
        )
    }

    private fun startTransitFavoritesFlow() {
        if (!ensureLocationPermission()) return
        startTransitCompass()
        tts.speak("Kedvenc megállók betöltése. Várj.")
        val heading = transitCompass?.heading() ?: 0f
        TransitHelper.fetchFavoriteStops(
            context = this,
            onResult = { places ->
                postWhenAlive {
                    showTransitBrowse(
                        places,
                        title = "Kedvenc megállók",
                        radiusMode = TransitHelper.StopRadiusMode.NEAR
                    )
                }
            },
            onError = { message -> postWhenAlive { tts.speak(message) } },
            headingDegrees = heading
        )
    }

    private fun startTransitStopFlow() {
        ensureMicAndRun {
            startTransitCompass()
            activeFlow = AppFlow.TransitAwaitStop
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd a megálló nevét.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val stop = spoken.trim()
                    if (stop.isBlank()) {
                        exitFlow("Nem értettem a megálló nevét.")
                        return@listen
                    }
                    voiceInput.cancel()
                    tts.speak("Megálló keresése: $stop. Várj egy pillanatot.")
                    val heading = transitCompass?.heading() ?: 0f
                    TransitHelper.searchStop(
                        context = this,
                        stopName = stop,
                        onResult = { places ->
                            postWhenAlive {
                                showTransitBrowse(places, "Megálló keresés", TransitHelper.StopRadiusMode.NEAR)
                            }
                        },
                        onError = { message -> postWhenAlive { exitFlow(message) } },
                        headingDegrees = heading
                    )
                },
                onError = { exitFlow("Nem értettem a megálló nevét.") }
            )
        }
    }

    private fun startTransitCompass() {
        transitCompass?.stop()
        transitCompass = CompassProvider(this).also { it.start() }
    }

    private fun stopTransitCompass() {
        transitCompass?.stop()
        transitCompass = null
    }

    private fun startTransitRouteFlow() {
        ensureMicAndRun {
            activeFlow = AppFlow.TransitAwaitDestination
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd hová szeretnél menni tömegközlekedéssel.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val destination = spoken.trim()
                    if (destination.isBlank()) {
                        exitFlow("Nem értettem a célállomást.")
                        return@listen
                    }
                    voiceInput.cancel()
                    tts.speak("Útvonal keresése: $destination. Várj egy pillanatot.")
                    TransitHelper.fetchTransitRoute(
                        context = this,
                        destination = destination,
                        onResult = { route -> postWhenAlive { showTransitRouteBrowse(route) } },
                        onError = { message -> postWhenAlive { exitFlow(message) } }
                    )
                },
                onError = { exitFlow("Nem értettem a célállomást.") }
            )
        }
    }

    private fun showTransitBrowse(
        places: List<TransitPlace>,
        title: String,
        radiusMode: TransitHelper.StopRadiusMode = TransitHelper.StopRadiusMode.NEAR
    ) {
        activeFlow = AppFlow.TransitBrowse(places, 0, title, radiusMode)
        updateFlowDisplay()
        tts.speak(
            "$title. ${places.size} találat. ${radiusMode.label}. " +
                "Söpörj fel-le választás, jobbra műveletek, balra vissza."
        )
        tts.speakAdd(places.first().speakPreview())
    }

    private fun navigateTransitList(flow: AppFlow.TransitBrowse, delta: Int) {
        val next = (flow.index + delta + flow.places.size) % flow.places.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.places[next].speakPreview())
    }

    private fun enterTransitContextMenu(flow: AppFlow.TransitBrowse) {
        val place = flow.places[flow.index]
        val actions = buildList {
            add(TransitContextAction.SPEAK_FULL)
            if (place.isFavorite) add(TransitContextAction.REMOVE_FAVORITE)
            else add(TransitContextAction.SAVE_FAVORITE)
            if (flow.title == "Közeli megállók") add(TransitContextAction.TOGGLE_RADIUS)
            add(TransitContextAction.REFRESH)
        }
        activeFlow = AppFlow.TransitContextMenu(
            flow.places,
            flow.index,
            actions,
            0,
            flow.title,
            flow.radiusMode
        )
        updateFlowDisplay()
        tts.speak("Megálló műveletek. ${actions.first().label}. Söpörj fel-le választás, jobbra végrehajtás, balra vissza.")
    }

    private fun navigateTransitContextMenu(flow: AppFlow.TransitContextMenu, delta: Int) {
        val next = (flow.actionIndex + delta + flow.actions.size) % flow.actions.size
        activeFlow = flow.copy(actionIndex = next)
        updateFlowDisplay()
        tts.speak(flow.actions[next].label)
    }

    private fun onTransitContextActivate(flow: AppFlow.TransitContextMenu) {
        val place = flow.places[flow.placeIndex]
        when (flow.actions[flow.actionIndex]) {
            TransitContextAction.SPEAK_FULL -> tts.speak(place.speakFull())
            TransitContextAction.SAVE_FAVORITE -> {
                val saved = TransitStopStore.add(
                    this,
                    name = place.name,
                    latitude = place.latitude,
                    longitude = place.longitude,
                    stopId = place.stopId,
                    address = place.address
                )
                if (saved == null) {
                    tts.speak("${place.name} már kedvencnek van mentve, vagy nem sikerült menteni.")
                } else {
                    val updated = flow.places.mapIndexed { index, item ->
                        if (index == flow.placeIndex) item.copy(isFavorite = true) else item
                    }
                    activeFlow = AppFlow.TransitBrowse(updated, flow.placeIndex, flow.title, flow.radiusMode)
                    updateFlowDisplay()
                    tts.speak("${place.name} kedvenc megállónak mentve.")
                }
            }
            TransitContextAction.REMOVE_FAVORITE -> {
                val favorite = TransitStopStore.getAll(this)
                    .firstOrNull { it.name.equals(place.name, true) || it.stopId == place.stopId }
                if (favorite != null && TransitStopStore.remove(this, favorite.id)) {
                    val updated = flow.places.mapIndexed { index, item ->
                        if (index == flow.placeIndex) item.copy(isFavorite = false) else item
                    }
                    activeFlow = AppFlow.TransitBrowse(updated, flow.placeIndex, flow.title, flow.radiusMode)
                    updateFlowDisplay()
                    tts.speak("${place.name} törölve a kedvencek közül.")
                } else {
                    tts.speak("Nem találtam kedvencnek mentve: ${place.name}.")
                }
            }
            TransitContextAction.TOGGLE_RADIUS -> refreshTransitWithRadius(flow)
            TransitContextAction.REFRESH -> refreshTransitList(flow)
        }
    }

    private fun refreshTransitWithRadius(flow: AppFlow.TransitContextMenu) {
        val newMode = if (flow.radiusMode == TransitHelper.StopRadiusMode.NEAR) {
            TransitHelper.StopRadiusMode.EXTENDED
        } else {
            TransitHelper.StopRadiusMode.NEAR
        }
        tts.speak("${newMode.label}. Frissítés.")
        val heading = transitCompass?.heading() ?: 0f
        TransitHelper.fetchNearbyStops(
            context = this,
            onResult = { places ->
                postWhenAlive {
                    showTransitBrowse(places, flow.title, newMode)
                }
            },
            onError = { message -> postWhenAlive { tts.speak(message) } },
            radiusMode = newMode,
            headingDegrees = heading
        )
    }

    private fun refreshTransitList(flow: AppFlow.TransitContextMenu) {
        tts.speak("Megállók frissítése.")
        val heading = transitCompass?.heading() ?: 0f
        if (flow.title == "Kedvenc megállók") {
            TransitHelper.fetchFavoriteStops(
                context = this,
                onResult = { places ->
                    postWhenAlive {
                        showTransitBrowse(places, flow.title, flow.radiusMode)
                    }
                },
                onError = { message -> postWhenAlive { tts.speak(message) } },
                headingDegrees = heading
            )
        } else {
            TransitHelper.fetchNearbyStops(
                context = this,
                onResult = { places ->
                    postWhenAlive {
                        showTransitBrowse(places, flow.title, flow.radiusMode)
                    }
                },
                onError = { message -> postWhenAlive { tts.speak(message) } },
                radiusMode = flow.radiusMode,
                headingDegrees = heading
            )
        }
    }

    private fun returnToTransitBrowse(flow: AppFlow.TransitContextMenu) {
        activeFlow = AppFlow.TransitBrowse(flow.places, flow.placeIndex, flow.title, flow.radiusMode)
        updateFlowDisplay()
        tts.speak("Vissza a megálló listában.")
        tts.speakAdd(flow.places[flow.placeIndex].speakPreview())
    }

    private fun showTransitRouteBrowse(route: com.superdl.launcher.transit.TransitRoute) {
        activeFlow = AppFlow.TransitRouteBrowse(route, 0)
        updateFlowDisplay()
        tts.speakThen(route.speakSummary()) {
            tts.speakAdd(
                "${route.steps.size} lépés. Söpörj fel-le lépésenként, jobbra ismétlés, balra vissza."
            )
            tts.speakAdd(route.steps.first().speakPreview())
        }
    }

    private fun navigateTransitRouteList(flow: AppFlow.TransitRouteBrowse, delta: Int) {
        val next = (flow.index + delta + flow.route.steps.size) % flow.route.steps.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.route.steps[next].speakPreview())
    }

    // ==================== VONAT (MÁV) ====================

    private fun startTrainNearbyFlow() {
        if (!ensureLocationPermission()) return
        startTransitCompass()
        tts.speak("Közeli vasútállomások keresése indulási időkkel. Várj egy pillanatot.")
        val heading = transitCompass?.heading() ?: 0f
        TrainHelper.fetchNearbyStations(
            context = this,
            onResult = { stations ->
                postWhenAlive {
                    showTrainBrowse(
                        stations,
                        title = "Közeli állomások",
                        radiusMode = TrainHelper.StationRadiusMode.NEAR
                    )
                }
            },
            onError = { message -> postWhenAlive { tts.speak(message) } },
            headingDegrees = heading
        )
    }

    private fun startTrainFavoritesFlow() {
        if (!ensureLocationPermission()) return
        startTransitCompass()
        tts.speak("Kedvenc állomások betöltése. Várj.")
        val heading = transitCompass?.heading() ?: 0f
        TrainHelper.fetchFavoriteStations(
            context = this,
            onResult = { stations ->
                postWhenAlive {
                    showTrainBrowse(
                        stations,
                        title = "Kedvenc állomások",
                        radiusMode = TrainHelper.StationRadiusMode.NEAR
                    )
                }
            },
            onError = { message -> postWhenAlive { tts.speak(message) } },
            headingDegrees = heading
        )
    }

    private fun startTrainStationFlow() {
        ensureMicAndRun {
            startTransitCompass()
            activeFlow = AppFlow.TrainAwaitStation
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd az állomás nevét.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val station = spoken.trim()
                    if (station.isBlank()) {
                        exitFlow("Nem értettem az állomás nevét.")
                        return@listen
                    }
                    voiceInput.cancel()
                    tts.speak("Állomás keresése: $station. Várj egy pillanatot.")
                    val heading = transitCompass?.heading() ?: 0f
                    TrainHelper.searchStation(
                        context = this,
                        stationName = station,
                        onResult = { stations ->
                            postWhenAlive {
                                showTrainBrowse(stations, "Állomás keresés", TrainHelper.StationRadiusMode.NEAR)
                            }
                        },
                        onError = { message -> postWhenAlive { exitFlow(message) } },
                        headingDegrees = heading
                    )
                },
                onError = { exitFlow("Nem értettem az állomás nevét.") }
            )
        }
    }

    private fun showTrainBrowse(
        stations: List<TrainStation>,
        title: String,
        radiusMode: TrainHelper.StationRadiusMode = TrainHelper.StationRadiusMode.NEAR
    ) {
        activeFlow = AppFlow.TrainBrowse(stations, 0, title, radiusMode)
        updateFlowDisplay()
        tts.speak(
            "$title. ${stations.size} találat. ${radiusMode.label}. " +
                "Söpörj fel-le választás, jobbra műveletek, balra vissza."
        )
        tts.speakAdd(stations.first().speakPreview())
    }

    private fun navigateTrainList(flow: AppFlow.TrainBrowse, delta: Int) {
        val next = (flow.index + delta + flow.stations.size) % flow.stations.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.stations[next].speakPreview())
    }

    private fun enterTrainContextMenu(flow: AppFlow.TrainBrowse) {
        val station = flow.stations[flow.index]
        val actions = buildList {
            add(TrainContextAction.SPEAK_FULL)
            if (station.isFavorite) add(TrainContextAction.REMOVE_FAVORITE)
            else add(TrainContextAction.SAVE_FAVORITE)
            if (flow.title == "Közeli állomások") add(TrainContextAction.TOGGLE_RADIUS)
            add(TrainContextAction.REFRESH)
        }
        activeFlow = AppFlow.TrainContextMenu(
            flow.stations,
            flow.index,
            actions,
            0,
            flow.title,
            flow.radiusMode
        )
        updateFlowDisplay()
        tts.speak("Állomás műveletek. ${actions.first().label}. Söpörj fel-le választás, jobbra végrehajtás, balra vissza.")
    }

    private fun navigateTrainContextMenu(flow: AppFlow.TrainContextMenu, delta: Int) {
        val next = (flow.actionIndex + delta + flow.actions.size) % flow.actions.size
        activeFlow = flow.copy(actionIndex = next)
        updateFlowDisplay()
        tts.speak(flow.actions[next].label)
    }

    private fun onTrainContextActivate(flow: AppFlow.TrainContextMenu) {
        val station = flow.stations[flow.stationIndex]
        when (flow.actions[flow.actionIndex]) {
            TrainContextAction.SPEAK_FULL -> tts.speak(station.speakFull())
            TrainContextAction.SAVE_FAVORITE -> {
                val saved = TrainStationStore.add(
                    this,
                    name = station.name,
                    latitude = station.latitude,
                    longitude = station.longitude,
                    stationId = station.stationId,
                    address = station.address
                )
                if (saved == null) {
                    tts.speak("${station.name} már kedvencnek van mentve, vagy nem sikerült menteni.")
                } else {
                    val updated = flow.stations.mapIndexed { index, item ->
                        if (index == flow.stationIndex) item.copy(isFavorite = true) else item
                    }
                    activeFlow = AppFlow.TrainBrowse(updated, flow.stationIndex, flow.title, flow.radiusMode)
                    updateFlowDisplay()
                    tts.speak("${station.name} kedvenc állomásnak mentve.")
                }
            }
            TrainContextAction.REMOVE_FAVORITE -> {
                val favorite = TrainStationStore.getAll(this)
                    .firstOrNull { it.name.equals(station.name, true) || it.stationId == station.stationId }
                if (favorite != null && TrainStationStore.remove(this, favorite.id)) {
                    val updated = flow.stations.mapIndexed { index, item ->
                        if (index == flow.stationIndex) item.copy(isFavorite = false) else item
                    }
                    activeFlow = AppFlow.TrainBrowse(updated, flow.stationIndex, flow.title, flow.radiusMode)
                    updateFlowDisplay()
                    tts.speak("${station.name} törölve a kedvencek közül.")
                } else {
                    tts.speak("Nem találtam kedvencnek mentve: ${station.name}.")
                }
            }
            TrainContextAction.TOGGLE_RADIUS -> refreshTrainWithRadius(flow)
            TrainContextAction.REFRESH -> refreshTrainList(flow)
        }
    }

    private fun refreshTrainWithRadius(flow: AppFlow.TrainContextMenu) {
        val newMode = if (flow.radiusMode == TrainHelper.StationRadiusMode.NEAR) {
            TrainHelper.StationRadiusMode.EXTENDED
        } else {
            TrainHelper.StationRadiusMode.NEAR
        }
        tts.speak("${newMode.label}. Frissítés.")
        val heading = transitCompass?.heading() ?: 0f
        TrainHelper.fetchNearbyStations(
            context = this,
            onResult = { stations ->
                postWhenAlive {
                    showTrainBrowse(stations, flow.title, newMode)
                }
            },
            onError = { message -> postWhenAlive { tts.speak(message) } },
            radiusMode = newMode,
            headingDegrees = heading
        )
    }

    private fun refreshTrainList(flow: AppFlow.TrainContextMenu) {
        tts.speak("Állomások frissítése.")
        val heading = transitCompass?.heading() ?: 0f
        if (flow.title == "Kedvenc állomások") {
            TrainHelper.fetchFavoriteStations(
                context = this,
                onResult = { stations ->
                    postWhenAlive {
                        showTrainBrowse(stations, flow.title, flow.radiusMode)
                    }
                },
                onError = { message -> postWhenAlive { tts.speak(message) } },
                headingDegrees = heading
            )
        } else if (flow.title == "Állomás keresés") {
            val station = flow.stations[flow.stationIndex]
            TrainHelper.searchStation(
                context = this,
                stationName = station.name,
                onResult = { stations ->
                    postWhenAlive {
                        showTrainBrowse(stations, flow.title, flow.radiusMode)
                    }
                },
                onError = { message -> postWhenAlive { tts.speak(message) } },
                headingDegrees = heading
            )
        } else {
            TrainHelper.fetchNearbyStations(
                context = this,
                onResult = { stations ->
                    postWhenAlive {
                        showTrainBrowse(stations, flow.title, flow.radiusMode)
                    }
                },
                onError = { message -> postWhenAlive { tts.speak(message) } },
                radiusMode = flow.radiusMode,
                headingDegrees = heading
            )
        }
    }

    private fun returnToTrainBrowse(flow: AppFlow.TrainContextMenu) {
        activeFlow = AppFlow.TrainBrowse(flow.stations, flow.stationIndex, flow.title, flow.radiusMode)
        updateFlowDisplay()
        tts.speak("Vissza az állomás listában.")
        tts.speakAdd(flow.stations[flow.stationIndex].speakPreview())
    }

    // ==================== ELENA FELÉBRESZTŐ ====================

    private fun toggleElenaWakeListen(speak: Boolean = true): Boolean {
        val enabled = !ElenaWakeStore.isListenEnabled(this)
        setElenaWakeListen(enabled, speak)
        return enabled
    }

    private fun setElenaWakeListen(enabled: Boolean, speak: Boolean = true) {
        if (!enabled) {
            ElenaWakeStore.listeningPaused = false
            voiceInput.cancel()
        }
        ElenaWakeStore.setListenEnabled(this, enabled)
        syncElenaWakeListenService()
        if (speak) {
            tts.speak(ElenaWakeHelper.speakListenStatus(this, enabled))
        }
    }

    private fun pauseElenaWakeListening() {
        ElenaWakeStore.listeningPaused = true
        if (!ElenaWakeStore.isListenEnabled(this)) return
        startService(
            Intent(this, ElenaWakeListenService::class.java).apply {
                action = ElenaWakeListenService.ACTION_PAUSE
            }
        )
    }

    private fun resumeElenaWakeListening() {
        if (!ElenaWakeStore.isListenEnabled(this)) return
        ElenaWakeStore.listeningPaused = false
        startService(
            Intent(this, ElenaWakeListenService::class.java).apply {
                action = ElenaWakeListenService.ACTION_RESUME
            }
        )
    }

    private fun syncElenaWakeListenService() {
        if (ElenaWakeStore.isListenEnabled(this)) {
            val serviceIntent = Intent(this, ElenaWakeListenService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(serviceIntent)
            } else {
                startService(serviceIntent)
            }
        } else {
            stopService(
                Intent(this, ElenaWakeListenService::class.java).apply {
                    action = ElenaWakeListenService.ACTION_STOP
                }
            )
        }
    }

    private fun startElenaWakeTrainFlow(fromAssistant: Boolean = false) {
        ensureMicAndRun {
            activeFlow = AppFlow.ElenaWakeTrainAwaitPhrase
            updateFlowDisplay()
            tts.speakThen(
                "Mondd a saját felébresztő mondatod. Például: Szia ${ElenaWakeHelper.ASSISTANT_NAME}, " +
                    "vagy Kérlek ${ElenaWakeHelper.ASSISTANT_NAME}."
            ) {
                voiceInput.listenPrompt(
                    prompt = "Felébresztő mondat",
                    onResult = { spoken -> finishElenaWakeTrain(spoken, fromAssistant) },
                    onError = {
                        if (fromAssistant) {
                            tts.speakThen("Nem hallottam. Próbáld újra.") {
                                startElenaWakeTrainFlow(fromAssistant = true)
                            }
                        } else {
                            exitFlow("Elena tanítás megszakítva.")
                        }
                    }
                )
            }
        }
    }

    private fun finishElenaWakeTrain(spoken: String, fromAssistant: Boolean) {
        val normalized = VoiceAssistantHelper.normalize(spoken)
        if (normalized.length < 3) {
            tts.speakThen("Túl rövid. Mondd újra a teljes mondatot.") {
                startElenaWakeTrainFlow(fromAssistant)
            }
            return
        }
        val saved = ElenaWakeStore.addCustomPhrase(this, spoken)
        val message = if (saved) {
            "Mentve. Saját felébresztő: $normalized."
        } else {
            "Ez a mondat már mentve van, vagy túl rövid."
        }
        if (fromAssistant) {
            activeFlow = AppFlow.VoiceAssistantChat
            updateFlowDisplay()
            tts.speakThen(message) { resumeVoiceAssistantListening() }
        } else {
            exitFlow(message)
        }
    }

    // ==================== HANGOS ASSZISZTENS (ELENA) ====================

    private fun shouldLaunchVoiceAssistant(intent: Intent?): Boolean {
        if (intent == null) return false
        return intent.getBooleanExtra(EXTRA_LAUNCH_VOICE_ASSISTANT, false) ||
            intent.action == ACTION_LAUNCH_VOICE_ASSISTANT ||
            intent.action == Intent.ACTION_ASSIST ||
            intent.action == ACTION_VOICE_ASSIST
    }

    private fun queueVoiceAssistantLaunchIfNeeded(intent: Intent?) {
        if (!shouldLaunchVoiceAssistant(intent)) return
        voiceInput.cancel()
        tts.stop()
        pendingAssistantLaunch = true
        pendingAssistantFromKeyguard =
            intent?.getBooleanExtra(EXTRA_ASSISTANT_FROM_KEYGUARD, false) == true
        pendingWakeCommand = intent?.getStringExtra(EXTRA_WAKE_COMMAND)?.trim()?.takeIf { it.isNotBlank() }
        pendingWakeGreetingOnly = intent?.getBooleanExtra(EXTRA_WAKE_GREETING_ONLY, false) == true
        intent?.removeExtra(EXTRA_LAUNCH_VOICE_ASSISTANT)
        intent?.removeExtra(EXTRA_ASSISTANT_FROM_KEYGUARD)
        intent?.removeExtra(EXTRA_WAKE_COMMAND)
        intent?.removeExtra(EXTRA_WAKE_GREETING_ONLY)
        intent?.action = null
        val lockedMode = pendingAssistantFromKeyguard
        val wakeCommand = pendingWakeCommand
        val greetingOnly = pendingWakeGreetingOnly
        pendingVoiceAction = {
            startVoiceAssistantFlow(
                lockedMode = lockedMode,
                initialCommand = wakeCommand,
                greetingOnly = greetingOnly
            )
        }
    }

    private fun runPendingVoiceActionIfReady() {
        val action = pendingVoiceAction ?: return
        val allowLocked = pendingAssistantLaunch && pendingAssistantFromKeyguard
        if (!isForeground && !pendingAssistantLaunch) return
        if (LockSession.needsUnlock(this) && !allowLocked && !pendingAssistantLaunch) return
        pendingVoiceAction = null
        mainHandler.postDelayed({ action() }, 150)
    }

    private fun openAssistantActivationSettings() {
        val intent = AssistantRoleHelper.createActivationIntent(this)
        if (intent != null) {
            assistantActivationLauncher.launch(intent)
        } else {
            startPermissionGuideFlow(PermissionGuideType.ASSISTANT_ROLE, "Asszisztens aktiválás")
        }
    }

    private fun startAssistantDefaultSetupFlow() {
        if (AssistantRoleHelper.isVoiceInteractionActive(this)) {
            tts.speak(AssistantRoleHelper.speakStatus(this))
            return
        }
        if (AssistantRoleHelper.needsActivation(this)) {
            tts.speakThen(AssistantRoleHelper.speakStatus(this)) {
                openAssistantActivationSettings()
            }
            return
        }
        if (AssistantRoleHelper.isAssistantRoleHeld(this)) {
            tts.speak(AssistantRoleHelper.speakStatus(this))
            return
        }
        val intent = AssistantRoleHelper.createRoleRequestIntent(this)
        if (intent != null) {
            tts.speakThen(
                "A Super DL most megjelenik a rendszer digitális asszisztens listájában. " +
                    "Válaszd ki a Super DL-t, hogy az oldalsó gomb hosszú nyomására ${ElenaWakeHelper.ASSISTANT_NAME} induljon."
            ) {
                assistantRoleLauncher.launch(intent)
            }
            return
        }
        startPermissionGuideFlow(PermissionGuideType.ASSISTANT_ROLE, "Alapértelmezett asszisztens beállítása")
    }

    private fun startDialerDefaultSetupFlow() {
        if (DialerRoleHelper.isDefaultDialer(this)) {
            tts.speak(DialerRoleHelper.speakStatus(this))
            return
        }
        val intent = DialerRoleHelper.createRoleRequestIntent(this)
        if (intent != null) {
            tts.speakThen(
                "A Super DL most megjelenik a telefon alkalmazások listájában. " +
                    "Válaszd ki a Super DL-t, hogy a bejövő hívások száma és neve látható legyen."
            ) {
                dialerRoleLauncher.launch(intent)
            }
            return
        }
        startPermissionGuideFlow(PermissionGuideType.DIALER_ROLE, "Alapértelmezett telefon beállítása")
    }

    private fun startVoiceAssistantFlow(
        lockedMode: Boolean = false,
        initialCommand: String? = null,
        greetingOnly: Boolean = false
    ) {
        voiceAssistantReturnPending = false
        assistantLockedMode = lockedMode
        pendingAssistantLaunch = false
        pendingAssistantFromKeyguard = false
        pendingWakeCommand = null
        pendingWakeGreetingOnly = false
        pauseElenaWakeListening()
        if (lockedMode) applyAssistantWindowFlags(true)
        ensureMicAndRun {
            activeFlow = AppFlow.VoiceAssistantAwaitQuestion
            updateFlowDisplay()
            val intro = when {
                greetingOnly -> ElenaWakeHelper.wakeGreeting()
                initialCommand != null -> ElenaWakeHelper.wakeGreeting()
                lockedMode -> "${ElenaWakeHelper.ASSISTANT_NAME}, zárolt mód. Egyszerű parancsok engedélyezettek. Hallgatlak."
                else -> "${ElenaWakeHelper.ASSISTANT_NAME}. Hallgatlak."
            }
            tts.speakThen(intro) {
                if (!initialCommand.isNullOrBlank()) {
                    activeFlow = AppFlow.VoiceAssistantChat
                    updateFlowDisplay()
                    processVoiceAssistant(initialCommand)
                } else {
                    // INDÍTÁSKOR mindenképpen hallgatnia kell — itt nem szabad a
                    // "parancs utáni" logikát használni, mert az azonnal kilépne.
                    beginVoiceAssistantListening()
                }
            }
        }
    }

    private fun applyAssistantWindowFlags(enabled: Boolean) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(enabled)
            setTurnScreenOn(enabled)
        } else {
            @Suppress("DEPRECATION")
            if (enabled) {
                window.addFlags(
                    android.view.WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                        android.view.WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
                )
            } else {
                window.clearFlags(
                    android.view.WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                        android.view.WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
                )
            }
        }
    }

    private fun startSmsDefaultSetupFlow() {
        if (SmsRoleHelper.isDefaultSmsApp(this)) {
            tts.speak(SmsRoleHelper.speakStatus(this))
            return
        }
        val intent = SmsRoleHelper.createRoleRequestIntent(this)
        if (intent != null) {
            tts.speakThen(
                "A Super DL most megjelenik az üzenet alkalmazások listájában. " +
                    "Válaszd ki a Super DL-t az üzenetek küldéséhez és fogadásához."
            ) {
                smsRoleLauncher.launch(intent)
            }
            return
        }
        startPermissionGuideFlow(PermissionGuideType.SMS_ROLE, "Alapértelmezett üzenet app beállítása")
    }

    private fun isVoiceAssistantActive(): Boolean =
        activeFlow is AppFlow.VoiceAssistantChat || activeFlow is AppFlow.VoiceAssistantAwaitQuestion

    /**
     * Az asszisztens lezárása a parancs végrehajtása után. Csendben visszatér a
     * menübe: a válasz már elhangzott, fölösleges még egy "kilépés" mondat.
     */
    private fun exitVoiceAssistantAfterCommand() {
        voiceAssistantReturnPending = false
        assistantLockedMode = false
        try {
            voiceInput.cancel()
        } catch (_: Exception) {
        }
        // A válasz már elhangzott, ezért csendben lépünk vissza a menübe.
        exitFlow("")
    }

    /**
     * A parancs UTÁNI folytatás. Alapból NEM hallgat tovább, hanem kilép —
     * korábban itt "ragadt be" az asszisztens: a feladat kész volt, mégis tovább
     * várt utasításra. Aki több parancsot szeretne egymás után, bekapcsolhatja a
     * Folyamatos beszélgetést az Asszisztens menüben.
     */
    private fun resumeVoiceAssistantListening() {
        if (!isVoiceAssistantActive()) return
        voiceAssistantReturnPending = false
        if (!AssistantPrefs.isContinuousMode(this)) {
            exitVoiceAssistantAfterCommand()
            return
        }
        beginVoiceAssistantListening()
    }

    /**
     * A tényleges figyelés elindítása. Ezt hívjuk az asszisztens INDÍTÁSAKOR is —
     * ilyenkor mindenképpen meg kell hallgatnia a felhasználót, függetlenül a
     * folyamatos beszélgetés beállításától.
     */
    private fun beginVoiceAssistantListening() {
        if (!isVoiceAssistantActive()) return
        voiceAssistantReturnPending = false

        ensureMicAndRun {
            if (!isVoiceAssistantActive()) return@ensureMicAndRun
            activeFlow = AppFlow.VoiceAssistantChat
            updateFlowDisplay()
            voiceInput.listenPromptAssistant(
                prompt = "Elena parancs",
                hints = SpeechContextBuilder.assistantHints(this),
                onResult = { result ->
                    if (!isVoiceAssistantActive()) return@listenPromptAssistant
                    if (result.hypotheses.isEmpty()) {
                        tts.speakThen("Nem hallottam semmit. Mondd újra lassan, tisztán.") {
                            resumeVoiceAssistantListening()
                        }
                        return@listenPromptAssistant
                    }
                    processVoiceAssistant(result)
                },
                onError = { errorCode ->
                    if (!isVoiceAssistantActive()) return@listenPromptAssistant
                    val message = assistantListenErrorMessage(errorCode)
                    tts.speakThen(message) { resumeVoiceAssistantListening() }
                }
            )
        }
    }

    private fun assistantListenErrorMessage(errorCode: Int): String = when (errorCode) {
        android.speech.SpeechRecognizer.ERROR_SPEECH_TIMEOUT ->
            "Nem hallottam időben. Mondd újra lassan, a sípszó után."
        android.speech.SpeechRecognizer.ERROR_NO_MATCH ->
            "Nem értettem a szöveget. Próbáld rövidebben, pl.: idő, ébresztő, hívd fel."
        android.speech.SpeechRecognizer.ERROR_NETWORK,
        android.speech.SpeechRecognizer.ERROR_NETWORK_TIMEOUT ->
            "Nincs stabil internet a felismeréshez. Próbáld újra, vagy mondd rövidebben."
        android.speech.SpeechRecognizer.ERROR_AUDIO ->
            "Nem érhető el a mikrofon. Ellenőrizd az engedélyt."
        else ->
            "Nem értettem. Próbáld újra lassan és tisztán."
    }

    private fun processVoiceAssistant(result: com.superdl.launcher.voice.SpeechRecognitionResult) {
        voiceInput.cancel()
        val interpreted = VoiceAssistantHelper.interpretBest(result, this)
        processVoiceAssistant(interpreted.heard, interpreted.intent)
    }

    private fun processVoiceAssistant(
        question: String,
        intent: VoiceAssistantIntent = VoiceAssistantHelper.interpret(question, this)
    ) {
        voiceInput.cancel()
        if (assistantLockedMode && !VoiceAssistantHelper.isAllowedWhenLocked(intent)) {
            activeFlow = AppFlow.VoiceAssistantChat
            updateFlowDisplay()
            tts.speakThen("Ehhez oldd fel a telefont a PIN kóddal.") {
                resumeVoiceAssistantListening()
            }
            return
        }
        when (intent) {
            is VoiceAssistantIntent.Speak -> {
                activeFlow = AppFlow.VoiceAssistantChat
                updateFlowDisplay()
                val message = if (intent.message.startsWith("Nem értettem")) {
                    VoiceAssistantHelper.unknownFeedback(question)
                } else {
                    intent.message
                }
                tts.speakThen(message) { resumeVoiceAssistantListening() }
            }
            is VoiceAssistantIntent.CallContact -> resolveAssistantCallContact(intent.query)
            is VoiceAssistantIntent.RunAction -> executeAssistantAction(intent.action)
            is VoiceAssistantIntent.TransitRoute -> startTransitRouteFromAssistant(intent.destination)
            is VoiceAssistantIntent.NavWalkRoute -> fetchWalkingRouteFromAssistant(intent.destination)
            is VoiceAssistantIntent.YoutubeSearch -> {
                voiceAssistantReturnPending = true
                searchYoutube(intent.query)
            }
            is VoiceAssistantIntent.BookSearch -> {
                voiceAssistantReturnPending = true
                resolveBookSearch(intent.query)
            }
            is VoiceAssistantIntent.OpenExternalApp -> launchExternalAppFromAssistant(intent.query)
            is VoiceAssistantIntent.WebSearch -> {
                voiceInput.cancel()
                activeFlow = AppFlow.VoiceAssistantChat
                updateFlowDisplay()
                runWebSearch(intent.query, fromAssistant = true)
            }
        }
    }

    private fun executeAssistantAction(action: MenuAction) {
        when (action) {
            MenuAction.TIME_NOW -> tts.speakThen(InfoHelper.speakDateTime()) { resumeVoiceAssistantListening() }
            MenuAction.BATTERY -> {
                tts.speakThen(InfoHelper.batteryAndSignalReport(this)) { resumeVoiceAssistantListening() }
            }
            MenuAction.WIFI_TOGGLE -> {
                toggleWifi()
                resumeVoiceAssistantListening()
            }
            MenuAction.HOTSPOT_TOGGLE -> {
                toggleHotspot()
                resumeVoiceAssistantListening()
            }
            MenuAction.BT_TOGGLE -> {
                toggleBluetooth()
                resumeVoiceAssistantListening()
            }
            MenuAction.FLASHLIGHT -> {
                toggleFlashlight()
                resumeVoiceAssistantListening()
            }
            MenuAction.CALL_FILTER_BLOCK_PRIVATE_TOGGLE,
            MenuAction.CALL_FILTER_MODE_CYCLE -> {
                cycleCallFilterMode()
                resumeVoiceAssistantListening()
            }
            MenuAction.CALL_FILTER_MODE_STATUS -> {
                tts.speakThen(CallFilterStore.speakMode(this)) { resumeVoiceAssistantListening() }
            }

            MenuAction.QR_SCAN -> {
                voiceAssistantReturnPending = true
                tts.speak("Beépített Q R olvasó indítása.")
                qrScanLauncher.launch(Intent(this, QrScanActivity::class.java))
            }
            MenuAction.NAV_WHERE -> startSubFlowFromAssistant { startNavWhereFlow() }
            MenuAction.WEATHER -> {
                tts.speak("Időjárás betöltése. Várj egy pillanatot.")
                WeatherHelper.fetch(
                    onResult = { info -> tts.speakThen(info.speakSummary()) { resumeVoiceAssistantListening() } },
                    onError = { message -> tts.speakThen(message) { resumeVoiceAssistantListening() } }
                )
            }
            MenuAction.VOLUME_UP -> {
                val am = getSystemService(AUDIO_SERVICE) as AudioManager
                am.adjustVolume(AudioManager.ADJUST_RAISE, AudioManager.FLAG_PLAY_SOUND)
                tts.speakThen("Hangerő növelve.") { resumeVoiceAssistantListening() }
            }
            MenuAction.VOLUME_DOWN -> {
                val am = getSystemService(AUDIO_SERVICE) as AudioManager
                am.adjustVolume(AudioManager.ADJUST_LOWER, AudioManager.FLAG_PLAY_SOUND)
                tts.speakThen("Hangerő csökkentve.") { resumeVoiceAssistantListening() }
            }
            MenuAction.TTS_SPEED_UP -> {
                tts.speedUp()
                resumeVoiceAssistantListening()
            }
            MenuAction.TTS_SPEED_DOWN -> {
                tts.speedDown()
                resumeVoiceAssistantListening()
            }
            MenuAction.TTS_ENGINE_READ -> {
                readCurrentTtsEngine()
                resumeVoiceAssistantListening()
            }
            MenuAction.BATTERY_PATROL_TOGGLE -> {
                toggleBatteryPatrol()
                resumeVoiceAssistantListening()
            }
            MenuAction.SOS -> activateSos()
            MenuAction.NAV_WALK -> startSubFlowFromAssistant { startNavWalkFlow() }
            MenuAction.NAV_SEARCH -> startSubFlowFromAssistant { startNavSearchFlow() }
            MenuAction.TRANSIT -> startSubFlowFromAssistant { startTransitNearbyFlow() }
            MenuAction.TRANSIT_STOP -> startSubFlowFromAssistant { startTransitStopFlow() }
            MenuAction.TRANSIT_FAVORITES -> startSubFlowFromAssistant { startTransitFavoritesFlow() }
            MenuAction.TRANSIT_ROUTE -> startSubFlowFromAssistant { startTransitRouteFlow() }
            MenuAction.TRAIN_NEARBY -> startSubFlowFromAssistant { startTrainNearbyFlow() }
            MenuAction.TRAIN_STATION_SEARCH -> startSubFlowFromAssistant { startTrainStationFlow() }
            MenuAction.TRAIN_FAVORITES -> startSubFlowFromAssistant { startTrainFavoritesFlow() }
            MenuAction.CONTACTS -> startSubFlowFromAssistant { startContactCallFlow() }
            MenuAction.CONTACT_BOOK -> startSubFlowFromAssistant { startContactBookFlow() }
            MenuAction.CONTACT_SYNC -> {
                runContactSync(manual = true)
                resumeVoiceAssistantListening()
            }
            MenuAction.CALL_LOG -> startSubFlowFromAssistant { startCallLogFlow() }
            MenuAction.DIAL -> startSubFlowFromAssistant { startDialFlow() }
            MenuAction.CONTACT_CREATE -> startSubFlowFromAssistant { startContactCreateFlow() }
            MenuAction.FAVORITES_ADD -> startSubFlowFromAssistant { startFavoritesAddFlow() }
            MenuAction.FAVORITES_CALL -> startSubFlowFromAssistant { startFavoritesFlow(FavoritesListMode.CALL) }
            MenuAction.FAVORITES_DELETE -> startSubFlowFromAssistant { startFavoritesFlow(FavoritesListMode.DELETE) }
            MenuAction.TIMER_CREATE -> startSubFlowFromAssistant { startTimerCreateFlow() }
            MenuAction.TIMER_LIST -> startSubFlowFromAssistant { startTimerListFlow(TimerListMode.VIEW) }
            MenuAction.TIMER_START -> startSubFlowFromAssistant { startTimerListFlow(TimerListMode.START) }
            MenuAction.TIMER_STOP -> {
                stopActiveTimer()
                resumeVoiceAssistantListening()
            }
            MenuAction.TIMER_DELETE -> startSubFlowFromAssistant { startTimerListFlow(TimerListMode.DELETE) }
            MenuAction.GPS_RADAR -> startSubFlowFromAssistant { startGpsRadarFlow() }
            MenuAction.GPS_RADAR_SAVED_LIST -> startSubFlowFromAssistant { startGpsSavedPoiFlow() }
            MenuAction.GPS_RADAR_SAVE_OWN -> requestGpsSaveOwnLocation(fromAssistant = true)
            MenuAction.GPS_RADAR_SAVE_POI -> requestGpsSaveCurrentPoi(fromAssistant = true)
            MenuAction.DICTAPHONE_RECORD -> startSubFlowFromAssistant { startDictaphoneRecordingFlow() }
            MenuAction.DICTAPHONE_LIBRARY -> startSubFlowFromAssistant { startDictaphoneLibraryFlow() }
            MenuAction.SMS_WRITE -> startSubFlowFromAssistant { startSmsComposeFlow() }
            MenuAction.SMS_READ -> startSubFlowFromAssistant { startSmsInboxFlow() }
            MenuAction.SMS_SENT_READ -> startSubFlowFromAssistant { startSmsSentFlow() }
            MenuAction.EMAIL_WRITE -> startSubFlowFromAssistant { startEmailComposeFlow() }
            MenuAction.ALARM_SET -> startSubFlowFromAssistant { startAlarmSetFlow() }
            MenuAction.ALARM_LIST -> startSubFlowFromAssistant { startAlarmListFlow(deleteMode = false) }
            MenuAction.ALARM_DELETE -> startSubFlowFromAssistant { startAlarmListFlow(deleteMode = true) }
            MenuAction.ALARM_READ_NEXT -> {
                speakNextAlarm()
                resumeVoiceAssistantListening()
            }
            MenuAction.MEDICATION_READ -> {
                readMedicationReminders()
                resumeVoiceAssistantListening()
            }
            MenuAction.MEDICATION_ADD -> startSubFlowFromAssistant { startMedicationAddFlow() }
            MenuAction.MEDICATION_DELETE -> startSubFlowFromAssistant { startMedicationListFlow(deleteMode = true) }
            MenuAction.DAY_GREETING -> {
                tts.speak("Napi üdvözlés betöltése. Várj egy pillanatot.")
                DayInfoHelper.fetchGreeting(
                    onResult = { greeting -> tts.speakThen(greeting) { resumeVoiceAssistantListening() } }
                )
            }
            MenuAction.NEWS_READ -> startSubFlowFromAssistant { startNewsReadFlow() }
            MenuAction.WEB_SEARCH -> startSubFlowFromAssistant { startWebSearchFlow() }
            MenuAction.DAY_SUMMARY -> {
                tts.speak("Napi összefoglaló összeállítása. Várj.")
                DaySummaryHelper.fetchAndSpeak(
                    context = this,
                    onSpeak = { summary -> tts.speakThen(summary) { resumeVoiceAssistantListening() } },
                    onError = { message -> tts.speakThen(message) { resumeVoiceAssistantListening() } }
                )
            }
            MenuAction.STATUS_REPORT -> {
                tts.speakThen(StatusReportHelper.buildReport(this)) { resumeVoiceAssistantListening() }
            }
            MenuAction.SHOPPING_LIST -> startSubFlowFromAssistant { startShoppingListFlow() }
            MenuAction.EMAIL_IMAP_READ -> startSubFlowFromAssistant { startEmailInboxFlow() }
            MenuAction.CALENDAR_READ -> startSubFlowFromAssistant { startCalendarReadFlow() }
            MenuAction.CALENDAR_TOMORROW -> startSubFlowFromAssistant { startCalendarTomorrowFlow() }
            MenuAction.CALENDAR_WEEK -> startSubFlowFromAssistant { startCalendarWeekFlow() }
            MenuAction.CALENDAR_ADD -> startSubFlowFromAssistant { startCalendarAddFlow() }
            MenuAction.NOTE_LIST -> startSubFlowFromAssistant { startNoteListFlow(deleteMode = false) }
            MenuAction.NOTE_CREATE -> startSubFlowFromAssistant { startNoteCreateFlow() }
            MenuAction.NOTE_DELETE -> startSubFlowFromAssistant { startNoteListFlow(deleteMode = true) }
            MenuAction.NOTIFICATIONS_READ -> startSubFlowFromAssistant { startNotificationReadFlow() }
            MenuAction.YOUTUBE -> startSubFlowFromAssistant { startYoutubeFlow() }
            MenuAction.MUSIC -> startSubFlowFromAssistant { startMusicLibraryFlow() }
            MenuAction.WEATHER_CITY -> startSubFlowFromAssistant { startWeatherCityFlow() }
            MenuAction.LIGHT_DETECTOR -> {
                voiceAssistantReturnPending = true
                tts.speak("Fénydetektor indítása.")
                startActivity(Intent(this, LightDetectorActivity::class.java))
            }
            MenuAction.COLOR_DETECTOR -> {
                voiceAssistantReturnPending = true
                tts.speak("Színfelismerő indítása.")
                startActivity(Intent(this, ColorDetectorActivity::class.java))
            }
            MenuAction.ENV_SCANNER -> {
                voiceAssistantReturnPending = true
                tts.speak("Környezeti kitekintő indítása.")
                startActivity(Intent(this, EnvironmentScannerActivity::class.java))
            }
            MenuAction.ENV_SNAPSHOT -> {
                voiceAssistantReturnPending = true
                startActivity(
                    Intent(this, EnvironmentScannerActivity::class.java)
                        .putExtra(EnvironmentScannerActivity.EXTRA_SNAPSHOT_MODE, true)
                )
            }
            MenuAction.CURRENCY_RECOGNIZER -> {
                voiceAssistantReturnPending = true
                tts.speak("Super DL Pénzfelismerő indítása.")
                startActivity(Intent(this, CurrencyRecognizerActivity::class.java))
            }
            MenuAction.MEDICATION_READER -> {
                voiceAssistantReturnPending = true
                tts.speak("Gyógyszerdoboz olvasó indítása.")
                startActivity(textReaderIntent(TextReaderMode.MEDICATION_BOX))
            }
            MenuAction.LABEL_READER -> {
                voiceAssistantReturnPending = true
                tts.speak("Címke olvasó indítása.")
                startActivity(textReaderIntent(TextReaderMode.PRODUCT_LABEL))
            }
            MenuAction.TEXT_READER -> {
                voiceAssistantReturnPending = true
                tts.speak("Szöveg olvasó indítása.")
                startActivity(textReaderIntent(TextReaderMode.GENERAL_TEXT))
            }
            MenuAction.CONTINUOUS_OCR -> {
                voiceAssistantReturnPending = true
                tts.speak("Folyamatos szövegolvasó indítása.")
                startActivity(textReaderIntent(TextReaderMode.CONTINUOUS))
            }
            MenuAction.CALCULATOR -> startSubFlowFromAssistant { startCalculatorFlow() }
            MenuAction.SOUND_TRAINING -> startSubFlowFromAssistant { startSoundTrainingFlow() }
            MenuAction.SOUND_THEME_SELECT -> startSubFlowFromAssistant { startSoundThemeFlow() }
            MenuAction.TRAINING_PLAYGROUND -> startSubFlowFromAssistant { startTrainingPlaygroundFlow() }
            MenuAction.BOOK_LIBRARY -> startSubFlowFromAssistant { startBookLibraryFlow() }
            MenuAction.BOOK_SEARCH -> startSubFlowFromAssistant { startBookSearchFlow() }
            MenuAction.BOOK_RECENT -> startSubFlowFromAssistant { startBookRecentFlow() }
            MenuAction.BOOK_RESUME -> {
                voiceAssistantReturnPending = true
                resumeLastBook()
            }
            MenuAction.BOOK_BOOKMARKS -> startSubFlowFromAssistant { startBookBookmarkFlow(deleteMode = false) }
            MenuAction.BOOK_BOOKMARK_DELETE -> startSubFlowFromAssistant { startBookBookmarkFlow(deleteMode = true) }
            MenuAction.BOOK_FOLDER_SET -> startSubFlowFromAssistant { startBookFolderSetFlow() }
            MenuAction.BOOK_FOLDER_READ -> {
                val folders = BookStore.getCustomFolders(this).map { File(it) }
                tts.speakThen(BookFolderHelper.speakFolders(folders)) { resumeVoiceAssistantListening() }
            }
            MenuAction.BOOK_FOLDER_CLEAR -> {
                clearBookFolders()
                resumeVoiceAssistantListening()
            }
            MenuAction.EMAIL_IMPORT -> startSubFlowFromAssistant { startEmailImportFlow() }
            MenuAction.EMAIL_ADD -> startSubFlowFromAssistant { startEmailAddFlow() }
            MenuAction.EMAIL_LIST -> startSubFlowFromAssistant { startEmailListFlow() }
            MenuAction.EMAIL_SMTP_SETUP -> startSubFlowFromAssistant { startEmailSmtpSetupFlow() }
            MenuAction.EMAIL_SMTP_READ -> {
                val config = SmtpConfigStore.get(this)
                val message = if (config == null) "Nincs beállított e-mail küldő." else config.speakSummary()
                tts.speakThen(message) { resumeVoiceAssistantListening() }
            }
            MenuAction.EMAIL_SMTP_CLEAR -> {
                clearEmailSmtpConfig()
                resumeVoiceAssistantListening()
            }
            MenuAction.SOS_SET_1 -> startSubFlowFromAssistant { startSosNumberSetup(1) }
            MenuAction.SOS_SET_2 -> startSubFlowFromAssistant { startSosNumberSetup(2) }
            MenuAction.SOS_SET_3 -> startSubFlowFromAssistant { startSosNumberSetup(3) }
            MenuAction.SOS_SET_4 -> startSubFlowFromAssistant { startSosNumberSetup(4) }
            MenuAction.SOS_READ_ALL -> {
                val summary = SosPreferences.getNumbers(this).mapIndexed { index, number ->
                    val slot = index + 1
                    if (number.isBlank()) "S.O.S. szám $slot: nincs beállítva" else "S.O.S. szám $slot: $number"
                }.joinToString(". ")
                tts.speakThen(summary) { resumeVoiceAssistantListening() }
            }
            MenuAction.PATROL_BATTERY_TOGGLE -> {
                togglePatrolBattery()
                resumeVoiceAssistantListening()
            }
            MenuAction.PATROL_CALL_ALERT_TOGGLE -> {
                togglePatrolCallAlert()
                resumeVoiceAssistantListening()
            }
            MenuAction.PATROL_SMS_ALERT_TOGGLE -> {
                togglePatrolSmsAlert()
                resumeVoiceAssistantListening()
            }
            MenuAction.PATROL_NOTIFICATION_ALERT_TOGGLE -> {
                togglePatrolNotificationAlert()
                resumeVoiceAssistantListening()
            }
            MenuAction.PATROL_TIME_ANNOUNCE_TOGGLE -> {
                togglePatrolTimeAnnounce()
                resumeVoiceAssistantListening()
            }
            MenuAction.PATROL_TIME_INTERVAL_CYCLE -> {
                cyclePatrolTimeInterval()
                resumeVoiceAssistantListening()
            }
            MenuAction.PATROL_NIGHT_MODE_TOGGLE -> {
                togglePatrolNightMode()
                resumeVoiceAssistantListening()
            }
            MenuAction.PATROL_NIGHT_START_SET -> startSubFlowFromAssistant { startPatrolNightStartFlow() }
            MenuAction.PATROL_NIGHT_END_SET -> startSubFlowFromAssistant { startPatrolNightEndFlow() }
            MenuAction.PATROL_POWER_BUTTON_TIME_TOGGLE -> {
                togglePatrolPowerButtonTime()
                resumeVoiceAssistantListening()
            }
            MenuAction.VOICE_ASSISTANT -> {
                tts.speakThen(VoiceAssistantHelper.helpText()) { resumeVoiceAssistantListening() }
            }
            MenuAction.ELENA_WAKE_LISTEN_TOGGLE -> {
                val enabled = toggleElenaWakeListen(speak = false)
                tts.speakThen(ElenaWakeHelper.speakListenStatus(this, enabled)) { resumeVoiceAssistantListening() }
            }
            MenuAction.ELENA_WAKE_LISTEN_ON -> {
                setElenaWakeListen(true, speak = false)
                tts.speakThen(ElenaWakeHelper.speakListenStatus(this, true)) { resumeVoiceAssistantListening() }
            }
            MenuAction.ELENA_WAKE_LISTEN_OFF -> {
                setElenaWakeListen(false, speak = false)
                tts.speakThen(ElenaWakeHelper.speakListenStatus(this, false)) { resumeVoiceAssistantListening() }
            }
            MenuAction.ELENA_WAKE_TRAIN -> startSubFlowFromAssistant { startElenaWakeTrainFlow(fromAssistant = true) }
            MenuAction.ELENA_WAKE_CUSTOM_LIST -> {
                tts.speakThen(ElenaWakeHelper.speakCustomPhrases(this)) { resumeVoiceAssistantListening() }
            }
            MenuAction.ASSISTANT_DEFAULT_SETUP -> {
                if (AssistantRoleHelper.isAssistantRoleHeld(this)) {
                    tts.speakThen(AssistantRoleHelper.speakStatus(this)) { resumeVoiceAssistantListening() }
                } else {
                    voiceAssistantReturnPending = true
                    startAssistantDefaultSetupFlow()
                }
            }
            MenuAction.ASSISTANT_DEFAULT_STATUS -> {
                tts.speakThen(AssistantRoleHelper.speakStatus(this)) { resumeVoiceAssistantListening() }
            }
            MenuAction.DIALER_DEFAULT_SETUP -> {
                if (DialerRoleHelper.isDefaultDialer(this)) {
                    tts.speakThen(DialerRoleHelper.speakStatus(this)) { resumeVoiceAssistantListening() }
                } else {
                    voiceAssistantReturnPending = true
                    startDialerDefaultSetupFlow()
                }
            }
            MenuAction.DIALER_DEFAULT_STATUS -> {
                tts.speakThen(DialerRoleHelper.speakStatus(this)) { resumeVoiceAssistantListening() }
            }
            MenuAction.TTS_ENGINE_SELECT -> startSubFlowFromAssistant { startTtsEngineFlow() }
            MenuAction.DICTAPHONE_SETTINGS -> startSubFlowFromAssistant { startDictaphoneSettingsFlow() }
            MenuAction.LOCATION_TRAIN -> {
                voiceAssistantReturnPending = true
                startLocationTrainFlow()
            }
            MenuAction.LOCATION_WATCH_START -> {
                voiceAssistantReturnPending = true
                startLocationWatchFlow()
            }
            MenuAction.LOCATION_WATCH_TEXT -> startSubFlowFromAssistant { startLocationWatchTextFlow() }
            MenuAction.LOCATION_PROFILE_LIST -> startSubFlowFromAssistant { startLocationProfileListFlow(deleteMode = false) }
            MenuAction.LOCATION_WATCH_STOP -> {
                stopLocationWatchFlow()
                resumeVoiceAssistantListening()
            }
            MenuAction.FACE_CAMERA -> {
                voiceAssistantReturnPending = true
                startFaceCameraFlow(selfie = false)
            }
            MenuAction.FACE_CAMERA_SELFIE -> {
                voiceAssistantReturnPending = true
                startFaceCameraFlow(selfie = true)
            }
            MenuAction.FACE_CAMERA_QUALITY -> startSubFlowFromAssistant { startCameraQualityFlow() }
            MenuAction.GPS_ROUTE_RECORD -> startSubFlowFromAssistant { startGpsRouteRecordFlow() }
            MenuAction.GPS_ROUTE_STOP -> {
                stopGpsRouteOrGuidanceFlow()
                resumeVoiceAssistantListening()
            }
            MenuAction.GPS_ROUTE_LIST -> startSubFlowFromAssistant { startGpsRouteListFlow(deleteMode = false) }
            MenuAction.GPS_ROUTE_GUIDE -> startSubFlowFromAssistant { startGpsRouteListFlow(deleteMode = false, guideMode = true) }
            MenuAction.GPS_ROUTE_DELETE -> startSubFlowFromAssistant { startGpsRouteListFlow(deleteMode = true) }
            MenuAction.TIMER_EDIT -> startSubFlowFromAssistant { startTimerListFlow(TimerListMode.EDIT) }
            MenuAction.LOCK_PIN_SET -> startSubFlowFromAssistant { startLockPinSetupFlow() }
            MenuAction.LOCK_PIN_STATUS -> {
                tts.speakThen(LockPinStore.speakStatus(this)) { resumeVoiceAssistantListening() }
            }
            MenuAction.LOCK_PIN_TOGGLE -> {
                if (!LockPinStore.hasPinSet(this)) {
                    startSubFlowFromAssistant { startLockPinSetupFlow() }
                } else {
                    toggleLockPin()
                    resumeVoiceAssistantListening()
                }
            }
            MenuAction.KEYGUARD_PIN_ASSIST_TOGGLE -> {
                toggleKeyguardPinAssist()
                resumeVoiceAssistantListening()
            }
            MenuAction.KEYGUARD_PIN_ASSIST_SETUP -> {
                setupKeyguardPinAssist()
                resumeVoiceAssistantListening()
            }
            MenuAction.KEYGUARD_PIN_ASSIST_STATUS -> {
                tts.speakThen(KeyguardPinSettings.speakStatus(this)) { resumeVoiceAssistantListening() }
            }
            MenuAction.EXTERNAL_APPS -> startSubFlowFromAssistant { startExternalAppsFlow() }
            MenuAction.FAVORITE_APPS_LAUNCH ->
                startSubFlowFromAssistant { startFavoriteAppsFlow(AppFlow.FavoriteAppsMode.LAUNCH) }
            MenuAction.FAVORITE_APPS_ADD -> startSubFlowFromAssistant { startFavoriteAppsAddFlow() }
            MenuAction.FAVORITE_APPS_REMOVE ->
                startSubFlowFromAssistant { startFavoriteAppsFlow(AppFlow.FavoriteAppsMode.REMOVE) }
            MenuAction.ABOUT_APP -> {
                tts.speakThen(LegalTexts.aboutApp()) { resumeVoiceAssistantListening() }
            }
            MenuAction.ABOUT_DEVELOPER -> {
                tts.speakThen(LegalTexts.aboutDeveloper()) { resumeVoiceAssistantListening() }
            }
            MenuAction.CONTACT_EMAIL -> {
                tts.speakThen(LegalTexts.contactDeveloper()) {
                    if (!EmailHelper.isConfigured(this)) {
                        tts.speakThen(
                            "Az e-mail küldéshez előbb állítsd be az e-mail küldőt. " +
                                "A fejlesztő címe felolvashatóan: ${LegalTexts.speakEmail()}."
                        ) { resumeVoiceAssistantListening() }
                    } else {
                        voiceAssistantReturnPending = true
                        enterEmailRecipientConfirm(
                            EmailRecipient(LegalTexts.DEVELOPER_EMAIL, LegalTexts.DEVELOPER_NAME)
                        )
                    }
                }
            }
            MenuAction.PRIVACY_POLICY -> startSubFlowFromAssistant {
                startLegalBrowseFlow(LegalTexts.privacyPolicy(), "Adatvédelmi tájékoztató")
            }
            MenuAction.TERMS_OF_USE -> startSubFlowFromAssistant {
                startLegalBrowseFlow(LegalTexts.termsOfUse(), "Felhasználási feltételek")
            }
            MenuAction.LEGAL_NOTICE -> startSubFlowFromAssistant {
                startLegalBrowseFlow(LegalTexts.legalNotice(), "Jogi nyilatkozat")
            }
            MenuAction.EXIT_LAUNCHER -> startSubFlowFromAssistant { startLauncherExitConfirmFlow() }
            else -> tts.speakThen("Ez a parancs még nem elérhető hangból.") { resumeVoiceAssistantListening() }
        }
    }

    private fun startTransitRouteFromAssistant(destination: String) {
        if (!ensureLocationPermission()) {
            tts.speakThen("Helymeghatározás engedély szükséges az útvonalhoz.") { resumeVoiceAssistantListening() }
            return
        }
        voiceAssistantReturnPending = true
        tts.speak("Útvonal keresése: $destination. Várj egy pillanatot.")
        TransitHelper.fetchTransitRoute(
            context = this,
            destination = destination,
            onResult = { route -> showTransitRouteBrowse(route) },
            onError = { message ->
                voiceAssistantReturnPending = false
                tts.speakThen(message) { resumeVoiceAssistantListening() }
            }
        )
    }

    // ==================== YOUTUBE ====================

    private fun startYoutubeFlow() {
        ensureMicAndRun {
            activeFlow = AppFlow.YoutubeAwaitQuery
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd mit keresel a YouTube-on.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val query = spoken.trim()
                    if (query.isBlank()) {
                        exitFlow("Nem értettem a keresést.")
                        return@listen
                    }
                    searchYoutube(query)
                },
                onError = { exitFlow("Nem értettem a keresést.") }
            )
        }
    }

    private fun searchYoutube(query: String, page: Int = 0) {
        voiceInput.cancel()
        tts.speak("Keresés: $query. Várj egy pillanatot.")
        YoutubeHelper.search(
            query = query,
            page = page,
            onResult = { result ->
                activeFlow = AppFlow.YoutubeBrowse(result.videos, 0, query, result.page, result.hasMore)
                updateFlowDisplay()
                val moreHint = if (result.hasMore) " Az utolsó találatnál lefelé söprés a következő 20 videóhoz." else ""
                tts.speak(
                    "${result.videos.size} találat. Söpörj fel-le választás, jobbra lejátszás, balra vissza.$moreHint"
                )
                tts.speakAdd(result.videos.first().speakPreview())
            },
            onError = { message -> exitFlow(message, error = true) }
        )
    }

    private fun navigateYoutubeList(flow: AppFlow.YoutubeBrowse, delta: Int) {
        if (delta > 0 && flow.index == flow.videos.lastIndex && flow.hasMore && flow.query.isNotBlank()) {
            tts.speak("Következő találatok betöltése. Várj.")
            YoutubeHelper.search(
                query = flow.query,
                page = flow.page + 1,
                onResult = { result ->
                    activeFlow = AppFlow.YoutubeBrowse(result.videos, 0, flow.query, result.page, result.hasMore)
                    updateFlowDisplay()
                    tts.speak("${result.videos.size} új találat, ${result.page + 1}. oldal.")
                    tts.speakAdd(result.videos.first().speakPreview())
                },
                onError = { tts.speak("A következő találatok nem tölthetők.") }
            )
            return
        }
        val next = (flow.index + delta + flow.videos.size) % flow.videos.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.videos[next].speakPreview())
    }

    private fun enterYoutubePlayConfirm(videos: List<YoutubeVideo>, index: Int) {
        val video = videos[index]
        activeFlow = AppFlow.YoutubePlayConfirm(video, videos, index)
        updateFlowDisplay()
        repeatYoutubePlayConfirm(video)
    }

    private fun repeatYoutubePlayConfirm(video: YoutubeVideo) {
        tts.speak(
            "${video.speakFull()} Lejátsszam? Söpörj jobbra a lejátszáshoz, söprés balra a mégsehez. Ismétlés: söprés fel."
        )
    }

    private fun playYoutubeVideo(video: YoutubeVideo) {
        voiceInput.cancel()
        YoutubeHelper.playVideo(this, video)
        exitFlow("Lejátszás: ${video.title}.")
    }

    // ==================== NÉVJEGY & JOGI ====================

    private fun contactDeveloperByEmailInternal() {
        tts.speak(LegalTexts.contactDeveloper())
        if (!EmailHelper.isConfigured(this)) {
            tts.speakAdd(
                "Az e-mail küldéshez előbb állítsd be az e-mail küldőt. " +
                    "A fejlesztő címe felolvashatóan: ${LegalTexts.speakEmail()}."
            )
            return
        }
        val developer = EmailRecipient(LegalTexts.DEVELOPER_EMAIL, LegalTexts.DEVELOPER_NAME)
        enterEmailRecipientConfirm(developer)
    }

    private fun startLauncherExitConfirmFlow() {
        activeFlow = AppFlow.LauncherExitConfirm
        updateFlowDisplay()
        tts.speak(
            "Kezdőképernyő váltás. Söpörj jobbra a rendszer választó megnyitásához. Söpörj balra vissza a beállításokhoz."
        )
    }

    private fun openLauncherExitSettings() {
        val intent = LauncherExitHelper.createHomeSettingsIntent(this)
        if (intent != null) {
            tts.speakThen("Megnyitom a kezdőképernyő alkalmazás választót.") {
                try {
                    launcherExitSettingsLauncher.launch(intent)
                } catch (_: Exception) {
                    activeFlow = AppFlow.Menu
                    updateDisplay()
                    startPermissionGuideFlow(PermissionGuideType.LAUNCHER_EXIT, "Launcher váltás útmutató")
                }
            }
        } else {
            startPermissionGuideFlow(PermissionGuideType.LAUNCHER_EXIT, "Launcher váltás útmutató")
        }
    }

    private fun startPermissionGuideFlow(type: PermissionGuideType, title: String) {
        val sections = PermissionGuideTexts.sections(type).map {
            LegalSection(it.title, it.body)
        }
        if (sections.isEmpty()) {
            tts.speak("Nincs útmutató.")
            return
        }
        activeFlow = AppFlow.GuideBrowse(sections, 0, title)
        updateFlowDisplay()
        tts.speak("$title. ${sections.size} rész. Söpörj fel-le navigálás, jobbra teljes felolvasás, balra vissza.")
        tts.speakAdd(guideSectionPreview(sections.first()))
    }

    private fun guideSectionPreview(section: LegalSection): String {
        val preview = section.body.take(100)
        return if (preview.length < section.body.length) "${section.title}. $preview…" else "${section.title}. $preview"
    }

    private fun navigateGuideList(flow: AppFlow.GuideBrowse, delta: Int) {
        if (flow.sections.isEmpty()) return
        val next = (flow.index + delta + flow.sections.size) % flow.sections.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(guideSectionPreview(flow.sections[next]))
    }

    private fun handleQrFollowUp(type: QrActionType, payload: String) {
        when (type) {
            QrActionType.CALL -> {
                if (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE)
                    != PackageManager.PERMISSION_GRANTED
                ) {
                    tts.speak("Hívás engedély szükséges.")
                    return
                }
                placeCall(payload, payload)
            }
            QrActionType.SMS -> {
                val recipient = Recipient(payload, payload)
                enterSmsRecipientConfirm(recipient)
            }
            QrActionType.EMAIL -> {
                val recipient = EmailRecipient(payload.lowercase(), payload)
                enterEmailRecipientConfirm(recipient)
            }
            QrActionType.NAVIGATE -> fetchWalkingRouteFromQr(payload)
            else -> Unit
        }
    }

    private fun startLegalBrowseFlow(sections: List<LegalSection>, title: String) {
        if (sections.isEmpty()) {
            tts.speak("Nincs megjeleníthető szöveg.")
            return
        }
        activeFlow = AppFlow.LegalBrowse(sections, 0)
        updateFlowDisplay()
        tts.speak("$title. ${sections.size} rész. Söpörj fel-le navigálás, jobbra teljes felolvasás, balra vissza.")
        tts.speakAdd(sections.first().speakPreview())
    }

    private fun navigateLegalList(flow: AppFlow.LegalBrowse, delta: Int) {
        val next = (flow.index + delta + flow.sections.size) % flow.sections.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.sections[next].speakPreview())
    }

    // ==================== S.O.S. ====================

    private fun activateSos() {
        val numbers = SosPreferences.getNumbers(this).filter { it.isNotBlank() }
        if (numbers.isEmpty()) {
            tts.speak("Nincs beállítva S.O.S. telefonszám. Kérlek add meg a beállításokban.")
            return
        }
        startSosCountdown()
    }

    private fun startSosCountdown() {
        sosCountdownActive = true
        activeFlow = AppFlow.SosCountdown(SOS_COUNTDOWN_SECONDS)
        updateFlowDisplay()

        tts.speakThen(
            "S.O.S. vészjelzés. $SOS_COUNTDOWN_SECONDS másodperc múlva indul. " +
            "Söpörj balra, vagy mondd: mégse a leállításhoz."
        ) {
            if (!sosCountdownActive) return@speakThen
            startSosCancelListener()
            runCountdownStep(SOS_COUNTDOWN_SECONDS)
        }
    }

    private fun runCountdownStep(secondsLeft: Int) {
        if (!sosCountdownActive) return

        if (secondsLeft <= 0) {
            executeSos()
            return
        }

        activeFlow = AppFlow.SosCountdown(secondsLeft)
        updateFlowDisplay()
        vibrate(150)

        tts.speakThen(sosCountdownSpeech(secondsLeft)) {
            if (!sosCountdownActive) return@speakThen
            countdownHandler.postDelayed({ runCountdownStep(secondsLeft - 1) }, 1000)
        }
    }

    private fun sosCountdownSpeech(secondsLeft: Int): String = when (secondsLeft) {
        5 -> "Öt"
        4 -> "Négy"
        3 -> "Három"
        2 -> "Kettő"
        1 -> "Egy"
        else -> secondsLeft.toString()
    }

    private fun startSosCancelListener() {
        if (!sosCountdownActive) return
        if (!voiceInput.isAvailable()) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            return
        }

        voiceInput.listenPrompt(
            prompt = "Mégse",
            onResult = { spoken ->
                if (!sosCountdownActive) return@listenPrompt
                if (VoiceConfirmation.parse(spoken) == VoiceConfirmation.Result.CANCEL) {
                    cancelSosCountdown()
                } else {
                    startSosCancelListener()
                }
            },
            onError = {
                if (sosCountdownActive) startSosCancelListener()
            }
        )
    }

    private fun cancelSosCountdown() {
        sosCountdownActive = false
        countdownHandler.removeCallbacksAndMessages(null)
        voiceInput.cancel()
        tts.stop()
        activeFlow = AppFlow.Menu
        updateDisplay()
        tts.speak("S.O.S. vészjelzés megszakítva.")
    }

    private fun executeSos() {
        val numbers = SosPreferences.getNumbers(this).filter { it.isNotBlank() }
        if (numbers.isEmpty()) {
            cancelSosCountdown()
            return
        }

        sosCountdownActive = false
        countdownHandler.removeCallbacksAndMessages(null)
        voiceInput.cancel()
        activeFlow = AppFlow.Menu
        updateDisplay()

        tts.speak("S.O.S. vészjelzés aktiválva! Hívom a mentőszámokat.")
        vibrate(500)
        startForegroundService(Intent(this, SosService::class.java).apply {
            putStringArrayListExtra(SosService.EXTRA_NUMBERS, ArrayList(numbers))
        })
    }

    private fun startSosNumberSetup(slot: Int) {
        activeFlow = AppFlow.SosSetupMethodPick(slot, 0)
        updateFlowDisplay()
        tts.speak(
            "S.O.S. szám $slot. Válassz: szám beírása, vagy névjegyből. " +
                "Fel-le választás, jobbra megerősítés, balra vissza."
        )
        tts.speakAdd(sosSetupMethodLabel(0))
    }

    private fun sosSetupMethodLabel(index: Int): String =
        if (index == 0) "A – Szám beírása" else "B – Névjegyből választás"

    private fun navigateSosSetupMethodPick(flow: AppFlow.SosSetupMethodPick, delta: Int) {
        val next = (flow.index + delta + 2) % 2
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(sosSetupMethodLabel(next))
    }

    private fun onSosSetupMethodActivate(flow: AppFlow.SosSetupMethodPick) {
        when (flow.index) {
            0 -> enterNumericDictationAwait(
                AppFlow.NumericDictationAwait(
                    purpose = NumberPadPurpose.SOS,
                    sosSlot = flow.slot
                )
            )
            1 -> startSosContactBrowse(flow.slot)
        }
    }

    private fun startSosContactBrowse(slot: Int) {
        val contacts = ContactHelper.listAllWithPhone(this)
        if (contacts.isEmpty()) {
            tts.speak("Nincs névjegy telefonszámmal.")
            return
        }
        activeFlow = AppFlow.SosContactCandidateBrowse(contacts, 0, slot)
        updateFlowDisplay()
        tts.speak(
            "${contacts.size} névjegy. Fel-le választás, jobbra mentés S.O.S. számként, balra vissza."
        )
        tts.speakAdd(contacts.first().let { "${it.name}. ${ContactHelper.maskPhone(it.phone)}" })
    }

    private fun navigateSosContactCandidates(flow: AppFlow.SosContactCandidateBrowse, delta: Int) {
        val next = (flow.index + delta + flow.contacts.size) % flow.contacts.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        val contact = flow.contacts[next]
        tts.speak("${contact.name}. ${ContactHelper.maskPhone(contact.phone)}")
    }

    private fun saveSosNumberFromContact(slot: Int, contact: ContactMatch) {
        SosPreferences.setNumber(this, slot, contact.phone)
        activeFlow = AppFlow.Menu
        updateDisplay()
        feedbackSuccess()
        tts.speak("S.O.S. szám $slot mentve: ${contact.name}.")
    }

    private fun startFavoritesAddFlow() {
        val candidates = FavoriteContactCatalog.getAddableCandidates(this)
        if (candidates.isEmpty()) {
            tts.speak("Nincs hozzáadható névjegy, vagy minden már kedvenc.")
            return
        }
        activeFlow = AppFlow.FavoriteContactCandidateBrowse(candidates, 0)
        updateFlowDisplay()
        tts.speak(
            "${candidates.size} választható névjegy. Söpörj fel-le választás, jobbra hozzáadás, balra vissza."
        )
        tts.speakAdd(candidates.first().speakPreview())
    }

    private fun navigateFavoriteContactCandidates(flow: AppFlow.FavoriteContactCandidateBrowse, delta: Int) {
        val next = (flow.index + delta + flow.candidates.size) % flow.candidates.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.candidates[next].speakPreview())
    }

    private fun addFavoriteContactCandidate(flow: AppFlow.FavoriteContactCandidateBrowse) {
        val candidate = flow.candidates[flow.index]
        if (!FavoritesStore.add(this, candidate.name(), candidate.phone())) {
            tts.speak("Ez a szám már kedvenc.")
            return
        }
        feedbackSuccess()
        val updated = FavoriteContactCatalog.getAddableCandidates(this)
        if (updated.isEmpty()) {
            exitFlow("Kedvenc mentve: ${candidate.name()}. Nincs több hozzáadható névjegy.", success = true)
            return
        }
        val nextIndex = flow.index.coerceAtMost(updated.lastIndex)
        activeFlow = AppFlow.FavoriteContactCandidateBrowse(updated, nextIndex)
        updateFlowDisplay()
        tts.speak("Kedvenc mentve: ${candidate.name()}.")
        tts.speakAdd(updated[nextIndex].speakPreview())
    }

    private fun readAllSosNumbers() {
        val summary = SosPreferences.getNumbers(this).mapIndexed { index, number ->
            val slot = index + 1
            if (number.isBlank()) "S.O.S. szám $slot: nincs beállítva" else "S.O.S. szám $slot: $number"
        }.joinToString(". ")
        tts.speak(summary)
    }

    // ==================== ZSEBLÁMPA ====================

    // ==================== KÖNYVEK ====================

    private fun startBookLibraryFlow() {
        tts.speak("Könyvtár keresése. Várj egy pillanatot.")
        activeFlow = AppFlow.BookLoading
        updateFlowDisplay()
        Thread {
            val books = BookLibrary.scan(this)
            postWhenAlive {
                if (activeFlow !is AppFlow.BookLoading) return@postWhenAlive
                if (books.isEmpty()) {
                    exitFlow("Nem találtam könyvet a telefonon. Tedd a Letöltések, Dokumentumok vagy Könyvek mappába.")
                    return@postWhenAlive
                }
                activeFlow = AppFlow.BookLibraryBrowse(books, 0)
                updateFlowDisplay()
                tts.speak(
                    "${books.size} könyv. Támogatott formátumok: EPUB, PDF, MOBI, TXT, DOCX és mások. " +
                        "Söpörj fel-le választás, jobbra megnyitás, balra vissza."
                )
                tts.speakAdd(books.first().speakPreview())
            }
        }.start()
    }

    private fun startBookRecentFlow() {
        Thread {
            val books = BookLibrary.resolveRecent(this)
            postWhenAlive {
                if (books.isEmpty()) {
                    tts.speak("Még nincs nem rég olvasott könyv.")
                    return@postWhenAlive
                }
                activeFlow = AppFlow.BookRecentBrowse(books, 0)
                updateFlowDisplay()
                tts.speak("${books.size} nem rég olvasott könyv. Söpörj fel-le választás, jobbra folytatás, balra vissza.")
                tts.speakAdd(books.first().speakPreview())
            }
        }.start()
    }

    private fun startBookBookmarkFlow(deleteMode: Boolean) {
        val bookmarks = BookStore.getBookmarks(this)
        if (bookmarks.isEmpty()) {
            tts.speak("Még nincs mentett könyvjelző.")
            return
        }
        activeFlow = AppFlow.BookBookmarkBrowse(bookmarks, 0, deleteMode)
        updateFlowDisplay()
        val intro = if (deleteMode) {
            "${bookmarks.size} könyvjelző. Törlés mód. Söpörj fel-le választás, jobbra törlés megerősítése."
        } else {
            "${bookmarks.size} könyvjelző. Söpörj fel-le választás, jobbra ugrás a könyvjelzőhöz, balra vissza."
        }
        tts.speak(intro)
        tts.speakAdd(bookmarks.first().speakPreview())
    }

    private fun startBookSearchFlow() {
        ensureMicAndRun {
            activeFlow = AppFlow.BookSearchAwaitQuery
            updateFlowDisplay()
            listenForBookSearchQuery()
        }
    }

    private fun listenForBookSearchQuery() {
        voiceInput.listen(
            prompt = "Mondd a keresett könyv címét vagy szerzőjét.",
            speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
            onResult = { spoken -> resolveBookSearch(spoken) },
            onError = { exitFlow("Nem értettem a keresést.") }
        )
    }

    private fun resolveBookSearch(query: String) {
        voiceInput.cancel()
        val trimmed = query.trim()
        if (trimmed.isBlank()) {
            exitFlow("Üres keresés.")
            return
        }
        tts.speak("Keresés: $trimmed. Várj.")
        activeFlow = AppFlow.BookLoading
        updateFlowDisplay()
        Thread {
            val all = BookLibrary.scan(this)
            val matches = BookSearchHelper.search(all, trimmed)
            postWhenAlive {
                if (activeFlow !is AppFlow.BookLoading) return@postWhenAlive
                if (matches.isEmpty()) {
                    exitFlow("Nincs találat erre: $trimmed.")
                    return@postWhenAlive
                }
                activeFlow = AppFlow.BookLibraryBrowse(matches, 0)
                updateFlowDisplay()
                tts.speak("${matches.size} találat. Söpörj fel-le választás, jobbra megnyitás, balra vissza.")
                tts.speakAdd(matches.first().speakPreview())
            }
        }.start()
    }

    private fun onBookmarkListActivate(flow: AppFlow.BookBookmarkBrowse) {
        val bookmark = flow.bookmarks[flow.index]
        if (flow.deleteMode) {
            enterBookmarkDeleteConfirm(bookmark, flow.bookmarks, flow.index)
        } else {
            jumpToBookmark(bookmark)
        }
    }

    private fun enterBookmarkDeleteConfirm(
        bookmark: BookBookmark,
        bookmarks: List<BookBookmark>,
        index: Int
    ) {
        activeFlow = AppFlow.BookBookmarkDeleteConfirm(bookmark, bookmarks, index)
        updateFlowDisplay()
        repeatBookmarkDeleteConfirm(bookmark)
    }

    private fun repeatBookmarkDeleteConfirm(bookmark: BookBookmark) {
        tts.speak("Törlöd ezt a könyvjelzőt? ${bookmark.speakPreview()} Söpörj jobbra a törléshez, söprés balra a mégsehez.")
    }

    private fun deleteBookmark(bookmark: BookBookmark) {
        voiceInput.cancel()
        BookStore.deleteBookmark(this, bookmark.id)
        val remaining = BookStore.getBookmarks(this)
        if (remaining.isEmpty()) {
            exitFlow("Könyvjelző törölve. Nincs több mentett könyvjelző.")
            return
        }
        val nextIndex = 0.coerceAtMost(remaining.lastIndex)
        activeFlow = AppFlow.BookBookmarkBrowse(remaining, nextIndex, deleteMode = true)
        updateFlowDisplay()
        tts.speak("Könyvjelző törölve. ${remaining.size} maradt.")
        tts.speakAdd(remaining[nextIndex].speakPreview())
    }

    private fun startBookFolderSetFlow() {
        ensureMicAndRun {
            voiceInput.listen(
                prompt = "Mondd a könyvmappa nevét vagy útvonalát. Például: Letöltések, Dokumentumok, Könyvek, vagy teljes útvonal.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken -> saveBookFolder(spoken) },
                onError = { tts.speak("Nem értettem a mappa nevét. Próbáld újra.") }
            )
        }
    }

    private fun saveBookFolder(spoken: String) {
        val folder = BookFolderHelper.parseSpokenFolder(this, spoken)
        if (folder == null) {
            tts.speak("A mappa nem található vagy nem olvasható. Próbáld újra, vagy mondj teljes útvonalat.")
            return
        }
        val ok = BookStore.addCustomFolder(this, folder.absolutePath)
        if (!ok) {
            tts.speak("Legfeljebb öt egyéni könyvmappa adható meg. Töröld a régieket, vagy használd a könyvmappa törlése menüt.")
            return
        }
        tts.speak("Könyvmappa mentve. ${BookFolderHelper.speakFolder(folder)}")
    }

    private fun readBookFolders() {
        val folders = BookStore.getCustomFolders(this).map { File(it) }
        tts.speak(BookFolderHelper.speakFolders(folders))
    }

    private fun clearBookFolders() {
        BookStore.clearCustomFolders(this)
        tts.speak("Egyéni könyvmappák törölve. Az alapértelmezett mappák továbbra is használatban.")
    }

    private fun resumeLastBook() {
        val recent = BookLibrary.resolveRecent(this)
        val book = recent.firstOrNull()
        if (book == null) {
            if (voiceAssistantReturnPending) {
                voiceAssistantReturnPending = false
                tts.speakThen("Nincs folytatható könyv. Először nyiss meg egyet a könyvtárból.") {
                    resumeVoiceAssistantListening()
                }
            } else {
                tts.speak("Nincs folytatható könyv. Először nyiss meg egyet a könyvtárból.")
            }
            return
        }
        openBook(book, resume = true)
    }

    private fun navigateBookList(flow: AppFlow.BookLibraryBrowse, delta: Int) {
        val next = (flow.index + delta + flow.books.size) % flow.books.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.books[next].speakPreview())
    }

    private fun navigateRecentBookList(flow: AppFlow.BookRecentBrowse, delta: Int) {
        val next = (flow.index + delta + flow.books.size) % flow.books.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.books[next].speakPreview())
    }

    private fun navigateBookmarkList(flow: AppFlow.BookBookmarkBrowse, delta: Int) {
        val next = (flow.index + delta + flow.bookmarks.size) % flow.bookmarks.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        tts.speak(flow.bookmarks[next].speakPreview())
    }

    private fun openBook(book: BookEntry, resume: Boolean = false) {
        val offset = if (resume) BookStore.getPosition(this, book.path) else 0
        tts.speak("Könyv betöltése: ${book.title}. Várj.")
        activeFlow = AppFlow.BookLoading
        updateFlowDisplay()
        Thread {
            val loaded = loadBookText(book)
            postWhenAlive {
                if (activeFlow !is AppFlow.BookLoading) return@postWhenAlive
                if (loaded.success == null) {
                    exitBookReading(loaded.errorMessage ?: "A könyv betöltése sikertelen.")
                    return@postWhenAlive
                }
                val (title, text) = loaded.success
                activeFlow = AppFlow.BookReading(book, 0, 0, 0)
                updateFlowDisplay()
                val intro = if (offset > 0) {
                    "Folytatás: ${book.title}. Mentett pozícióból."
                } else {
                    "Olvasás: ${book.title}."
                }
                tts.speakThen(
                    "$intro Söpörj fel: ismétlés. Le: következő rész. Jobbra: könyvjelző. Balra: leállítás."
                ) {
                    bookReader.startWithText(book, title, text, offset)
                }
            }
        }.start()
    }

    private fun jumpToBookmark(bookmark: BookBookmark) {
        val books = BookLibrary.scan(this)
        val book = books.firstOrNull { it.path == bookmark.bookPath }
            ?: BookEntry(
                path = bookmark.bookPath,
                title = bookmark.bookTitle,
                format = bookmark.bookPath.substringAfterLast('.', "txt"),
                sizeBytes = 0L
            )
        tts.speak("Ugrás a könyvjelzőhöz: ${bookmark.bookTitle}.")
        activeFlow = AppFlow.BookLoading
        updateFlowDisplay()
        Thread {
            val loaded = loadBookText(book)
            postWhenAlive {
                if (activeFlow !is AppFlow.BookLoading) return@postWhenAlive
                if (loaded.success == null) {
                    exitBookReading(loaded.errorMessage ?: "A könyv betöltése sikertelen.")
                    return@postWhenAlive
                }
                val (title, text) = loaded.success
                activeFlow = AppFlow.BookReading(book, 0, 0, bookmark.charOffset)
                updateFlowDisplay()
                tts.speakThen("Olvasás a könyvjelzőtől. ${bookmark.preview.take(80)}") {
                    bookReader.startWithText(book, title, text, bookmark.charOffset)
                }
            }
        }.start()
    }

    private data class BookLoadResult(
        val success: Pair<String, String>? = null,
        val errorMessage: String? = null
    )

    private fun loadBookText(book: BookEntry): BookLoadResult {
        val cacheFile = BookLibrary.materializeToCache(this, book)
            ?: return BookLoadResult(errorMessage = "A könyv betöltése sikertelen.")
        return BookTextExtractor.extract(this, cacheFile).fold(
            onSuccess = { BookLoadResult(success = it.title to it.text) },
            onFailure = { BookLoadResult(errorMessage = it.message ?: "A könyv betöltése sikertelen.") }
        )
    }

    private fun addBookBookmark() {
        val bookmark = bookReader.addBookmark()
        if (bookmark == null) {
            tts.speak("A könyvjelző mentése sikertelen. Elérted a maximumot, vagy nincs aktív olvasás.")
            return
        }
        tts.speak("Könyvjelző mentve. ${bookmark.speakPreview()}")
    }

    private fun finishBookReading(message: String) {
        bookReader.stop()
        exitFlow(message)
    }

    private fun exitBookReading(message: String) {
        bookReader.stop()
        exitFlow(message)
    }

    private fun startTtsEngineFlow() {
        tts.speak("T T S hangok keresése. Kérem várjon.")
        Thread {
            val options = TtsVoiceCatalog.getSelectableOptions(applicationContext)
            postWhenAlive {
                if (options.isEmpty()) {
                    tts.speak(
                        "Nem található telepített T T S hang. " +
                            "Telepíts egyet a rendszer beállításokban, például Google beszéd, vagy eSpeak."
                    )
                    return@postWhenAlive
                }
                val index = TtsVoiceCatalog.findCurrentIndex(options, this)
                activeFlow = AppFlow.TtsVoiceBrowse(options, index)
                updateFlowDisplay()
                tts.speak(
                    "${options.size} T T S hang. Söpörj fel-le választás, jobbra kiválasztás és beállítás, balra vissza."
                )
                speakTtsVoice(options[index])
            }
        }.start()
    }

    private fun navigateTtsVoiceList(flow: AppFlow.TtsVoiceBrowse, delta: Int) {
        val next = (flow.index + delta + flow.options.size) % flow.options.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        speakTtsVoice(flow.options[next])
    }

    private fun speakTtsVoice(option: TtsVoiceOption) {
        tts.speak(option.speakFull())
    }

    private fun selectTtsVoice(option: TtsVoiceOption) {
        voiceInput.cancel()
        activeFlow = AppFlow.Menu
        updateDisplay()
        tts.switchEngine(
            packageName = option.enginePackage,
            voiceName = option.voiceName,
            onReady = {
                feedbackSuccess()
                tts.speak(
                    "T T S hang beállítva: ${option.displayLabel}. Ez egy teszt felolvasás az új hanggal."
                )
            },
            onFailed = {
                tts.switchEngine(packageName = null, voiceName = null) {
                    tts.speak(
                        "A kiválasztott T T S hang nem indítható. Visszaállítva a rendszer alapértelmezett hangra."
                    )
                }
            }
        )
    }

    private fun readCurrentTtsEngine() {
        val options = TtsVoiceCatalog.getSelectableOptions(this)
        if (options.isEmpty()) {
            tts.speak("Nem található telepített T T S hang.")
            return
        }
        val current = options[TtsVoiceCatalog.findCurrentIndex(options, this)]
        tts.speak("Aktuális T T S hang: ${current.speakFull()}.")
    }

    private fun startSoundTrainingFlow() {
        val items = SoundType.trainingOrder
        activeFlow = AppFlow.SoundTrainingBrowse(items, 0)
        updateFlowDisplay()
        tts.speak(
            "Hangok betanítása. ${items.size} hang. Söpörj fel-le választás, jobbra hallgatás és magyarázat, balra vissza."
        )
        playSoundTrainingItem(items.first())
    }

    private fun navigateSoundTraining(flow: AppFlow.SoundTrainingBrowse, delta: Int) {
        val next = (flow.index + delta + flow.items.size) % flow.items.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        sounds.play(SoundType.MENU_NAV)
        tts.speak(flow.items[next].label)
    }

    private fun playSoundTrainingItem(type: SoundType) {
        sounds.play(type)
        tts.speak("${type.label}. ${type.description}")
    }

    private fun startSoundThemeFlow() {
        val themes = SoundTheme.selectable
        val current = SoundThemeStore.get(this)
        val index = themes.indexOf(current).coerceAtLeast(0)
        activeFlow = AppFlow.SoundThemeBrowse(themes, index)
        updateFlowDisplay()
        tts.speak(
            "Söpörj hangtéma. ${themes.size} választék. " +
                "Söpörj fel-le választás, jobbra beállítás és előnézet, balra vissza."
        )
        speakSoundTheme(themes[index])
    }

    private fun navigateSoundTheme(flow: AppFlow.SoundThemeBrowse, delta: Int) {
        val next = (flow.index + delta + flow.themes.size) % flow.themes.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        sounds.play(SoundType.MENU_NAV)
        speakSoundTheme(flow.themes[next])
    }

    private fun speakSoundTheme(theme: SoundTheme) {
        val current = SoundThemeStore.get(this)
        tts.speak("${theme.label}. ${theme.description} Jelenlegi: ${current.label}.")
    }

    private fun selectSoundTheme(flow: AppFlow.SoundThemeBrowse) {
        val theme = flow.themes[flow.index]
        SoundThemeStore.set(this, theme)
        sounds.reloadTheme()
        theme.previewSwipeTypes().forEachIndexed { index, type ->
            mainHandler.postDelayed({ sounds.play(type) }, index * 220L)
        }
        feedbackSuccess()
        activeFlow = AppFlow.Menu
        updateDisplay()
        tts.speak("Söpörj hangtéma beállítva: ${theme.label}.")
    }

    private fun cycleAlertSoundVolume() {
        AlertSoundSettingsStore.cycleVolumePercent(this)
        tts.speak(AlertSoundSettingsStore.speakVolume(this))
        AlertSoundPlayer.preview(this, AlertSoundPreset.DOUBLE_BEEP)
    }

    private fun toggleAlertSilentMode() {
        val label = "Néma mód"
        val wasEnabled = AlertSoundSettingsStore.isSilentMode(this)
        tts.speak(ToggleAnnouncement.speakBinaryToggle(label, wasEnabled))
        val next = AlertSoundSettingsStore.toggleSilentMode(this)
        val systemResult = QuietModeHelper.apply(this, next)
        val extra = when {
            next && systemResult.dndApplied ->
                "Bekapcsolva. Az emlékeztető hangok és értesítés-bemondások némák. A söprés hangok és a telefon csengőhangja továbbra is működik."
            next && systemResult.needsPolicyAccess ->
                "Az emlékeztető hangok és értesítés-bemondások némák. A söprés hangok és a telefon csengőhangja továbbra is működik. " +
                    "A teljes rendszer-csendhez engedélyezd a Super DL-t a megnyitott Ne zavarjanak beállításban."
            next ->
                "Bekapcsolva. Az emlékeztető hangok némák. A söprés hangok és a telefon csengőhangja továbbra is működik."
            else ->
                "Kikapcsolva. A korábbi értesítési beállítás visszaállítva."
        }
        tts.speak(ToggleAnnouncement.speakAfterToggle(label, next, extra))
        if (next && systemResult.needsPolicyAccess) {
            QuietModeHelper.openPolicyAccessSettings(this)
        }
        if (!next) {
            AlertSoundPlayer.preview(this, AlertSoundPreset.SOFT_CHIME)
        }
    }

    private fun startAlertSoundPresetFlow(category: AlertSoundCategory) {
        val presets = AlertSoundPreset.selectable
        val current = AlertSoundStore.getPreset(this, category)
        val index = presets.indexOf(current).coerceAtLeast(0)
        activeFlow = AppFlow.AlertSoundPresetBrowse(category, presets, index)
        updateFlowDisplay()
        tts.speak(
            "${category.label}. ${presets.size} hangválaszték. " +
                "Söpörj fel-le választás, jobbra beállítás és előnézet, balra vissza."
        )
        speakAlertSoundPreset(category, presets[index])
    }

    private fun navigateAlertSoundPreset(flow: AppFlow.AlertSoundPresetBrowse, delta: Int) {
        val next = (flow.index + delta + flow.presets.size) % flow.presets.size
        activeFlow = flow.copy(index = next)
        updateFlowDisplay()
        sounds.play(SoundType.MENU_NAV)
        speakAlertSoundPreset(flow.category, flow.presets[next])
    }

    private fun speakAlertSoundPreset(category: AlertSoundCategory, preset: AlertSoundPreset) {
        tts.speak("${preset.label}. Jelenlegi: ${AlertSoundStore.getPreset(this, category).label}.")
    }

    private fun selectAlertSoundPreset(flow: AppFlow.AlertSoundPresetBrowse) {
        val preset = flow.presets[flow.index]
        AlertSoundStore.setPreset(this, flow.category, preset)
        AlertSoundPlayer.preview(this, preset)
        feedbackSuccess()
        activeFlow = AppFlow.Menu
        updateDisplay()
        tts.speak("${flow.category.label} hang beállítva: ${preset.label}.")
    }

    // ==================== TANULÓ MÓD ====================

    private fun startTrainingPlaygroundFlow() {
        val steps = TrainingCurriculum.steps
        lastLeftSwipeAt = 0L
        activeFlow = AppFlow.TrainingPlayground(steps, 0, 0, false)
        updateFlowDisplay()
        enterTrainingStep(activeFlow as AppFlow.TrainingPlayground)
    }

    private fun enterTrainingStep(flow: AppFlow.TrainingPlayground) {
        val step = flow.steps[flow.stepIndex]
        when (step) {
            is TrainingStep.Explain -> tts.speak(step.text)
            is TrainingStep.Practice -> {
                tts.speak(step.instruction)
                mainHandler.postDelayed({
                    val current = activeFlow
                    if (current is AppFlow.TrainingPlayground &&
                        current.stepIndex == flow.stepIndex &&
                        !current.awaitingAdvance
                    ) {
                        tts.speak(step.choices[current.choiceIndex])
                    }
                }, 900L)
            }
        }
    }

    private fun handleTrainingNavigate(flow: AppFlow.TrainingPlayground, delta: Int) {
        val step = flow.steps[flow.stepIndex]
        when (step) {
            is TrainingStep.Explain -> tts.speak(step.text)
            is TrainingStep.Practice -> {
                if (flow.awaitingAdvance) {
                    tts.speak(step.successText)
                    return
                }
                val next = (flow.choiceIndex + delta + step.choices.size) % step.choices.size
                activeFlow = flow.copy(choiceIndex = next)
                updateFlowDisplay()
                sounds.play(SoundType.MENU_NAV)
                tts.speak(step.choices[next])
            }
        }
    }

    private fun handleTrainingActivate(flow: AppFlow.TrainingPlayground) {
        val step = flow.steps[flow.stepIndex]
        when (step) {
            is TrainingStep.Explain -> advanceTrainingStep(flow)
            is TrainingStep.Practice -> {
                if (flow.awaitingAdvance) {
                    advanceTrainingStep(flow)
                    return
                }
                if (flow.choiceIndex == step.correctIndex) {
                    feedbackSuccess()
                    activeFlow = flow.copy(awaitingAdvance = true)
                    updateFlowDisplay()
                    tts.speak(step.successText)
                } else {
                    feedbackError()
                    tts.speak(step.wrongText)
                }
            }
        }
    }

    private fun advanceTrainingStep(flow: AppFlow.TrainingPlayground) {
        val nextIndex = flow.stepIndex + 1
        if (nextIndex >= flow.steps.size) {
            exitFlow("Tanuló mód kész. Gratulálok!", success = true)
            return
        }
        activeFlow = AppFlow.TrainingPlayground(flow.steps, nextIndex, 0, false)
        updateFlowDisplay()
        enterTrainingStep(activeFlow as AppFlow.TrainingPlayground)
    }

    private fun toggleBatteryPatrol() {
        val label = "Teljes őrség"
        val wasEnabled = BatteryPatrolManager.isEnabled(this)
        tts.speak(ToggleAnnouncement.speakBinaryToggle(label, wasEnabled))
        val next = !wasEnabled
        BatteryPatrolManager.setEnabled(this, next)
        val extra = if (next) {
            "Bekapcsolva. Akkumulátor, idő, értesítés és képernyő figyelés a beállítások szerint. Zárolt képernyőn is működik."
        } else {
            "Kikapcsolva."
        }
        tts.speak(ToggleAnnouncement.speakAfterToggle(label, next, extra))
    }

    private fun togglePatrolBattery() {
        togglePatrolSetting("Akkumulátor figyelés", PatrolStore.isBatteryEnabled(this)) { enabled ->
            PatrolStore.setBatteryEnabled(this, enabled)
        }
    }

    private fun togglePatrolCallAlert() {
        togglePatrolSetting("Hívás értesítés", PatrolStore.isCallAlertEnabled(this)) { enabled ->
            PatrolStore.setCallAlertEnabled(this, enabled)
        }
    }

    private fun togglePatrolSmsAlert() {
        togglePatrolSetting("Üzenet értesítés", PatrolStore.isSmsAlertEnabled(this)) { enabled ->
            PatrolStore.setSmsAlertEnabled(this, enabled)
        }
    }

    private fun togglePatrolNotificationAlert() {
        togglePatrolSetting("Egyéb értesítés", PatrolStore.isNotificationAlertEnabled(this)) { enabled ->
            PatrolStore.setNotificationAlertEnabled(this, enabled)
        }
    }

    private fun togglePatrolTimeAnnounce() {
        val label = "Idő bemondás"
        val wasEnabled = PatrolStore.isTimeAnnounceEnabled(this)
        tts.speak(ToggleAnnouncement.speakBinaryToggle(label, wasEnabled))
        val next = !wasEnabled
        PatrolStore.setTimeAnnounceEnabled(this, next)
        val interval = PatrolStore.getTimeIntervalMinutes(this)
        val extra = if (next) "Bekapcsolva. Gyakoriság: $interval perc." else "Kikapcsolva."
        tts.speak(ToggleAnnouncement.speakAfterToggle(label, next, extra))
    }

    private fun togglePatrolSetting(
        label: String,
        wasEnabled: Boolean,
        apply: (Boolean) -> Unit
    ) {
        tts.speak(ToggleAnnouncement.speakBinaryToggle(label, wasEnabled))
        val next = !wasEnabled
        apply(next)
        tts.speak(ToggleAnnouncement.speakAfterToggle(label, next))
    }

    private fun cyclePatrolTimeInterval() {
        val next = PatrolStore.cycleTimeInterval(this)
        tts.speak("Idő bemondás gyakorisága: $next perc.")
    }

    private fun togglePatrolNightMode() {
        val label = "Éjszakai csend"
        val wasEnabled = PatrolStore.isNightModeEnabled(this)
        tts.speak(ToggleAnnouncement.speakBinaryToggle(label, wasEnabled))
        val next = !wasEnabled
        PatrolStore.setNightModeEnabled(this, next)
        val extra = if (next) {
            "Bekapcsolva. ${PatrolStore.speakNightStart(this)} és ${PatrolStore.speakNightEnd(this)} között csend van."
        } else {
            "Kikapcsolva."
        }
        tts.speak(ToggleAnnouncement.speakAfterToggle(label, next, extra))
    }

    private fun startPatrolNightStartFlow() {
        ensureMicAndRun {
            activeFlow = AppFlow.PatrolNightAwaitStart
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd az éjszakai csend kezdetét. Például: huszonkettő óra.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val parsed = VoiceTimeParser.parse(spoken)
                    if (parsed == null) {
                        tts.speak("Nem értettem az időpontot. Próbáld újra.")
                        return@listen
                    }
                    PatrolStore.setNightStartMinutes(this, parsed.first * 60 + parsed.second)
                    activeFlow = AppFlow.Menu
                    updateDisplay()
                    tts.speak("Éjszakai csend kezdete: ${PatrolStore.speakNightStart(this)}.")
                },
                onError = { exitFlow("Nem értettem az időpontot.") }
            )
        }
    }

    private fun startPatrolNightEndFlow() {
        ensureMicAndRun {
            activeFlow = AppFlow.PatrolNightAwaitEnd
            updateFlowDisplay()
            voiceInput.listen(
                prompt = "Mondd az éjszakai csend végét. Például: hét óra.",
                speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
                onResult = { spoken ->
                    val parsed = VoiceTimeParser.parse(spoken)
                    if (parsed == null) {
                        tts.speak("Nem értettem az időpontot. Próbáld újra.")
                        return@listen
                    }
                    PatrolStore.setNightEndMinutes(this, parsed.first * 60 + parsed.second)
                    activeFlow = AppFlow.Menu
                    updateDisplay()
                    tts.speak("Éjszakai csend vége: ${PatrolStore.speakNightEnd(this)}.")
                },
                onError = { exitFlow("Nem értettem az időpontot.") }
            )
        }
    }

    private fun togglePatrolPowerButtonTime() {
        val label = "Bekapcsoló gomb idő bemondás"
        val wasEnabled = PatrolStore.isPowerButtonTimeEnabled(this)
        tts.speak(ToggleAnnouncement.speakBinaryToggle(label, wasEnabled))
        val next = !wasEnabled
        PatrolStore.setPowerButtonTimeEnabled(this, next)
        val extra = if (next) {
            "Bekapcsolva. Zárolt képernyőn is működik."
        } else {
            "Kikapcsolva."
        }
        tts.speak(ToggleAnnouncement.speakAfterToggle(label, next, extra))
    }

    private fun toggleWifi() {
        try {
            val wasEnabled = ConnectivityHelper.isWifiEnabled(this)
            tts.speak(ToggleAnnouncement.speakBinaryToggle("WiFi", wasEnabled))
            val result = ConnectivityHelper.toggleWifi(this)
            if (result.success) {
                tts.speak(ToggleAnnouncement.speakAfterToggle("WiFi", result.nowEnabled))
            } else {
                tts.speak(
                    "WiFi jelenleg ${if (result.nowEnabled) "BEKAPCSOLVA" else "KIKAPCSOLVA"}. " +
                        (result.failureMessage ?: "WiFi kapcsolás sikertelen.")
                )
            }
        } catch (_: Exception) {
            tts.speak("WiFi kapcsolás sikertelen.")
        }
    }

    private fun toggleHotspot() {
        if (!ConnectivityHelper.hasNearbyWifiPermission(this)) {
            pendingHotspotToggle = true
            tts.speak("A közeli WiFi eszközök engedély kell a hotspot-hoz.")
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.NEARBY_WIFI_DEVICES),
                PERM_REQUEST
            )
            return
        }
        runHotspotToggle()
    }

    private fun runHotspotToggle() {
        val wasEnabled = ConnectivityHelper.isHotspotEnabled(this)
        tts.speak(ToggleAnnouncement.speakBinaryToggle("Hotspot", wasEnabled))
        Thread({
            try {
                val result = ConnectivityHelper.toggleHotspot(
                    applicationContext,
                    knownWasEnabled = wasEnabled
                )
                runOnUiThread {
                    if (result.success) {
                        tts.speak(ToggleAnnouncement.speakAfterToggle("Hotspot", result.nowEnabled))
                    } else {
                        tts.speak(
                            result.failureMessage
                                ?: "Hotspot kapcsolás sikertelen. Hotspot jelenleg " +
                                "${if (result.nowEnabled) "BEKAPCSOLVA" else "KIKAPCSOLVA"}."
                        )
                    }
                }
            } catch (_: Exception) {
                runOnUiThread { tts.speak("Hotspot kapcsolás nem sikerült.") }
            }
        }, "SuperDL-HotspotToggle").start()
    }

    private fun toggleBluetooth() {
        val wasEnabled = ConnectivityHelper.isBluetoothEnabled(this)
        tts.speak(ToggleAnnouncement.speakBinaryToggle("Bluetooth", wasEnabled))
        val result = ConnectivityHelper.toggleBluetooth(this)
        if (result.success) {
            tts.speak(ToggleAnnouncement.speakAfterToggle("Bluetooth", result.nowEnabled))
        } else {
            tts.speak(
                "Bluetooth jelenleg ${if (result.nowEnabled) "BEKAPCSOLVA" else "KIKAPCSOLVA"}. " +
                    (result.failureMessage ?: "Bluetooth kapcsolás sikertelen.")
            )
            if (result.failureMessage?.contains("engedély") == true) {
                startPermissionGuideFlow(PermissionGuideType.BLUETOOTH_MANUAL, "Bluetooth kézi kapcsolás")
            }
        }
    }

    private fun cycleCallFilterMode() {
        val previous = CallFilterStore.getMode(this)
        val next = CallFilterStore.cycleMode(this)
        tts.speak("Hívás szűrő mód váltva. Előző: ${previous.menuLabel}.")
        tts.speakAdd(next.speakLabel)
        ensureCallScreeningRole(promptIfMissing = true)
    }

    private fun ensureCallScreeningRole(promptIfMissing: Boolean) {
        if (CallFilterHelper.isScreeningRoleHeld(this)) return
        if (!promptIfMissing) return
        val intent = CallFilterHelper.createRoleRequestIntent(this)
        if (intent != null) {
            tts.speakAdd("A hívás szűrő működéséhez engedélyezd a Super DL-t hívás szűrőként.")
            callScreeningRoleLauncher.launch(intent)
        } else {
            startPermissionGuideFlow(PermissionGuideType.CALL_SCREENING, "Hívás szűrő engedély")
        }
    }

    private fun textReaderIntent(mode: TextReaderMode): Intent =
        Intent(this, TextReaderActivity::class.java)
            .putExtra(TextReaderMode.EXTRA_MODE, mode.extraValue)

    private fun toggleFlashlight() {
        try {
            val cm = getSystemService(CAMERA_SERVICE) as CameraManager
            val cameraId = cm.cameraIdList.firstOrNull() ?: return
            val wasOn = FlashlightState.isOn
            tts.speak(ToggleAnnouncement.speakBinaryToggle("Zseblámpa", wasOn))
            FlashlightState.isOn = !wasOn
            cm.setTorchMode(cameraId, FlashlightState.isOn)
            tts.speak(ToggleAnnouncement.speakAfterToggle("Zseblámpa", FlashlightState.isOn))
        } catch (_: Exception) {
            tts.speak("Zseblámpa nem elérhető.")
        }
    }

    // ==================== UI ====================

    private fun updateDisplay() {
        if (activeFlow !is AppFlow.Menu) {
            updateFlowDisplay()
            return
        }
        val item = currentMenu[currentIndex]
        tvItem.text = item.label
        tvPosition.text = "${if (menuStack.isEmpty()) "Főmenü" else "Almenü"}  •  ${currentIndex + 1} / ${currentMenu.size}"
        tvHint.text = buildHintText(item)
    }

    private fun updateFlowDisplay() {
        when (val flow = activeFlow) {
            AppFlow.PodcastLoading -> {
                tvItem.text = "Podcast betöltése…"
                tvPosition.text = "Podcast"
                tvHint.text = "⬅ mégse"
            }
            AppFlow.PodcastSearchAwaitQuery -> {
                tvItem.text = "Mit keresel?"
                tvPosition.text = "Podcast keresés"
                tvHint.text = "Mondd a podcast nevét vagy témát  •  ⬅ mégse"
            }
            is AppFlow.PodcastListBrowse -> {
                val p = flow.podcasts.getOrNull(flow.index)
                tvItem.text = p?.title ?: ""
                tvPosition.text = "${flow.title}  •  ${flow.index + 1} / ${flow.podcasts.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ adások  •  ⬅ vissza"
            }
            is AppFlow.PodcastEpisodeBrowse -> {
                val ep = flow.episodes.getOrNull(flow.index)
                tvItem.text = ep?.title ?: ""
                tvPosition.text = "${flow.podcast.title}  •  ${flow.index + 1} / ${flow.episodes.size}"
                tvHint.text = "⬆⬇ adások  •  ➡ menü  •  ⬅ vissza"
            }
            is AppFlow.PodcastEpisodeMenu -> {
                val actions = podcastEpisodeActions(flow.podcast)
                tvItem.text = actions.getOrNull(flow.actionIndex) ?: ""
                tvPosition.text = flow.episodes.getOrNull(flow.episodeIndex)?.title ?: "Epizód"
                tvHint.text = "⬆⬇ műveletek  •  ➡ indít  •  ⬅ vissza"
            }
            is AppFlow.PodcastCountryBrowse -> {
                val c = PodcastStore.COUNTRIES.getOrNull(flow.index)
                tvItem.text = c?.second ?: ""
                tvPosition.text = "Ország  •  ${flow.index + 1} / ${PodcastStore.COUNTRIES.size}"
                tvHint.text = "⬆⬇ országok  •  ➡ kiválaszt  •  ⬅ vissza"
            }
            is AppFlow.SmsAwaitRecipient -> {
                tvItem.text = "Üzenet küldése"
                tvPosition.text = "1 / 3  •  Címzett"
                tvHint.text = "Diktáld a címzettet  •  ⬅ mégse"
            }
            is AppFlow.SmsPickContact -> {
                val c = flow.matches[flow.index]
                tvItem.text = c.name
                tvPosition.text = "Címzett  •  ${flow.index + 1} / ${flow.matches.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ megerősítés  •  ⬅ mégse"
            }
            is AppFlow.SmsRecipientConfirm -> {
                tvItem.text = flow.recipient.label
                tvPosition.text = "Címzett megerősítés  •  ${ContactHelper.maskPhone(flow.recipient.phone)}"
                tvHint.text = "➡ igen / ⬅ nem  •  ⬆⬇ ismétlés"
            }
            is AppFlow.SmsAwaitMessage -> {
                tvItem.text = flow.recipient.label
                tvPosition.text = "2 / 3  •  Üzenet diktálása"
                tvHint.text = "Diktáld az üzenetet  •  ⬅ mégse"
            }
            is AppFlow.SmsConfirm -> {
                tvItem.text = flow.message
                tvPosition.text = "3 / 3  •  ${flow.recipient.label}"
                tvHint.text = "➡ küldés  •  ⬅ mégse  •  szóban: küldés, nem  •  ⬆⬇ ismétlés"
            }
            is AppFlow.SmsInbox -> {
                val msg = flow.messages[flow.index]
                val contactLabel = SmsHelper.resolveSenderLabel(this, msg.address)
                tvItem.text = msg.body.ifBlank { "(üres üzenet)" }
                val partyLabel = when (flow.folder) {
                    SmsFolder.INBOX -> "Feladó: $contactLabel"
                    SmsFolder.SENT -> "Címzett: $contactLabel"
                }
                tvPosition.text = "${flow.folder.label} üzenetek  •  ${flow.index + 1} / ${flow.messages.size}  •  $partyLabel"
                tvHint.text = "⬆⬇ navigálás  •  ➡ műveletek  •  ⬅ vissza"
            }
            is AppFlow.SmsContextMenu -> {
                val msg = flow.messages[flow.messageIndex]
                val contactLabel = SmsHelper.resolveSenderLabel(this, msg.address)
                tvItem.text = flow.actions[flow.actionIndex].label
                tvPosition.text = "${flow.folder.label} műveletek  •  ${flow.actionIndex + 1} / ${flow.actions.size}  •  $contactLabel"
                tvHint.text = "⬆⬇ választás  •  ➡ végrehajtás  •  ⬅ vissza"
            }
            is AppFlow.SmsDeleteConfirm -> {
                val msg = flow.messages[flow.messageIndex]
                tvItem.text = msg.body
                tvPosition.text = "Üzenet törlése"
                tvHint.text = "➡ törlés  •  ⬅ mégse"
            }
            AppFlow.EmailAwaitRecipient -> {
                tvItem.text = "E-mail küldése"
                tvPosition.text = "1 / 4  •  Címzett"
                tvHint.text = "Diktáld a címzettet  •  ⬅ mégse"
            }
            is AppFlow.EmailPickRecipient -> {
                val recipient = flow.matches[flow.index]
                tvItem.text = recipient.label
                tvPosition.text = "Címzett  •  ${flow.index + 1} / ${flow.matches.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ megerősítés  •  ⬅ mégse"
            }
            is AppFlow.EmailRecipientConfirm -> {
                tvItem.text = flow.recipient.label
                tvPosition.text = "Címzett megerősítés"
                tvHint.text = "➡ igen / ⬅ nem  •  ⬆⬇ ismétlés"
            }
            is AppFlow.EmailAwaitSubject -> {
                tvItem.text = flow.recipient.label
                tvPosition.text = "2 / 4  •  Tárgy diktálása"
                tvHint.text = "Mondd a tárgyat vagy: névtelen  •  ⬅ mégse"
            }
            is AppFlow.EmailAwaitBody -> {
                tvItem.text = flow.subject.ifBlank { "Névtelen tárgy" }
                tvPosition.text = "3 / 4  •  ${flow.recipient.label}"
                tvHint.text = "Diktáld az e-mail szövegét  •  ⬅ mégse"
            }
            is AppFlow.EmailConfirm -> {
                tvItem.text = flow.body
                tvPosition.text = "4 / 4  •  ${flow.recipient.label}"
                tvHint.text = "➡ küldés  •  ⬅ mégse  •  szóban: küldés, nem  •  ⬆⬇ ismétlés"
            }
            is AppFlow.EmailBrowseRecipients -> {
                val recipient = flow.recipients[flow.index]
                tvItem.text = recipient.label
                tvPosition.text = "E-mail címek  •  ${flow.index + 1} / ${flow.recipients.size}"
                tvHint.text = "⬆⬇ navigálás  •  ➡ felolvas  •  ⬅ vissza"
            }
            is AppFlow.CallPickContact -> {
                val c = flow.matches[flow.index]
                tvItem.text = c.name
                tvPosition.text = "Névjegy  •  ${flow.index + 1} / ${flow.matches.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ megerősítés  •  ⬅ mégse"
            }
            is AppFlow.CallConfirm -> {
                tvItem.text = flow.contact.name
                tvPosition.text = "Hívás megerősítés  •  ${ContactHelper.maskPhone(flow.contact.phone)}"
                tvHint.text = "➡ hívás  •  ⬅ mégse  •  ⬆⬇ ismétlés"
            }
            is AppFlow.ContactBookBrowse -> {
                val item = flow.items[flow.index]
                tvItem.text = when (item) {
                    ContactBookItem.SyncAction -> "Szinkronizálás"
                    is ContactBookItem.Entry -> item.contact.name
                }
                val contactCount = (flow.items.size - 1).coerceAtLeast(0)
                tvPosition.text = if (item is ContactBookItem.SyncAction) {
                    "Névjegyzék  •  szinkron  •  $contactCount névjegy"
                } else {
                    "Névjegyzék  •  ${flow.index} / $contactCount"
                }
                tvHint.text = when (item) {
                    ContactBookItem.SyncAction -> "➡ szinkron  •  ⬆⬇ navigálás  •  ⬅ vissza"
                    is ContactBookItem.Entry -> "➡ műveletek  •  ⬆⬇ navigálás  •  ⬅ vissza  •  ${ContactHelper.maskPhone(item.contact.phone)}"
                }
            }
            is AppFlow.ContactLetterBrowse -> {
                val group = flow.groups[flow.index]
                val letterName = if (group.letter == "#") "#" else group.letter
                tvItem.text = letterName
                tvPosition.text = "Névjegyzék betűk  •  ${flow.index + 1} / ${flow.groups.size}"
                tvHint.text = "➡ belépés  •  ⬆⬇ betűk  •  ⬅ vissza  •  ${group.contacts.size} névjegy"
            }
            is AppFlow.ContactContextMenu -> {
                val entry = flow.items.getOrNull(flow.contactIndex) as? ContactBookItem.Entry
                tvItem.text = flow.actions[flow.actionIndex].label
                tvPosition.text = "Névjegy műveletek  •  ${flow.actionIndex + 1} / ${flow.actions.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ végrehajtás  •  ⬅ vissza  •  ${entry?.contact?.name.orEmpty()}"
            }
            is AppFlow.ContactEditAwaitName -> {
                tvItem.text = flow.contact.name
                tvPosition.text = "Névjegy szerkesztése  •  új név"
                tvHint.text = "Diktáld az új nevet  •  ⬅ mégse"
            }
            is AppFlow.ContactEditAwaitPhone -> {
                tvItem.text = flow.newName
                tvPosition.text = "Névjegy szerkesztése  •  új telefonszám"
                tvHint.text = "Diktáld az új számot  •  ⬅ mégse"
            }
            is AppFlow.ContactDeleteConfirm -> {
                tvItem.text = flow.contact.name
                tvPosition.text = "Névjegy törlése  •  ${ContactHelper.maskPhone(flow.contact.phone)}"
                tvHint.text = "➡ törlés  •  ⬅ mégse  •  ⬆⬇ ismétlés"
            }
            is AppFlow.SetupWizardBrowse -> {
                val req = flow.requirements.getOrNull(flow.index)
                tvItem.text = req?.title.orEmpty()
                tvPosition.text = "Beállítás varázsló  •  ${flow.index + 1} / ${flow.requirements.size}" +
                    (req?.let { "  •  ${it.severityLabel()}" } ?: "")
                tvHint.text = "⬆⬇ választás  •  ➡ megadás  •  ⬅ kilépés"
            }
            is AppFlow.SetupWizardAwaitReturn -> {
                tvItem.text = flow.requirement.title
                tvPosition.text = "Beállítás varázsló  •  várakozás"
                tvHint.text = "Add meg a rendszer képernyőjén, majd gyere vissza  •  ⬅ folytatás"
            }
            is AppFlow.SosCountdown -> {
                tvItem.text = flow.secondsLeft.toString()
                tvPosition.text = "S.O.S. VÉSZJELZÉS  •  ${flow.secondsLeft} mp"
                tvHint.text = "⬅ LEÁLLÍTÁS  •  szóban: mégse, nem"
            }
            AppFlow.AlarmAwaitTime -> {
                tvItem.text = "Új ébresztő"
                tvPosition.text = "1 / 4  •  Idő diktálása"
                tvHint.text = "Mondd az időt  •  ⬅ mégse"
            }
            is AppFlow.AlarmAwaitLabel -> {
                tvItem.text = "${flow.hour.toString().padStart(2, '0')}:${flow.minute.toString().padStart(2, '0')}"
                tvPosition.text = "2 / 4  •  Név diktálása"
                tvHint.text = "Mondd a nevet vagy: névtelen  •  ⬅ mégse"
            }
            is AppFlow.AlarmRepeatBrowse -> {
                tvItem.text = flow.options[flow.index].speakLabel(alarmDraftWeekDays)
                tvPosition.text = "3 / 4  •  Ismétlés"
                tvHint.text = "⬆⬇ választás  •  ➡ tovább  •  ⬅ mégse"
            }
            is AppFlow.AlarmConfirm -> {
                val name = flow.label.ifBlank { "Névtelen" }
                tvItem.text = name
                tvPosition.text = "4 / 4  •  ${flow.hour.toString().padStart(2, '0')}:${flow.minute.toString().padStart(2, '0')}  •  ${alarmDraftRepeat.speakLabel(alarmDraftWeekDays)}"
                tvHint.text = "➡ beállít  •  ⬅ mégse"
            }
            is AppFlow.AlarmListBrowse -> {
                val alarm = flow.alarms[flow.index]
                tvItem.text = alarm.label.ifBlank { "Ébresztő" }
                tvPosition.text = if (flow.deleteMode) "Törlés  •  ${flow.index + 1} / ${flow.alarms.size}"
                else "Ébresztők  •  ${flow.index + 1} / ${flow.alarms.size}"
                tvHint.text = if (flow.deleteMode)
                    "⬆⬇ választás  •  ➡ törlés  •  ⬅ vissza"
                else
                    "⬆⬇ választás  •  ➡ hang módosítása  •  ⬅ vissza"
            }
            is AppFlow.AlarmDeleteConfirm -> {
                tvItem.text = flow.alarm.label.ifBlank { "Ébresztő" }
                tvPosition.text = "Törlés megerősítés  •  ${flow.alarm.speakTime()}"
                tvHint.text = "➡ törlés  •  ⬅ mégse"
            }
            AppFlow.MedicationAwaitName -> {
                tvItem.text = medicationDraftName ?: "Gyógyszer neve"
                tvPosition.text = "Patika Őrangyal  •  1 / 4  •  Név diktálása"
                tvHint.text = "Mondd a gyógyszer nevét  •  ⬅ mégse"
            }
            is AppFlow.MedicationTimeOfDayBrowse -> {
                val option = flow.options[flow.index]
                val checked = option in flow.selected
                tvItem.text = "${if (checked) "☑" else "☐"} ${option.label}"
                tvPosition.text = "Patika Őrangyal  •  Napszak  •  ${flow.selected.size} kiválasztva  •  ${flow.name}"
                tvHint.text = "⬆⬇ napszakok  •  ➡ ${if (checked) "levesz" else "kipipál"}  •  ⬅ tovább"
            }
            AppFlow.MedicationAwaitCourseDays -> {
                tvItem.text = "Hány napig?"
                tvPosition.text = "Patika Őrangyal  •  Kúra hossza  •  ${medicationDraftName ?: ""}"
                tvHint.text = "Mondd a napok számát, vagy folyamatos  •  ⬅ mégse"
            }
            is AppFlow.MedicationCycleBrowse -> {
                tvItem.text = flow.options[flow.index].label
                tvPosition.text = "Patika Őrangyal  •  3 / 4  •  Ismétlés  •  ${flow.name}"
                tvHint.text = "⬆⬇ választás  •  ➡ megerősítés  •  ⬅ mégse"
            }
            is AppFlow.MedicationWeekdayBrowse -> {
                val day = MedicationWeekdays.all[flow.index]
                val selected = day.dayOfWeek in flow.selectedDays
                tvItem.text = day.label
                tvPosition.text = "Patika Őrangyal  •  ${flow.cycleType.label}  •  ${flow.name}"
                tvHint.text = if (flow.cycleType == MedicationCycleType.CUSTOM) {
                    "⬆⬇ választás  •  ➡ ${if (selected) "kikapcsol" else "bekapcsol"}  •  ⬅ tovább"
                } else {
                    "⬆⬇ választás  •  ➡ kiválaszt  •  ⬅ mégse"
                }
            }
            is AppFlow.MedicationConfirm -> {
                tvItem.text = flow.name
                tvPosition.text = "Patika Őrangyal  •  4 / 4  •  ${flow.hour.toString().padStart(2, '0')}:${flow.minute.toString().padStart(2, '0')}"
                tvHint.text = "➡ mentés  •  ⬅ mégse  •  ⬆⬇ ismétlés"
            }
            is AppFlow.MedicationListBrowse -> {
                val reminder = flow.reminders[flow.index]
                tvItem.text = reminder.name
                tvPosition.text = if (flow.deleteMode) {
                    "Patika Őrangyal törlés  •  ${flow.index + 1} / ${flow.reminders.size}"
                } else {
                    "Patika Őrangyal  •  ${flow.index + 1} / ${flow.reminders.size}"
                }
                tvHint.text = if (flow.deleteMode) {
                    "⬆⬇ választás  •  ➡ törlés  •  ⬅ vissza"
                } else {
                    "⬆⬇ választás  •  ➡ felolvas  •  ⬅ vissza"
                }
            }
            is AppFlow.MedicationDeleteConfirm -> {
                tvItem.text = flow.reminder.name
                tvPosition.text = "Gyógyszer törlése  •  ${flow.reminder.speakTime()}"
                tvHint.text = "➡ törlés  •  ⬅ mégse"
            }
            is AppFlow.TimerUnitBrowse -> {
                val unit = flow.units[flow.index]
                tvItem.text = unit.label
                tvPosition.text = "1 / 4  •  Időtartam egysége"
                tvHint.text = "⬆⬇ választás  •  ➡ tovább  •  ⬅ mégse"
            }
            is AppFlow.TimerAwaitAmount -> {
                tvItem.text = flow.unit.label
                tvPosition.text = "2 / 4  •  Időtartam diktálása"
                tvHint.text = "Mondd a számot  •  ⬅ mégse"
            }
            is AppFlow.TimerIntervalBrowse -> {
                val interval = flow.intervals[flow.index]
                tvItem.text = "$interval perc"
                tvPosition.text = "3 / 4  •  Jelzés gyakorisága"
                tvHint.text = "⬆⬇ választás  •  ➡ tovább  •  ⬅ mégse"
            }
            is AppFlow.TimerAwaitLabel -> {
                tvItem.text = TimerSpeech.speakMinutes(flow.durationMinutes)
                tvPosition.text = "4 / 4  •  Név diktálása"
                tvHint.text = "Mondd az időzítő nevét  •  ⬅ mégse"
            }
            is AppFlow.TimerConfirm -> {
                tvItem.text = flow.label.ifBlank { "Névtelen időzítő" }
                tvPosition.text = "Megerősítés  •  ${TimerSpeech.speakMinutes(flow.durationMinutes)}"
                tvHint.text = "➡ mentés  •  ⬅ mégse  •  ⬆⬇ ismétlés"
            }
            is AppFlow.TimerListBrowse -> {
                val timer = flow.timers[flow.index]
                tvItem.text = timer.label.ifBlank { "Időzítő" }
                tvPosition.text = when (flow.mode) {
                    TimerListMode.DELETE -> "Törlés  •  ${flow.index + 1} / ${flow.timers.size}"
                    TimerListMode.START -> "Indítás  •  ${flow.index + 1} / ${flow.timers.size}"
                    TimerListMode.EDIT -> "Módosítás  •  ${flow.index + 1} / ${flow.timers.size}"
                    TimerListMode.VIEW -> "Időzítők  •  ${flow.index + 1} / ${flow.timers.size}"
                }
                tvHint.text = when (flow.mode) {
                    TimerListMode.DELETE -> "⬆⬇ választás  •  ➡ törlés  •  ⬅ vissza"
                    TimerListMode.START -> "⬆⬇ választás  •  ➡ indítás  •  ⬅ vissza"
                    TimerListMode.EDIT -> "⬆⬇ választás  •  ➡ módosítás  •  ⬅ vissza"
                    TimerListMode.VIEW -> "⬆⬇ választás  •  ➡ felolvas  •  ⬅ vissza"
                }
            }
            is AppFlow.TimerDeleteConfirm -> {
                tvItem.text = flow.timer.label.ifBlank { "Időzítő" }
                tvPosition.text = "Törlés megerősítés  •  ${flow.timer.speakDuration()}"
                tvHint.text = "➡ törlés  •  ⬅ mégse"
            }
            AppFlow.GpsRadarLoading -> {
                tvItem.text = "GPS Kitekintő"
                tvPosition.text = "Közeli helyek keresése"
                tvHint.text = "Várj…  •  ⬅ megszakítás"
            }
            is AppFlow.GpsRadarBrowse -> {
                val poi = flow.pois[flow.index]
                tvItem.text = poi.name
                val category = if (poi.category.isNotBlank()) "  •  ${poi.category}" else ""
                tvPosition.text = "Radar  •  ${flow.index + 1} / ${flow.pois.size}  •  ${poi.distanceMeters} m$category"
                tvHint.text = "⬆⬇ választás  •  ➡ műveletek  •  ⬅ bezárás"
            }
            is AppFlow.GpsRadarContextMenu -> {
                val poi = flow.pois[flow.poiIndex]
                tvItem.text = flow.actions[flow.actionIndex].label
                tvPosition.text = "G P S műveletek  •  ${flow.actionIndex + 1} / ${flow.actions.size}  •  ${poi.name}"
                tvHint.text = "⬆⬇ választás  •  ➡ végrehajtás  •  ⬅ vissza"
            }
            is AppFlow.GpsRadarGuiding -> {
                val poi = flow.pois.getOrNull(flow.index) ?: GpsRadarStore.targetPoi
                tvItem.text = poi?.name ?: "Cél"
                tvPosition.text = "Célkövetés  •  ${poi?.distanceMeters ?: 0} m  •  ${poi?.clockDirection ?: ""}"
                tvHint.text = "⬆ ismétlés  •  ⬇ saját hely mentése  •  ➡ POI mentése  •  ⬅ zárolás feloldása"
            }
            is AppFlow.GpsRadarAwaitSaveName -> {
                tvItem.text = "Saját hely mentése"
                tvPosition.text = "Név diktálása"
                tvHint.text = "Mondd a nevet  •  ⬅ mégse"
            }
            is AppFlow.GpsSavedPoiBrowse -> {
                val saved = flow.saved[flow.index]
                tvItem.text = saved.speakPreview()
                tvPosition.text = "Egyéni helyek  •  ${flow.index + 1} / ${flow.saved.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ műveletek  •  ⬅ vissza"
            }
            is AppFlow.SavedPoiContextMenu -> {
                val poi = flow.saved[flow.poiIndex]
                tvItem.text = flow.actions[flow.actionIndex].label
                tvPosition.text = "${poi.name}  •  ${flow.actionIndex + 1} / ${flow.actions.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ végrehajtás  •  ⬅ vissza"
            }
            is AppFlow.SavedPoiVoiceRecording -> {
                val poi = flow.saved[flow.poiIndex]
                tvItem.text = "Felvétel: ${poi.name}"
                tvPosition.text = "Hangjegyzet rögzítése"
                tvHint.text = "➡ mentés  •  ⬅ megszakítás"
            }
            AppFlow.GpsRouteRecordingActive -> {
                val points = GpsRouteSession.points.size
                tvItem.text = GpsRouteSession.recordingName.ifBlank { "Útvonal" }
                tvPosition.text = "GPS útvonal rögzítés  •  $points pont"
                tvHint.text = "⬆⬇ állapot  •  ➡ útpont  •  ⬅ mentés"
            }
            is AppFlow.GpsRouteAwaitName -> {
                tvItem.text = flow.route.speakPreview()
                tvPosition.text = "Útvonal elnevezése"
                tvHint.text = "Diktáld a nevet  •  ⬅ alapértelmezett névvel mentés"
            }
            is AppFlow.GpsRouteBrowse -> {
                val route = flow.routes[flow.index]
                tvItem.text = route.speakPreview()
                tvPosition.text = when {
                    flow.deleteMode -> "Útvonal törlés  •  ${flow.index + 1} / ${flow.routes.size}"
                    flow.guideMode -> "Útvonal útmutatás  •  ${flow.index + 1} / ${flow.routes.size}"
                    else -> "Mentett útvonalak  •  ${flow.index + 1} / ${flow.routes.size}"
                }
                tvHint.text = when {
                    flow.deleteMode -> "⬆⬇ választás  •  ➡ törlés  •  ⬅ vissza"
                    flow.guideMode -> "⬆⬇ választás  •  ➡ útmutatás  •  ⬅ vissza"
                    else -> "⬆⬇ választás  •  ➡ felolvas  •  ⬅ vissza"
                }
            }
            is AppFlow.GpsRouteDeleteConfirm -> {
                tvItem.text = flow.route.speakPreview()
                tvPosition.text = "Útvonal törlése"
                tvHint.text = "➡ törlés  •  ⬅ mégse  •  ⬆⬇ ismétlés"
            }
            is AppFlow.GpsRouteGuidingActive -> {
                tvItem.text = flow.route.speakPreview()
                tvPosition.text = "Útvonal útmutatás"
                tvHint.text = "⬆⬇ ismétlés  •  ⬅ leállítás"
            }
            is AppFlow.LocationProfileBrowse -> {
                val profile = flow.profiles[flow.index]
                tvItem.text = profile.speakPreview()
                tvPosition.text = if (flow.deleteMode) {
                    "Helyszín törlés  •  ${flow.index + 1} / ${flow.profiles.size}"
                } else {
                    "Mentett helyszínek  •  ${flow.index + 1} / ${flow.profiles.size}"
                }
                tvHint.text = if (flow.deleteMode) {
                    "⬆⬇ választás  •  ➡ törlés  •  ⬅ vissza"
                } else {
                    "⬆⬇ választás  •  ➡ műveletek  •  ⬅ vissza"
                }
            }
            is AppFlow.LocationProfileActions -> {
                val options = AppFlow.LocationProfileActions.OPTIONS
                tvItem.text = options[flow.actionIndex]
                tvPosition.text = "${flow.profile.speakPreview()}  •  ${flow.profile.referenceImagePaths.size} fotó"
                tvHint.text = "⬆⬇ művelet  •  ➡ végrehajtás  •  ⬅ vissza"
            }
            is AppFlow.LocationProfileDeleteConfirm -> {
                tvItem.text = flow.profile.speakPreview()
                tvPosition.text = "Helyszín profil törlése"
                tvHint.text = "➡ törlés  •  ⬅ mégse  •  ⬆⬇ ismétlés"
            }
            is AppFlow.CameraQualityBrowse -> {
                val profile = flow.profiles[flow.index]
                tvItem.text = profile.label
                tvPosition.text = "Kamera minőség  •  ${flow.index + 1} / ${flow.profiles.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ mentés  •  ⬅ vissza"
            }
            AppFlow.NavWhereLoading -> {
                tvItem.text = "Hol vagyok?"
                tvPosition.text = "Pontosság javítása"
                tvHint.text = "Állj egy helyben  •  ⬅ megszakítás"
            }
            is AppFlow.NavWhereResult -> {
                tvItem.text = flow.address
                tvPosition.text = "Hol vagyok?  •  ±${flow.accuracyMeters} m"
                tvHint.text = "⬆⬇ ismétlés  •  ➡ mentés  •  ⬅ vissza"
            }
            is AppFlow.GpsSaveRefining -> {
                tvItem.text = "Saját hely mentése"
                tvPosition.text = "Pontosság javítása"
                tvHint.text = "Állj egy helyben  •  ⬅ megszakítás"
            }
            AppFlow.DictaphoneRecording -> {
                val elapsed = DictaphoneManager.elapsedMillis()
                val sec = (elapsed / 1000).toInt()
                val min = sec / 60
                val rem = sec % 60
                tvItem.text = if (DictaphoneManager.isPaused()) "Szünetel" else "Felvétel"
                tvPosition.text = "Profi Diktafon  •  ${min}:%02d".format(rem)
                tvHint.text = "⬆⬇ eltelt idő  •  ➡ szünet/folytatás  •  ⬅ mentés"
            }
            is AppFlow.DictaphoneSettingsBrowse -> {
                val option = flow.options[flow.index]
                val config = DictaphoneSettingsStore.load(this)
                tvItem.text = option.label
                tvPosition.text = "Beállítás  •  ${flow.index + 1} / ${flow.options.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ módosítás  •  ⬅ bezárás  •  ${option.speakCurrent(config)}"
            }
            is AppFlow.DictaphoneFormatBrowse -> {
                tvItem.text = flow.formats[flow.index].label
                tvPosition.text = "Formátum  •  ${flow.index + 1} / ${flow.formats.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ mentés  •  ⬅ vissza"
            }
            is AppFlow.DictaphoneSampleRateBrowse -> {
                tvItem.text = flow.rates[flow.index].label
                tvPosition.text = "Mintavétel  •  ${flow.index + 1} / ${flow.rates.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ mentés  •  ⬅ vissza"
            }
            is AppFlow.DictaphoneBitrateBrowse -> {
                tvItem.text = flow.bitrates[flow.index].label
                tvPosition.text = "Bitráta  •  ${flow.index + 1} / ${flow.bitrates.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ mentés  •  ⬅ vissza"
            }
            is AppFlow.DictaphoneChannelsBrowse -> {
                tvItem.text = flow.channels[flow.index].label
                tvPosition.text = "Csatorna  •  ${flow.index + 1} / ${flow.channels.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ mentés  •  ⬅ vissza"
            }
            is AppFlow.DictaphoneRecordingsBrowse -> {
                val entry = flow.recordings[flow.index]
                tvItem.text = entry.displayName()
                tvPosition.text = "Felvételek  •  ${flow.index + 1} / ${flow.recordings.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ műveletek  •  ⬅ vissza"
            }
            is AppFlow.DictaphoneRecordingContextMenu -> {
                val entry = flow.recordings[flow.recordingIndex]
                tvItem.text = flow.actions[flow.actionIndex].label
                tvPosition.text = "Felvétel műveletek  •  ${entry.displayName()}"
                tvHint.text = "⬆⬇ választás  •  ➡ végrehajtás  •  ⬅ vissza"
            }
            is AppFlow.DictaphoneShareEmailAwaitRecipient -> {
                tvItem.text = flow.entry.displayName()
                tvPosition.text = "Felvétel e-mailben  •  Címzett"
                tvHint.text = "Diktáld a címzettet  •  ⬅ mégse"
            }
            is AppFlow.DictaphoneShareEmailPickRecipient -> {
                val recipient = flow.matches[flow.index]
                tvItem.text = recipient.label
                tvPosition.text = "Felvétel e-mailben  •  ${flow.index + 1} / ${flow.matches.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ megerősítés  •  ⬅ mégse"
            }
            is AppFlow.DictaphoneShareEmailConfirm -> {
                tvItem.text = flow.entry.displayName()
                tvPosition.text = "Felvétel e-mailben  •  ${flow.recipient.label}"
                tvHint.text = "➡ elküldés  •  ⬅ mégse  •  ⬆⬇ ismétlés"
            }
            is AppFlow.DictaphoneRecordingDeleteConfirm -> {
                val entry = flow.recordings[flow.recordingIndex]
                tvItem.text = entry.displayName()
                tvPosition.text = "Felvétel törlése"
                tvHint.text = "➡ törlés  •  ⬅ mégse  •  ⬆⬇ ismétlés"
            }
            is AppFlow.CalendarBrowse -> {
                val event = flow.events[flow.index]
                tvItem.text = event.title
                tvPosition.text = "Naptár  •  ${flow.index + 1} / ${flow.events.size}"
                tvHint.text = "⬆⬇ navigálás  •  ➡ műveletek  •  ⬅ vissza"
            }
            is AppFlow.CalendarPick -> {
                val event = flow.events[flow.index]
                tvItem.text = event.title
                val verb = if (flow.purpose == CalendarPickPurpose.EDIT) "szerkesztés" else "törlés"
                tvPosition.text = "Program $verb  •  ${flow.index + 1} / ${flow.events.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ $verb  •  ⬅ vissza"
            }
            is AppFlow.CatalogBrowse -> {
                val m = flow.modules[flow.index]
                tvItem.text = m.name
                tvPosition.text = "Katalógus  •  ${flow.index + 1} / ${flow.modules.size}  •  ${m.type.label}"
                tvHint.text = "⬆⬇ választás  •  ➡ letöltés  •  ⬅ vissza"
            }
            is AppFlow.CalendarTargetPick -> {
                val cal = flow.calendars[flow.index]
                tvItem.text = cal.displayName
                tvPosition.text = "Naptár  •  ${flow.index + 1} / ${flow.calendars.size}" +
                    if (cal.syncs) "  •  szinkronizál" else "  •  csak helyi"
                tvHint.text = "⬆⬇ választás  •  ➡ kiválasztás  •  ⬅ vissza"
            }
            is AppFlow.AlarmSkipPick -> {
                val alarm = flow.alarms[flow.index]
                val mark = if (alarm.id in flow.selected) "✔ " else ""
                tvItem.text = "$mark${alarm.speakSummary()}"
                tvPosition.text = "Kihagyás  •  ${flow.index + 1} / ${flow.alarms.size}  •  ${flow.selected.size} kijelölve"
                tvHint.text = "⬆⬇ választás  •  ➡ kijelölés  •  ⬅ tovább"
            }
            is AppFlow.AlarmSkipCount -> {
                tvItem.text = if (flow.count == 0) "Kihagyás kikapcsolása" else "${flow.count} ébresztés kihagyása"
                tvPosition.text = "Kihagyás  •  ${flow.selected.size} ébresztő"
                tvHint.text = "⬆⬇ szám  •  ➡ mentés  •  ⬅ vissza"
            }
            is AppFlow.CalendarContextMenu -> {
                val event = flow.events[flow.eventIndex]
                tvItem.text = flow.actions[flow.actionIndex].label
                tvPosition.text = "Program műveletek  •  ${event.title}"
                tvHint.text = "⬆⬇ választás  •  ➡ végrehajtás  •  ⬅ vissza"
            }
            is AppFlow.CalendarAlarmContextMenu -> {
                tvItem.text = flow.actions[flow.actionIndex].label
                tvPosition.text = "Program ideje  •  ${flow.event.title}"
                tvHint.text = "⬆⬇ választás  •  ➡ megerősítés  •  ⬅ bezárás"
            }
            is AppFlow.CalendarDeleteConfirm -> {
                tvItem.text = flow.event.title
                tvPosition.text = "Program törlése"
                tvHint.text = "➡ törlés  •  ⬅ mégse"
            }
            is AppFlow.CalendarRecurrenceBrowse -> {
                tvItem.text = flow.options[flow.index].speakSummary()
                tvPosition.text = "5 / 6  •  Ismétlés"
                tvHint.text = "⬆⬇ választás  •  ➡ megerősítés  •  ⬅ mégse"
            }
            is AppFlow.CalendarWeekBrowse -> {
                val day = flow.days[flow.index]
                tvItem.text = day.dayLabel
                tvPosition.text = "Heti program  •  ${flow.index + 1} / ${flow.days.size}"
                tvHint.text = "⬆⬇ navigálás  •  ➡ felolvas  •  ⬅ vissza"
            }
            AppFlow.CalendarAwaitTitle -> {
                tvItem.text = if (calendarEditEventId != null) "Program szerkesztése" else "Új program"
                tvPosition.text = "1 / 6  •  Név diktálása"
                tvHint.text = "Mondd a program nevét  •  ⬅ mégse"
            }
            is AppFlow.CalendarAwaitDate -> {
                tvItem.text = flow.title
                tvPosition.text = "2 / 6  •  Dátum diktálása"
                tvHint.text = "Mondd: ma, holnap, péntek  •  ➡ diktálás  •  ⬇ offline  •  ⬅ mégse"
            }
            is AppFlow.CalendarAwaitStartTime -> {
                tvItem.text = flow.title
                tvPosition.text = "3 / 6  •  Kezdés diktálása"
                tvHint.text = "Mondd a kezdési időt  •  ➡ diktálás  •  ⬇ offline  •  ⬅ mégse"
            }
            is AppFlow.CalendarAwaitEndTime -> {
                tvItem.text = "${flow.startHour.toString().padStart(2, '0')}:${flow.startMinute.toString().padStart(2, '0')}"
                tvPosition.text = "4 / 6  •  Befejezés diktálása"
                tvHint.text = "Mondd a végét vagy: egy óra  •  ➡ diktálás  •  ⬇ offline  •  ⬅ mégse"
            }
            is AppFlow.CalendarConfirm -> {
                tvItem.text = flow.title
                tvPosition.text = "6 / 6  •  Megerősítés  •  ${flow.recurrence.speakSummary()}"
                tvHint.text = "➡ mentés  •  ⬅ mégse  •  ⬆⬇ ismétlés"
            }
            is AppFlow.CallLogBrowse -> {
                val entry = flow.entries[flow.index]
                tvItem.text = entry.name.ifBlank { entry.number }
                tvPosition.text = "Hívásnapló  •  ${flow.index + 1} / ${flow.entries.size}"
                tvHint.text = "⬆⬇ navigálás  •  ➡ műveletek  •  ⬅ vissza"
            }
            is AppFlow.CallLogContextMenu -> {
                val entry = flow.entries[flow.entryIndex]
                tvItem.text = flow.actions[flow.actionIndex].label
                tvPosition.text = "Hívás műveletek  •  ${flow.actionIndex + 1} / ${flow.actions.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ végrehajtás  •  ⬅ vissza  •  ${entry.name.ifBlank { entry.number }}"
            }
            is AppFlow.CallLogSaveContactAwaitName -> {
                val entry = flow.entries[flow.entryIndex]
                tvItem.text = entry.number
                tvPosition.text = "Névjegy mentése"
                tvHint.text = "Diktáld a nevet  •  ⬅ mégse"
            }
            is AppFlow.ContactCreateAwaitName -> {
                tvItem.text = "Új névjegy neve"
                tvPosition.text = ContactHelper.maskPhone(flow.phone)
                tvHint.text = "Diktáld a nevet  •  ⬅ mégse"
            }
            is AppFlow.FavoritesBrowse -> {
                val favorite = flow.favorites[flow.index]
                tvItem.text = favorite.speakPreview()
                tvPosition.text = when (flow.mode) {
                    FavoritesListMode.CALL -> "Kedvencek  •  ${flow.index + 1} / ${flow.favorites.size}"
                    FavoritesListMode.DELETE -> "Kedvenc törlése  •  ${flow.index + 1} / ${flow.favorites.size}"
                }
                tvHint.text = when (flow.mode) {
                    FavoritesListMode.CALL -> "⬆⬇ választás  •  ➡ hívás  •  ⬅ vissza"
                    FavoritesListMode.DELETE -> "⬆⬇ választás  •  ➡ törlés  •  ⬅ vissza"
                }
            }
            is AppFlow.FavoriteDeleteConfirm -> {
                tvItem.text = flow.favorite.speakPreview()
                tvPosition.text = "Kedvenc törlése"
                tvHint.text = "➡ törlés  •  ⬅ mégse"
            }
            is AppFlow.MusicBrowse -> {
                val track = flow.tracks[flow.index]
                tvItem.text = track.title
                tvPosition.text = "Zene  •  ${flow.index + 1} / ${flow.tracks.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ lejátszás  •  ⬅ vissza"
            }
            is AppFlow.RadioBrowse -> {
                tvItem.text = flow.stations[flow.index].name
                tvPosition.text = "Rádió  •  ${flow.index + 1} / ${flow.stations.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ indítás  •  ⬅ vissza"
            }
            is AppFlow.NumericDictationAwait -> {
                tvItem.text = when (flow.purpose) {
                    NumberPadPurpose.PHONE -> "Tárcsázás"
                    NumberPadPurpose.SOS -> "S.O.S. szám ${flow.sosSlot ?: ""}"
                    NumberPadPurpose.CONTACT -> "Új névjegy"
                    NumberPadPurpose.CALCULATOR -> "Számológép"
                    NumberPadPurpose.TIME -> when {
                        flow.alarmDraft -> "Ébresztő"
                        flow.calendarTitle != null -> "Naptár"
                        medicationDraftName != null -> medicationDraftName
                        else -> "Idő"
                    }
                    NumberPadPurpose.AMOUNT -> "Időzítő"
                    NumberPadPurpose.DATE -> "Naptár"
                    NumberPadPurpose.PRICE -> flow.shoppingItemName ?: "Ár"
                    NumberPadPurpose.PIN -> "PIN"
                }
                tvPosition.text = "Diktálás"
                tvHint.text = "➡ diktálás  •  ⬇ offline billentyűzet  •  ⬅ mégse"
            }
            AppFlow.CalculatorAwaitInput -> {
                tvItem.text = "Számológép"
                tvPosition.text = "Diktálás"
                tvHint.text = "➡ diktálás  •  ⬇ offline billentyűzet  •  ⬅ mégse"
            }
            AppFlow.CalculatorVoiceInput -> {
                tvItem.text = "Számológép diktálás"
                tvPosition.text = "Hangos bevitel"
                tvHint.text = "Mondd a számolást  •  ⬇ offline billentyűzet  •  ⬅ vissza"
            }
            is AppFlow.NumberPadInput -> {
                val item = flow.items[flow.index]
                tvItem.text = item.label
                tvPosition.text = when (flow.purpose) {
                    NumberPadPurpose.PHONE -> "Tárcsázás"
                    NumberPadPurpose.SOS -> "S.O.S. szám ${flow.sosSlot ?: ""}"
                    NumberPadPurpose.CONTACT -> "Új névjegy  •  Szám bevitele"
                    NumberPadPurpose.CALCULATOR -> "Számológép"
                    NumberPadPurpose.TIME -> when {
                        flow.alarmDraft -> "Ébresztő  •  Idő bevitele"
                        flow.calendarTitle != null && flow.calendarAwaitEnd -> "Naptár  •  Befejezés"
                        flow.calendarTitle != null -> "Naptár  •  Kezdés"
                        else -> "Patika Őrangyal  •  Idő bevitele"
                    }
                    NumberPadPurpose.AMOUNT -> "Időzítő  •  Időtartam"
                    NumberPadPurpose.DATE -> "Naptár  •  Dátum"
                    NumberPadPurpose.PRICE -> "Bevásárlólista  •  Ár"
                    NumberPadPurpose.PIN -> when (flow.pinMode) {
                        PinPadMode.UNLOCK -> "Zárolás"
                        PinPadMode.SETUP -> "PIN beállítás"
                        PinPadMode.CONFIRM -> "PIN megerősítés"
                        null -> "PIN"
                    }
                } + "  •  ${flow.index + 1} / ${flow.items.size}"
                val bufferHint = when (flow.purpose) {
                    NumberPadPurpose.PIN ->
                        if (flow.buffer.isEmpty()) "" else "  •  ${flow.buffer.length} számjegy"
                    NumberPadPurpose.TIME ->
                        if (flow.buffer.isBlank()) "" else "  •  ${flow.buffer}"
                    NumberPadPurpose.DATE ->
                        if (flow.buffer.isBlank()) "" else "  •  ${flow.buffer}"
                    NumberPadPurpose.PRICE ->
                        if (flow.buffer.isBlank()) "" else "  •  ${flow.buffer} Ft"
                    else ->
                        if (flow.buffer.isBlank()) "" else "  •  ${flow.buffer}"
                }
                val backHint = if (flow.purpose == NumberPadPurpose.PIN) "egy törlés" else "töröl"
                tvHint.text = "⬆⬇ ${item.label}$bufferHint  •  ➡ beír  •  ⬅ $backHint"
            }
            is AppFlow.ExternalAppBrowse -> {
                val app = flow.apps[flow.index]
                tvItem.text = app.label
                tvPosition.text = "Külső alkalmazások  •  ${flow.index + 1} / ${flow.apps.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ megnyit  •  ⬅ vissza"
            }
            AppFlow.WeatherAwaitCity -> {
                tvItem.text = "Időjárás város szerint"
                tvPosition.text = "Hangos keresés"
                tvHint.text = "Mondd a várost  •  ⬅ mégse"
            }
            AppFlow.PatrolNightAwaitStart -> {
                tvItem.text = "Éjszakai csend kezdete"
                tvPosition.text = "Őrség beállítás"
                tvHint.text = "Mondd az időpontot  •  ⬅ mégse"
            }
            AppFlow.PatrolNightAwaitEnd -> {
                tvItem.text = "Éjszakai csend vége"
                tvPosition.text = "Őrség beállítás"
                tvHint.text = "Mondd az időpontot  •  ⬅ mégse"
            }
            is AppFlow.NotificationBrowse -> {
                val n = flow.notifications[flow.index]
                tvItem.text = n.title.ifBlank { n.text }
                tvPosition.text = "Értesítések  •  ${flow.index + 1} / ${flow.notifications.size}"
                tvHint.text = "⬆⬇ navigálás  •  ➡ felolvas  •  ⬅ vissza"
            }
            is AppFlow.NewsFeedBrowse -> {
                val feed = flow.feeds[flow.index]
                tvItem.text = feed.name
                tvPosition.text = "Hírforrások  •  ${flow.index + 1} / ${flow.feeds.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ betöltés  •  ⬅ vissza"
            }
            is AppFlow.NewsBrowse -> {
                val item = flow.items[flow.index]
                tvItem.text = item.title
                val pageLabel = if (flow.page > 0) "  •  ${flow.page + 1}. oldal" else ""
                tvPosition.text = "${item.source}  •  ${flow.index + 1} / ${flow.items.size}$pageLabel"
                val moreHint = if (flow.hasMore && flow.index == flow.items.lastIndex) "  •  ⬇ következő 20" else ""
                tvHint.text = "⬆⬇ navigálás  •  ➡ felolvas  •  ⬅ vissza$moreHint"
            }
            is AppFlow.NewsFeedManageBrowse -> {
                val feed = flow.feeds[flow.index]
                val status = if (NewsFeedStore.isEnabled(this, feed.id)) "bekapcsolva" else "kikapcsolva"
                tvItem.text = feed.name
                tvPosition.text = "Hírforrások  •  ${flow.index + 1} / ${flow.feeds.size}  •  $status"
                tvHint.text = "⬆⬇ választás  •  ➡ ki-be  •  ⬅ vissza"
            }
            AppFlow.SearchAwaitQuery -> {
                tvItem.text = "Internet kereső"
                tvPosition.text = "Keresés diktálása"
                tvHint.text = "Mondd mit keresel  •  ⬅ mégse"
            }
            AppFlow.SearchLoading -> {
                tvItem.text = "Internet kereső"
                tvPosition.text = "Keresés folyamatban"
                tvHint.text = "Kérem várjon  •  ⬅ megszakítás"
            }
            is AppFlow.SearchResultBrowse -> {
                val result = flow.results[flow.index]
                tvItem.text = result.title
                tvPosition.text = "Keresés  •  ${flow.index + 1} / ${flow.results.size}"
                tvHint.text = "⬆ következő  •  ⬇ mentés jegyzetként  •  ➡ felolvas  •  ⬅ vissza"
            }
            is AppFlow.SearchArticleReading -> {
                tvItem.text = flow.result.title
                tvPosition.text = "Cikk  •  ${flow.chunkIndex + 1} / ${flow.totalChunks.coerceAtLeast(1)}  •  ${flow.percent}%"
                tvHint.text = "⬆ ismétlés  •  ⬇ mentés jegyzetként  •  ➡ ismétlés  •  ⬅ találatok"
            }
            is AppFlow.NewsArticleReading -> {
                tvItem.text = flow.title
                tvPosition.text = "Hír cikk"
                tvHint.text = "⬆ ismétlés  •  ⬇ következő rész  •  ➡ ismétlés  •  ⬅ hírek"
            }
            is AppFlow.MedicationSearchResult -> {
                tvItem.text = flow.title
                tvPosition.text = "Gyógyszer tájékoztató"
                tvHint.text = "⬆ ismétlés  •  ⬇ következő rész  •  ➡ ismétlés  •  ⬅ vissza"
            }
            AppFlow.MedicationSearchAwaitName -> {
                tvItem.text = "Gyógyszer neve?"
                tvPosition.text = "Gyógyszerkereső  •  Név diktálása"
                tvHint.text = "Mondd a gyógyszer nevét  •  ⬅ mégse"
            }
            AppFlow.MedicationSearchLoading -> {
                tvItem.text = "Keresés…"
                tvPosition.text = "Gyógyszerkereső"
                tvHint.text = "⬅ mégse"
            }
            is AppFlow.NoteListBrowse -> {
                val note = flow.notes[flow.index]
                tvItem.text = note.title
                tvPosition.text = if (flow.deleteMode) {
                    "Jegyzet törlése  •  ${flow.index + 1} / ${flow.notes.size}"
                } else {
                    "Saját jegyzetek  •  ${flow.index + 1} / ${flow.notes.size}"
                }
                tvHint.text = if (flow.deleteMode) {
                    "⬆⬇ választás  •  ➡ törlés  •  ⬅ vissza"
                } else {
                    "⬆⬇ választás  •  ➡ megnyitás  •  ⬅ vissza"
                }
            }
            is AppFlow.NoteDeleteConfirm -> {
                tvItem.text = flow.note.title
                tvPosition.text = "Jegyzet törlése"
                tvHint.text = "➡ törlés  •  ⬅ mégse"
            }
            AppFlow.NoteAwaitTitle -> {
                tvItem.text = "Új jegyzet"
                tvPosition.text = "1 / 2  •  Cím diktálása"
                tvHint.text = "Mondd a jegyzet címét  •  ⬅ mégse"
            }
            is AppFlow.NoteAwaitBody -> {
                tvItem.text = flow.title
                tvPosition.text = "2 / 2  •  Szöveg diktálása"
                tvHint.text = "Mondd a jegyzet szövegét  •  ⬅ mégse"
            }
            is AppFlow.NoteReading -> {
                tvItem.text = flow.note.title
                tvPosition.text = "Jegyzet  •  ${flow.chunkIndex + 1} / ${flow.totalChunks.coerceAtLeast(1)}  •  ${flow.percent}%"
                tvHint.text = "⬆ ismétlés  •  ⬇ következő  •  ⬅ lista"
            }
            AppFlow.EmailInboxLoading -> {
                tvItem.text = "E-mailek"
                tvPosition.text = "Betöltés"
                tvHint.text = "Kérem várjon  •  ⬅ megszakítás"
            }
            is AppFlow.EmailInboxBrowse -> {
                val mail = flow.mails[flow.index]
                tvItem.text = mail.subject
                tvPosition.text = "E-mail  •  ${flow.index + 1} / ${flow.mails.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ teljes levél  •  ⬅ vissza"
            }
            is AppFlow.EmailReadBody -> {
                tvItem.text = flow.mail.subject
                tvPosition.text = "Levél felolvasása  •  ${flow.index + 1} / ${flow.mails.size}"
                tvHint.text = "⬆⬇ ismétlés  •  ⬅ lista"
            }
            is AppFlow.ShoppingListPick -> {
                tvItem.text = flow.names[flow.index]
                tvPosition.text = "Bevásárlólista  •  ${flow.index + 1} / ${flow.names.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ megnyitás  •  ⬇ szerkesztés  •  ⬅ vissza"
            }
            is AppFlow.ShoppingListBrowse -> {
                if (flow.showingSummary) {
                    tvItem.text = "Árösszesítő"
                    tvPosition.text = "${flow.listName}  •  összesen"
                    tvHint.text = "⬆⬇ választás  •  ➡ műveletek  •  ⬅ kilépés"
                } else {
                    val item = flow.items[flow.index]
                    val slots = shoppingBrowseSlotCount(flow.items)
                    tvItem.text = item.name
                    tvPosition.text = "${flow.listName}  •  ${flow.index + 1} / $slots"
                    tvHint.text = "⬆⬇ választás  •  ➡ műveletek  •  ⬅ kilépés"
                }
            }
            is AppFlow.ShoppingItemContextMenu -> {
                tvItem.text = flow.actions[flow.actionIndex].label
                tvPosition.text = "${flow.listName}  •  tétel műveletek"
                tvHint.text = "⬆⬇ választás  •  ➡ végrehajtás  •  ⬅ vissza"
            }
            is AppFlow.ShoppingListContextMenu -> {
                tvItem.text = flow.actions[flow.actionIndex].label
                tvPosition.text = "${flow.names[flow.listIndex]}  •  lista műveletek"
                tvHint.text = "⬆⬇ választás  •  ➡ végrehajtás  •  ⬅ vissza"
            }
            is AppFlow.ShoppingDeleteItemConfirm -> {
                tvItem.text = flow.item.name
                tvPosition.text = "Tétel törlése"
                tvHint.text = "➡ törlés  •  ⬅ mégse"
            }
            is AppFlow.ShoppingDeleteListConfirm -> {
                tvItem.text = flow.listName
                tvPosition.text = "Lista törlése"
                tvHint.text = "➡ törlés  •  ⬅ mégse"
            }
            is AppFlow.ShoppingEditItemAwaitName -> {
                tvItem.text = flow.item.name
                tvPosition.text = "Tétel átnevezése"
                tvHint.text = "Mondd az új nevet  •  ⬅ mégse"
            }
            is AppFlow.ShoppingRenameListAwaitName -> {
                tvItem.text = flow.oldName
                tvPosition.text = "Lista átnevezése"
                tvHint.text = "Mondd az új nevet  •  ⬅ mégse"
            }
            AppFlow.ShoppingListAwaitName -> {
                tvItem.text = "Új bevásárlólista"
                tvPosition.text = "Név diktálása"
                tvHint.text = "Mondd a lista nevét  •  ⬅ mégse"
            }
            AppFlow.ShoppingListAwaitItem -> {
                tvItem.text = "Új tétel"
                tvPosition.text = "Diktálás"
                tvHint.text = "Mondd a tétel nevét  •  ⬅ mégse"
            }
            is AppFlow.ShoppingListAwaitMore -> {
                tvItem.text = "Következő tétel"
                tvPosition.text = flow.listName
                tvHint.text = "Diktálás vagy mondd: kész  •  ⬅ lista kész"
            }
            is AppFlow.EmailSmtpPickAccount -> {
                tvItem.text = flow.accounts[flow.index]
                tvPosition.text = "E-mail fiók  •  ${flow.index + 1} / ${flow.accounts.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ kiválasztás  •  ⬅ mégse"
            }
            AppFlow.NavAwaitWalkDestination -> {
                tvItem.text = "Gyalogos útvonal"
                tvPosition.text = "Hangos navigáció"
                tvHint.text = "Mondd a célállomást  •  ⬅ mégse"
            }
            AppFlow.NavAwaitPlaceQuery -> {
                tvItem.text = "Hely keresése"
                tvPosition.text = "Hangos keresés"
                tvHint.text = "Mondd a címet vagy helyet  •  ⬅ mégse"
            }
            is AppFlow.NavPlaceBrowse -> {
                val place = flow.places[flow.index]
                tvItem.text = place.shortName
                tvPosition.text = "Helyek  •  ${flow.index + 1} / ${flow.places.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ térkép  •  ⬅ vissza"
            }
            AppFlow.TransitAwaitStop -> {
                tvItem.text = "Megálló keresése"
                tvPosition.text = "Hangos keresés"
                tvHint.text = "Mondd a megálló nevét  •  ⬅ mégse"
            }
            AppFlow.TransitAwaitDestination -> {
                tvItem.text = "Útvonaltervezés"
                tvPosition.text = "Tömegközlekedés  •  Hangos útvonal"
                tvHint.text = "Mondd a célállomást  •  ⬅ mégse"
            }
            is AppFlow.TransitBrowse -> {
                val place = flow.places[flow.index]
                tvItem.text = place.name
                val direction = place.clockDirection?.let { "  •  $it" }.orEmpty()
                tvPosition.text = "${flow.title}  •  ${flow.index + 1} / ${flow.places.size}$direction"
                tvHint.text = "⬆⬇ választás  •  ➡ műveletek  •  ⬅ vissza"
            }
            is AppFlow.TransitContextMenu -> {
                val place = flow.places[flow.placeIndex]
                tvItem.text = flow.actions[flow.actionIndex].label
                tvPosition.text = "Megálló műveletek  •  ${flow.actionIndex + 1} / ${flow.actions.size}  •  ${place.name}"
                tvHint.text = "⬆⬇ választás  •  ➡ végrehajtás  •  ⬅ vissza"
            }
            is AppFlow.TransitRouteBrowse -> {
                val step = flow.route.steps[flow.index]
                tvItem.text = step.instruction
                tvPosition.text = "Útvonal  •  ${flow.index + 1} / ${flow.route.steps.size}"
                tvHint.text = "⬆⬇ lépés  •  ➡ ismétlés  •  ⬅ vissza"
            }
            AppFlow.TrainAwaitStation -> {
                tvItem.text = "Állomás keresése"
                tvPosition.text = "Vonat  •  Hangos keresés"
                tvHint.text = "Mondd az állomás nevét  •  ⬅ mégse"
            }
            is AppFlow.TrainBrowse -> {
                val station = flow.stations[flow.index]
                tvItem.text = station.name
                val direction = station.clockDirection?.let { "  •  $it" }.orEmpty()
                tvPosition.text = "Vonat  •  ${flow.title}  •  ${flow.index + 1} / ${flow.stations.size}$direction"
                tvHint.text = "⬆⬇ választás  •  ➡ műveletek  •  ⬅ vissza"
            }
            is AppFlow.TrainContextMenu -> {
                val station = flow.stations[flow.stationIndex]
                tvItem.text = flow.actions[flow.actionIndex].label
                tvPosition.text = "Vonat műveletek  •  ${flow.actionIndex + 1} / ${flow.actions.size}  •  ${station.name}"
                tvHint.text = "⬆⬇ választás  •  ➡ végrehajtás  •  ⬅ vissza"
            }
            AppFlow.VoiceAssistantAwaitQuestion,
            AppFlow.VoiceAssistantChat -> {
                tvItem.text = ElenaWakeHelper.ASSISTANT_NAME
                tvPosition.text = "Parancs diktálása"
                tvHint.text = "Diktálj  •  Szia ${ElenaWakeHelper.ASSISTANT_NAME}  •  ➡ új parancs  •  ⬅ kilépés"
            }
            AppFlow.ElenaWakeTrainAwaitPhrase -> {
                tvItem.text = "Elena tanítás"
                tvPosition.text = "Saját felébresztő mondat"
                tvHint.text = "Mondd a mondatot  •  ⬅ mégse"
            }
            AppFlow.YoutubeAwaitQuery -> {
                tvItem.text = "YouTube keresés"
                tvPosition.text = "1 / 2  •  Keresés diktálása"
                tvHint.text = "Mondd mit keresel  •  ⬅ mégse"
            }
            is AppFlow.YoutubeBrowse -> {
                val video = flow.videos[flow.index]
                tvItem.text = video.title
                val pageLabel = if (flow.page > 0) "  •  ${flow.page + 1}. oldal" else ""
                tvPosition.text = "YouTube  •  ${flow.index + 1} / ${flow.videos.size}$pageLabel"
                val moreHint = if (flow.hasMore && flow.index == flow.videos.lastIndex) "  •  ⬇ következő 20" else ""
                tvHint.text = "⬆⬇ választás  •  ➡ lejátszás  •  ⬅ vissza$moreHint"
            }
            is AppFlow.GpsArrivalLocationPrompt -> {
                tvItem.text = AppFlow.GpsArrivalLocationPrompt.OPTIONS[flow.index]
                tvPosition.text = "Megérkeztél: ${flow.destinationName}"
                tvHint.text = "⬆⬇ választás  •  ➡ megerősítés  •  ⬅ kihagyás"
            }
            is AppFlow.CardBrowse -> {
                val card = flow.cards[flow.index]
                tvItem.text = card.name
                tvPosition.text = if (flow.deleteMode) {
                    "Kártyák törlése  •  ${flow.index + 1} / ${flow.cards.size}"
                } else {
                    "Mentett kártyák  •  ${flow.index + 1} / ${flow.cards.size}"
                }
                tvHint.text = "⬆⬇ választás  •  ➡ ${if (flow.deleteMode) "törlés" else "felolvas"}  •  ⬅ vissza"
            }
            is AppFlow.CardDeleteConfirm -> {
                tvItem.text = flow.card.name
                tvPosition.text = "Kártya törlés megerősítés"
                tvHint.text = "➡ törlés  •  ⬅ mégse"
            }
            is AppFlow.YoutubePlayConfirm -> {
                tvItem.text = flow.video.title
                tvPosition.text = "Lejátszás megerősítés  •  ${flow.video.channel}"
                tvHint.text = "➡ lejátszás  •  ⬅ mégse  •  ⬆⬇ ismétlés"
            }
            is AppFlow.LegalBrowse -> {
                val section = flow.sections[flow.index]
                tvItem.text = section.title
                tvPosition.text = "Jogi információ  •  ${flow.index + 1} / ${flow.sections.size}"
                tvHint.text = "⬆⬇ navigálás  •  ➡ felolvas  •  ⬅ vissza"
            }
            is AppFlow.GuideBrowse -> {
                val section = flow.sections[flow.index]
                tvItem.text = section.title
                tvPosition.text = "${flow.title}  •  ${flow.index + 1} / ${flow.sections.size}"
                tvHint.text = "⬆⬇ navigálás  •  ➡ felolvas  •  ⬅ vissza"
            }
            AppFlow.LauncherExitConfirm -> {
                tvItem.text = "Kilépés a Super DL launcherből"
                tvPosition.text = "Megerősítés"
                tvHint.text = "➡ kezdőképernyő választó  •  ⬅ mégse"
            }
            AppFlow.EmailSmtpAwaitUsername -> {
                tvItem.text = "E-mail küldő"
                tvPosition.text = "Gmail cím"
                tvHint.text = "Mondd a Gmail címedet  •  ⬅ mégse"
            }
            AppFlow.EmailSmtpAwaitPassword -> {
                tvItem.text = "E-mail küldő"
                tvPosition.text = "Alkalmazásjelszó"
                tvHint.text = "Mondd a jelszót  •  ⬅ mégse"
            }
            AppFlow.EmailSmtpAwaitFromName -> {
                tvItem.text = "E-mail küldő"
                tvPosition.text = "Küldő név"
                tvHint.text = "Mondd a nevedet  •  ⬅ mégse"
            }
            is AppFlow.BookLibraryBrowse -> {
                val book = flow.books[flow.index]
                tvItem.text = book.title
                tvPosition.text = "Könyvtár  •  ${flow.index + 1} / ${flow.books.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ megnyit  •  ⬅ vissza"
            }
            is AppFlow.BookRecentBrowse -> {
                val book = flow.books[flow.index]
                tvItem.text = book.title
                tvPosition.text = "Nem rég olvasott  •  ${flow.index + 1} / ${flow.books.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ folytat  •  ⬅ vissza"
            }
            is AppFlow.BookBookmarkBrowse -> {
                val bookmark = flow.bookmarks[flow.index]
                tvItem.text = bookmark.bookTitle
                tvPosition.text = if (flow.deleteMode) "Törlés  •  ${flow.index + 1} / ${flow.bookmarks.size}"
                else "Könyvjelzők  •  ${flow.index + 1} / ${flow.bookmarks.size}"
                tvHint.text = if (flow.deleteMode)
                    "⬆⬇ választás  •  ➡ törlés  •  ⬅ vissza"
                else
                    "⬆⬇ választás  •  ➡ ugrás  •  ⬅ vissza"
            }
            is AppFlow.BookBookmarkDeleteConfirm -> {
                tvItem.text = flow.bookmark.bookTitle
                tvPosition.text = "Könyvjelző törlés  •  ${flow.bookmark.preview.take(40)}"
                tvHint.text = "➡ törlés  •  ⬅ mégse"
            }
            AppFlow.BookSearchAwaitQuery -> {
                tvItem.text = "Könyv keresése"
                tvPosition.text = "Hangos keresés"
                tvHint.text = "Diktáld a címet  •  ⬅ mégse"
            }
            is AppFlow.BookReading -> {
                tvItem.text = flow.book.title
                tvPosition.text = "Olvasás  •  ${flow.percent}%  •  ${flow.chunkIndex + 1} / ${flow.totalChunks.coerceAtLeast(1)}"
                tvHint.text = "⬆ ismétlés  •  ⬇ következő  •  ➡ könyvjelző  •  ⬅ leállítás"
            }
            AppFlow.BookLoading -> {
                tvItem.text = "Könyv betöltése"
                tvPosition.text = "Kérem várjon"
                tvHint.text = "⬅ megszakítás"
            }
            is AppFlow.TtsVoiceBrowse -> {
                val option = flow.options[flow.index]
                tvItem.text = option.displayLabel
                tvPosition.text = "T T S hang  •  ${flow.index + 1} / ${flow.options.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ beállít  •  ⬅ vissza"
            }
            is AppFlow.FavoriteAppsBrowse -> {
                val favorite = flow.favorites[flow.index]
                tvItem.text = favorite.label
                tvPosition.text = when (flow.mode) {
                    AppFlow.FavoriteAppsMode.LAUNCH -> "Kedvenc appok  •  ${flow.index + 1} / ${flow.favorites.size}"
                    AppFlow.FavoriteAppsMode.REMOVE -> "Kedvenc törlés  •  ${flow.index + 1} / ${flow.favorites.size}"
                    AppFlow.FavoriteAppsMode.ADD -> "Kedvenc appok"
                }
                tvHint.text = when (flow.mode) {
                    AppFlow.FavoriteAppsMode.LAUNCH -> "⬆⬇ választás  •  ➡ indít  •  ⬅ vissza"
                    AppFlow.FavoriteAppsMode.REMOVE -> "⬆⬇ választás  •  ➡ töröl  •  ⬅ vissza"
                    AppFlow.FavoriteAppsMode.ADD -> "⬆⬇ választás  •  ⬅ vissza"
                }
            }
            is AppFlow.FavoriteAppsCandidateBrowse -> {
                val candidate = flow.candidates[flow.index]
                tvItem.text = candidate.label
                tvPosition.text = "Kedvenc hozzáadása  •  ${flow.index + 1} / ${flow.candidates.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ hozzáad  •  ⬅ vissza"
            }
            is AppFlow.FavoriteContactCandidateBrowse -> {
                val candidate = flow.candidates[flow.index]
                tvItem.text = candidate.name()
                tvPosition.text = "Kedvenc hozzáadása  •  ${flow.index + 1} / ${flow.candidates.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ hozzáad  •  ⬅ vissza"
            }
            is AppFlow.SosSetupMethodPick -> {
                tvItem.text = sosSetupMethodLabel(flow.index)
                tvPosition.text = "S.O.S. szám ${flow.slot}"
                tvHint.text = "⬆⬇ választás  •  ➡ megerősít  •  ⬅ vissza"
            }
            is AppFlow.SosContactCandidateBrowse -> {
                val contact = flow.contacts[flow.index]
                tvItem.text = contact.name
                tvPosition.text = "S.O.S. névjegy  •  ${flow.index + 1} / ${flow.contacts.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ mentés  •  ⬅ vissza"
            }
            is AppFlow.AlertSoundPresetBrowse -> {
                val preset = flow.presets[flow.index]
                tvItem.text = preset.label
                tvPosition.text = "Hangok  •  ${flow.category.label}"
                tvHint.text = "⬆⬇ választás  •  ➡ beállítás és előnézet  •  ⬅ vissza"
            }
            is AppFlow.SoundTrainingBrowse -> {
                val item = flow.items[flow.index]
                tvItem.text = item.label
                tvPosition.text = "Hangok  •  ${flow.index + 1} / ${flow.items.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ hallgatás  •  ⬅ vissza"
            }
            is AppFlow.SoundThemeBrowse -> {
                val theme = flow.themes[flow.index]
                tvItem.text = theme.label
                tvPosition.text = "Söpörj hangtéma  •  ${flow.index + 1} / ${flow.themes.size}"
                tvHint.text = "⬆⬇ választás  •  ➡ beállítás és előnézet  •  ⬅ vissza"
            }
            is AppFlow.TrainingPlayground -> {
                val step = flow.steps[flow.stepIndex]
                when (step) {
                    is TrainingStep.Explain -> {
                        tvItem.text = "Magyarázat"
                        tvPosition.text = "Tanuló mód  •  ${flow.stepIndex + 1} / ${flow.steps.size}"
                        tvHint.text = "➡ tovább  •  ⬆⬇ ismétlés  •  ⬅⬅ kilépés"
                    }
                    is TrainingStep.Practice -> {
                        if (flow.awaitingAdvance) {
                            tvItem.text = "Helyes válasz!"
                            tvPosition.text = "Tanuló mód  •  ${flow.stepIndex + 1} / ${flow.steps.size}"
                            tvHint.text = "➡ következő feladat  •  ⬅⬅ kilépés"
                        } else {
                            tvItem.text = step.choices[flow.choiceIndex]
                            tvPosition.text = "Gyakorlat  •  ${flow.choiceIndex + 1} / ${step.choices.size}"
                            tvHint.text = "⬆⬇ keresés  •  ➡ válasz  •  ⬅⬅ kilépés"
                        }
                    }
                }
            }
            AppFlow.Menu -> updateDisplay()
        }
    }

    private fun buildHintText(item: MenuItem): String {
        return when (item.action) {
            MenuAction.EXIT_LAUNCHER ->
                "⬆⬇ navigálás  •  ➡➡ megerősítés  •  ⬅ vissza"
            MenuAction.WIFI_TOGGLE, MenuAction.HOTSPOT_TOGGLE, MenuAction.BT_TOGGLE ->
                "⬆⬇ navigálás  •  ➡ kapcsol  •  ⬅ vissza"
            MenuAction.SUBMENU -> if (item.children.isNotEmpty())
                "⬆⬇ navigálás  •  ➡ almenü megnyit  •  ⬅ vissza"
            else
                "⬆⬇ navigálás  •  ➡ vissza  •  ⬅ vissza"
            MenuAction.SOS -> "⬆⬇ navigálás  •  ➡ S.O.S. indít (5 mp)  •  ⬅ vissza"
            else -> "⬆⬇ navigálás  •  ➡ megnyit  •  ⬅ vissza"
        }
    }

    // ==================== ENGEDÉLYEK & MIKROFON ====================

    private fun ensureMicAndRun(action: () -> Unit) {
        if (!voiceInput.isAvailable()) {
            feedbackError()
            tts.speak("A diktálás nem elérhető ezen az eszközön.")
            return
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            pendingVoiceAction = action
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), PERM_REQUEST)
            tts.speak("Mikrofon engedély szükséges.")
            return
        }
        action()
    }

    private fun requestPermissionsIfNeeded() {
        val missing = REQUIRED_PERMISSIONS.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), PERM_REQUEST)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != PERM_REQUEST) return

        // A beállítás varázsló kérése: bármi lett az eredmény, ÚJRAMÉRÜNK és
        // visszatérünk a listához. A varázsló nem áll meg egy elutasításnál —
        // a felhasználó később is megadhatja.
        val wizardPending = setupWizardPending
        setupWizardPending = null
        if (wizardPending != null) {
            val granted = grantResults.isNotEmpty() &&
                grantResults.all { it == PackageManager.PERMISSION_GRANTED }
            if (granted) {
                tts.speak("Megadva.")
            } else {
                tts.speak(
                    "Ez az engedély most nem lett megadva. Később bármikor visszatérhetsz ide."
                )
            }
            returnToSetupWizard()
            return
        }

        if (pendingHotspotToggle) {
            pendingHotspotToggle = false
            if (ConnectivityHelper.hasNearbyWifiPermission(this)) {
                runHotspotToggle()
                return
            }
        }

        val voiceAction = pendingVoiceAction
        pendingVoiceAction = null
        if (voiceAction != null &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            == PackageManager.PERMISSION_GRANTED
        ) {
            voiceAction()
            return
        }

        val smsFolder = pendingSmsFolderRead
        pendingSmsFolderRead = null
        if (smsFolder != null &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.READ_SMS)
            == PackageManager.PERMISSION_GRANTED
        ) {
            openSmsFolderFlow(smsFolder)
            return
        }

        val denied = permissions.indices
            .filter { grantResults.getOrNull(it) != PackageManager.PERMISSION_GRANTED }
            .map { permissionLabel(permissions[it]) }
        if (denied.isEmpty()) {
            tts.speak("Minden kért engedély megadva. ${LegalTexts.APP_SHORT_NAME} készen áll.")
        } else {
            tts.speak(
                "Néhány engedély hiányzik: ${denied.joinToString(", ")}. " +
                    "A funkciók korlátozva lehetnek. A Beállításokban adhatod meg."
            )
        }
    }

    private fun permissionLabel(permission: String): String = when (permission) {
        Manifest.permission.CALL_PHONE -> "telefonhívás"
        Manifest.permission.ANSWER_PHONE_CALLS -> "híváskezelés"
        Manifest.permission.READ_CONTACTS -> "névjegyek"
        Manifest.permission.WRITE_CONTACTS -> "névjegy mentés"
        Manifest.permission.READ_CALL_LOG -> "hívásnapló"
        Manifest.permission.READ_PHONE_NUMBERS -> "telefonszámok"
        Manifest.permission.SEND_SMS, Manifest.permission.READ_SMS -> "üzenetek"
        Manifest.permission.ACCESS_FINE_LOCATION -> "helymeghatározás"
        Manifest.permission.CAMERA -> "kamera"
        Manifest.permission.RECORD_AUDIO -> "mikrofon"
        Manifest.permission.READ_CALENDAR, Manifest.permission.WRITE_CALENDAR -> "naptár"
        Manifest.permission.POST_NOTIFICATIONS -> "értesítések"
        Manifest.permission.READ_MEDIA_AUDIO -> "zene"
        Manifest.permission.BLUETOOTH_CONNECT -> "bluetooth"
        Manifest.permission.NEARBY_WIFI_DEVICES -> "közeli WiFi eszközök"
        Manifest.permission.GET_ACCOUNTS -> "fiókok"
        Manifest.permission.READ_EXTERNAL_STORAGE -> "fájlok"
        else -> permission.substringAfterLast('.')
    }

    // ==================== ÉLETCIKLUS ====================

    private fun vibrate(ms: Long) {
        vibrator?.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE))
    }

    override fun onDestroy() {
        stopDictaphoneElapsedLoop()
        DictaphonePlayback.stop()
        if (DictaphoneManager.isRecording()) {
            DictaphoneManager.cancelRecording(this)
        }
        stopRadarSession(stopGuidance = GpsRadarManager.isGuiding())
        cancelGpsRefining()
        sosCountdownActive = false
        countdownHandler.removeCallbacksAndMessages(null)
        mainHandler.removeCallbacksAndMessages(null)
        if (::bookReader.isInitialized && bookReader.isActive) bookReader.stop()
        if (::articleReader.isInitialized && articleReader.isActive) articleReader.stop()
        if (::noteReader.isInitialized && noteReader.isActive) noteReader.stop()
        mediaButtonHandler?.stop()
        voiceInput.destroy()
        tts.shutdown()
        if (::sounds.isInitialized) sounds.release()
        super.onDestroy()
    }

    override fun onStart() {
        super.onStart()
        isForeground = true
        registerLockReceiver()
        registerGpsArrivalReceiver()
        registerSmsIncomingReceiver()
        if (mediaButtonHandler == null) {
            mediaButtonHandler = AssistantMediaButtonHandler(this)
        }
        mediaButtonHandler?.start()
        if (pendingAssistantLaunch) {
            runPendingVoiceActionIfReady()
        }
    }

    override fun onStop() {
        lockReceiver?.let { unregisterReceiver(it) }
        lockReceiver = null
        gpsArrivalReceiver?.let { unregisterReceiver(it) }
        gpsArrivalReceiver = null
        smsIncomingReceiver?.let { unregisterReceiver(it) }
        smsIncomingReceiver = null
        super.onStop()
    }

    override fun onResume() {
        super.onResume()
        if (CallSession.isInCallUiActive) {
            CallHelper.bringInCallToFront(this)
            return
        }
        isForeground = true
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        )
        if (LockSession.needsUnlock(this) && !LockSession.lockScreenVisible && !pendingAssistantLaunch) {
            showLockScreen()
        } else {
            runPendingVoiceActionIfReady()
            if (voiceAssistantReturnPending &&
                (activeFlow == AppFlow.VoiceAssistantChat || activeFlow == AppFlow.VoiceAssistantAwaitQuestion)
            ) {
                mainHandler.postDelayed({ resumeVoiceAssistantListening() }, 500)
            }
            checkPendingGpsArrivalPrompt()
        }
    }

    private fun checkPendingGpsArrivalPrompt() {
        val destination = GpsRadarStore.pendingArrivalPrompt ?: return
        if (activeFlow !is AppFlow.Menu && activeFlow !is AppFlow.GpsRadarGuiding) return
        postWhenAlive { startGpsArrivalLocationPrompt(destination) }
    }

    private fun registerSmsIncomingReceiver() {
        if (smsIncomingReceiver != null) return
        val filter = IntentFilter(SmsIncomingNotifier.ACTION_SMS_INCOMING)
        smsIncomingReceiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                postWhenAlive { refreshSmsInboxIfVisible() }
            }
        }
        ContextCompat.registerReceiver(
            this,
            smsIncomingReceiver,
            filter,
            ContextCompat.RECEIVER_NOT_EXPORTED
        )
    }

    private fun registerGpsArrivalReceiver() {
        if (gpsArrivalReceiver != null) return
        val filter = IntentFilter(GpsRadarService.ACTION_GPS_ARRIVAL)
        gpsArrivalReceiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                val name = intent.getStringExtra(GpsRadarService.EXTRA_DESTINATION_NAME).orEmpty()
                if (name.isBlank()) return
                postWhenAlive {
                    if (isForeground) {
                        startGpsArrivalLocationPrompt(name)
                    }
                }
            }
        }
        ContextCompat.registerReceiver(
            this,
            gpsArrivalReceiver,
            filter,
            ContextCompat.RECEIVER_NOT_EXPORTED
        )
    }

    override fun onPause() {
        isForeground = false
        mediaButtonHandler?.stop()
        super.onPause()
    }

    private fun registerLockReceiver() {
        if (lockReceiver != null) return
        val filter = IntentFilter().apply {
            addAction(Intent.ACTION_SCREEN_ON)
            addAction(Intent.ACTION_SCREEN_OFF)
        }
        lockReceiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                when (intent.action) {
                    Intent.ACTION_SCREEN_OFF -> LockSession.lock()
                    Intent.ACTION_SCREEN_ON -> onScreenTurnedOn()
                }
            }
        }
        ContextCompat.registerReceiver(
            this,
            lockReceiver,
            filter,
            ContextCompat.RECEIVER_NOT_EXPORTED
        )
    }

    private fun onScreenTurnedOn() {
        if (!LockSession.needsUnlock(this)) return
        postWhenAlive {
            if (!LockSession.needsUnlock(this)) return@postWhenAlive
            if (isForeground) {
                val pinFlow = activeFlow as? AppFlow.NumberPadInput
                if (pinFlow?.purpose == NumberPadPurpose.PIN && pinFlow.pinMode == PinPadMode.UNLOCK) return@postWhenAlive
                showLockScreen()
            } else if (!LockSession.lockScreenVisible) {
                startActivity(Intent(this, LockScreenActivity::class.java))
            }
        }
    }
}