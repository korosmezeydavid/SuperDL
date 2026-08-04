package com.superdl.launcher.menu

// Menüelem típusok
enum class MenuAction {
    SUBMENU,        // Almenübe lép
    CALL_LOG,       // Hívásnapló felolvasása
    CONTACTS,       // Névjegyből hívás diktálással
    CONTACT_BOOK,   // Névjegyzék böngészése
    CONTACT_SYNC,   // Névjegyek szinkronizálása
    DIAL,           // Számtárcsázás
    SMS_READ,       // SMS olvasás
    SMS_SENT_READ,  // Kimenő SMS olvasás
    SMS_WRITE,      // SMS írás diktálással
    EMAIL_WRITE,    // E-mail diktálása és küldése
    EMAIL_IMPORT,   // E-mail címek importálása
    EMAIL_ADD,      // E-mail cím hozzáadása
    EMAIL_LIST,     // Mentett e-mail címek
    EMAIL_SMTP_SETUP,  // E-mail küldő beállítása
    EMAIL_SMTP_READ,   // E-mail küldő felolvasása
    EMAIL_SMTP_CLEAR,  // E-mail küldő törlése
    SOS,            // S.O.S. hívás
    ALARM_SET,      // Új ébresztő diktálása
    ALARM_LIST,     // Ébresztők listája
    ASSISTANT_CONTINUOUS,  // Elena: folyamatos beszélgetés (parancs után tovább hallgat)
    KEYBOARD_MATRIX_CELL,   // Mátrix: gombok távolsága (4 fokozat)
    KEYBOARD_MATRIX_SPEED,  // Mátrix: pörgetés sebessége (4 fokozat)
    KEYBOARD_MATRIX_HELP,   // Mátrix: mozdulatok felolvasása
    CATALOG_BROWSE,      // Katalógus: elérhető modulok böngészése és letöltése
    CATALOG_INSTALLED,   // Katalógus: a letöltött modulok listája
    CATALOG_UPDATE,      // Katalógus: frissítés keresése az alkalmazáshoz
    KEYBOARD_TEXT_BANK,     // Mátrix: a szövegtár tartalmának felolvasása
    KEYBOARD_PICKER,        // Billentyűzet választása (rendszer választó)
    KEYBOARD_SETTINGS,      // Billentyűzetek engedélyezése a rendszerben
    SCREEN_CURTAIN_TOGGLE,  // Sötét mód: a képernyő teljes elfüggönyözése
    SCREEN_READER_TOGGLE,   // Képernyőolvasó ki/be (csak külső appokban)
    SCREEN_READER_SETUP,    // Képernyőolvasó engedélyezése a rendszerben
    SCREEN_READER_STATUS,   // Képernyőolvasó állapota
    SCREEN_READER_HELP,     // Képernyőolvasó mozdulatainak felolvasása
    SCREEN_READER_COUNTER,  // Képernyőolvasó: pozíció bemondása ki/be
    SCREEN_READER_PHONETIC, // Képernyőolvasó: betűző ábécé ki/be
    SCREEN_READER_AUTOREAD, // Képernyőolvasó: automatikus felolvasás új képernyőn
    SCREEN_READER_PANIC,    // Képernyőolvasó AZONNALI leállítása (biztonsági retesz)
    ALARM_DELETE,   // Ébresztő törlése
    ALARM_SKIP,     // Ébresztések kihagyása (N következő alkalom kihagyása)
    ALARM_READ_NEXT,// Következő ébresztő
    TIME_NOW,       // Pontos idő
    CALENDAR_READ,  // Mai program felolvasása
    CALENDAR_TOMORROW, // Holnapi program
    CALENDAR_WEEK,  // Heti program áttekintése
    CALENDAR_ADD,   // Új program beállítása
    CALENDAR_CHOOSE_TARGET, // Melyik naptárba kerüljenek a programok
    CALENDAR_STATUS,        // Naptárak állapota (mi szinkronizál, hova írunk)
    CALENDAR_EDIT_PICK,    // Program kiválasztása szerkesztésre (napi listából)
    CALENDAR_DELETE_PICK,  // Program kiválasztása törlésre (napi listából)
    NOTE_LIST,      // Saját jegyzetek listája
    NOTE_CREATE,    // Új jegyzet diktálással
    NOTE_DELETE,    // Jegyzet törlése
    MUSIC,          // Zene a telefonon
    MUSIC_RESUME_LAST,  // Zene: az utoljára hallgatott szám folytatása a mentett pozíciótól
    USB_FILE_TRANSFER, // USB fájlátvitel be/ki (a rendszer USB-képernyőjén)
    FILE_MANAGER,      // Fájlkezelő
    WIFI_PORTAL,       // WiFi fájlportál be/ki (feltöltés gépről böngészővel)
    PODCAST_TOP,        // Podcast: népszerű műsorok (ország szerint)
    PODCAST_SEARCH,     // Podcast: keresés
    PODCAST_SUBSCRIPTIONS, // Podcast: feliratkozásaim
    PODCAST_DOWNLOADS,  // Podcast: letöltött adások
    PODCAST_COUNTRY,    // Podcast: ország választása
    PODCAST_OPML_IMPORT, // Podcast: feliratkozások importálása OPML fájlból
    PODCAST_OPML_EXPORT, // Podcast: feliratkozások exportálása OPML fájlba
    MUSIC_PLAY_MODE,   // Zene: lejátszási mód váltása
    MUSIC_SEEK_STEP,   // Zene: tekerés egység váltása
    MUSIC_EQ_PROFILE,  // Zene: hangszínprofil (EQ) váltása
    MUSIC_SPEECH_ENABLED,  // Zene: FŐKAPCSOLÓ — beszéljen-e egyáltalán lejátszás közben
    MUSIC_SPEAK_SKIP,  // Zene: beszéljen-e számváltásnál (ki/be)
    MUSIC_SPEAK_STOP,  // Zene: beszéljen-e leállításnál (ki/be)
    MUSIC_SPEAK_SEEK,  // Zene: beszéljen-e tekerésnél (ki/be)
    YOUTUBE,        // YouTube keresés + lejátszás
    RADIO_HUNGARIAN,   // Rádió: magyar állomások betöltése és lejátszás
    RADIO_FAVORITES,   // Rádió: mentett kedvenc állomások
    RADIO_SEARCH,      // Rádió: állomás keresése név szerint (hangos)
    RADIO_RECORDINGS,  // Rádió: elmentett felvételek listája
    RADIO_SCHEDULE,    // Rádió: időzített felvételek kezelése
    NEWS_READ,      // Hírek felolvasása (RSS)
    WEB_SEARCH,     // Internet kereső – felolvasott találatok
    DAY_GREETING,   // Napi üdvözlés (dátum, névnap, időjárás)
    DAY_SUMMARY,    // Napi összefoglaló
    STATUS_REPORT,  // Gyors helyzetjelentés (offline: idő, akku, térerő, hívások, üzenetek, ébresztő, naptár)
    SHOPPING_LIST,  // Bevásárlólista
    SHOPPING_NEW_LIST,  // Bevásárlólista: új lista létrehozása (diktálva)
    EMAIL_IMAP_READ, // Bejövő e-mailek olvasása
    EMAIL_DIAGNOSTICS, // E-mail kapcsolat lépésenkénti naplózása fájlba (hibakereséshez)
    BT_ASSISTANT_TOGGLE, // Bluetooth gomb → asszisztens
    TRANSIT,        // Közeli megállók felolvasása
    TRANSIT_STOP,   // Megálló keresése felolvasással
    TRANSIT_FAVORITES, // Kedvenc megállók (Holabusz-szerű)
    TRANSIT_ROUTE,  // Útvonal tömegközlekedéssel felolvasással
    TRAIN_NEARBY,        // Közeli vasútállomások indulási időkkel
    TRAIN_STATION_SEARCH, // Állomás keresése felolvasással
    TRAIN_FAVORITES,     // Kedvenc állomások indulási időkkel
    NAV_WHERE,      // Hol vagyok?
    NAV_WALK,       // Gyalogos útvonal diktálással
    NAV_SEARCH,     // Cím vagy hely keresése
    GPS_RADAR,      // GPS Kitekintő – közeli POI radar
    COMPASS_SCAN,   // Hang-iránytű - élő tájékozódás forgatással
    COMPASS_SCAN_STOP, // Hang-iránytű leállítása
    GPS_RADAR_SAVED_LIST, // Mentett helyek listája
    GPS_RADAR_SAVE_OWN,   // Saját hely mentése (GPS folyamatban)
    GPS_RADAR_SAVE_POI,   // Aktuális POI mentése (GPS folyamatban)
    NOTIFICATIONS_READ, // Értesítések olvasása
    WEATHER,        // Időjárás most
    WEATHER_CITY,   // Időjárás város szerint
    FLASHLIGHT,     // Zseblámpa
    BATTERY,        // Akkumulátor állapot
    BATTERY_PATROL_TOGGLE, // Teljes őrség ki-be
    PATROL_BATTERY_TOGGLE, // Akkumulátor figyelés ki-be
    PATROL_CALL_ALERT_TOGGLE, // Hívás értesítés ki-be
    PATROL_SMS_ALERT_TOGGLE, // Üzenet értesítés ki-be
    PATROL_NOTIFICATION_ALERT_TOGGLE, // Egyéb értesítés ki-be
    PATROL_TIME_ANNOUNCE_TOGGLE, // Idő bemondás ki-be
    PATROL_TIME_INTERVAL_CYCLE, // Idő bemondás gyakorisága
    PATROL_NIGHT_MODE_TOGGLE, // Éjszakai csend ki-be
    PATROL_NIGHT_START_SET, // Éjszakai csend kezdete
    PATROL_NIGHT_END_SET, // Éjszakai csend vége
    PATROL_POWER_BUTTON_TIME_TOGGLE, // Bekapcsoló gomb idő bemondás
    WIFI_TOGGLE,    // WiFi kapcsoló
    HOTSPOT_TOGGLE, // Hotspot kapcsoló
    BT_TOGGLE,      // Bluetooth kapcsoló
    VOICE_ASSISTANT, // Elena – hangos asszisztens (helyi parancsok)
    ELENA_WAKE_LISTEN_TOGGLE, // Elena figyelő ki-be
    ELENA_WAKE_LISTEN_ON, // Elena figyelő bekapcsolása
    ELENA_WAKE_LISTEN_OFF, // Elena figyelő kikapcsolása
    ELENA_WAKE_TRAIN, // Saját felébresztő mondat tanítása
    ELENA_WAKE_CUSTOM_LIST, // Mentett felébresztő mondatok felolvasása
    ASSISTANT_DEFAULT_SETUP, // Alapértelmezett digitális asszisztens beállítása
    ASSISTANT_DEFAULT_STATUS, // Alapértelmezett asszisztens állapota
    DIALER_DEFAULT_SETUP, // Alapértelmezett telefon alkalmazás beállítása
    DIALER_DEFAULT_STATUS, // Alapértelmezett telefon alkalmazás állapota
    QR_SCAN,        // QR kód olvasó
    LIGHT_DETECTOR, // Fénydetektor kamerával
    COLOR_DETECTOR, // Színfelismerő kamerával
    ENV_SCANNER,    // Környezeti Kitekintő – kamera objektumfelismerés
    ENV_SNAPSHOT,   // Mi van előttem? - egy-gombos jelenetleírás
    CURRENCY_RECOGNIZER, // Super DL Pénzfelismerő – offline forint bankjegy
    MEDICATION_READER,   // Gyógyszerdoboz olvasó – kamera OCR
    LABEL_READER,        // Címke olvasó – kamera OCR
    TEXT_READER,         // Szöveg olvasó – általános kamera OCR
    CONTINUOUS_OCR,      // Folyamatos OCR – automatikus szövegváltozás-felismerés
    SOUND_TRAINING, // Program hangjainak megismerése
    SETUP_WIZARD,   // Beállítás varázsló – végigvezet a hiányzó engedélyeken
    SETUP_STATUS,   // Beállítás állapot felolvasása
    DIAGNOSTICS,    // Diagnosztika – mi nem működik és miért
    BATTERY_OPT_REQUEST, // Korlátlan háttérfutás kérése (akku-optimalizálás alól)
    AUTOSTART_SETUP,     // Gyártói automatikus indítás (Xiaomi, Huawei, Oppo...)
    TRAINING_PLAYGROUND, // Tanuló mód – funkciók bemutatása
    BOOK_LIBRARY,   // Könyvtár – telefonon lévő könyvek
    BOOK_SEARCH,    // Könyv keresése felolvasással
    BOOK_RECENT,    // Nem rég olvasott könyvek
    BOOK_BOOKMARKS, // Mentett könyvjelzők
    BOOK_BOOKMARK_DELETE, // Könyvjelző törlése
    BOOK_RESUME,    // Utoljára olvasott könyv folytatása
    BOOK_FOLDER_SET,   // Egyéni könyvmappa beállítása
    BOOK_FOLDER_READ,  // Egyéni könyvmappa felolvasása
    BOOK_FOLDER_CLEAR, // Egyéni könyvmappák törlése
    CALCULATOR,     // Számológép diktálással
    VOLUME_UP,      // Hangerő fel
    VOLUME_DOWN,    // Hangerő le
    TTS_SPEED_UP,   // TTS gyorsabb
    TTS_SPEED_DOWN, // TTS lassabb
    TTS_ENGINE_SELECT, // TTS motor választása
    TTS_ENGINE_READ,   // Aktuális TTS motor felolvasása
    EXIT_LAUNCHER,  // Kilépés a launcherből
    SOS_SET_1,      // S.O.S. szám 1 beállítása
    SOS_SET_2,      // S.O.S. szám 2 beállítása
    SOS_SET_3,      // S.O.S. szám 3 beállítása
    SOS_SET_4,      // S.O.S. szám 4 beállítása
    SOS_READ_ALL,   // S.O.S. számok felolvasása
    ABOUT_APP,      // Az alkalmazásról
    ABOUT_DEVELOPER,// Fejlesztő
    CONTACT_EMAIL,  // Fejlesztői e-mail
    PRIVACY_POLICY, // Adatvédelmi tájékoztató
    TERMS_OF_USE,   // Felhasználási feltételek
    LEGAL_NOTICE,   // Jogi nyilatkozat
    EXTERNAL_APPS,  // Külső alkalmazások listája
    FAVORITE_APPS_LAUNCH, // Kedvenc alkalmazás indítása
    FAVORITE_APPS_ADD,    // Kedvenc alkalmazás hozzáadása
    FAVORITE_APPS_REMOVE, // Kedvenc alkalmazás törlése
    LOCK_PIN_TOGGLE, // PIN zárolás ki-be
    LOCK_PIN_SET,    // PIN kód beállítása / módosítása
    LOCK_PIN_STATUS, // PIN zárolás állapota
    KEYGUARD_PIN_ASSIST_TOGGLE, // Rendszer PIN segéd ki-be
    KEYGUARD_PIN_ASSIST_SETUP,  // Rendszer PIN segéd engedélyezése
    KEYGUARD_PIN_ASSIST_STATUS, // Rendszer PIN segéd állapota
    TIMER_CREATE,    // Új időzítő mentése
    TIMER_LIST,      // Időzítők listája
    TIMER_START,     // Időzítő indítása
    TIMER_STOP,      // Aktív időzítő leállítása
    TIMER_EDIT,      // Időzítő módosítása
    TIMER_DELETE,    // Időzítő törlése
    DICTAPHONE_RECORD,   // Profi diktafon felvétel
    DICTAPHONE_SETTINGS, // Profi diktafon minőség beállítás
    DICTAPHONE_RAW_TOGGLE, // Profi diktafon: teljesen nyers felvétel ki/be
    DICTAPHONE_CAPABILITIES, // Profi diktafon: mit tud a készülék mikrofonja
    DICTAPHONE_LIBRARY,  // Mentett felvételek
    FAVORITES_ADD,       // Kedvenc hozzáadása
    FAVORITES_CALL,      // Kedvenc hívása
    FAVORITES_DELETE,    // Kedvenc törlése
    SMS_DEFAULT_SETUP,   // Alapértelmezett üzenet app beállítása
    SMS_DEFAULT_STATUS,  // Alapértelmezett üzenet app állapota
    CONTACT_CREATE,      // Új névjegy létrehozása
    CALL_FILTER_BLOCK_PRIVATE_TOGGLE, // Régi – kompatibilitás
    CALL_FILTER_MODE_CYCLE,          // Hívás szűrő mód váltása (4 szint)
    CALL_FILTER_MODE_STATUS,         // Hívás szűrő állapota
    MEDICATION_READ,     // Patika Őrangyal – emlékeztetők felolvasása
    MEDICATION_ADD,      // Patika Őrangyal – új gyógyszer rögzítése
    MEDICATION_SEARCH,   // Gyógyszerkereső - tájékoztató lekérése névből
    MEDICATION_DELETE,   // Patika Őrangyal – emlékeztető törlése
    ALERT_SOUND_CALENDAR,      // Program emlékeztető hang
    ALERT_SOUND_MEDICATION,    // Gyógyszer emlékeztető hang
    ALERT_SOUND_ALARM,         // Ébresztő hang
    ALERT_SOUND_SMS,           // SMS hang
    ALERT_SOUND_EMAIL,         // E-mail hang
    ALERT_SOUND_NOTIFICATION,  // Egyéb értesítés hang
    ALERT_SOUND_VOLUME_CYCLE,  // Csengőhang hangerő
    ALERT_SILENT_MODE_TOGGLE,  // Néma mód ki-be
    SOUND_THEME_SELECT,        // Söpörj hangtéma választás
    RINGTONE_SELECT,           // Gyári csengőhang választása a híváshoz
    LOCATION_TRAIN,            // Helyszín profil tanítása
    LOCATION_WATCH_START,      // Helyszín figyelő – mentett profilok
    LOCATION_WATCH_TEXT,       // Helyszín figyelő – szabad szöveg
    LOCATION_PROFILE_LIST,     // Mentett helyszín profilok listája
    LOCATION_WATCH_STOP,       // Helyszín figyelő leállítása
    FACE_CAMERA,               // Arc kamera – hátlapi
    FACE_CAMERA_SELFIE,        // Arc kamera – szelfi
    FACE_CAMERA_QUALITY,       // Kamera minőség beállítás
    GPS_ROUTE_RECORD,          // GPS útvonal rögzítése
    GPS_ROUTE_STOP,            // GPS útvonal rögzítés / útmutatás leállítása
    GPS_ROUTE_LIST,            // Mentett GPS útvonalak listája
    GPS_ROUTE_GUIDE,           // GPS útvonal útmutatás
    GPS_ROUTE_DELETE,          // GPS útvonal törlése
    CARD_TRAIN,                // Kártya hozzáadása (eleje + hátulja)
    CARD_RECOGNIZE,            // Kártya felismerése kamerával
    CARD_LIST,                 // Mentett kártyák listája
    CARD_DELETE,               // Kártya törlése
    NEWS_FEED_MANAGE,          // Hírforrások kezelése
    NEWS_FEED_IMPORT_OPML,     // Hírforrások OPML import
    HEARING_AID,               // Hallás erősítő – valós idejű hang
    GAME_UNO,                  // UNO kártyajáték
    GAME_BLACKJACK,            // Blackjack
    GAME_POKER,                // Póker – ötlapos húzás
    GAME_SLOT,                 // Félkarú rabló – nyerőgép
    GAME_MILLE_BORNES,         // Mille Bornes – ezer mérföld
}

data class MenuItem(
    val id: String,
    val label: String,          // Magyar TTS szöveg
    val action: MenuAction,
    val children: List<MenuItem> = emptyList()
)

object MenuTree {

    val root: List<MenuItem> = listOf(

        // A SÖTÉT MÓD a lista ELEJÉN: egy söpréssel elérhető, mert gyakran és
        // gyorsan kell (magánszféra, akkumulátor-kímélés).
        MenuItem("screen_curtain", "Sötét mód", MenuAction.SCREEN_CURTAIN_TOGGLE),

        MenuItem("calls", "Telefon és Hívások", MenuAction.SUBMENU, listOf(
            MenuItem("call_contacts", "Névjegyből hívás", MenuAction.CONTACTS),
            MenuItem("contact_book", "Névjegyzék", MenuAction.CONTACT_BOOK),
            MenuItem("contact_sync", "Névjegyek szinkronizálása", MenuAction.CONTACT_SYNC),
            MenuItem("call_log", "Hívásnapló felolvasása", MenuAction.CALL_LOG),
            MenuItem("call_dial", "Szám tárcsázása", MenuAction.DIAL),
            MenuItem("fav_add", "Kedvenc hozzáadása", MenuAction.FAVORITES_ADD),
            MenuItem("fav_call", "Kedvenc hívása", MenuAction.FAVORITES_CALL),
            MenuItem("fav_delete", "Kedvenc törlése", MenuAction.FAVORITES_DELETE),
            MenuItem("contact_create", "Új névjegy létrehozása", MenuAction.CONTACT_CREATE),
            MenuItem("call_back", "Vissza a főmenübe", MenuAction.SUBMENU)
        )),

        MenuItem("sms", "Üzenetek és E-mail", MenuAction.SUBMENU, listOf(
            MenuItem("sms_sub", "SMS üzenetek", MenuAction.SUBMENU, listOf(
                MenuItem("sms_read", "Bejövő üzenetek olvasása", MenuAction.SMS_READ),
                MenuItem("sms_sent_read", "Kimenő üzenetek", MenuAction.SMS_SENT_READ),
                MenuItem("sms_write", "Üzenet diktálása és küldése", MenuAction.SMS_WRITE),
                MenuItem("sms_settings_sub", "SMS beállítások", MenuAction.SUBMENU, listOf(
                    MenuItem("sms_default_setup", "Alapértelmezett üzenet app beállítása", MenuAction.SMS_DEFAULT_SETUP),
                    MenuItem("sms_default_status", "Üzenet app állapota", MenuAction.SMS_DEFAULT_STATUS),
                    MenuItem("sms_settings_back", "Vissza", MenuAction.SUBMENU)
                )),
                MenuItem("sms_sub_back", "Vissza", MenuAction.SUBMENU)
            )),
            MenuItem("email_sub", "E-mail", MenuAction.SUBMENU, listOf(
                MenuItem("email_imap_read", "E-mailek olvasása", MenuAction.EMAIL_IMAP_READ),
                MenuItem("email_write", "E-mail diktálása és küldése", MenuAction.EMAIL_WRITE),
                MenuItem("email_contacts_sub", "E-mail címjegyzék", MenuAction.SUBMENU, listOf(
                    MenuItem("email_list", "Mentett e-mail címek", MenuAction.EMAIL_LIST),
                    MenuItem("email_add", "E-mail cím hozzáadása", MenuAction.EMAIL_ADD),
                    MenuItem("email_import", "E-mail címek importálása", MenuAction.EMAIL_IMPORT),
                    MenuItem("email_contacts_back", "Vissza", MenuAction.SUBMENU)
                )),
                MenuItem("email_account_sub", "E-mail fiók beállítása", MenuAction.SUBMENU, listOf(
                    MenuItem("email_smtp_setup", "Fiók beállítása", MenuAction.EMAIL_SMTP_SETUP),
                    MenuItem("email_smtp_read", "Beállítás felolvasása", MenuAction.EMAIL_SMTP_READ),
                    MenuItem("email_diag", "E-mail kapcsolat naplózása", MenuAction.EMAIL_DIAGNOSTICS),
                    MenuItem("email_smtp_clear", "Beállítás törlése", MenuAction.EMAIL_SMTP_CLEAR),
                    MenuItem("email_account_back", "Vissza", MenuAction.SUBMENU)
                )),
                MenuItem("email_sub_back", "Vissza", MenuAction.SUBMENU)
            )),
            MenuItem("sms_back", "Vissza a főmenübe", MenuAction.SUBMENU)
        )),

        MenuItem("sos", "S.O.S. Vészjelzés", MenuAction.SOS),

        MenuItem("time", "Idő és Szervezés", MenuAction.SUBMENU, listOf(
            MenuItem("clock_sub", "Óra és ébresztés", MenuAction.SUBMENU, listOf(
                MenuItem("time_now", "Pontos idő felolvasása", MenuAction.TIME_NOW),
                MenuItem("alarm_set", "Új ébresztő beállítása", MenuAction.ALARM_SET),
                MenuItem("alarm_next", "Következő ébresztő", MenuAction.ALARM_READ_NEXT),
                MenuItem("alarm_list", "Ébresztők listája", MenuAction.ALARM_LIST),
                MenuItem("alarm_delete", "Ébresztő törlése", MenuAction.ALARM_DELETE),
                MenuItem("alarm_skip", "Ébresztések kihagyása", MenuAction.ALARM_SKIP),
                MenuItem("timer_create", "Új időzítő mentése", MenuAction.TIMER_CREATE),
                MenuItem("timer_list", "Időzítők listája", MenuAction.TIMER_LIST),
                MenuItem("timer_start", "Időzítő indítása", MenuAction.TIMER_START),
                MenuItem("timer_stop", "Aktív időzítő leállítása", MenuAction.TIMER_STOP),
                MenuItem("timer_edit", "Időzítő módosítása", MenuAction.TIMER_EDIT),
                MenuItem("timer_delete", "Időzítő törlése", MenuAction.TIMER_DELETE),
                MenuItem("clock_back", "Vissza", MenuAction.SUBMENU)
            )),
            MenuItem("program_sub", "Program (naptár)", MenuAction.SUBMENU, listOf(
                MenuItem("calendar_add", "Program létrehozása", MenuAction.CALENDAR_ADD),
                MenuItem("calendar_edit", "Program szerkesztése", MenuAction.CALENDAR_EDIT_PICK),
                MenuItem("calendar_delete", "Program törlése", MenuAction.CALENDAR_DELETE_PICK),
                MenuItem("calendar_read", "Program napi áttekintő", MenuAction.CALENDAR_READ),
                MenuItem("calendar_tomorrow", "Program holnapi áttekintő", MenuAction.CALENDAR_TOMORROW),
                MenuItem("calendar_week", "Program heti áttekintő", MenuAction.CALENDAR_WEEK),
                MenuItem("calendar_target", "Melyik naptárba írjunk", MenuAction.CALENDAR_CHOOSE_TARGET),
                MenuItem("calendar_status", "Naptárak állapota", MenuAction.CALENDAR_STATUS),
                MenuItem("program_back", "Vissza", MenuAction.SUBMENU)
            )),
            MenuItem("notes_sub", "Jegyzetek", MenuAction.SUBMENU, listOf(
                MenuItem("note_list", "Saját jegyzetek", MenuAction.NOTE_LIST),
                MenuItem("note_create", "Új jegyzet", MenuAction.NOTE_CREATE),
                MenuItem("note_delete", "Jegyzet törlése", MenuAction.NOTE_DELETE),
                MenuItem("notes_back", "Vissza", MenuAction.SUBMENU)
            )),
            MenuItem("time_back", "Vissza a főmenübe", MenuAction.SUBMENU)
        )),

        MenuItem("media", "Zene és Média", MenuAction.SUBMENU, listOf(
            MenuItem("music_resume", "Utoljára játszott folytatása", MenuAction.MUSIC_RESUME_LAST),
            MenuItem("music", "Zene a telefonon", MenuAction.MUSIC),
            MenuItem("usb_transfer", "Fájlátvitel géppel", MenuAction.USB_FILE_TRANSFER),
            MenuItem("wifi_portal", "WiFi fájlportál be és ki", MenuAction.WIFI_PORTAL),
            MenuItem("podcast", "Podcast", MenuAction.SUBMENU, listOf(
                MenuItem("podcast_top", "Népszerű podcastok", MenuAction.PODCAST_TOP),
                MenuItem("podcast_search", "Podcast keresése", MenuAction.PODCAST_SEARCH),
                MenuItem("podcast_subs", "Feliratkozásaim", MenuAction.PODCAST_SUBSCRIPTIONS),
                MenuItem("podcast_downloads", "Letöltéseim", MenuAction.PODCAST_DOWNLOADS),
                MenuItem("podcast_country", "Ország választása", MenuAction.PODCAST_COUNTRY),
                MenuItem("podcast_opml_import", "Feliratkozások importálása fájlból", MenuAction.PODCAST_OPML_IMPORT),
                MenuItem("podcast_opml_export", "Feliratkozások mentése fájlba", MenuAction.PODCAST_OPML_EXPORT),
            )),
            MenuItem("music_settings", "Zene beállítások", MenuAction.SUBMENU, listOf(
                MenuItem("music_play_mode", "Lejátszási mód", MenuAction.MUSIC_PLAY_MODE),
                MenuItem("music_seek_step", "Tekerés egység", MenuAction.MUSIC_SEEK_STEP),
                MenuItem("music_eq", "Hangszínprofil", MenuAction.MUSIC_EQ_PROFILE),
                MenuItem("music_speech", "Beszéd-visszajelzés", MenuAction.SUBMENU, listOf(
                    MenuItem("music_speech_master", "Beszéd a lejátszás alatt", MenuAction.MUSIC_SPEECH_ENABLED),
                    MenuItem("music_speak_skip", "Számváltásnál beszéljen", MenuAction.MUSIC_SPEAK_SKIP),
                    MenuItem("music_speak_stop", "Leállításnál beszéljen", MenuAction.MUSIC_SPEAK_STOP),
                    MenuItem("music_speak_seek", "Tekerésnél beszéljen", MenuAction.MUSIC_SPEAK_SEEK),
                )),
            )),
            MenuItem("youtube", "YouTube hangos keresés", MenuAction.YOUTUBE),
            MenuItem("radio", "Internetes rádió", MenuAction.SUBMENU, listOf(
                MenuItem("radio_hungarian", "Magyar állomások", MenuAction.RADIO_HUNGARIAN),
                MenuItem("radio_favorites", "Kedvenc állomásaim", MenuAction.RADIO_FAVORITES),
                MenuItem("radio_search", "Állomás keresése", MenuAction.RADIO_SEARCH),
                MenuItem("radio_recordings", "Felvételeim", MenuAction.RADIO_RECORDINGS),
                MenuItem("radio_schedule", "Időzített felvételek", MenuAction.RADIO_SCHEDULE),
            )),
            MenuItem("media_back", "Vissza a főmenübe", MenuAction.SUBMENU)
        )),

        MenuItem("games", "Játékok", MenuAction.SUBMENU, listOf(
            MenuItem("game_uno", "UNO kártyajáték", MenuAction.GAME_UNO),
            MenuItem("game_blackjack", "Blackjack", MenuAction.GAME_BLACKJACK),
            MenuItem("game_poker", "Póker ötlapos húzás", MenuAction.GAME_POKER),
            MenuItem("game_slot", "Félkarú rabló", MenuAction.GAME_SLOT),
            MenuItem("game_mille_bornes", "Mille Bornes", MenuAction.GAME_MILLE_BORNES),
            MenuItem("games_back", "Vissza a főmenübe", MenuAction.SUBMENU)
        )),

        MenuItem("books", "Könyvek", MenuAction.SUBMENU, listOf(
            MenuItem("book_library", "Könyvtár", MenuAction.BOOK_LIBRARY),
            MenuItem("book_search", "Könyv keresése felolvasással", MenuAction.BOOK_SEARCH),
            MenuItem("book_recent", "Nem rég olvasott könyvek", MenuAction.BOOK_RECENT),
            MenuItem("book_bookmarks", "Könyvjelzők", MenuAction.BOOK_BOOKMARKS),
            MenuItem("book_bookmark_delete", "Könyvjelző törlése", MenuAction.BOOK_BOOKMARK_DELETE),
            MenuItem("book_resume", "Olvasás folytatása", MenuAction.BOOK_RESUME),
            MenuItem("book_folder_set", "Könyvmappa beállítása", MenuAction.BOOK_FOLDER_SET),
            MenuItem("book_folder_read", "Könyvmappa felolvasása", MenuAction.BOOK_FOLDER_READ),
            MenuItem("book_folder_clear", "Könyvmappa törlése", MenuAction.BOOK_FOLDER_CLEAR),
            MenuItem("books_back", "Vissza a főmenübe", MenuAction.SUBMENU)
        )),

        MenuItem("info", "Információ", MenuAction.SUBMENU, listOf(
            MenuItem("day_greeting", "Napi üdvözlés", MenuAction.DAY_GREETING),
            MenuItem("day_summary", "Napi összefoglaló", MenuAction.DAY_SUMMARY),
            MenuItem("weather", "Időjárás most", MenuAction.WEATHER),
            MenuItem("weather_city", "Időjárás város szerint", MenuAction.WEATHER_CITY),
            MenuItem("news_read", "Hírek felolvasása", MenuAction.NEWS_READ),
            MenuItem("news_feed_manage", "Hírforrások kezelése", MenuAction.NEWS_FEED_MANAGE),
            MenuItem("news_feed_opml", "Hírforrások OPML import", MenuAction.NEWS_FEED_IMPORT_OPML),
            MenuItem("web_search", "Internet kereső", MenuAction.WEB_SEARCH),
            MenuItem("battery", "Akkumulátor állapot", MenuAction.BATTERY),
            MenuItem("info_back", "Vissza a főmenübe", MenuAction.SUBMENU)
        )),

        MenuItem("community", "Közlekedés", MenuAction.SUBMENU, listOf(
            MenuItem("nav_where", "Hol vagyok?", MenuAction.NAV_WHERE),
            MenuItem("nav_walk", "Gyalogos útvonal diktálással", MenuAction.NAV_WALK),
            MenuItem("nav_search", "Cím vagy hely keresése", MenuAction.NAV_SEARCH),
            MenuItem("gps_radar", "G P S Kitekintő", MenuAction.SUBMENU, listOf(
                MenuItem("gps_radar_nearby", "Közeli helyek", MenuAction.GPS_RADAR),
                MenuItem("compass_scan", "Hang-iránytű", MenuAction.COMPASS_SCAN),
                MenuItem("compass_scan_stop", "Hang-iránytű leállítása", MenuAction.COMPASS_SCAN_STOP),
                MenuItem("gps_radar_custom", "Egyéni helyek", MenuAction.GPS_RADAR_SAVED_LIST),
                MenuItem("gps_radar_back", "Vissza a közlekedéshez", MenuAction.SUBMENU)
            )),
            MenuItem("location_watch", "Helyszín felismerő", MenuAction.SUBMENU, listOf(
                MenuItem("location_train", "Helyszín tanítása", MenuAction.LOCATION_TRAIN),
                MenuItem("location_watch_start", "Figyelő indítása", MenuAction.LOCATION_WATCH_START),
                MenuItem("location_watch_text", "Figyelő szabad szöveggel", MenuAction.LOCATION_WATCH_TEXT),
                MenuItem("location_profile_list", "Mentett helyszínek", MenuAction.LOCATION_PROFILE_LIST),
                MenuItem("location_watch_stop", "Figyelő leállítása", MenuAction.LOCATION_WATCH_STOP),
                MenuItem("location_watch_back", "Vissza a közlekedéshez", MenuAction.SUBMENU)
            )),
            MenuItem("env_snapshot", "Mi van előttem? Környezeti kitekintő", MenuAction.ENV_SNAPSHOT),
            MenuItem("transit_nearby", "Közeli megállók felolvasása", MenuAction.TRANSIT),
            MenuItem("transit_stop", "Megálló keresése felolvasással", MenuAction.TRANSIT_STOP),
            MenuItem("transit_favorites", "Kedvenc megállók indulási időkkel", MenuAction.TRANSIT_FAVORITES),
            MenuItem("transit_route", "Útvonal tömegközlekedéssel felolvasással", MenuAction.TRANSIT_ROUTE),
            MenuItem("train", "Vonat", MenuAction.SUBMENU, listOf(
                MenuItem("train_nearby", "Közeli állomások indulási időkkel", MenuAction.TRAIN_NEARBY),
                MenuItem("train_station", "Állomás keresése felolvasással", MenuAction.TRAIN_STATION_SEARCH),
                MenuItem("train_favorites", "Kedvenc állomások indulási időkkel", MenuAction.TRAIN_FAVORITES),
                MenuItem("train_back", "Vissza a közlekedéshez", MenuAction.SUBMENU)
            )),
            MenuItem("gps_route", "G P S útvonal", MenuAction.SUBMENU, listOf(
                MenuItem("gps_route_record", "Útvonal rögzítése", MenuAction.GPS_ROUTE_RECORD),
                MenuItem("gps_route_stop", "Rögzítés vagy útmutatás leállítása", MenuAction.GPS_ROUTE_STOP),
                MenuItem("gps_route_list", "Mentett útvonalak", MenuAction.GPS_ROUTE_LIST),
                MenuItem("gps_route_guide", "Útvonal útmutatás", MenuAction.GPS_ROUTE_GUIDE),
                MenuItem("gps_route_delete", "Útvonal törlése", MenuAction.GPS_ROUTE_DELETE),
                MenuItem("gps_route_back", "Vissza a közlekedéshez", MenuAction.SUBMENU)
            )),
            MenuItem("community_back", "Vissza a főmenübe", MenuAction.SUBMENU)
        )),

        MenuItem("tools", "Eszközök", MenuAction.SUBMENU, listOf(
            MenuItem("file_manager", "Fájlkezelő", MenuAction.FILE_MANAGER),
            MenuItem("flashlight", "Zseblámpa", MenuAction.FLASHLIGHT),
            MenuItem("tools_readers", "Olvasók", MenuAction.SUBMENU, listOf(
                MenuItem("qr", "Q R kód olvasó", MenuAction.QR_SCAN),
                MenuItem("medication_reader", "Gyógyszerdoboz olvasó", MenuAction.MEDICATION_READER),
                MenuItem("label_reader", "Címke olvasó", MenuAction.LABEL_READER),
                MenuItem("text_reader", "Szöveg olvasó", MenuAction.TEXT_READER),
                MenuItem("continuous_ocr", "Folyamatos szövegolvasó", MenuAction.CONTINUOUS_OCR),
                MenuItem("tools_readers_back", "Vissza az eszközökhöz", MenuAction.SUBMENU)
            )),
            MenuItem("tools_recognizers", "Felismerők", MenuAction.SUBMENU, listOf(
                MenuItem("light_detector", "Fénydetektor kamerával", MenuAction.LIGHT_DETECTOR),
                MenuItem("color_detector", "Színfelismerő kamerával", MenuAction.COLOR_DETECTOR),
                MenuItem("env_snapshot_tools", "Mi van előttem? Környezeti kitekintő", MenuAction.ENV_SNAPSHOT),
                MenuItem("currency_recognizer", "Super DL Pénzfelismerő", MenuAction.CURRENCY_RECOGNIZER),
                MenuItem("card_organizer", "Kártya rendszerező", MenuAction.SUBMENU, listOf(
                    MenuItem("card_train", "Új kártya hozzáadása", MenuAction.CARD_TRAIN),
                    MenuItem("card_recognize", "Kártya felismerése", MenuAction.CARD_RECOGNIZE),
                    MenuItem("card_list", "Mentett kártyák", MenuAction.CARD_LIST),
                    MenuItem("card_delete", "Kártya törlése", MenuAction.CARD_DELETE),
                    MenuItem("card_back", "Vissza a felismerőkhöz", MenuAction.SUBMENU)
                )),
                MenuItem("tools_recognizers_back", "Vissza az eszközökhöz", MenuAction.SUBMENU)
            )),
            MenuItem("tools_camera", "Kamera", MenuAction.SUBMENU, listOf(
                MenuItem("face_camera", "Kamera és szelfi", MenuAction.FACE_CAMERA),
                MenuItem("face_camera_quality", "Kamera minőség", MenuAction.FACE_CAMERA_QUALITY),
                MenuItem("tools_camera_back", "Vissza az eszközökhöz", MenuAction.SUBMENU)
            )),
            MenuItem("tools_daily", "Mindennapi", MenuAction.SUBMENU, listOf(
                MenuItem("hearing_aid", "Hallás erősítő", MenuAction.HEARING_AID),
                MenuItem("calculator", "Számológép", MenuAction.CALCULATOR),
                MenuItem("shopping", "Bevásárlólista", MenuAction.SUBMENU, listOf(
                    MenuItem("shopping_open", "Listáim megnyitása", MenuAction.SHOPPING_LIST),
                    MenuItem("shopping_new", "Új lista létrehozása", MenuAction.SHOPPING_NEW_LIST),
                    MenuItem("shopping_back", "Vissza", MenuAction.SUBMENU)
                )),
                MenuItem("dictaphone", "Profi Diktafon", MenuAction.SUBMENU, listOf(
                    MenuItem("dict_record", "Felvétel indítása", MenuAction.DICTAPHONE_RECORD),
                    MenuItem("dict_settings", "Minőség és formátum beállítása", MenuAction.DICTAPHONE_SETTINGS),
                    MenuItem("dict_raw", "Teljesen nyers felvétel", MenuAction.DICTAPHONE_RAW_TOGGLE),
                    MenuItem("dict_caps", "Mit tud a mikrofonom", MenuAction.DICTAPHONE_CAPABILITIES),
                    MenuItem("dict_library", "Mentett felvételek", MenuAction.DICTAPHONE_LIBRARY),
                    MenuItem("dict_back", "Vissza a mindennapihoz", MenuAction.SUBMENU)
                )),
                MenuItem("pharmacy_guardian", "Patika Őrangyal", MenuAction.SUBMENU, listOf(
                    MenuItem("med_read", "Aktuális emlékeztetők felolvasása", MenuAction.MEDICATION_READ),
                    MenuItem("med_add", "Új gyógyszer rögzítése", MenuAction.MEDICATION_ADD),
                    MenuItem("med_search", "Gyógyszerkereső", MenuAction.MEDICATION_SEARCH),
                    MenuItem("med_delete", "Emlékeztető törlése", MenuAction.MEDICATION_DELETE),
                    MenuItem("pharmacy_back", "Vissza a mindennapihoz", MenuAction.SUBMENU)
                )),
                MenuItem("tools_daily_back", "Vissza az eszközökhöz", MenuAction.SUBMENU)
            )),
            MenuItem("tools_back", "Vissza a főmenübe", MenuAction.SUBMENU)
        )),

        MenuItem("assistant", "Asszisztens", MenuAction.SUBMENU, listOf(
            MenuItem("voice_assistant", "Elena", MenuAction.VOICE_ASSISTANT),
            MenuItem("elena_wake_listen", "Elena figyelő", MenuAction.ELENA_WAKE_LISTEN_TOGGLE),
            MenuItem("assistant_continuous", "Folyamatos beszélgetés", MenuAction.ASSISTANT_CONTINUOUS),
            MenuItem("elena_wake_train", "Elena felébresztő tanítása", MenuAction.ELENA_WAKE_TRAIN),
            MenuItem("elena_wake_custom_list", "Saját felébresztő mondatok", MenuAction.ELENA_WAKE_CUSTOM_LIST),
            MenuItem("assistant_default_setup", "Alapértelmezett asszisztens beállítása", MenuAction.ASSISTANT_DEFAULT_SETUP),
            MenuItem("assistant_default_status", "Asszisztens állapota", MenuAction.ASSISTANT_DEFAULT_STATUS),
            MenuItem("bt_assistant", "Bluetooth gomb asszisztens", MenuAction.BT_ASSISTANT_TOGGLE),
            MenuItem("assistant_back", "Vissza a főmenübe", MenuAction.SUBMENU)
        )),

        MenuItem("external_apps", "Minden alkalmazás", MenuAction.EXTERNAL_APPS),

        MenuItem("favorite_apps", "Kedvenc alkalmazások", MenuAction.SUBMENU, listOf(
            MenuItem("fav_apps_launch", "Kedvenc alkalmazás indítása", MenuAction.FAVORITE_APPS_LAUNCH),
            MenuItem("fav_apps_add", "Kedvenc alkalmazás hozzáadása", MenuAction.FAVORITE_APPS_ADD),
            MenuItem("fav_apps_remove", "Kedvenc alkalmazás törlése", MenuAction.FAVORITE_APPS_REMOVE),
            MenuItem("fav_apps_back", "Vissza a főmenübe", MenuAction.SUBMENU)
        )),

        MenuItem("settings", "Beállítások", MenuAction.SUBMENU, listOf(
            MenuItem("catalog", "Katalógus", MenuAction.SUBMENU, listOf(
                MenuItem("catalog_browse", "Elérhető modulok", MenuAction.CATALOG_BROWSE),
                MenuItem("catalog_installed", "Letöltött modulok", MenuAction.CATALOG_INSTALLED),
                MenuItem("catalog_update", "Frissítés keresése", MenuAction.CATALOG_UPDATE),
                MenuItem("catalog_back", "Vissza", MenuAction.SUBMENU)
            )),
            MenuItem("advanced", "Haladó és technikai", MenuAction.SUBMENU, listOf(
                MenuItem("screen_reader", "Képernyőolvasó és billentyűzet", MenuAction.SUBMENU, listOf(
                    MenuItem("sr_toggle", "Képernyőolvasó ki és be", MenuAction.SCREEN_READER_TOGGLE),
                    MenuItem("sr_setup", "Engedélyezés a rendszerben", MenuAction.SCREEN_READER_SETUP),
                    MenuItem("sr_status", "Állapot", MenuAction.SCREEN_READER_STATUS),
                    MenuItem("sr_help", "Mozdulatok felolvasása", MenuAction.SCREEN_READER_HELP),
                    MenuItem("sr_counter", "Pozíció bemondása", MenuAction.SCREEN_READER_COUNTER),
                    MenuItem("sr_phonetic", "Betűző ábécé", MenuAction.SCREEN_READER_PHONETIC),
                    MenuItem("sr_autoread", "Automatikus felolvasás", MenuAction.SCREEN_READER_AUTOREAD),
                    MenuItem("kb_picker", "Billentyűzet választása", MenuAction.KEYBOARD_PICKER),
                    MenuItem("kb_settings", "Billentyűzetek engedélyezése", MenuAction.KEYBOARD_SETTINGS),
                    MenuItem("kb_matrix_cell", "Mátrix: gombok távolsága", MenuAction.KEYBOARD_MATRIX_CELL),
                    MenuItem("kb_matrix_speed", "Mátrix: pörgetés sebessége", MenuAction.KEYBOARD_MATRIX_SPEED),
                    MenuItem("kb_matrix_help", "Mátrix mozdulatai", MenuAction.KEYBOARD_MATRIX_HELP),
                    MenuItem("kb_text_bank", "Szövegtár tartalma", MenuAction.KEYBOARD_TEXT_BANK),
                    MenuItem("sr_panic", "AZONNALI leállítás", MenuAction.SCREEN_READER_PANIC),
                    MenuItem("sr_back", "Vissza", MenuAction.SUBMENU)
                )),
                MenuItem("setup_wizard", "Beállítás varázsló", MenuAction.SETUP_WIZARD),
                MenuItem("setup_status", "Beállítás állapota", MenuAction.SETUP_STATUS),
                MenuItem("diagnostics", "Diagnosztika", MenuAction.DIAGNOSTICS),
                MenuItem("battery_opt", "Korlátlan háttérfutás engedélyezése", MenuAction.BATTERY_OPT_REQUEST),
                MenuItem("autostart", "Automatikus indítás a gyártónál", MenuAction.AUTOSTART_SETUP),
                MenuItem("advanced_back", "Vissza a beállításokhoz", MenuAction.SUBMENU)
            )),
            MenuItem("sos_settings", "S.O.S. paraméterek", MenuAction.SUBMENU, listOf(
                MenuItem("sos_set_1", "S.O.S. szám 1 beállítása", MenuAction.SOS_SET_1),
                MenuItem("sos_set_2", "S.O.S. szám 2 beállítása", MenuAction.SOS_SET_2),
                MenuItem("sos_set_3", "S.O.S. szám 3 beállítása", MenuAction.SOS_SET_3),
                MenuItem("sos_set_4", "S.O.S. szám 4 beállítása", MenuAction.SOS_SET_4),
                MenuItem("sos_read", "S.O.S. számok felolvasása", MenuAction.SOS_READ_ALL),
                MenuItem("sos_settings_back", "Vissza a beállításokhoz", MenuAction.SUBMENU)
            )),
            MenuItem("patrol_master", "Teljes őrség ki-be", MenuAction.BATTERY_PATROL_TOGGLE),
            MenuItem("security", "Biztonság", MenuAction.SUBMENU, listOf(
                MenuItem("lock_toggle", "PIN zárolás ki-be", MenuAction.LOCK_PIN_TOGGLE),
                MenuItem("lock_set", "PIN kód beállítása", MenuAction.LOCK_PIN_SET),
                MenuItem("lock_status", "PIN zárolás állapota", MenuAction.LOCK_PIN_STATUS),
                MenuItem("keyguard_pin_toggle", "Rendszer PIN segéd ki-be", MenuAction.KEYGUARD_PIN_ASSIST_TOGGLE),
                MenuItem("keyguard_pin_setup", "Rendszer PIN segéd engedélyezése", MenuAction.KEYGUARD_PIN_ASSIST_SETUP),
                MenuItem("keyguard_pin_status", "Rendszer PIN segéd állapota", MenuAction.KEYGUARD_PIN_ASSIST_STATUS),
                MenuItem("call_filter_mode", "Hívás szűrő mód", MenuAction.CALL_FILTER_MODE_CYCLE),
                MenuItem("call_filter_status", "Hívás szűrő állapota", MenuAction.CALL_FILTER_MODE_STATUS),
                MenuItem("dialer_default_setup", "Alapértelmezett telefon beállítása", MenuAction.DIALER_DEFAULT_SETUP),
                MenuItem("dialer_default_status", "Telefon alkalmazás állapota", MenuAction.DIALER_DEFAULT_STATUS),
                MenuItem("security_back", "Vissza a beállításokhoz", MenuAction.SUBMENU)
            )),
            MenuItem("sound_settings", "Hangok", MenuAction.SUBMENU, listOf(
                MenuItem("sound_theme", "Söpörj hangtéma", MenuAction.SOUND_THEME_SELECT),
                MenuItem("ringtone_select", "Csengőhang választása", MenuAction.RINGTONE_SELECT),
                MenuItem("sound_volume", "Csengőhang hangerő", MenuAction.ALERT_SOUND_VOLUME_CYCLE),
                MenuItem("sound_silent", "Néma mód ki-be", MenuAction.ALERT_SILENT_MODE_TOGGLE),
                MenuItem("sound_calendar", "Program emlékeztető hang", MenuAction.ALERT_SOUND_CALENDAR),
                MenuItem("sound_medication", "Gyógyszer emlékeztető hang", MenuAction.ALERT_SOUND_MEDICATION),
                MenuItem("sound_alarm", "Ébresztő hang", MenuAction.ALERT_SOUND_ALARM),
                MenuItem("sound_sms", "SMS hang", MenuAction.ALERT_SOUND_SMS),
                MenuItem("sound_email", "E-mail hang", MenuAction.ALERT_SOUND_EMAIL),
                MenuItem("sound_notification", "Egyéb értesítés hang", MenuAction.ALERT_SOUND_NOTIFICATION),
                MenuItem("sound_settings_back", "Vissza a beállításokhoz", MenuAction.SUBMENU)
            )),
            MenuItem("patrol_settings", "Őrség beállítások", MenuAction.SUBMENU, listOf(
                MenuItem("patrol_battery", "Akkumulátor figyelés ki-be", MenuAction.PATROL_BATTERY_TOGGLE),
                MenuItem("patrol_call", "Hívás értesítés ki-be", MenuAction.PATROL_CALL_ALERT_TOGGLE),
                MenuItem("patrol_sms", "Üzenet értesítés ki-be", MenuAction.PATROL_SMS_ALERT_TOGGLE),
                MenuItem("patrol_notification", "Egyéb értesítés ki-be", MenuAction.PATROL_NOTIFICATION_ALERT_TOGGLE),
                MenuItem("patrol_time", "Idő bemondás ki-be", MenuAction.PATROL_TIME_ANNOUNCE_TOGGLE),
                MenuItem("patrol_interval", "Idő bemondás gyakorisága", MenuAction.PATROL_TIME_INTERVAL_CYCLE),
                MenuItem("patrol_night", "Éjszakai csend ki-be", MenuAction.PATROL_NIGHT_MODE_TOGGLE),
                MenuItem("patrol_night_start", "Éjszakai csend kezdete", MenuAction.PATROL_NIGHT_START_SET),
                MenuItem("patrol_night_end", "Éjszakai csend vége", MenuAction.PATROL_NIGHT_END_SET),
                MenuItem("patrol_power", "Bekapcsoló gomb idő bemondás", MenuAction.PATROL_POWER_BUTTON_TIME_TOGGLE),
                MenuItem("patrol_settings_back", "Vissza a beállításokhoz", MenuAction.SUBMENU)
            )),
            MenuItem("vol_up", "Hangerő növelése", MenuAction.VOLUME_UP),
            MenuItem("vol_down", "Hangerő csökkentése", MenuAction.VOLUME_DOWN),
            MenuItem("tts_up", "Beszéd gyorsítása", MenuAction.TTS_SPEED_UP),
            MenuItem("tts_down", "Beszéd lassítása", MenuAction.TTS_SPEED_DOWN),
            MenuItem("tts_engine", "T T S hang választása", MenuAction.TTS_ENGINE_SELECT),
            MenuItem("tts_engine_read", "Aktuális T T S hang felolvasása", MenuAction.TTS_ENGINE_READ),
            MenuItem("notifications", "Értesítések olvasása", MenuAction.NOTIFICATIONS_READ),
            MenuItem("wifi", "WiFi be- és kikapcsolás", MenuAction.WIFI_TOGGLE),
            MenuItem("bt", "Bluetooth be- és kikapcsolás", MenuAction.BT_TOGGLE),
            MenuItem("launcher_switch", "Kezdőképernyő váltás", MenuAction.SUBMENU, listOf(
                MenuItem("exit", "Kilépés a Super DL launcherből", MenuAction.EXIT_LAUNCHER),
                MenuItem("launcher_switch_back", "Vissza a beállításokhoz", MenuAction.SUBMENU)
            )),
            MenuItem("settings_back", "Vissza a főmenübe", MenuAction.SUBMENU)
        )),

        MenuItem("about", "Névjegy és jogi információk", MenuAction.SUBMENU, listOf(
            MenuItem("sound_training", "Program hangjainak megismerése", MenuAction.SOUND_TRAINING),
            MenuItem("training_playground", "Tanuló mód, funkciók bemutatása", MenuAction.TRAINING_PLAYGROUND),
            MenuItem("about_app", "Az alkalmazásról", MenuAction.ABOUT_APP),
            MenuItem("about_dev", "Fejlesztő: Kőrösmezey Dávid", MenuAction.ABOUT_DEVELOPER),
            MenuItem("contact_email", "Kapcsolat e-mailben", MenuAction.CONTACT_EMAIL),
            MenuItem("privacy", "Adatvédelmi tájékoztató", MenuAction.PRIVACY_POLICY),
            MenuItem("terms", "Felhasználási feltételek", MenuAction.TERMS_OF_USE),
            MenuItem("legal", "Jogi nyilatkozat", MenuAction.LEGAL_NOTICE),
            MenuItem("about_back", "Vissza a főmenübe", MenuAction.SUBMENU)
        ))
    )

    fun allItems(): List<MenuItem> {
        fun flatten(items: List<MenuItem>): List<MenuItem> =
            items.flatMap { item -> listOf(item) + flatten(item.children) }
        return flatten(root)
    }
}