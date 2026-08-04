package com.superdl.launcher.news

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import org.xmlpull.v1.XmlPullParser
import org.xmlpull.v1.XmlPullParserFactory
import java.io.File
import java.io.InputStream

object NewsFeedStore {

    private const val PREFS = "superdl"
    private const val KEY = "news_feed_config"

    private val DEFAULT_FEEDS = listOf(
        NewsFeed("telex", "Telex", "Általános", "https://telex.hu/rss"),
        NewsFeed("444", "444", "Általános", "https://444.hu/feed"),
        NewsFeed("index", "Index", "Általános", "https://index.hu/24ora/rss/"),
        NewsFeed("hvg", "HVG", "Általános", "https://hvg.hu/rss"),
        NewsFeed("24hu", "24.hu", "Általános", "https://24.hu/feed/"),
        NewsFeed("portfolio", "Portfolio", "Gazdaság", "https://www.portfolio.hu/rss/all.xml"),
        NewsFeed("origo", "Origo", "Általános", "https://www.origo.hu/contentpartner/rss/hircentrum/origo.xml"),
        NewsFeed("rtl", "RTL", "Általános", "https://www.rtl.hu/content/rss"),
        NewsFeed("nepszava", "Népszava", "Politika", "https://nepszava.hu/rss"),
        NewsFeed("magyarnemzet", "Magyar Nemzet", "Politika", "https://magyarnemzet.hu/rss"),
        NewsFeed("hirstart", "Hírstart", "Általános", "https://www.hirstart.hu/rss.php"),
        NewsFeed("nemzetisport", "Nemzeti Sport", "Sport", "https://www.nemzetisport.hu/rss"),
        NewsFeed("index_sport", "Index Sport", "Sport", "https://index.hu/sport/rss/"),
        NewsFeed("hwsw", "HWSW", "Tech", "https://www.hwsw.hu/rss"),
        NewsFeed("itbusiness", "IT Business", "Tech", "https://www.itbusiness.hu/rss"),
        NewsFeed("kultura", "Kultúra.hu", "Kultúra", "https://kultura.hu/rss/"),
        NewsFeed("magyarorszag", "Magyarorszag.hu", "Általános", "https://magyarorszag.hu/rss"),
        NewsFeed("mandiner", "Mandiner", "Politika", "https://mandiner.hu/rss"),
        NewsFeed("blikk", "Blikk", "Bulvár", "https://www.blikk.hu/rss"),
        NewsFeed("magyarhang", "Magyar Hang", "Politika", "https://magyarhang.org/feed/"),
        NewsFeed("klubradio", "Klubrádió", "Politika", "https://klubradio.hu/feed/"),
        NewsFeed("totalcar", "Totalcar", "Autó", "https://totalcar.hu/rss/"),
        NewsFeed("pcworld", "PC World", "Tech", "https://pcworld.hu/rss")
    )

    fun allDefaultFeeds(): List<NewsFeed> = DEFAULT_FEEDS

    fun enabledFeeds(context: Context): List<NewsFeed> {
        val config = loadConfig(context)
        return DEFAULT_FEEDS.filter { config[it.id] != false }
            .plus(customFeeds(context).filter { config[it.id] != false })
    }

    fun allAvailableFeeds(context: Context): List<NewsFeed> =
        listOf(NewsFeed(RssHelper.ALL_FEEDS_ID, "Összes hír", "", "")) +
            enabledFeeds(context)

    fun customFeeds(context: Context): List<NewsFeed> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString("news_custom_feeds", null) ?: return emptyList()
        return parseFeedArray(raw)
    }

    fun isEnabled(context: Context, feedId: String): Boolean =
        loadConfig(context)[feedId] != false

    fun setEnabled(context: Context, feedId: String, enabled: Boolean) {
        val config = loadConfig(context).toMutableMap()
        config[feedId] = enabled
        saveConfig(context, config)
    }

    fun addCustomFeed(context: Context, feed: NewsFeed): Boolean {
        if (feed.url.isBlank() || feed.name.isBlank()) return false
        val current = customFeeds(context).toMutableList()
        if (current.any { it.id == feed.id || it.url == feed.url }) return false
        current.add(feed)
        saveCustomFeeds(context, current)
        setEnabled(context, feed.id, true)
        return true
    }

    fun removeCustomFeed(context: Context, feedId: String): Boolean {
        val current = customFeeds(context)
        if (current.none { it.id == feedId }) return false
        saveCustomFeeds(context, current.filterNot { it.id == feedId })
        val config = loadConfig(context).toMutableMap()
        config.remove(feedId)
        saveConfig(context, config)
        return true
    }

    fun importOpml(context: Context, input: InputStream): Int {
        val imported = parseOpml(input)
        var count = 0
        imported.forEach { feed ->
            if (addCustomFeed(context, feed)) count++
        }
        return count
    }

    fun importOpmlFile(context: Context, path: String): Int {
        val file = File(path)
        if (!file.exists() || !file.isFile) return 0
        return file.inputStream().use { importOpml(context, it) }
    }

    private fun parseOpml(input: InputStream): List<NewsFeed> {
        val factory = XmlPullParserFactory.newInstance()
        val parser = factory.newPullParser()
        parser.setInput(input, null)
        val feeds = mutableListOf<NewsFeed>()
        var event = parser.eventType
        var inOutline = false
        var title = ""
        var xmlUrl = ""
        var category = "Egyéni"

        while (event != XmlPullParser.END_DOCUMENT) {
            when (event) {
                XmlPullParser.START_TAG -> when (parser.name.lowercase()) {
                    "outline" -> {
                        val type = parser.getAttributeValue(null, "type").orEmpty()
                        val url = parser.getAttributeValue(null, "xmlUrl").orEmpty()
                        val text = parser.getAttributeValue(null, "text")
                            ?: parser.getAttributeValue(null, "title").orEmpty()
                        if (url.isNotBlank() && (type.isBlank() || type.equals("rss", true))) {
                            val id = "opml_${url.hashCode()}"
                            feeds.add(NewsFeed(id, text.trim().ifBlank { "OPML forrás" }, category, url.trim()))
                        } else if (text.isNotBlank()) {
                            category = text.trim()
                        }
                        inOutline = true
                        title = text
                        xmlUrl = url
                    }
                }
                XmlPullParser.END_TAG -> if (parser.name.equals("outline", true)) {
                    if (xmlUrl.isNotBlank()) {
                        val id = "opml_${xmlUrl.hashCode()}"
                        feeds.add(
                            NewsFeed(
                                id,
                                title.trim().ifBlank { "OPML forrás" },
                                category,
                                xmlUrl.trim()
                            )
                        )
                    }
                    inOutline = false
                    title = ""
                    xmlUrl = ""
                }
            }
            event = parser.next()
        }
        return feeds.distinctBy { it.url }
    }

    private fun loadConfig(context: Context): Map<String, Boolean> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY, null) ?: return emptyMap()
        return try {
            val obj = JSONObject(raw)
            buildMap {
                obj.keys().forEach { key ->
                    put(key, obj.optBoolean(key, true))
                }
            }
        } catch (_: Exception) {
            emptyMap()
        }
    }

    private fun saveConfig(context: Context, config: Map<String, Boolean>) {
        val obj = JSONObject()
        config.forEach { (key, value) -> obj.put(key, value) }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY, obj.toString())
            .apply()
    }

    private fun saveCustomFeeds(context: Context, feeds: List<NewsFeed>) {
        val array = JSONArray()
        feeds.forEach { feed ->
            array.put(
                JSONObject()
                    .put("id", feed.id)
                    .put("name", feed.name)
                    .put("category", feed.category)
                    .put("url", feed.url)
            )
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString("news_custom_feeds", array.toString())
            .apply()
    }

    private fun parseFeedArray(raw: String): List<NewsFeed> = try {
        val array = JSONArray(raw)
        buildList {
            for (i in 0 until array.length()) {
                val item = array.getJSONObject(i)
                val url = item.optString("url").trim()
                val name = item.optString("name").trim()
                if (url.isBlank() || name.isBlank()) continue
                add(
                    NewsFeed(
                        id = item.optString("id", "custom_${url.hashCode()}"),
                        name = name,
                        category = item.optString("category", "Egyéni"),
                        url = url
                    )
                )
            }
        }
    } catch (_: Exception) {
        emptyList()
    }
}