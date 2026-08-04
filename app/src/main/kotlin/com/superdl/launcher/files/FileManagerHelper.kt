package com.superdl.launcher.files

import android.content.Context
import android.os.Environment
import android.text.format.Formatter
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Egy elem a fájlkezelőben (mappa vagy fájl).
 */
data class FileItem(
    val file: File,
    val isParent: Boolean = false
) {
    val name: String get() = if (isParent) "Vissza a szülő mappába" else file.name
    val isDirectory: Boolean get() = file.isDirectory

    /** Vak felhasználónak felolvasható előnézet: mi ez, mekkora, mikori. */
    fun speakPreview(context: Context): String {
        if (isParent) return name
        return if (isDirectory) {
            val count = try {
                file.listFiles()?.size ?: 0
            } catch (_: Exception) {
                0
            }
            "$name, mappa, $count elem"
        } else {
            val size = Formatter.formatShortFileSize(context, file.length())
            val kind = FileKind.of(file).hungarianName
            "$name, $kind, $size"
        }
    }

    fun speakDetails(context: Context): String {
        val modified = SimpleDateFormat("yyyy. MMMM d. HH:mm", Locale("hu", "HU"))
            .format(Date(file.lastModified()))
        val size = if (isDirectory) {
            val count = try { file.listFiles()?.size ?: 0 } catch (_: Exception) { 0 }
            "$count elemet tartalmaz"
        } else {
            Formatter.formatShortFileSize(context, file.length())
        }
        return "$name. ${FileKind.of(file).hungarianName}. $size. Módosítva: $modified."
    }
}

/**
 * Fájltípusok, hogy a felolvasás magyarul és érthetően szóljon.
 */
enum class FileKind(val hungarianName: String, val extensions: Set<String>) {
    AUDIO("hangfájl", setOf("mp3", "wav", "m4a", "aac", "ogg", "flac", "opus", "amr")),
    IMAGE("kép", setOf("jpg", "jpeg", "png", "gif", "webp", "bmp", "heic")),
    VIDEO("videó", setOf("mp4", "mkv", "avi", "mov", "3gp", "webm")),
    DOCUMENT("dokumentum", setOf("pdf", "doc", "docx", "odt", "rtf", "epub", "mobi")),
    TEXT("szövegfájl", setOf("txt", "md", "log", "csv")),
    DATA("adatfájl", setOf("json", "xml", "opml", "html", "htm")),
    ARCHIVE("tömörített fájl", setOf("zip", "rar", "7z", "tar", "gz")),
    APP("alkalmazás", setOf("apk")),
    FOLDER("mappa", emptySet()),
    OTHER("fájl", emptySet());

    companion object {
        fun of(file: File): FileKind {
            if (file.isDirectory) return FOLDER
            val ext = file.extension.lowercase()
            return entries.firstOrNull { ext in it.extensions } ?: OTHER
        }
    }
}

/**
 * A fájlkezelő logikája: mappák bejárása, rendezés, műveletek.
 *
 * Vak-barát elvek:
 *  - a mappák előre kerülnek, utána a fájlok (így kiszámítható a lista)
 *  - ábécé szerint, ékezet-érzéketlenül
 *  - a rejtett fájlok alapból nem látszanak (zavarnának)
 *  - a lista élén mindig ott a "Vissza a szülő mappába", ha van hova
 */
object FileManagerHelper {

    /** A gyökér, ahonnan indulunk: a telefon fő tárhelye. */
    fun rootDir(): File = Environment.getExternalStorageDirectory()

    /**
     * A portál mappája: ide kerülnek a gépről feltöltött fájlok.
     * (A WifiPortalServer is ide ír.)
     */
    fun portalDir(): File {
        val dir = File(rootDir(), "SuperDL/Portal")
        if (!dir.exists()) dir.mkdirs()
        return dir
    }

    /** Szövegfájl tartalmának beolvasása (felolvasáshoz, jelszó-importhoz). */
    fun readTextFile(file: File, maxChars: Int = 20_000): String? = try {
        if (!file.exists() || !file.isFile) null else file.readText().take(maxChars)
    } catch (_: Exception) {
        null
    }

    /**
     * Keresés fájlnév alapján, rekurzívan az adott mappától lefelé.
     * Vak-barát: a találatokat felolvasható sorrendben adja, és korlátozzuk,
     * hogy ne fusson percekig a teljes tárhelyen.
     *
     * @param query amit keresünk (ékezet- és kis/nagybetű-érzéketlen)
     * @param maxResults ennyi találat után megáll
     * @param maxDepth ilyen mélyen megy le a mappákba
     */
    fun search(
        startDir: File,
        query: String,
        maxResults: Int = 50,
        maxDepth: Int = 6
    ): List<FileItem> {
        val needle = normalizeForSearch(query)
        if (needle.isBlank()) return emptyList()
        val results = mutableListOf<FileItem>()
        try {
            startDir.walkTopDown()
                .maxDepth(maxDepth)
                .filterNot { it.isHidden }
                .forEach { f ->
                    if (results.size >= maxResults) return@forEach
                    if (f == startDir) return@forEach
                    if (normalizeForSearch(f.name).contains(needle)) {
                        results.add(FileItem(f))
                    }
                }
        } catch (_: Exception) {
        }
        // Mappák előre, aztán ábécé – ugyanaz a kiszámítható rend, mint a listákban.
        return results.sortedWith(
            compareByDescending<FileItem> { it.isDirectory }
                .thenBy { it.name.lowercase(Locale("hu", "HU")) }
        )
    }

    /** Ékezet- és kisbetű-érzéketlen alak a kereséshez. */
    private fun normalizeForSearch(text: String): String =
        java.text.Normalizer.normalize(text.lowercase(Locale("hu", "HU")), java.text.Normalizer.Form.NFD)
            .replace(Regex("\\p{InCombiningDiacriticalMarks}+"), "")
            .trim()

    /** Gyors elérésű helyek – ezekkel indul a fájlkezelő. */
    fun quickPlaces(): List<Pair<String, File>> {
        val root = rootDir()
        val places = mutableListOf<Pair<String, File>>()
        places.add("Fő tárhely" to root)
        listOf(
            "Letöltések" to Environment.DIRECTORY_DOWNLOADS,
            "Zene" to Environment.DIRECTORY_MUSIC,
            "Képek" to Environment.DIRECTORY_PICTURES,
            "Dokumentumok" to Environment.DIRECTORY_DOCUMENTS,
            "Videók" to Environment.DIRECTORY_MOVIES
        ).forEach { (label, type) ->
            val dir = Environment.getExternalStoragePublicDirectory(type)
            if (dir != null && dir.exists()) places.add(label to dir)
        }
        // A SuperDL saját mappája (ide kerülnek a portálon feltöltött fájlok)
        val superdl = File(root, "SuperDL")
        if (superdl.exists()) places.add("SuperDL mappa" to superdl)
        return places
    }

    /**
     * Egy mappa tartalma, vak-barát sorrendben.
     * @param includeParent tegyünk-e a lista élére "vissza a szülőbe" elemet
     */
    fun listDir(dir: File, includeParent: Boolean = true): List<FileItem> {
        val items = mutableListOf<FileItem>()
        val parent = dir.parentFile
        if (includeParent && parent != null && parent.canRead() && dir != rootDir()) {
            items.add(FileItem(parent, isParent = true))
        }
        val children = try {
            dir.listFiles()?.filterNot { it.isHidden } ?: emptyList()
        } catch (_: Exception) {
            emptyList()
        }
        val sorted = children.sortedWith(
            compareByDescending<File> { it.isDirectory }
                .thenBy { it.name.lowercase(Locale("hu", "HU")) }
        )
        items.addAll(sorted.map { FileItem(it) })
        return items
    }

    /** Új mappa létrehozása. */
    fun createFolder(parent: File, name: String): Boolean = try {
        val clean = sanitizeName(name)
        if (clean.isBlank()) false else File(parent, clean).mkdirs()
    } catch (_: Exception) {
        false
    }

    /** Törlés (mappa esetén a teljes tartalommal). */
    fun delete(file: File): Boolean = try {
        if (file.isDirectory) file.deleteRecursively() else file.delete()
    } catch (_: Exception) {
        false
    }

    /** Átnevezés. */
    fun rename(file: File, newName: String): Boolean = try {
        val clean = sanitizeName(newName)
        if (clean.isBlank()) false else file.renameTo(File(file.parentFile, clean))
    } catch (_: Exception) {
        false
    }

    /** Másolás egy célmappába. */
    fun copyTo(source: File, targetDir: File): Boolean = try {
        val target = uniqueTarget(targetDir, source.name)
        if (source.isDirectory) {
            source.copyRecursively(target, overwrite = false)
        } else {
            source.copyTo(target, overwrite = false)
            true
        }
    } catch (_: Exception) {
        false
    }

    /** Áthelyezés egy célmappába. */
    fun moveTo(source: File, targetDir: File): Boolean = try {
        val target = uniqueTarget(targetDir, source.name)
        if (source.renameTo(target)) {
            true
        } else {
            // Másik köteten a rename nem megy: másol + töröl.
            if (copyTo(source, targetDir)) delete(source) else false
        }
    } catch (_: Exception) {
        false
    }

    /** Ütközés esetén "név (2).kiterjesztés" alakot ad. */
    private fun uniqueTarget(dir: File, name: String): File {
        var candidate = File(dir, name)
        if (!candidate.exists()) return candidate
        val base = name.substringBeforeLast('.', name)
        val ext = name.substringAfterLast('.', "")
        var i = 2
        while (candidate.exists() && i < 1000) {
            val newName = if (ext.isBlank()) "$base ($i)" else "$base ($i).$ext"
            candidate = File(dir, newName)
            i++
        }
        return candidate
    }

    /** A fájlnévből kiszedi a tiltott karaktereket. */
    private fun sanitizeName(name: String): String =
        name.trim().replace(Regex("[/\\\\:*?\"<>|]"), "").take(120)

    /** Egy mappa teljes mérete (rekurzívan) – felolvasáshoz. */
    fun folderSize(dir: File): Long = try {
        dir.walkTopDown().filter { it.isFile }.map { it.length() }.sum()
    } catch (_: Exception) {
        0L
    }

    /** Szabad hely a tárhelyen. */
    fun freeSpaceText(context: Context): String = try {
        val free = rootDir().freeSpace
        val total = rootDir().totalSpace
        "Szabad hely: ${Formatter.formatShortFileSize(context, free)} a " +
            "${Formatter.formatShortFileSize(context, total)}-ból."
    } catch (_: Exception) {
        ""
    }
}
