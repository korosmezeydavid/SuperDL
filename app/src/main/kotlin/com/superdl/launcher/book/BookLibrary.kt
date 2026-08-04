package com.superdl.launcher.book

import android.content.Context
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import java.io.File
import java.io.InputStream

object BookLibrary {

    fun scan(context: Context): List<BookEntry> {
        val found = linkedMapOf<String, BookEntry>()
        scanAppFolders(context, found)
        scanPublicFolders(found)
        scanCustomFolders(context, found)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            scanMediaStore(context, found)
        }
        return found.values.sortedBy { it.title.lowercase() }
    }

    private fun scanCustomFolders(context: Context, found: LinkedHashMap<String, BookEntry>) {
        BookStore.getCustomFolders(context).forEach { path ->
            val dir = File(path)
            if (dir.exists() && dir.isDirectory) walkDir(dir, found)
        }
    }

    fun resolveRecent(context: Context): List<BookEntry> {
        val all = scan(context).associateBy { it.path }
        return BookStore.getRecentPaths(context)
            .mapNotNull { all[it] }
    }

    private fun scanAppFolders(context: Context, found: LinkedHashMap<String, BookEntry>) {
        val dirs = listOfNotNull(
            context.getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS),
            context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS),
            context.getExternalFilesDir(null)?.let { File(it, "Books") }
        )
        dirs.forEach { dir ->
            if (dir.exists()) walkDir(dir, found)
        }
    }

    private fun scanPublicFolders(found: LinkedHashMap<String, BookEntry>) {
        @Suppress("DEPRECATION")
        val roots = listOfNotNull(
            Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS),
            Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS),
            Environment.getExternalStoragePublicDirectory("Books")
        )
        roots.forEach { dir ->
            if (dir.exists()) walkDir(dir, found)
        }
    }

    private fun walkDir(dir: File, found: LinkedHashMap<String, BookEntry>) {
        dir.listFiles()?.forEach { file ->
            if (file.isDirectory) {
                walkDir(file, found)
            } else if (BookTextExtractor.isSupported(file)) {
                addEntry(file, found)
            }
        }
    }

    private fun scanMediaStore(context: Context, found: LinkedHashMap<String, BookEntry>) {
        val resolver = context.contentResolver
        val projection = arrayOf(
            MediaStore.Files.FileColumns._ID,
            MediaStore.Files.FileColumns.DISPLAY_NAME,
            MediaStore.Files.FileColumns.SIZE
        )
        val selection = buildString {
            append("(")
            BookTextExtractor.SUPPORTED_EXTENSIONS.forEachIndexed { index, _ ->
                if (index > 0) append(" OR ")
                append("${MediaStore.Files.FileColumns.DISPLAY_NAME} LIKE ?")
            }
            append(")")
        }
        val args = BookTextExtractor.SUPPORTED_EXTENSIONS.map { "%.$it" }.toTypedArray()
        resolver.query(
            MediaStore.Files.getContentUri("external"),
            projection,
            selection,
            args,
            "${MediaStore.Files.FileColumns.DISPLAY_NAME} ASC"
        )?.use { cursor ->
            val idCol = cursor.getColumnIndexOrThrow(MediaStore.Files.FileColumns._ID)
            val nameCol = cursor.getColumnIndexOrThrow(MediaStore.Files.FileColumns.DISPLAY_NAME)
            val sizeCol = cursor.getColumnIndexOrThrow(MediaStore.Files.FileColumns.SIZE)
            while (cursor.moveToNext()) {
                val id = cursor.getLong(idCol)
                val name = cursor.getString(nameCol) ?: continue
                val size = cursor.getLong(sizeCol)
                val uri = MediaStore.Files.getContentUri("external", id)
                val path = uri.toString()
                val ext = name.substringAfterLast('.', "").lowercase()
                if (ext !in BookTextExtractor.SUPPORTED_EXTENSIONS) continue
                found[path] = BookEntry(
                    path = path,
                    title = name.substringBeforeLast('.'),
                    format = ext,
                    sizeBytes = size
                )
            }
        }
    }

    private fun addEntry(file: File, found: LinkedHashMap<String, BookEntry>) {
        found[file.absolutePath] = BookEntry(
            path = file.absolutePath,
            title = file.nameWithoutExtension,
            format = file.extension.lowercase(),
            sizeBytes = file.length()
        )
    }

    fun openInputStream(context: Context, entry: BookEntry): InputStream? {
        return if (entry.path.startsWith("content://")) {
            context.contentResolver.openInputStream(android.net.Uri.parse(entry.path))
        } else {
            val file = entry.file()
            if (file.exists()) file.inputStream() else null
        }
    }

    fun materializeToCache(context: Context, entry: BookEntry): File? {
        if (!entry.path.startsWith("content://")) {
            val file = entry.file()
            return if (file.exists()) file else null
        }
        val cacheDir = File(context.cacheDir, "books").apply { mkdirs() }
        val safeName = entry.path.hashCode().toUInt().toString(16)
        val out = File(cacheDir, "$safeName.${entry.format}")
        if (out.exists() && out.length() == entry.sizeBytes) return out
        val input = openInputStream(context, entry) ?: return null
        input.use { src ->
            out.outputStream().use { dst -> src.copyTo(dst) }
        }
        return out
    }
}