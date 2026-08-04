package com.superdl.launcher.files

import android.content.Intent
import android.os.Bundle
import android.os.Environment
import android.view.MotionEvent
import android.view.View
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import com.superdl.launcher.R
import com.superdl.launcher.feedback.SoundFeedback
import com.superdl.launcher.feedback.SoundType
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager
import com.superdl.launcher.voice.VoiceInput
import java.io.File

/**
 * Vak-barát fájlkezelő, végig a megszokott fa-logikával:
 *   fel/le: lépkedés, jobbra: belépés vagy művelet-menü, balra: vissza.
 *
 * Két szint van:
 *  1) BÖNGÉSZŐ – mappák és fájlok listája (a mappák elöl)
 *  2) MŰVELET-MENÜ – egy fájlra/mappára: megnyitás, átnevezés, másolás,
 *     áthelyezés, törlés, adatok, (szövegfájlnál) felolvasás
 */
class FileManagerActivity : AppCompatActivity() {

    private lateinit var tvTitle: TextView
    private lateinit var tvPosition: TextView
    private lateinit var tvStatus: TextView
    private lateinit var tvHint: TextView
    private lateinit var tts: TtsManager
    private lateinit var sounds: SoundFeedback
    private lateinit var gestureListener: SwipeGestureListener

    private var currentDir: File = FileManagerHelper.rootDir()
    private var items: List<FileItem> = emptyList()
    private var index = 0

    // Művelet-menü állapot
    private var actionMode = false
    private var actionIndex = 0
    private var actionTarget: FileItem? = null

    // Vágólap (másolás/áthelyezés)
    private var clipboardFile: File? = null
    private var clipboardIsMove = false

    // Keresés
    private var inSearchResults = false
    private var searchQuery = ""
    private lateinit var voiceInput: VoiceInput

    private enum class FileAction(val label: String) {
        OPEN("Megnyitás"),
        READ_TEXT("Felolvasás"),
        DETAILS("Adatok"),
        RENAME("Átnevezés"),
        COPY("Másolás"),
        MOVE("Áthelyezés"),
        PASTE("Beillesztés ide"),
        SEARCH("Keresés ebben a mappában"),
        DELETE("Törlés")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_media_player)
        applyImmersive()

        tvTitle = findViewById(R.id.tvPlayerTitle)
        tvPosition = findViewById(R.id.tvPlayerPosition)
        tvStatus = findViewById(R.id.tvPlayerStatus)
        tvHint = findViewById(R.id.tvPlayerHint)
        tvStatus.text = ""

        tts = TtsManager(this)
        sounds = SoundFeedback(this)
        voiceInput = VoiceInput(this)

        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = { sounds.play(SoundType.SWIPE_UP); navigate(-1) },
            onSwipeDown = { sounds.play(SoundType.SWIPE_DOWN); navigate(+1) },
            onSwipeRight = { sounds.play(SoundType.SWIPE_RIGHT); activate() },
            onSwipeLeft = { sounds.play(SoundType.SWIPE_LEFT); goBack() }
        )

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = goBack()
        })

        val startPath = intent.getStringExtra(EXTRA_START_DIR)
        currentDir = if (!startPath.isNullOrBlank()) File(startPath) else FileManagerHelper.rootDir()

        tts.runWhenReady {
            tts.speak(
                "Fájlkezelő. ${FileManagerHelper.freeSpaceText(this)} " +
                    "Söpörj fel-le a fájlok között, jobbra a megnyitáshoz, balra vissza."
            )
            loadDir(currentDir, announce = true)
        }
    }

    // ==================== Böngészés ====================

    private fun loadDir(dir: File, announce: Boolean = true) {
        currentDir = dir
        items = FileManagerHelper.listDir(dir)
        index = 0
        actionMode = false
        updateDisplay()
        if (announce) {
            val name = if (dir == FileManagerHelper.rootDir()) "Fő tárhely" else dir.name
            val count = items.count { !it.isParent }
            if (items.isEmpty()) {
                tts.speak("$name. Ez a mappa üres. Balra söprés a visszalépéshez.")
            } else {
                tts.speak("$name, $count elem. ${items[0].speakPreview(this)}")
            }
        }
    }

    private fun navigate(delta: Int) {
        if (actionMode) {
            val actions = availableActions()
            if (actions.isEmpty()) return
            actionIndex = (actionIndex + delta + actions.size) % actions.size
            updateDisplay()
            tts.speak(actions[actionIndex].label)
            return
        }
        if (items.isEmpty()) {
            tts.speak("Ez a mappa üres.")
            return
        }
        index = (index + delta + items.size) % items.size
        updateDisplay()
        tts.speak(items[index].speakPreview(this))
    }

    private fun activate() {
        // Törlés-megerősítés: ha épp kérdeztünk, a jobbra söprés a törlést jelenti.
        pendingDelete?.let { item ->
            pendingDelete = null
            val path = item.file.absolutePath
            val ok = FileManagerHelper.delete(item.file)
            actionMode = false
            actionTarget = null
            if (ok) {
                // A média-adatbázisból is töröljük, különben a zenelejátszó
                // még mindig mutatná a már nem létező számot.
                try {
                    android.media.MediaScannerConnection.scanFile(
                        this, arrayOf(path), null, null
                    )
                } catch (_: Exception) {
                }
                tts.speak("${item.name} törölve.")
                loadDir(currentDir, announce = false)
            } else {
                tts.speak("A törlés nem sikerült. Lehet, hogy nincs jogosultság ehhez a fájlhoz.")
            }
            updateDisplay()
            return
        }
        if (actionMode) {
            performAction(availableActions()[actionIndex])
            return
        }
        if (items.isEmpty()) return
        val item = items[index]
        when {
            item.isParent -> loadDir(item.file)
            item.isDirectory -> loadDir(item.file)
            else -> enterActionMode(item)
        }
    }

    private fun goBack() {
        // Ha törlés-megerősítésre vártunk, a balra söprés a mégse.
        if (pendingDelete != null) {
            pendingDelete = null
            tts.speak("Törlés megszakítva.")
            return
        }
        if (actionMode) {
            actionMode = false
            actionTarget = null
            updateDisplay()
            tts.speak("Vissza a fájlokhoz. ${items.getOrNull(index)?.speakPreview(this) ?: ""}")
            return
        }
        // Keresési találatokból vissza a mappához.
        if (inSearchResults) {
            inSearchResults = false
            searchQuery = ""
            loadDir(currentDir)
            tts.speak("Vissza a mappához.")
            return
        }
        val parent = currentDir.parentFile
        if (currentDir == FileManagerHelper.rootDir() || parent == null || !parent.canRead()) {
            tts.speak("Fájlkezelő bezárva.")
            finish()
            return
        }
        loadDir(parent)
    }

    // ==================== Művelet-menü ====================

    private fun enterActionMode(item: FileItem) {
        actionTarget = item
        actionMode = true
        actionIndex = 0
        updateDisplay()
        val actions = availableActions()
        tts.speak("${item.name}. Műveletek. ${actions.firstOrNull()?.label ?: ""}")
    }

    /** A művelet-lista a helyzethez igazodik (pl. Beillesztés csak ha van vágólap). */
    private fun availableActions(): List<FileAction> {
        val target = actionTarget ?: return emptyList()
        val list = mutableListOf<FileAction>()
        if (!target.isDirectory) {
            list.add(FileAction.OPEN)
            if (FileKind.of(target.file) == FileKind.TEXT) list.add(FileAction.READ_TEXT)
        }
        list.add(FileAction.DETAILS)
        list.add(FileAction.RENAME)
        list.add(FileAction.COPY)
        list.add(FileAction.MOVE)
        if (clipboardFile != null) list.add(FileAction.PASTE)
        // Keresés: bármelyik elem menüjéből indítható, az AKTUÁLIS mappában keres.
        if (!inSearchResults) list.add(FileAction.SEARCH)
        list.add(FileAction.DELETE)
        return list
    }

    private fun performAction(action: FileAction) {
        val target = actionTarget ?: return
        when (action) {
            FileAction.OPEN -> openFile(target.file)
            FileAction.READ_TEXT -> readTextFile(target.file)
            FileAction.DETAILS -> tts.speak(target.speakDetails(this))
            FileAction.RENAME -> tts.speak(
                "Az átnevezés diktálással a következő verzióban jön. " +
                    "Addig a portálon vagy gépről tudod átnevezni."
            )
            FileAction.COPY -> {
                clipboardFile = target.file
                clipboardIsMove = false
                actionMode = false
                updateDisplay()
                tts.speak("${target.name} másolásra kijelölve. Menj a célmappába, és válaszd a Beillesztés ide műveletet.")
            }
            FileAction.MOVE -> {
                clipboardFile = target.file
                clipboardIsMove = true
                actionMode = false
                updateDisplay()
                tts.speak("${target.name} áthelyezésre kijelölve. Menj a célmappába, és válaszd a Beillesztés ide műveletet.")
            }
            FileAction.PASTE -> pasteHere()
            FileAction.SEARCH -> startSearch()
            FileAction.DELETE -> deleteWithConfirm(target)
        }
    }

    // ==================== Keresés ====================

    /** Hangbevitellel megkérdezzük mit keres, majd az aktuális mappában keresünk. */
    private fun startSearch() {
        actionMode = false
        val dirName = if (currentDir == FileManagerHelper.rootDir()) "a fő tárhelyen" else "itt: ${currentDir.name}"
        voiceInput.listen(
            prompt = "Mit keresel $dirName? Mondd a fájl nevét vagy egy részletét.",
            speakFirst = { text, onDone -> tts.speakThen(text, onDone) },
            onResult = { spoken ->
                val query = spoken.trim()
                if (query.isBlank()) {
                    tts.speak("Nem értettem. A keresés megszakítva.")
                    updateDisplay()
                    return@listen
                }
                runSearch(query)
            },
            onError = {
                tts.speak("A keresés megszakítva.")
                updateDisplay()
            }
        )
    }

    private fun runSearch(query: String) {
        searchQuery = query
        tts.speak("Keresés: $query. Egy pillanat.")
        // A keresés lassú lehet nagy mappákban, ezért háttérszálon fut.
        Thread {
            val results = FileManagerHelper.search(currentDir, query)
            runOnUiThread {
                if (results.isEmpty()) {
                    inSearchResults = false
                    tts.speak("Nincs találat erre: $query. Visszatérek a mappához.")
                    updateDisplay()
                    return@runOnUiThread
                }
                inSearchResults = true
                items = results
                index = 0
                actionMode = false
                updateDisplay()
                tts.speak(
                    "${results.size} találat erre: $query. " +
                        "Söpörj fel-le a találatok között, balra a visszatéréshez. " +
                        "${results[0].speakPreview(this)}"
                )
            }
        }.start()
    }

    private fun pasteHere() {
        val source = clipboardFile ?: return
        val ok = if (clipboardIsMove) {
            FileManagerHelper.moveTo(source, currentDir)
        } else {
            FileManagerHelper.copyTo(source, currentDir)
        }
        clipboardFile = null
        actionMode = false
        if (ok) {
            tts.speak(if (clipboardIsMove) "Áthelyezve." else "Másolva.")
            loadDir(currentDir, announce = false)
            updateDisplay()
        } else {
            tts.speak("A művelet nem sikerült. Lehet, hogy nincs jogosultság ehhez a mappához.")
        }
    }

    private fun deleteWithConfirm(item: FileItem) {
        // Kétlépcsős megerősítés hanggal: még egy jobbra söprés kell.
        // FONTOS: a jelzőt AZONNAL beállítjuk, nem a bemondás után – különben
        // aki a mondat vége előtt söpör (vakon ez természetes), az újra a
        // műveleti menüt aktiválná, és a kérdés végtelen hurokba kerülne.
        pendingDelete = item
        tts.speak(
            "Biztosan törlöd? ${item.name}. Söpörj jobbra a törléshez, balra a mégsehez."
        )
    }

    private var pendingDelete: FileItem? = null

    private fun openFile(file: File) {
        try {
            val uri = FileProvider.getUriForFile(this, "$packageName.fileprovider", file)
            val mime = when (FileKind.of(file)) {
                FileKind.AUDIO -> "audio/*"
                FileKind.IMAGE -> "image/*"
                FileKind.VIDEO -> "video/*"
                FileKind.TEXT -> "text/plain"
                FileKind.DOCUMENT -> "application/pdf"
                else -> "*/*"
            }
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, mime)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            startActivity(intent)
        } catch (_: Exception) {
            tts.speak("Ezt a fájlt nem tudom megnyitni. Nincs hozzá alkalmazás a telefonon.")
        }
    }

    private fun readTextFile(file: File) {
        try {
            if (file.length() > 200_000) {
                tts.speak("Ez a szövegfájl túl nagy a felolvasáshoz.")
                return
            }
            val text = file.readText().trim()
            if (text.isBlank()) {
                tts.speak("A fájl üres.")
                return
            }
            tts.speak(text.take(3000))
        } catch (_: Exception) {
            tts.speak("Nem sikerült elolvasni a fájlt.")
        }
    }

    // ==================== Kijelző ====================

    private fun updateDisplay() {
        if (actionMode) {
            val actions = availableActions()
            tvTitle.text = actions.getOrNull(actionIndex)?.label ?: ""
            tvPosition.text = actionTarget?.name ?: ""
            tvHint.text = "⬆⬇ műveletek  •  ➡ indít  •  ⬅ vissza"
            return
        }
        val item = items.getOrNull(index)
        tvTitle.text = item?.name ?: "Üres mappa"
        val dirName = if (currentDir == FileManagerHelper.rootDir()) "Fő tárhely" else currentDir.name
        tvPosition.text = if (items.isEmpty()) dirName else "$dirName  •  ${index + 1} / ${items.size}"
        tvHint.text = "⬆⬇ fájlok  •  ➡ megnyitás  •  ⬅ vissza"
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
        tts.shutdown()
        sounds.release()
        super.onDestroy()
    }

    companion object {
        const val EXTRA_START_DIR = "start_dir"
    }
}
