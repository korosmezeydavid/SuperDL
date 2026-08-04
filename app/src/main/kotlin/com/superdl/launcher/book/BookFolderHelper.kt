package com.superdl.launcher.book

import android.content.Context
import android.os.Environment
import java.io.File
import java.text.Normalizer
import java.util.Locale

object BookFolderHelper {

    fun parseSpokenFolder(context: Context, spoken: String): File? {
        val trimmed = spoken.trim()
        if (trimmed.isBlank()) return null

        val normalized = normalize(trimmed)
        val mapped = when {
            normalized.contains("letoltes") || normalized == "downloads" ->
                publicDir(Environment.DIRECTORY_DOWNLOADS)
            normalized.contains("dokumentum") || normalized == "documents" ->
                publicDir(Environment.DIRECTORY_DOCUMENTS)
            normalized.contains("konyv") || normalized == "books" ->
                publicDir("Books")
            normalized.contains("superdl") ->
                File(context.getExternalFilesDir(null), "Books")
            trimmed.startsWith("/") || trimmed.contains(":\\") -> File(trimmed)
            else -> {
                val direct = File(trimmed)
                if (direct.isAbsolute && direct.exists()) direct
                else publicDir(Environment.DIRECTORY_DOWNLOADS)?.let { File(it, trimmed) }
            }
        } ?: return null

        return mapped.takeIf { it.exists() && it.isDirectory }
    }

    fun speakFolder(file: File): String {
        val name = file.name.ifBlank { file.absolutePath }
        return "Mappa: $name."
    }

    fun speakFolders(folders: List<File>): String {
        if (folders.isEmpty()) return "Nincs egyéni könyvmappa beállítva. Az alapértelmezett mappák használatban."
        return buildString {
            append("${folders.size} egyéni könyvmappa. ")
            folders.forEachIndexed { index, folder ->
                append("${index + 1}. ${folder.name}. ")
            }
        }
    }

    private fun publicDir(type: String): File? {
        @Suppress("DEPRECATION")
        return Environment.getExternalStoragePublicDirectory(type)
    }

    private fun normalize(text: String): String {
        val lower = text.lowercase(Locale("hu", "HU"))
        return Normalizer.normalize(lower, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .replace(Regex("[^a-z0-9\\s]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
    }
}