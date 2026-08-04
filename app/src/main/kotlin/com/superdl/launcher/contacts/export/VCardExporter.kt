package com.superdl.launcher.contacts.export

import android.content.Context
import android.provider.ContactsContract

/**
 * Az összes névjegy kimentése vCard (.vcf) formátumba.
 *
 * MIÉRT vCard ÉS NEM CSV: a vCard a névjegyek szabványos formátuma — bármelyik
 * telefon, a Google Kapcsolatok és az iPhone is visszaimportálja. Ráadásul
 * MINDENT visz: több telefonszám, több e-mail, cím, cég, jegyzet. A CSV ezeknél
 * elbukik, mert a névjegy nem egy sima táblázatsor.
 *
 * MIÉRT KÜLÖN A BackupManager-TŐL: a névjegyek NEM a mi SharedPreferences-ünkben
 * vannak, hanem az Android saját névjegy-adatbázisában. A BackupManager a
 * beállításokat menti; ez a névjegyeket. Két külön igény, két külön fájl.
 *
 * MIÉRT ÉRDEMES, HA A GOOGLE ÚGYIS MENT: mert a Google-szinkron nem a
 * felhasználó kezében van. Ez igen. "Dupla varrás jobban tart."
 *
 * A vCard 3.0-t használjuk, mert azt minden importáló érti.
 */
object VCardExporter {

    data class Result(
        val vcard: String,
        val contactCount: Int
    )

    /**
     * Minden névjegy egyetlen .vcf szövegben.
     *
     * Az összevont Contacts-on megyünk végig (nem a RawContacts-on), hogy a
     * duplikátumok ne jelenjenek meg többször.
     */
    fun exportAll(context: Context): Result {
        val resolver = context.contentResolver
        val builder = StringBuilder()
        var count = 0

        val contactsCursor = resolver.query(
            ContactsContract.Contacts.CONTENT_URI,
            arrayOf(
                ContactsContract.Contacts._ID,
                ContactsContract.Contacts.DISPLAY_NAME
            ),
            null, null,
            ContactsContract.Contacts.DISPLAY_NAME + " ASC"
        )

        contactsCursor?.use { c ->
            val idIdx = c.getColumnIndex(ContactsContract.Contacts._ID)
            val nameIdx = c.getColumnIndex(ContactsContract.Contacts.DISPLAY_NAME)

            while (c.moveToNext()) {
                val contactId = c.getString(idIdx) ?: continue
                val displayName = if (nameIdx >= 0) c.getString(nameIdx).orEmpty() else ""
                val card = buildCardForContact(context, contactId, displayName)
                if (card != null) {
                    builder.append(card)
                    count++
                }
            }
        }

        return Result(builder.toString(), count)
    }

    private fun buildCardForContact(
        context: Context,
        contactId: String,
        displayName: String
    ): String? {
        val phones = mutableListOf<Pair<String, String>>()   // típuscímke, szám
        val emails = mutableListOf<Pair<String, String>>()
        val addresses = mutableListOf<Pair<String, String>>()
        var organization: String? = null
        var note: String? = null

        val dataCursor = context.contentResolver.query(
            ContactsContract.Data.CONTENT_URI,
            arrayOf(
                ContactsContract.Data.MIMETYPE,
                ContactsContract.Data.DATA1,
                ContactsContract.Data.DATA2
            ),
            ContactsContract.Data.CONTACT_ID + " = ?",
            arrayOf(contactId),
            null
        ) ?: return null

        dataCursor.use { d ->
            val mimeIdx = d.getColumnIndex(ContactsContract.Data.MIMETYPE)
            val data1Idx = d.getColumnIndex(ContactsContract.Data.DATA1)
            val typeIdx = d.getColumnIndex(ContactsContract.Data.DATA2)

            while (d.moveToNext()) {
                val mime = d.getString(mimeIdx) ?: continue
                val value = if (data1Idx >= 0) d.getString(data1Idx).orEmpty() else ""
                if (value.isBlank()) continue
                val typeCode = if (typeIdx >= 0 && !d.isNull(typeIdx)) d.getInt(typeIdx) else -1

                when (mime) {
                    ContactsContract.CommonDataKinds.Phone.CONTENT_ITEM_TYPE ->
                        phones.add(phoneTypeLabel(typeCode) to value)
                    ContactsContract.CommonDataKinds.Email.CONTENT_ITEM_TYPE ->
                        emails.add(emailTypeLabel(typeCode) to value)
                    ContactsContract.CommonDataKinds.StructuredPostal.CONTENT_ITEM_TYPE ->
                        addresses.add(addressTypeLabel(typeCode) to value)
                    ContactsContract.CommonDataKinds.Organization.CONTENT_ITEM_TYPE ->
                        if (organization == null) organization = value
                    ContactsContract.CommonDataKinds.Note.CONTENT_ITEM_TYPE ->
                        if (note == null) note = value
                }
            }
        }

        // Ha egy névjegynek se neve, se száma, se e-mailje — kihagyjuk.
        if (displayName.isBlank() && phones.isEmpty() && emails.isEmpty()) return null

        return renderCard(displayName, phones, emails, addresses, organization, note)
    }

    private fun renderCard(
        displayName: String,
        phones: List<Pair<String, String>>,
        emails: List<Pair<String, String>>,
        addresses: List<Pair<String, String>>,
        organization: String?,
        note: String?
    ): String = buildString {
        append("BEGIN:VCARD\r\n")
        append("VERSION:3.0\r\n")
        append("FN:").append(escape(displayName)).append("\r\n")
        // A strukturált név (N) kötelező a 3.0-ban; a megjelenítendő nevet a
        // vezetéknév mezőbe tesszük, hogy semmi ne vesszen el.
        append("N:").append(escape(displayName)).append(";;;;\r\n")

        for ((label, number) in phones) {
            append("TEL;TYPE=").append(label).append(":").append(escape(number)).append("\r\n")
        }
        for ((label, email) in emails) {
            append("EMAIL;TYPE=").append(label).append(":").append(escape(email)).append("\r\n")
        }
        for ((label, addr) in addresses) {
            append("ADR;TYPE=").append(label).append(":;;").append(escape(addr)).append(";;;;\r\n")
        }
        organization?.let { append("ORG:").append(escape(it)).append("\r\n") }
        note?.let { append("NOTE:").append(escape(it)).append("\r\n") }
        append("END:VCARD\r\n")
    }

    // A vCard 3.0 escape-szabályai: a fordított perjel, vessző, pontosvessző és
    // az újsor speciális. Enélkül egy vesszős cím eltörné a formátumot.
    private fun escape(text: String): String =
        text.replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n")
            .replace("\r", "")

    private fun phoneTypeLabel(type: Int): String = when (type) {
        ContactsContract.CommonDataKinds.Phone.TYPE_MOBILE -> "CELL"
        ContactsContract.CommonDataKinds.Phone.TYPE_HOME -> "HOME"
        ContactsContract.CommonDataKinds.Phone.TYPE_WORK -> "WORK"
        ContactsContract.CommonDataKinds.Phone.TYPE_MAIN -> "MAIN"
        ContactsContract.CommonDataKinds.Phone.TYPE_FAX_WORK,
        ContactsContract.CommonDataKinds.Phone.TYPE_FAX_HOME -> "FAX"
        else -> "VOICE"
    }

    private fun emailTypeLabel(type: Int): String = when (type) {
        ContactsContract.CommonDataKinds.Email.TYPE_HOME -> "HOME"
        ContactsContract.CommonDataKinds.Email.TYPE_WORK -> "WORK"
        else -> "INTERNET"
    }

    private fun addressTypeLabel(type: Int): String = when (type) {
        ContactsContract.CommonDataKinds.StructuredPostal.TYPE_HOME -> "HOME"
        ContactsContract.CommonDataKinds.StructuredPostal.TYPE_WORK -> "WORK"
        else -> "OTHER"
    }
}
