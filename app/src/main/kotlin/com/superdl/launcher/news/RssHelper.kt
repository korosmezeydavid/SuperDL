package com.superdl.launcher.news

import android.content.Context
import android.os.Handler
import android.os.Looper
import org.xmlpull.v1.XmlPullParser
import org.xmlpull.v1.XmlPullParserFactory
import java.net.HttpURLConnection
import java.net.URL

data class NewsFeed(
    val id: String,
    val name: String,
    val category: String,
    val url: String
) {
    fun speakPreview(): String = if (category.isBlank()) name else "$category. $name"
}

data class RssItem(
    val title: String,
    val description: String,
    val source: String,
    val link: String = ""
) {
    fun speakPreview(): String {
        val preview = description.ifBlank { title }
        val trimmed = if (preview.length > 100) preview.take(100) + "…" else preview
        return "$source. $title. $trimmed"
    }

    fun speakFull(): String {
        val body = description.ifBlank { "Nincs leírás." }
        return "$source. $title. $body"
    }
}

data class RssPage(
    val items: List<RssItem>,
    val page: Int,
    val hasMore: Boolean
)

object RssHelper {

    const val ALL_FEEDS_ID = "all"
    const val PAGE_SIZE = 20

    fun allFeeds(context: Context): List<NewsFeed> = NewsFeedStore.allAvailableFeeds(context)

    fun fetchHeadlines(
        context: Context,
        page: Int = 0,
        onResult: (RssPage) -> Unit,
        onError: () -> Unit
    ) = fetchFromFeed(context, ALL_FEEDS_ID, page, onResult, onError)

    fun fetchFromFeed(
        context: Context,
        feedId: String,
        page: Int = 0,
        onResult: (RssPage) -> Unit,
        onError: () -> Unit
    ) {
        Thread {
            try {
                val rssPage = if (feedId == ALL_FEEDS_ID) {
                    fetchMixed(context, page)
                } else {
                    fetchSingle(context, feedId, page)
                }
                Handler(Looper.getMainLooper()).post {
                    if (rssPage.items.isEmpty()) onError() else onResult(rssPage)
                }
            } catch (_: Exception) {
                Handler(Looper.getMainLooper()).post { onError() }
            }
        }.start()
    }

    private fun fetchSingle(context: Context, feedId: String, page: Int): RssPage {
        val feed = NewsFeedStore.enabledFeeds(context).find { it.id == feedId }
            ?: NewsFeedStore.customFeeds(context).find { it.id == feedId }
            ?: return RssPage(emptyList(), page, false)
        val needed = (page + 1) * PAGE_SIZE + 1
        val all = parseFeed(feed.url, feed.name, maxItems = needed)
        val start = page * PAGE_SIZE
        val slice = all.drop(start).take(PAGE_SIZE)
        val hasMore = all.size > start + PAGE_SIZE
        return RssPage(slice, page, hasMore)
    }

    private fun fetchMixed(context: Context, page: Int): RssPage {
        val feeds = NewsFeedStore.enabledFeeds(context)
        val perFeed = 4
        val needed = (page + 1) * PAGE_SIZE + 1
        val items = mutableListOf<RssItem>()
        for (feed in feeds) {
            if (items.size >= needed) break
            items.addAll(parseFeed(feed.url, feed.name, maxItems = perFeed * (page + 2)))
        }
        val distinct = items.distinctBy { "${it.source}:${it.title}" }
        val start = page * PAGE_SIZE
        val slice = distinct.drop(start).take(PAGE_SIZE)
        val hasMore = distinct.size > start + PAGE_SIZE
        return RssPage(slice, page, hasMore)
    }

    private fun parseFeed(feedUrl: String, source: String, maxItems: Int): List<RssItem> {
        val connection = URL(feedUrl).openConnection() as HttpURLConnection
        connection.connectTimeout = 10_000
        connection.readTimeout = 10_000
        connection.setRequestProperty("User-Agent", "SuperDL/1.46")
        if (connection.responseCode !in 200..299) return emptyList()
        connection.inputStream.use { stream ->
            val factory = XmlPullParserFactory.newInstance()
            val parser = factory.newPullParser()
            parser.setInput(stream, null)

            val items = mutableListOf<RssItem>()
            var event = parser.eventType
            var inItem = false
            var title = ""
            var description = ""
            var link = ""

            while (event != XmlPullParser.END_DOCUMENT && items.size < maxItems) {
                when (event) {
                    XmlPullParser.START_TAG -> when (parser.name.lowercase()) {
                        "item", "entry" -> {
                            inItem = true
                            title = ""
                            description = ""
                            link = ""
                        }
                        "title" -> if (inItem) title = parser.nextText().stripTags().trim()
                        "link" -> if (inItem && link.isBlank()) {
                            // Atom: <link href="..."/> ; RSS: <link>...</link>
                            val href = parser.getAttributeValue(null, "href")
                            if (!href.isNullOrBlank()) {
                                link = href.trim()
                            } else {
                                val textLink = parser.nextText().trim()
                                if (textLink.isNotBlank()) link = textLink
                            }
                        }
                        "description", "summary", "content" ->
                            if (inItem && description.isBlank()) {
                                description = parser.nextText().stripTags().trim()
                            }
                    }
                    XmlPullParser.END_TAG -> if (parser.name.lowercase() in listOf("item", "entry")) {
                        if (title.isNotBlank()) {
                            items.add(RssItem(title, description, source, link))
                        }
                        inItem = false
                    }
                }
                event = parser.next()
            }
            return items
        }
    }

    private fun String.stripTags(): String =
        replace(Regex("<[^>]+>"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
}