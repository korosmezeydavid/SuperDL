package com.superdl.launcher.locationwatch

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

object LocationProfileStore {

    private const val PREFS = "superdl"
    private const val KEY = "location_profiles"
    private const val MAX_PROFILES = 50
    const val MAX_PHOTOS_PER_PROFILE = 20

    fun getAll(context: Context): List<LocationProfile> =
        loadRaw(context).sortedByDescending { it.createdAt }

    fun getById(context: Context, id: String): LocationProfile? =
        loadRaw(context).firstOrNull { it.id == id }

    fun update(context: Context, profile: LocationProfile): LocationProfile? {
        val trimmedName = profile.name.trim()
        if (trimmedName.isBlank()) return null
        val current = loadRaw(context).toMutableList()
        val index = current.indexOfFirst { it.id == profile.id }
        if (index < 0) return null
        val entry = profile.copy(name = trimmedName)
        current[index] = entry
        save(context, current)
        return entry
    }

    fun appendCaptures(
        context: Context,
        profileId: String,
        captures: List<LocationCaptureDraft>
    ): LocationProfile? {
        if (captures.isEmpty()) return getById(context, profileId)
        val existing = getById(context, profileId) ?: return null
        val newTokens = captures.flatMap { LocationMatcher.tokenize(it.ocrText) }.toSet()
        val mergedTokens = existing.ocrTokens + newTokens
        val newHashes = captures.map { it.visualHash }.filter { it.isNotBlank() }
        val mergedHashes = (existing.visualHashes + newHashes).take(MAX_PHOTOS_PER_PROFILE)
        val newPaths = captures.mapNotNull { it.thumbnailPath }
        val mergedPaths = (existing.referenceImagePaths + newPaths).take(MAX_PHOTOS_PER_PROFILE)
        if (mergedTokens.size < 2 && mergedHashes.isEmpty()) return null
        return update(
            context,
            existing.copy(
                ocrTokens = mergedTokens,
                ocrFingerprint = LocationMatcher.buildFingerprint(mergedTokens),
                visualHashes = mergedHashes,
                referenceImagePaths = mergedPaths,
                thumbnailPath = existing.thumbnailPath ?: mergedPaths.firstOrNull()
            )
        )
    }

    fun removeReferenceImage(
        context: Context,
        profileId: String,
        imageIndex: Int
    ): LocationProfile? {
        val existing = getById(context, profileId) ?: return null
        if (imageIndex !in existing.referenceImagePaths.indices) return null
        val pathToDelete = existing.referenceImagePaths[imageIndex]
        val newPaths = existing.referenceImagePaths.toMutableList().apply { removeAt(imageIndex) }
        val newHashes = existing.visualHashes.toMutableList().apply {
            if (imageIndex in indices) removeAt(imageIndex)
        }
        deleteFile(pathToDelete)
        if (newPaths.isEmpty() && newHashes.isEmpty() && existing.ocrTokens.size < 2) {
            remove(context, profileId)
            return null
        }
        return update(
            context,
            existing.copy(
                referenceImagePaths = newPaths,
                visualHashes = newHashes,
                thumbnailPath = newPaths.firstOrNull()
            )
        )
    }

    fun add(context: Context, profile: LocationProfile): LocationProfile? {
        val trimmedName = profile.name.trim()
        if (trimmedName.isBlank()) return null
        val current = loadRaw(context).toMutableList()
        if (current.any { it.id == profile.id }) return null
        while (current.size >= MAX_PROFILES) {
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
        val updated = current.filterNot { it.id == id }
        save(context, updated)
        deleteProfileAssets(removed)
        return true
    }

    fun buildProfileFromOcr(name: String, ocrText: String): LocationProfile? {
        val trimmedName = name.trim()
        if (trimmedName.isBlank()) return null
        val tokens = LocationMatcher.tokenize(ocrText)
        if (tokens.size < 2) return null
        return LocationProfile(
            id = UUID.randomUUID().toString(),
            name = trimmedName,
            createdAt = System.currentTimeMillis(),
            ocrTokens = tokens,
            ocrFingerprint = LocationMatcher.buildFingerprint(tokens)
        )
    }

    fun buildProfileFromCaptures(
        name: String,
        captures: List<LocationCaptureDraft>
    ): LocationProfile? {
        val trimmedName = name.trim()
        if (trimmedName.isBlank() || captures.isEmpty()) return null
        val tokens = captures
            .flatMap { LocationMatcher.tokenize(it.ocrText) }
            .toSet()
        val visualHashes = captures.map { it.visualHash }.filter { it.isNotBlank() }
        if (tokens.size < 2 && visualHashes.isEmpty()) return null
        val referenceImagePaths = captures.mapNotNull { it.thumbnailPath }
        return LocationProfile(
            id = UUID.randomUUID().toString(),
            name = trimmedName,
            createdAt = System.currentTimeMillis(),
            ocrTokens = tokens,
            ocrFingerprint = LocationMatcher.buildFingerprint(tokens),
            thumbnailPath = referenceImagePaths.firstOrNull(),
            visualHashes = visualHashes,
            referenceImagePaths = referenceImagePaths
        )
    }

    private fun deleteProfileAssets(profile: LocationProfile) {
        deleteFile(profile.thumbnailPath)
        profile.referenceImagePaths.forEach { deleteFile(it) }
    }

    private fun deleteFile(path: String?) {
        if (path.isNullOrBlank()) return
        try {
            val file = java.io.File(path)
            if (file.exists()) file.delete()
        } catch (_: Exception) {
        }
    }

    private fun loadRaw(context: Context): List<LocationProfile> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY, null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val item = array.getJSONObject(i)
                    val name = item.optString("name").trim()
                    if (name.isBlank()) continue
                    val tokensArray = item.optJSONArray("ocrTokens") ?: JSONArray()
                    val tokens = buildSet {
                        for (j in 0 until tokensArray.length()) {
                            val token = tokensArray.optString(j).trim()
                            if (token.length >= 2) add(token)
                        }
                    }
                    val visualHashes = parseStringArray(item.optJSONArray("visualHashes"))
                    if (tokens.isEmpty() && visualHashes.isEmpty()) continue
                    add(
                        LocationProfile(
                            id = item.optString("id", UUID.randomUUID().toString()),
                            name = name,
                            createdAt = item.optLong("createdAt", System.currentTimeMillis()),
                            ocrTokens = tokens,
                            ocrFingerprint = item.optString(
                                "ocrFingerprint",
                                LocationMatcher.buildFingerprint(tokens)
                            ),
                            thumbnailPath = item.optString("thumbnailPath").takeIf { it.isNotBlank() },
                            visualHashes = visualHashes,
                            referenceImagePaths = parseStringArray(item.optJSONArray("referenceImagePaths"))
                        )
                    )
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun parseStringArray(array: JSONArray?): List<String> {
        if (array == null) return emptyList()
        return buildList {
            for (i in 0 until array.length()) {
                val value = array.optString(i).trim()
                if (value.isNotBlank()) add(value)
            }
        }
    }

    private fun save(context: Context, profiles: List<LocationProfile>) {
        val array = JSONArray()
        profiles.forEach { profile ->
            val tokensArray = JSONArray()
            profile.ocrTokens.sorted().forEach { tokensArray.put(it) }
            val visualHashesArray = JSONArray()
            profile.visualHashes.forEach { visualHashesArray.put(it) }
            val referenceImagesArray = JSONArray()
            profile.referenceImagePaths.forEach { referenceImagesArray.put(it) }
            array.put(
                JSONObject()
                    .put("id", profile.id)
                    .put("name", profile.name)
                    .put("createdAt", profile.createdAt)
                    .put("ocrTokens", tokensArray)
                    .put("ocrFingerprint", profile.ocrFingerprint)
                    .put("thumbnailPath", profile.thumbnailPath.orEmpty())
                    .put("visualHashes", visualHashesArray)
                    .put("referenceImagePaths", referenceImagesArray)
            )
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY, array.toString())
            .apply()
    }
}