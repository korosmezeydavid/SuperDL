package com.superdl.launcher.cardorganizer

import android.content.Context
import com.superdl.launcher.locationwatch.VisualFingerprint
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

object CardStore {

    private const val PREFS = "superdl"
    private const val KEY = "card_profiles"
    private const val THUMBNAIL_DIR = "card_thumbnails"
    private const val MAX_CARDS = 100

    fun getAll(context: Context): List<CardProfile> =
        loadRaw(context).sortedByDescending { it.createdAt }

    fun getById(context: Context, id: String): CardProfile? =
        loadRaw(context).firstOrNull { it.id == id }

    fun add(context: Context, profile: CardProfile): CardProfile? {
        val trimmedName = profile.name.trim()
        if (trimmedName.isBlank()) return null
        val current = loadRaw(context).toMutableList()
        if (current.any { it.id == profile.id }) return null
        while (current.size >= MAX_CARDS) {
            val oldest = current.minByOrNull { it.createdAt } ?: break
            current.remove(oldest)
            deleteProfileAssets(oldest)
        }
        val entry = profile.copy(name = trimmedName)
        current.add(entry)
        save(context, current)
        return entry
    }

    fun remove(context: Context, id: String): Boolean {
        val current = loadRaw(context)
        val removed = current.firstOrNull { it.id == id } ?: return false
        save(context, current.filterNot { it.id == id })
        deleteProfileAssets(removed)
        return true
    }

    fun matchCard(cards: List<CardProfile>, candidateHash: String): CardProfile? {
        if (candidateHash.isBlank()) return null
        var best: CardProfile? = null
        var bestScore = VisualFingerprint.MATCH_THRESHOLD
        for (card in cards) {
            val score = VisualFingerprint.bestSimilarity(card.visualHashes, candidateHash)
            if (score >= bestScore) {
                bestScore = score
                best = card
            }
        }
        return best
    }

    fun saveThumbnail(context: Context, cardId: String, side: String, bitmap: android.graphics.Bitmap): String? {
        return try {
            val dir = File(context.filesDir, THUMBNAIL_DIR)
            if (!dir.exists()) dir.mkdirs()
            val file = File(dir, "${cardId}_$side.jpg")
            java.io.FileOutputStream(file).use { out ->
                bitmap.compress(android.graphics.Bitmap.CompressFormat.JPEG, 80, out)
            }
            file.absolutePath
        } catch (_: Exception) {
            null
        }
    }

    private fun deleteProfileAssets(profile: CardProfile) {
        deleteFile(profile.frontThumbnailPath)
        deleteFile(profile.backThumbnailPath)
    }

    private fun deleteFile(path: String?) {
        if (path.isNullOrBlank()) return
        try {
            File(path).delete()
        } catch (_: Exception) {
        }
    }

    private fun loadRaw(context: Context): List<CardProfile> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY, null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val item = array.getJSONObject(i)
                    val name = item.optString("name").trim()
                    if (name.isBlank()) continue
                    val frontHash = item.optString("frontVisualHash")
                    val backHash = item.optString("backVisualHash")
                    if (frontHash.isBlank() && backHash.isBlank()) continue
                    add(
                        CardProfile(
                            id = item.optString("id", UUID.randomUUID().toString()),
                            name = name,
                            createdAt = item.optLong("createdAt", System.currentTimeMillis()),
                            frontVisualHash = frontHash,
                            backVisualHash = backHash,
                            frontThumbnailPath = item.optString("frontThumbnailPath").takeIf { it.isNotBlank() },
                            backThumbnailPath = item.optString("backThumbnailPath").takeIf { it.isNotBlank() }
                        )
                    )
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun save(context: Context, profiles: List<CardProfile>) {
        val array = JSONArray()
        profiles.forEach { profile ->
            array.put(
                JSONObject()
                    .put("id", profile.id)
                    .put("name", profile.name)
                    .put("createdAt", profile.createdAt)
                    .put("frontVisualHash", profile.frontVisualHash)
                    .put("backVisualHash", profile.backVisualHash)
                    .put("frontThumbnailPath", profile.frontThumbnailPath.orEmpty())
                    .put("backThumbnailPath", profile.backThumbnailPath.orEmpty())
            )
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY, array.toString())
            .apply()
    }
}