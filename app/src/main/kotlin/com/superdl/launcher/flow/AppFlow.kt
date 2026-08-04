package com.superdl.launcher.flow

import com.superdl.launcher.alarm.AlarmEntry
import com.superdl.launcher.contacts.ContactMatch
import com.superdl.launcher.sms.Recipient
import com.superdl.launcher.sms.SmsFolder
import com.superdl.launcher.sms.SmsMessage

sealed class AppFlow {
    object Menu : AppFlow()

    object SmsAwaitRecipient : AppFlow()
    data class SmsPickContact(val matches: List<ContactMatch>, val index: Int) : AppFlow()
    data class SmsRecipientConfirm(val recipient: Recipient) : AppFlow()
    data class SmsAwaitMessage(val recipient: Recipient) : AppFlow()
    data class SmsConfirm(val recipient: Recipient, val message: String) : AppFlow()

    data class SmsInbox(
        val messages: List<SmsMessage>,
        val index: Int,
        val folder: SmsFolder = SmsFolder.INBOX
    ) : AppFlow()

    data class SmsContextMenu(
        val messages: List<SmsMessage>,
        val messageIndex: Int,
        val actions: List<com.superdl.launcher.sms.SmsContextAction>,
        val actionIndex: Int,
        val folder: SmsFolder = SmsFolder.INBOX
    ) : AppFlow()

    data class SmsDeleteConfirm(
        val messages: List<SmsMessage>,
        val messageIndex: Int,
        val folder: SmsFolder = SmsFolder.INBOX
    ) : AppFlow()

    object EmailAwaitRecipient : AppFlow()
    data class EmailPickRecipient(val matches: List<com.superdl.launcher.email.EmailRecipient>, val index: Int) : AppFlow()
    data class EmailRecipientConfirm(val recipient: com.superdl.launcher.email.EmailRecipient) : AppFlow()
    data class EmailAwaitSubject(val recipient: com.superdl.launcher.email.EmailRecipient) : AppFlow()
    data class EmailAwaitBody(val recipient: com.superdl.launcher.email.EmailRecipient, val subject: String) : AppFlow()
    data class EmailConfirm(
        val recipient: com.superdl.launcher.email.EmailRecipient,
        val subject: String,
        val body: String
    ) : AppFlow()
    data class EmailBrowseRecipients(val recipients: List<com.superdl.launcher.email.EmailRecipient>, val index: Int) : AppFlow()

    data class CallPickContact(val matches: List<ContactMatch>, val index: Int) : AppFlow()
    data class CallConfirm(val contact: ContactMatch) : AppFlow()

    data class ContactBookBrowse(
        val items: List<com.superdl.launcher.contacts.ContactBookItem>,
        val index: Int
    ) : AppFlow()

    data class ContactLetterBrowse(
        val groups: List<com.superdl.launcher.contacts.ContactLetterIndex.LetterGroup>,
        val index: Int
    ) : AppFlow()

    data class ContactContextMenu(
        val items: List<com.superdl.launcher.contacts.ContactBookItem>,
        val contactIndex: Int,
        val actions: List<com.superdl.launcher.contacts.ContactContextAction>,
        val actionIndex: Int
    ) : AppFlow()

    data class ContactEditAwaitName(val contact: ContactMatch) : AppFlow()
    data class ContactEditAwaitPhone(val contact: ContactMatch, val newName: String) : AppFlow()

    data class ContactDeleteConfirm(
        val contact: ContactMatch,
        val items: List<com.superdl.launcher.contacts.ContactBookItem>,
        val index: Int
    ) : AppFlow()

    data class SosCountdown(val secondsLeft: Int) : AppFlow()

    object AlarmAwaitTime : AppFlow()
    data class AlarmAwaitLabel(val hour: Int, val minute: Int) : AppFlow()
    data class AlarmRepeatBrowse(
        val hour: Int,
        val minute: Int,
        val label: String,
        val options: List<com.superdl.launcher.alarm.AlarmRepeatType>,
        val index: Int
    ) : AppFlow()
    data class AlarmConfirm(val hour: Int, val minute: Int, val label: String) : AppFlow()
    data class AlarmListBrowse(val alarms: List<AlarmEntry>, val index: Int, val deleteMode: Boolean = false) : AppFlow()
    data class AlarmDeleteConfirm(val alarm: AlarmEntry, val alarms: List<AlarmEntry>, val index: Int) : AppFlow()
    /** Katalógus: elérhető modulok böngészése és letöltése. */
    data class CatalogBrowse(
        val modules: List<com.superdl.launcher.catalog.CatalogModule>,
        val index: Int
    ) : AppFlow()

    data class CalendarBrowse(val events: List<com.superdl.launcher.calendar.CalendarEvent>, val index: Int) : AppFlow()

    /** Naptár-választó: melyik naptárba kerüljenek a felvett programok. */
    data class CalendarTargetPick(
        val calendars: List<com.superdl.launcher.calendar.CalendarHelper.CalendarInfo>,
        val index: Int
    ) : AppFlow()

    /**
     * Ébresztések kihagyása — 1. lépés: melyik ébresztőket érintse.
     * Fel-le: navigálás, jobbra: kijelölés váltása, balra: tovább / kilépés.
     */
    data class AlarmSkipPick(
        val alarms: List<com.superdl.launcher.alarm.AlarmEntry>,
        val index: Int,
        val selected: Set<Int>
    ) : AppFlow()

    /**
     * Ébresztések kihagyása — 2. lépés: hány következő alkalmat hagyjon ki.
     * Fel-le: darabszám, jobbra: mentés, balra: vissza a kijelöléshez.
     */
    data class AlarmSkipCount(
        val alarms: List<com.superdl.launcher.alarm.AlarmEntry>,
        val selected: Set<Int>,
        val count: Int
    ) : AppFlow()
    data class CalendarPick(
        val events: List<com.superdl.launcher.calendar.CalendarEvent>,
        val index: Int,
        val purpose: com.superdl.launcher.CalendarPickPurpose
    ) : AppFlow()
    data class CalendarWeekBrowse(val days: List<com.superdl.launcher.calendar.CalendarDayGroup>, val index: Int) : AppFlow()
    object CalendarAwaitTitle : AppFlow()
    data class CalendarAwaitDate(val title: String) : AppFlow()
    data class CalendarAwaitStartTime(val title: String, val dayStartMs: Long) : AppFlow()
    data class CalendarAwaitEndTime(
        val title: String,
        val dayStartMs: Long,
        val startHour: Int,
        val startMinute: Int
    ) : AppFlow()
    data class CalendarRecurrenceBrowse(
        val title: String,
        val beginMs: Long,
        val endMs: Long,
        val options: List<com.superdl.launcher.calendar.CalendarRecurrence>,
        val index: Int,
        val editEventId: Long? = null
    ) : AppFlow()

    data class CalendarConfirm(
        val title: String,
        val beginMs: Long,
        val endMs: Long,
        val recurrence: com.superdl.launcher.calendar.CalendarRecurrence,
        val editEventId: Long? = null
    ) : AppFlow()

    data class NoteListBrowse(
        val notes: List<com.superdl.launcher.notes.NoteEntry>,
        val index: Int,
        val deleteMode: Boolean = false
    ) : AppFlow()

    object NoteAwaitTitle : AppFlow()
    data class NoteAwaitBody(val title: String) : AppFlow()
    data class NoteReading(
        val note: com.superdl.launcher.notes.NoteEntry,
        val chunkIndex: Int,
        val totalChunks: Int,
        val percent: Int,
        val notes: List<com.superdl.launcher.notes.NoteEntry>,
        val noteIndex: Int
    ) : AppFlow()

    data class NoteDeleteConfirm(
        val note: com.superdl.launcher.notes.NoteEntry,
        val notes: List<com.superdl.launcher.notes.NoteEntry>,
        val index: Int
    ) : AppFlow()

    data class CalendarContextMenu(
        val events: List<com.superdl.launcher.calendar.CalendarEvent>,
        val eventIndex: Int,
        val actions: List<com.superdl.launcher.calendar.CalendarContextAction>,
        val actionIndex: Int
    ) : AppFlow()

    data class CalendarAlarmContextMenu(
        val event: com.superdl.launcher.calendar.CalendarEvent,
        val actions: List<com.superdl.launcher.calendar.CalendarAlarmAction>,
        val actionIndex: Int
    ) : AppFlow()

    data class CalendarDeleteConfirm(
        val event: com.superdl.launcher.calendar.CalendarEvent,
        val events: List<com.superdl.launcher.calendar.CalendarEvent>,
        val index: Int
    ) : AppFlow()
    data class CallLogBrowse(val entries: List<com.superdl.launcher.calllog.CallLogEntry>, val index: Int) : AppFlow()

    data class CallLogContextMenu(
        val entries: List<com.superdl.launcher.calllog.CallLogEntry>,
        val entryIndex: Int,
        val actions: List<com.superdl.launcher.calllog.CallLogContextAction>,
        val actionIndex: Int
    ) : AppFlow()

    data class CallLogSaveContactAwaitName(
        val entries: List<com.superdl.launcher.calllog.CallLogEntry>,
        val entryIndex: Int
    ) : AppFlow()

    data class ContactCreateAwaitName(val phone: String) : AppFlow()

    data class FavoritesBrowse(
        val favorites: List<com.superdl.launcher.favorites.FavoriteEntry>,
        val index: Int,
        val mode: com.superdl.launcher.favorites.FavoritesListMode
    ) : AppFlow()

    data class FavoriteDeleteConfirm(
        val favorite: com.superdl.launcher.favorites.FavoriteEntry,
        val favorites: List<com.superdl.launcher.favorites.FavoriteEntry>,
        val index: Int
    ) : AppFlow()

    data class FavoriteContactCandidateBrowse(
        val candidates: List<com.superdl.launcher.favorites.FavoriteContactCandidate>,
        val index: Int
    ) : AppFlow()

    data class SosSetupMethodPick(
        val slot: Int,
        val index: Int = 0
    ) : AppFlow()

    data class SosContactCandidateBrowse(
        val contacts: List<ContactMatch>,
        val index: Int,
        val slot: Int
    ) : AppFlow()
    data class MusicBrowse(val tracks: List<com.superdl.launcher.music.MusicTrack>, val index: Int) : AppFlow()
    data class RadioBrowse(val stations: List<com.superdl.launcher.radio.RadioStation>, val index: Int) : AppFlow()
    object CalculatorAwaitInput : AppFlow()
    object WeatherAwaitCity : AppFlow()
    data class EmailSmtpPickAccount(
        val accounts: List<String>,
        val index: Int
    ) : AppFlow()

    object EmailSmtpAwaitUsername : AppFlow()
    object EmailSmtpAwaitPassword : AppFlow()
    object EmailSmtpAwaitFromName : AppFlow()

    object SearchAwaitQuery : AppFlow()
    object SearchLoading : AppFlow()

    data class SearchResultBrowse(
        val results: List<com.superdl.launcher.search.SearchResult>,
        val index: Int,
        val query: String
    ) : AppFlow()

    data class SearchArticleReading(
        val result: com.superdl.launcher.search.SearchResult,
        val chunkIndex: Int,
        val totalChunks: Int,
        val percent: Int,
        val results: List<com.superdl.launcher.search.SearchResult>,
        val resultIndex: Int,
        val query: String,
        val sourceLabel: String = "",
        val articleBody: String = ""
    ) : AppFlow()

    object EmailInboxLoading : AppFlow()

    data class EmailInboxBrowse(
        val mails: List<com.superdl.launcher.email.ImapMail>,
        val index: Int
    ) : AppFlow()

    data class EmailReadBody(
        val mail: com.superdl.launcher.email.ImapMail,
        val mails: List<com.superdl.launcher.email.ImapMail>,
        val index: Int
    ) : AppFlow()

    data class ShoppingListPick(
        val names: List<String>,
        val index: Int
    ) : AppFlow()

    data class ShoppingListBrowse(
        val listName: String,
        val items: List<com.superdl.launcher.shopping.ShoppingItem>,
        val index: Int,
        val showingSummary: Boolean = false
    ) : AppFlow()

    object ShoppingListAwaitName : AppFlow()
    object ShoppingListAwaitItem : AppFlow()
    data class ShoppingListAwaitMore(
        val listName: String
    ) : AppFlow()

    data class ShoppingItemContextMenu(
        val listName: String,
        val items: List<com.superdl.launcher.shopping.ShoppingItem>,
        val itemIndex: Int,
        val actions: List<com.superdl.launcher.shopping.ShoppingContextAction>,
        val actionIndex: Int
    ) : AppFlow()

    data class ShoppingListContextMenu(
        val names: List<String>,
        val listIndex: Int,
        val actions: List<com.superdl.launcher.shopping.ShoppingListContextAction>,
        val actionIndex: Int
    ) : AppFlow()

    data class ShoppingDeleteItemConfirm(
        val listName: String,
        val item: com.superdl.launcher.shopping.ShoppingItem,
        val items: List<com.superdl.launcher.shopping.ShoppingItem>,
        val index: Int
    ) : AppFlow()

    data class ShoppingDeleteListConfirm(
        val listName: String,
        val names: List<String>,
        val index: Int
    ) : AppFlow()

    data class ShoppingEditItemAwaitName(
        val listName: String,
        val item: com.superdl.launcher.shopping.ShoppingItem,
        val items: List<com.superdl.launcher.shopping.ShoppingItem>,
        val index: Int
    ) : AppFlow()

    data class ShoppingRenameListAwaitName(
        val oldName: String,
        val names: List<String>,
        val index: Int
    ) : AppFlow()
    data class GuideBrowse(val sections: List<com.superdl.launcher.legal.LegalSection>, val index: Int, val title: String) : AppFlow()

    data class NotificationBrowse(val notifications: List<com.superdl.launcher.notifications.NotificationEntry>, val index: Int) : AppFlow()
    data class NewsFeedBrowse(val feeds: List<com.superdl.launcher.news.NewsFeed>, val index: Int) : AppFlow()
    data class NewsBrowse(
        val items: List<com.superdl.launcher.news.RssItem>,
        val index: Int,
        val feedId: String? = null,
        val page: Int = 0,
        val hasMore: Boolean = false
    ) : AppFlow()
    data class NewsArticleReading(
        val newsFlow: NewsBrowse,
        val title: String,
        val body: String
    ) : AppFlow()
    data class NewsFeedManageBrowse(
        val feeds: List<com.superdl.launcher.news.NewsFeed>,
        val index: Int
    ) : AppFlow()
    data class GpsArrivalLocationPrompt(
        val destinationName: String,
        val index: Int = 0
    ) : AppFlow() {
        companion object {
            val OPTIONS = listOf(
                "Helyszín figyelő bekapcsolása",
                "Új helyszín tanítása",
                "Nem kell most"
            )
        }
    }
    object TransitAwaitStop : AppFlow()
    object TransitAwaitDestination : AppFlow()
    object NavAwaitWalkDestination : AppFlow()
    object NavAwaitPlaceQuery : AppFlow()
    data class NavPlaceBrowse(val places: List<com.superdl.launcher.navigation.NavPlace>, val index: Int) : AppFlow()
    data class TransitBrowse(
        val places: List<com.superdl.launcher.transit.TransitPlace>,
        val index: Int,
        val title: String = "Megállók",
        val radiusMode: com.superdl.launcher.transit.TransitHelper.StopRadiusMode =
            com.superdl.launcher.transit.TransitHelper.StopRadiusMode.NEAR
    ) : AppFlow()
    data class TransitContextMenu(
        val places: List<com.superdl.launcher.transit.TransitPlace>,
        val placeIndex: Int,
        val actions: List<com.superdl.launcher.transit.TransitContextAction>,
        val actionIndex: Int,
        val title: String = "Megállók",
        val radiusMode: com.superdl.launcher.transit.TransitHelper.StopRadiusMode =
            com.superdl.launcher.transit.TransitHelper.StopRadiusMode.NEAR
    ) : AppFlow()
    data class TransitRouteBrowse(
        val route: com.superdl.launcher.transit.TransitRoute,
        val index: Int
    ) : AppFlow()

    object TrainAwaitStation : AppFlow()
    data class TrainBrowse(
        val stations: List<com.superdl.launcher.train.TrainStation>,
        val index: Int,
        val title: String = "Állomások",
        val radiusMode: com.superdl.launcher.train.TrainHelper.StationRadiusMode =
            com.superdl.launcher.train.TrainHelper.StationRadiusMode.NEAR
    ) : AppFlow()
    data class TrainContextMenu(
        val stations: List<com.superdl.launcher.train.TrainStation>,
        val stationIndex: Int,
        val actions: List<com.superdl.launcher.train.TrainContextAction>,
        val actionIndex: Int,
        val title: String = "Állomások",
        val radiusMode: com.superdl.launcher.train.TrainHelper.StationRadiusMode =
            com.superdl.launcher.train.TrainHelper.StationRadiusMode.NEAR
    ) : AppFlow()

    object VoiceAssistantAwaitQuestion : AppFlow()
    object VoiceAssistantChat : AppFlow()
    object ElenaWakeTrainAwaitPhrase : AppFlow()

    object YoutubeAwaitQuery : AppFlow()
    data class YoutubeBrowse(
        val videos: List<com.superdl.launcher.youtube.YoutubeVideo>,
        val index: Int,
        val query: String = "",
        val page: Int = 0,
        val hasMore: Boolean = false
    ) : AppFlow()
    data class YoutubePlayConfirm(
        val video: com.superdl.launcher.youtube.YoutubeVideo,
        val videos: List<com.superdl.launcher.youtube.YoutubeVideo>,
        val index: Int
    ) : AppFlow()

    data class LegalBrowse(val sections: List<com.superdl.launcher.legal.LegalSection>, val index: Int) : AppFlow()

    data class BookLibraryBrowse(val books: List<com.superdl.launcher.book.BookEntry>, val index: Int) : AppFlow()
    data class BookRecentBrowse(val books: List<com.superdl.launcher.book.BookEntry>, val index: Int) : AppFlow()
    data class BookBookmarkBrowse(
        val bookmarks: List<com.superdl.launcher.book.BookBookmark>,
        val index: Int,
        val deleteMode: Boolean = false
    ) : AppFlow()
    data class BookBookmarkDeleteConfirm(
        val bookmark: com.superdl.launcher.book.BookBookmark,
        val bookmarks: List<com.superdl.launcher.book.BookBookmark>,
        val index: Int
    ) : AppFlow()
    object BookSearchAwaitQuery : AppFlow()
    data class BookReading(
        val book: com.superdl.launcher.book.BookEntry,
        val chunkIndex: Int,
        val totalChunks: Int,
        val percent: Int,
        val paused: Boolean = false
    ) : AppFlow()

    object BookLoading : AppFlow()

    data class TtsVoiceBrowse(
        val options: List<com.superdl.launcher.tts.TtsVoiceOption>,
        val index: Int
    ) : AppFlow()

    enum class FavoriteAppsMode {
        LAUNCH,
        REMOVE,
        ADD
    }

    data class FavoriteAppsBrowse(
        val favorites: List<com.superdl.launcher.apps.FavoriteAppEntry>,
        val index: Int,
        val mode: FavoriteAppsMode
    ) : AppFlow()

    data class FavoriteAppsCandidateBrowse(
        val candidates: List<com.superdl.launcher.apps.FavoriteAppCandidate>,
        val index: Int
    ) : AppFlow()

    data class SoundTrainingBrowse(
        val items: List<com.superdl.launcher.feedback.SoundType>,
        val index: Int
    ) : AppFlow()

    data class AlertSoundPresetBrowse(
        val category: com.superdl.launcher.feedback.AlertSoundCategory,
        val presets: List<com.superdl.launcher.feedback.AlertSoundPreset>,
        val index: Int
    ) : AppFlow()

    data class SoundThemeBrowse(
        val themes: List<com.superdl.launcher.feedback.SoundTheme>,
        val index: Int
    ) : AppFlow()

    data class TrainingPlayground(
        val steps: List<com.superdl.launcher.training.TrainingStep>,
        val stepIndex: Int,
        val choiceIndex: Int = 0,
        val awaitingAdvance: Boolean = false
    ) : AppFlow()

    object PatrolNightAwaitStart : AppFlow()
    object PatrolNightAwaitEnd : AppFlow()

    data class NumericDictationAwait(
        val purpose: com.superdl.launcher.input.NumberPadPurpose,
        val sosSlot: Int? = null,
        val alarmDraft: Boolean = false,
        val timerUnit: com.superdl.launcher.timer.TimerUnitOption? = null,
        val editTimerId: Int? = null,
        val calendarTitle: String? = null,
        val calendarDayStartMs: Long? = null,
        val calendarAwaitEnd: Boolean = false,
        val calendarStartHour: Int? = null,
        val calendarStartMinute: Int? = null,
        val shoppingListName: String? = null,
        val shoppingItemName: String? = null,
        val shoppingEditItemId: Int? = null,
        val shoppingEditPriceOnly: Boolean = false
    ) : AppFlow()

    data class NumberPadInput(
        val purpose: com.superdl.launcher.input.NumberPadPurpose,
        val items: List<com.superdl.launcher.input.NumberPadItem>,
        val index: Int,
        val buffer: String,
        val sosSlot: Int? = null,
        val pinMode: com.superdl.launcher.input.PinPadMode? = null,
        val setupPin: String? = null,
        val alarmDraft: Boolean = false,
        val timerUnit: com.superdl.launcher.timer.TimerUnitOption? = null,
        val editTimerId: Int? = null,
        val calendarTitle: String? = null,
        val calendarDayStartMs: Long? = null,
        val calendarAwaitEnd: Boolean = false,
        val calendarStartHour: Int? = null,
        val calendarStartMinute: Int? = null,
        val shoppingListName: String? = null,
        val shoppingItemName: String? = null,
        val shoppingEditItemId: Int? = null,
        val shoppingEditPriceOnly: Boolean = false
    ) : AppFlow()

    object CalculatorVoiceInput : AppFlow()

    data class ExternalAppBrowse(
        val apps: List<com.superdl.launcher.apps.ExternalApp>,
        val index: Int
    ) : AppFlow()

    data class TimerUnitBrowse(
        val units: List<com.superdl.launcher.timer.TimerUnitOption>,
        val index: Int,
        val editTimerId: Int? = null
    ) : AppFlow()

    data class TimerAwaitAmount(
        val unit: com.superdl.launcher.timer.TimerUnitOption,
        val editTimerId: Int? = null
    ) : AppFlow()

    data class TimerIntervalBrowse(
        val durationMinutes: Int,
        val intervals: List<Int>,
        val index: Int,
        val editTimerId: Int? = null
    ) : AppFlow()

    data class TimerAwaitLabel(
        val durationMinutes: Int,
        val announceIntervalMinutes: Int,
        val editTimerId: Int? = null
    ) : AppFlow()

    data class TimerConfirm(
        val durationMinutes: Int,
        val announceIntervalMinutes: Int,
        val label: String,
        val editTimerId: Int? = null
    ) : AppFlow()

    data class TimerListBrowse(
        val timers: List<com.superdl.launcher.timer.TimerEntry>,
        val index: Int,
        val mode: com.superdl.launcher.timer.TimerListMode
    ) : AppFlow()

    data class TimerDeleteConfirm(
        val timer: com.superdl.launcher.timer.TimerEntry,
        val timers: List<com.superdl.launcher.timer.TimerEntry>,
        val index: Int
    ) : AppFlow()

    object GpsRadarLoading : AppFlow()

    data class GpsRadarBrowse(
        val pois: List<com.superdl.launcher.gps.GpsPoi>,
        val index: Int
    ) : AppFlow()

    data class GpsRadarGuiding(
        val pois: List<com.superdl.launcher.gps.GpsPoi>,
        val index: Int
    ) : AppFlow()

    data class GpsRadarContextMenu(
        val pois: List<com.superdl.launcher.gps.GpsPoi>,
        val poiIndex: Int,
        val actions: List<com.superdl.launcher.gps.GpsRadarContextAction>,
        val actionIndex: Int,
        val fromGuiding: Boolean = false
    ) : AppFlow()

    data class GpsRadarAwaitSaveName(
        val latitude: Double,
        val longitude: Double,
        val accuracyMeters: Int? = null,
        val category: String = "egyéni",
        val returnBrowse: GpsRadarBrowse? = null,
        val returnGuiding: GpsRadarGuiding? = null,
        val returnNavWhere: NavWhereResult? = null
    ) : AppFlow()

    object NavWhereLoading : AppFlow()

    data class NavWhereResult(
        val latitude: Double,
        val longitude: Double,
        val address: String,
        val accuracyMeters: Int
    ) : AppFlow()

    data class GpsSaveRefining(
        val returnBrowse: GpsRadarBrowse? = null,
        val returnGuiding: GpsRadarGuiding? = null,
        val fromAssistant: Boolean = false
    ) : AppFlow()

    data class GpsSavedPoiBrowse(
        val saved: List<com.superdl.launcher.gps.SavedPoi>,
        val index: Int
    ) : AppFlow()

    data class SavedPoiContextMenu(
        val saved: List<com.superdl.launcher.gps.SavedPoi>,
        val poiIndex: Int,
        val actions: List<com.superdl.launcher.gps.SavedPoiContextAction>,
        val actionIndex: Int
    ) : AppFlow()

    data class SavedPoiVoiceRecording(
        val saved: List<com.superdl.launcher.gps.SavedPoi>,
        val poiIndex: Int
    ) : AppFlow()

    object DictaphoneRecording : AppFlow()

    data class DictaphoneSettingsBrowse(
        val options: List<com.superdl.launcher.dictaphone.DictaphoneSettingsOption>,
        val index: Int
    ) : AppFlow()

    data class DictaphoneFormatBrowse(
        val formats: List<com.superdl.launcher.dictaphone.DictaphoneFormat>,
        val index: Int
    ) : AppFlow()

    data class DictaphoneSampleRateBrowse(
        val rates: List<com.superdl.launcher.dictaphone.DictaphoneSampleRate>,
        val index: Int
    ) : AppFlow()

    data class DictaphoneBitrateBrowse(
        val bitrates: List<com.superdl.launcher.dictaphone.DictaphoneBitrate>,
        val index: Int
    ) : AppFlow()

    data class DictaphoneChannelsBrowse(
        val channels: List<com.superdl.launcher.dictaphone.DictaphoneChannels>,
        val index: Int
    ) : AppFlow()



    data class DictaphoneRecordingsBrowse(
        val recordings: List<com.superdl.launcher.dictaphone.DictaphoneRecordingEntry>,
        val index: Int
    ) : AppFlow()

    data class DictaphoneRecordingContextMenu(
        val recordings: List<com.superdl.launcher.dictaphone.DictaphoneRecordingEntry>,
        val recordingIndex: Int,
        val actions: List<com.superdl.launcher.dictaphone.DictaphoneRecordingContextAction>,
        val actionIndex: Int
    ) : AppFlow()

    data class DictaphoneShareEmailAwaitRecipient(
        val entry: com.superdl.launcher.dictaphone.DictaphoneRecordingEntry
    ) : AppFlow()

    data class DictaphoneShareEmailPickRecipient(
        val entry: com.superdl.launcher.dictaphone.DictaphoneRecordingEntry,
        val matches: List<com.superdl.launcher.email.EmailRecipient>,
        val index: Int
    ) : AppFlow()

    data class DictaphoneShareEmailConfirm(
        val entry: com.superdl.launcher.dictaphone.DictaphoneRecordingEntry,
        val recipient: com.superdl.launcher.email.EmailRecipient
    ) : AppFlow()

    data class DictaphoneRecordingDeleteConfirm(
        val recordings: List<com.superdl.launcher.dictaphone.DictaphoneRecordingEntry>,
        val recordingIndex: Int
    ) : AppFlow()

    object MedicationAwaitName : AppFlow()

    data class MedicationTimeOfDayBrowse(
        val name: String,
        val options: List<com.superdl.launcher.medication.MedicationTimeOfDay>,
        val selected: Set<com.superdl.launcher.medication.MedicationTimeOfDay>,
        val index: Int
    ) : AppFlow()

    object MedicationAwaitCourseDays : AppFlow()

    object MedicationSearchAwaitName : AppFlow()

    // ==================== Podcast ====================
    object PodcastLoading : AppFlow()
    object PodcastSearchAwaitQuery : AppFlow()
    data class PodcastListBrowse(
        val podcasts: List<com.superdl.launcher.podcast.Podcast>,
        val index: Int,
        val title: String
    ) : AppFlow()
    data class PodcastEpisodeBrowse(
        val podcast: com.superdl.launcher.podcast.Podcast,
        val episodes: List<com.superdl.launcher.podcast.PodcastEpisode>,
        val index: Int
    ) : AppFlow()
    data class PodcastEpisodeMenu(
        val podcast: com.superdl.launcher.podcast.Podcast,
        val episodes: List<com.superdl.launcher.podcast.PodcastEpisode>,
        val episodeIndex: Int,
        val actionIndex: Int
    ) : AppFlow()
    data class PodcastCountryBrowse(val index: Int) : AppFlow()
    object MedicationSearchLoading : AppFlow()
    data class MedicationSearchResult(
        val title: String,
        val fullText: String
    ) : AppFlow()

    data class MedicationCycleBrowse(
        val name: String,
        val hour: Int,
        val minute: Int,
        val options: List<com.superdl.launcher.medication.MedicationCycleType>,
        val index: Int
    ) : AppFlow()

    data class MedicationWeekdayBrowse(
        val name: String,
        val hour: Int,
        val minute: Int,
        val cycleType: com.superdl.launcher.medication.MedicationCycleType,
        val selectedDays: Set<Int>,
        val index: Int
    ) : AppFlow()

    data class MedicationConfirm(
        val name: String,
        val hour: Int,
        val minute: Int,
        val cycleType: com.superdl.launcher.medication.MedicationCycleType,
        val weekDays: Set<Int>
    ) : AppFlow()

    data class MedicationListBrowse(
        val reminders: List<com.superdl.launcher.medication.MedicationReminder>,
        val index: Int,
        val deleteMode: Boolean = false
    ) : AppFlow()

    data class MedicationDeleteConfirm(
        val reminder: com.superdl.launcher.medication.MedicationReminder,
        val reminders: List<com.superdl.launcher.medication.MedicationReminder>,
        val index: Int
    ) : AppFlow()

    object LauncherExitConfirm : AppFlow()

    /**
     * Beállítás varázsló: végigvezet a hiányzó engedélyeken.
     *
     * MIÉRT LISTA + INDEX: ugyanaz a minta, mint a MedicationListBrowse-nál —
     * fel-le söprés a tételek között, jobbra a megadás. A `requirements` a
     * HIÁNYZÓ tételek listája, a felmérés pillanatában.
     */
    data class SetupWizardBrowse(
        val requirements: List<com.superdl.launcher.setup.SetupRequirements.Requirement>,
        val index: Int
    ) : AppFlow()

    /**
     * A varázsló megvárja, hogy a felhasználó visszatérjen a rendszerképernyőről.
     *
     * MIÉRT KELL KÜLÖN ÁLLAPOT: a szerepkör- és rendszerbeállítás-kérések másik
     * Activity-ben futnak. Amikor visszatérünk, újra kell mérni az állapotot —
     * enélkül a varázsló azt hinné, hogy még mindig hiányzik.
     */
    data class SetupWizardAwaitReturn(
        val requirement: com.superdl.launcher.setup.SetupRequirements.Requirement
    ) : AppFlow()


    object GpsRouteRecordingActive : AppFlow()

    data class GpsRouteAwaitName(val route: com.superdl.launcher.route.GpsRouteRecording) : AppFlow()

    data class GpsRouteBrowse(
        val routes: List<com.superdl.launcher.route.GpsRouteRecording>,
        val index: Int,
        val deleteMode: Boolean = false,
        val guideMode: Boolean = false
    ) : AppFlow()

    data class GpsRouteDeleteConfirm(
        val route: com.superdl.launcher.route.GpsRouteRecording,
        val routes: List<com.superdl.launcher.route.GpsRouteRecording>,
        val index: Int
    ) : AppFlow()

    data class GpsRouteGuidingActive(val route: com.superdl.launcher.route.GpsRouteRecording) : AppFlow()

    data class LocationProfileBrowse(
        val profiles: List<com.superdl.launcher.locationwatch.LocationProfile>,
        val index: Int,
        val deleteMode: Boolean = false
    ) : AppFlow()

    data class LocationProfileActions(
        val profile: com.superdl.launcher.locationwatch.LocationProfile,
        val profiles: List<com.superdl.launcher.locationwatch.LocationProfile>,
        val profileIndex: Int,
        val actionIndex: Int = 0
    ) : AppFlow() {
        companion object {
            val OPTIONS = listOf(
                "Figyelő indítása",
                "Fotók bővítése",
                "Fotók törlése"
            )
        }
    }

    data class CardBrowse(
        val cards: List<com.superdl.launcher.cardorganizer.CardProfile>,
        val index: Int,
        val deleteMode: Boolean = false
    ) : AppFlow()

    data class CardDeleteConfirm(
        val card: com.superdl.launcher.cardorganizer.CardProfile,
        val cards: List<com.superdl.launcher.cardorganizer.CardProfile>,
        val index: Int
    ) : AppFlow()

    data class LocationProfileDeleteConfirm(
        val profile: com.superdl.launcher.locationwatch.LocationProfile,
        val profiles: List<com.superdl.launcher.locationwatch.LocationProfile>,
        val index: Int
    ) : AppFlow()

    data class CameraQualityBrowse(
        val profiles: List<com.superdl.launcher.camera.CameraQualityProfile>,
        val index: Int
    ) : AppFlow()
}