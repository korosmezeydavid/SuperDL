package com.superdl.launcher.notifications

import android.service.notification.StatusBarNotification
import java.util.concurrent.CopyOnWriteArrayList

object NotificationStore {

    private const val MAX_ENTRIES = 30
    private val entries = CopyOnWriteArrayList<NotificationEntry>()

    fun add(sbn: StatusBarNotification, appLabel: String) {
        val extras = sbn.notification.extras
        val title = extras.getCharSequence(android.app.Notification.EXTRA_TITLE)?.toString()?.trim().orEmpty()
        val text = extras.getCharSequence(android.app.Notification.EXTRA_TEXT)?.toString()?.trim().orEmpty()
        if (title.isBlank() && text.isBlank()) return

        val entry = NotificationEntry(
            key = sbn.key,
            appLabel = appLabel.ifBlank { "Ismeretlen alkalmazás" },
            title = title,
            text = text,
            postedAt = sbn.postTime
        )
        entries.removeAll { it.key == entry.key }
        entries.add(0, entry)
        while (entries.size > MAX_ENTRIES) {
            entries.removeAt(entries.lastIndex)
        }
    }

    fun remove(key: String) {
        entries.removeAll { it.key == key }
    }

    fun getRecent(limit: Int = 20): List<NotificationEntry> =
        entries.take(limit)

    fun clear() {
        entries.clear()
    }
}