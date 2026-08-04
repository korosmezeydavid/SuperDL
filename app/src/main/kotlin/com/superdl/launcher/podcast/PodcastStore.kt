package com.superdl.launcher.podcast

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Podcast-beállítások és mentett adatok: ország, feliratkozások,
 * hallgatási pozíciók (hol hagytad abba), lejátszási sebesség.
 */
object PodcastStore {

    private const val PREFS = "superdl"
    private const val KEY_COUNTRY = "podcast_country"
    private const val KEY_SUBSCRIPTIONS = "podcast_subscriptions"
    private const val KEY_POSITIONS = "podcast_positions"
    private const val KEY_SPEED = "podcast_speed"
    private const val KEY_SEEN_EPISODES = "podcast_seen_counts"

    const val DEFAULT_COUNTRY = "hu"
    val SPEEDS = listOf(1.0f, 1.25f, 1.5f, 2.0f)

    /** Az elérhető országok (kód, magyar név). */
    val COUNTRIES = listOf(
        "hu" to "Magyarország",
        "us" to "Egyesült Államok",
        "gb" to "Egyesült Királyság",
        "de" to "Németország",
        "at" to "Ausztria",
        "sk" to "Szlovákia",
        "ro" to "Románia",
        "fr" to "Franciaország",
        "es" to "Spanyolország",
        "it" to "Olaszország"
    )

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    // ==================== Ország ====================

    fun getCountry(context: Context): String =
        prefs(context).getString(KEY_COUNTRY, DEFAULT_COUNTRY) ?: DEFAULT_COUNTRY

    fun setCountry(context: Context, code: String) {
        prefs(context).edit().putString(KEY_COUNTRY, code).apply()
    }

    fun countryName(code: String): String =
        COUNTRIES.firstOrNull { it.first == code }?.second ?: code.uppercase()

    // ==================== Feliratkozások ====================

    fun getSubscriptions(context: Context): List<Podcast> {
        val raw = prefs(context).getString(KEY_SUBSCRIPTIONS, null) ?: return emptyList()
        return try {
            val arr = JSONArray(raw)
            (0 until arr.length()).mapNotNull { i ->
                val o = arr.getJSONObject(i)
                val feed = o.optString("feedUrl")
                if (feed.isBlank()) return@mapNotNull null
                Podcast(
                    id = o.optString("id"),
                    title = o.optString("title"),
                    author = o.optString("author"),
                    feedUrl = feed
                )
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun isSubscribed(context: Context, podcast: Podcast): Boolean =
        getSubscriptions(context).any { it.feedUrl == podcast.feedUrl }

    /** Feliratkozás vagy leiratkozás. Igaz = mostantól feliratkozva. */
    fun toggleSubscription(context: Context, podcast: Podcast): Boolean {
        val list = getSubscriptions(context).toMutableList()
        val existing = list.firstOrNull { it.feedUrl == podcast.feedUrl }
        val subscribed: Boolean
        if (existing != null) {
            list.remove(existing)
            subscribed = false
        } else {
            list.add(podcast)
            subscribed = true
        }
        saveSubscriptions(context, list)
        return subscribed
    }

    private fun saveSubscriptions(context: Context, list: List<Podcast>) {
        val arr = JSONArray()
        list.forEach { p ->
            arr.put(JSONObject().apply {
                put("id", p.id)
                put("title", p.title)
                put("author", p.author)
                put("feedUrl", p.feedUrl)
            })
        }
        prefs(context).edit().putString(KEY_SUBSCRIPTIONS, arr.toString()).apply()
    }

    // ==================== Pozíció-memória ====================

    /** Hol hagytad abba ezt az epizódot (ezredmásodperc). */
    fun getPosition(context: Context, key: String): Int {
        val raw = prefs(context).getString(KEY_POSITIONS, null) ?: return 0
        return try {
            JSONObject(raw).optInt(key, 0)
        } catch (_: Exception) {
            0
        }
    }

    fun setPosition(context: Context, key: String, positionMs: Int) {
        val raw = prefs(context).getString(KEY_POSITIONS, null)
        val obj = try {
            if (raw != null) JSONObject(raw) else JSONObject()
        } catch (_: Exception) {
            JSONObject()
        }
        // A túl rövid pozíciókat nem érdemes tárolni (a szám elején van).
        if (positionMs < 15_000) {
            obj.remove(key)
        } else {
            obj.put(key, positionMs)
        }
        prefs(context).edit().putString(KEY_POSITIONS, obj.toString()).apply()
    }

    // ==================== Lejátszási sebesség ====================

    fun getSpeed(context: Context): Float =
        prefs(context).getFloat(KEY_SPEED, 1.0f)

    fun setSpeed(context: Context, speed: Float) {
        prefs(context).edit().putFloat(KEY_SPEED, speed).apply()
    }

    // ==================== Új adások jelzése ====================

    /** Hány epizódot láttunk legutóbb ennél a podcastnál. */
    fun getSeenCount(context: Context, feedUrl: String): Int {
        val raw = prefs(context).getString(KEY_SEEN_EPISODES, null) ?: return 0
        return try {
            JSONObject(raw).optInt(feedUrl, 0)
        } catch (_: Exception) {
            0
        }
    }

    fun setSeenCount(context: Context, feedUrl: String, count: Int) {
        val raw = prefs(context).getString(KEY_SEEN_EPISODES, null)
        val obj = try {
            if (raw != null) JSONObject(raw) else JSONObject()
        } catch (_: Exception) {
            JSONObject()
        }
        obj.put(feedUrl, count)
        prefs(context).edit().putString(KEY_SEEN_EPISODES, obj.toString()).apply()
    }
}
