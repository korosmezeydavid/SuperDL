package com.superdl.launcher.sound

import android.content.Context
import android.media.RingtoneManager
import android.net.Uri

/**
 * Az Android beépített (gyári) csengő-, értesítési- és ébresztőhangjait
 * listázza, hogy a vak felhasználó ezek közül választhasson – és minden
 * hangba bele tudjon hallgatni választás előtt.
 *
 * A telefon saját hangkészletét adja vissza (nem kell külső fájl), ezért
 * bármelyik eszközön a gyári hangokból lehet válogatni.
 */
object SystemRingtoneHelper {

    data class RingtoneItem(
        val title: String,
        val uri: Uri
    )

    /** Az ébresztőhöz használt gyári ébresztőhangok. */
    fun alarmTones(context: Context): List<RingtoneItem> =
        listTones(context, RingtoneManager.TYPE_ALARM)

    /** A híváshoz használt gyári csengőhangok. */
    fun ringtones(context: Context): List<RingtoneItem> =
        listTones(context, RingtoneManager.TYPE_RINGTONE)

    /** Az értesítésekhez használt gyári hangok. */
    fun notificationTones(context: Context): List<RingtoneItem> =
        listTones(context, RingtoneManager.TYPE_NOTIFICATION)

    private fun listTones(context: Context, type: Int): List<RingtoneItem> {
        val manager = RingtoneManager(context).apply { setType(type) }
        val items = mutableListOf<RingtoneItem>()
        try {
            val cursor = manager.cursor
            while (cursor.moveToNext()) {
                val title = cursor.getString(RingtoneManager.TITLE_COLUMN_INDEX)?.trim().orEmpty()
                if (title.isBlank()) continue
                val uri = manager.getRingtoneUri(cursor.position) ?: continue
                items.add(RingtoneItem(title, uri))
            }
        } catch (_: Exception) {
            // Ha a katalógus nem olvasható, üres listát adunk (a hívó kezeli).
        }
        return items
    }

    /** Az alapértelmezett hang az adott típushoz (ha a felhasználó nem választott). */
    fun defaultUri(type: Int): Uri? =
        RingtoneManager.getDefaultUri(type)

    /** Egy mentett URI-hoz megkeresi a hozzá tartozó nevet (visszaolvasáshoz). */
    fun titleForUri(context: Context, uri: Uri?): String? {
        if (uri == null) return null
        return try {
            RingtoneManager.getRingtone(context, uri)?.getTitle(context)
        } catch (_: Exception) {
            null
        }
    }
}
