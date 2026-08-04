package com.superdl.launcher.files

import android.content.Context
import android.util.Log
import com.superdl.launcher.alarm.AlarmRepeatType
import com.superdl.launcher.alarm.AlarmScheduler
import com.superdl.launcher.alarm.AlarmStore
import com.superdl.launcher.backup.BackupManager
import com.superdl.launcher.calendar.CalendarHelper
import com.superdl.launcher.contacts.ContactHelper
import com.superdl.launcher.contacts.export.VCardExporter
import com.superdl.launcher.email.EmailHelper
import com.superdl.launcher.email.SmtpConfig
import com.superdl.launcher.email.SmtpConfigStore
import com.superdl.launcher.email.SmtpTester
import com.superdl.launcher.gps.SavedPoiStore
import com.superdl.launcher.medication.MedicationCycleType
import com.superdl.launcher.medication.MedicationScheduler
import com.superdl.launcher.medication.MedicationStore
import com.superdl.launcher.medication.MedicationTimeOfDay
import com.superdl.launcher.medication.MedicationWeekdays
import com.superdl.launcher.notes.NoteStore
import com.superdl.launcher.podcast.PodcastStore
import com.superdl.launcher.settings.PermissionGuideTexts
import com.superdl.launcher.setup.DiagnosticsReport
import com.superdl.launcher.setup.SetupRequirements
import com.superdl.launcher.sms.SmsHelper
import java.net.URLDecoder

/**
 * A WiFi portál vezérlő-oldalai: SMS, névjegyek, jegyzetek a gépről,
 * rendes billentyűzettel.
 *
 * MIÉRT: vakon a telefonon gépelni lassú és hibás (a 16 karakteres Gmail
 * app-jelszót gyakorlatilag lehetetlen bediktálni). Ha a gépnél ülsz, ott a
 * billentyűzeted és a képernyőolvasód – onnan sokkal gyorsabb.
 *
 * AKADÁLYMENTESSÉG: ez NEM képernyő-tükrözés (mint az AirDroid), hanem tiszta,
 * szemantikus HTML: űrlap-címkék, aria-live állapotok, billentyűzettel bejárható
 * minden. Nincs kép, nincs kattintgatás, nincs egérrel-rajzolt felület.
 */
object PortalControlPages {

    private const val TAG = "SuperDL.PortalCtrl"

    /** A vezérlő-oldalak közös fejléce, navigációval. */
    private fun header(title: String, activeTab: String): String {
        fun tab(id: String, label: String, href: String): String =
            if (id == activeTab) {
                """<a href="$href" aria-current="page" class="tab active">$label</a>"""
            } else {
                """<a href="$href" class="tab">$label</a>"""
            }
        return """
        <!DOCTYPE html>
        <html lang="hu">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>$title – SuperDL</title>
        <style>${css()}</style>
        </head>
        <body>
        <a href="#main" class="skip">Ugrás a tartalomra</a>
        <header>
          <h1>SuperDL vezérlő</h1>
          <nav aria-label="Fő navigáció">
            ${tab("files", "Fájlok", "/")}
            ${tab("sms", "SMS", "/sms")}
            ${tab("email", "E-mail", "/email")}
            ${tab("contacts", "Névjegyek", "/contacts")}
            ${tab("notes", "Jegyzetek", "/notes")}
            ${tab("alarms", "Ébresztők", "/alarms")}
            ${tab("medication", "Patika Őrangyal", "/medication")}
            ${tab("calendar", "Naptár", "/calendar")}
            ${tab("shopping", "Bevásárlólista", "/shopping")}
            ${tab("places", "Emlékhelyek", "/places")}
            ${tab("podcast", "Podcast", "/podcast")}
            ${tab("media", "Fotók és hangok", "/media")}
            ${tab("radio", "Rádió", "/radio")}
            ${tab("status", "Állapot", "/status")}
            ${tab("setup", "Beállítás", "/setup")}
            ${tab("diagnostics", "Diagnosztika", "/diagnostics")}
            ${tab("backup", "Mentés", "/backup")}
          </nav>
        </header>
        <main id="main">
        """.trimIndent()
    }

    private fun footer(): String = "</main></body></html>"

    // ==================== SMS ====================

    fun smsPage(
        context: Context,
        sent: String? = null,
        error: String? = null,
        replyTo: String? = null
    ): String {
        val messages = try {
            SmsHelper.getRecentMessages(context, limit = 30)
        } catch (e: Exception) {
            Log.w(TAG, "getRecentMessages failed", e)
            emptyList()
        }

        val status = when {
            sent != null -> """<p class="ok" role="status">Elküldve: ${esc(sent)}</p>"""
            error != null -> """<p class="err" role="alert">${esc(error)}</p>"""
            else -> ""
        }

        val list = if (messages.isEmpty()) {
            "<p class='empty'>Nincs üzenet, vagy nincs olvasási jogosultság.</p>"
        } else {
            messages.joinToString("\n") { m ->
                // A számhoz megkeressük a nevet, ha van névjegy.
                val who = try {
                    ContactHelper.findNameByPhone(context, m.address) ?: m.address
                } catch (_: Exception) {
                    m.address
                }
                val time = java.text.SimpleDateFormat("MM. dd. HH:mm", java.util.Locale("hu", "HU"))
                    .format(java.util.Date(m.date))
                """
                <article class="msg">
                  <h3>${esc(who)}</h3>
                  <p>${esc(m.body)}</p>
                  <p class="time">${esc(time)}</p>
                  <div class="actions">
                    <form method="POST" action="/sms/reply" class="inline">
                      <input type="hidden" name="phone" value="${esc(m.address)}">
                      <button type="submit">Válasz neki: ${esc(who)}</button>
                    </form>
                    <form method="POST" action="/sms/delete" class="inline">
                      <input type="hidden" name="id" value="${m.id}">
                      <button type="submit" class="danger">Üzenet törlése: ${esc(who)}, ${esc(time)}</button>
                    </form>
                  </div>
                </article>
                """.trimIndent()
            }
        }

        // Ha válaszra kattintott, előre kitöltjük a címzettet.
        val phoneValue = if (replyTo != null) """ value="${esc(replyTo)}"""" else ""
        val focusScript = if (replyTo != null) {
            """<script>document.getElementById('body').focus();</script>"""
        } else {
            ""
        }

        return header("SMS", "sms") + """
        <h2>Új üzenet</h2>
        $status
        <form method="POST" action="/sms/send">
          <label for="phone">Telefonszám vagy név</label>
          <input type="text" id="phone" name="phone" required
                 autocomplete="tel" placeholder="+36 30 123 4567"$phoneValue>
          <button type="button" class="secondary" onclick="pasteInto('phone')">
            Beillesztés a vágólapról a telefonszám mezőbe
          </button>
          <label for="body">Üzenet</label>
          <textarea id="body" name="body" rows="4" required
                    placeholder="Írd ide az üzenetet"></textarea>
          <button type="button" class="secondary" onclick="pasteInto('body')">
            Beillesztés a vágólapról az üzenet mezőbe
          </button>
          <div id="paste-status" role="status" aria-live="polite" class="pastestatus"></div>
          <button type="submit">Küldés</button>
        </form>

        <h2>Legutóbbi üzenetek (${messages.size})</h2>
        $list
        ${clipboardScript()}
        $focusScript
        """.trimIndent() + footer()
    }

    fun handleSmsDelete(context: Context, body: String): String {
        val id = parseForm(body)["id"]?.toLongOrNull()
            ?: return smsPage(context, error = "Hiányzó azonosító.")
        return try {
            val ok = SmsHelper.deleteMessage(context, id)
            if (ok) {
                smsPage(context, sent = null, error = null)
            } else {
                smsPage(context, error = "Nem sikerült törölni az üzenetet.")
            }
        } catch (e: Exception) {
            Log.w(TAG, "sms delete failed", e)
            smsPage(context, error = "Nem sikerült törölni.")
        }
    }

    fun handleSmsReply(context: Context, body: String): String {
        val phone = parseForm(body)["phone"].orEmpty().trim()
        return smsPage(context, replyTo = phone.ifBlank { null })
    }

    /**
     * Vágólap-beillesztés gombbal.
     *
     * MIÉRT GOMB: a Ctrl+V működik, de aki a telefonján másolt ki egy számot
     * (Hívásnapló → Szám másolása), az a gépen nem tudja beilleszteni. Ez a
     * gomb a BÖNGÉSZŐ vágólapját olvassa – oda kerül, amit a gépen másoltál.
     * Minden beillesztést hangosan visszajelzünk (role=status).
     */
    private fun clipboardScript(): String = """
        <script>
        async function pasteInto(id) {
          var field = document.getElementById(id);
          var status = document.getElementById('paste-status');
          if (!field) return;
          try {
            var text = await navigator.clipboard.readText();
            if (!text) {
              status.textContent = 'A vágólap üres.';
              return;
            }
            field.value = text.trim();
            field.focus();
            status.textContent = 'Beillesztve: ' + text.trim();
          } catch (e) {
            // A böngésző nem engedte (nincs HTTPS, vagy nincs engedély).
            status.textContent = 'A böngésző nem engedi a vágólap olvasását. ' +
              'Kattints a mezőbe, és nyomj Ctrl és V billentyűt.';
            field.focus();
          }
        }
        </script>
    """.trimIndent()

    fun handleSmsSend(context: Context, body: String): String {
        val params = parseForm(body)
        val phoneRaw = params["phone"].orEmpty().trim()
        val message = params["body"].orEmpty().trim()

        if (phoneRaw.isBlank() || message.isBlank()) {
            return smsPage(context, error = "A telefonszám és az üzenet is kötelező.")
        }

        // Ha nevet írtak be, megkeressük a névjegyek között.
        val phone = if (phoneRaw.any { it.isDigit() } && phoneRaw.count { it.isDigit() } >= 6) {
            phoneRaw
        } else {
            val matches = try {
                ContactHelper.searchByName(context, phoneRaw)
            } catch (_: Exception) {
                emptyList()
            }
            when {
                matches.isEmpty() ->
                    return smsPage(context, error = "Nincs ilyen névjegy: $phoneRaw")
                matches.size > 1 ->
                    return smsPage(
                        context,
                        error = "Több találat erre: $phoneRaw. Írd be a teljes számot."
                    )
                else -> matches.first().phone
            }
        }

        val ok = try {
            SmsHelper.send(context, phone, message)
        } catch (e: Exception) {
            Log.w(TAG, "sms send failed", e)
            false
        }
        return if (ok) {
            smsPage(context, sent = phone)
        } else {
            smsPage(context, error = "Az üzenet küldése nem sikerült.")
        }
    }

    // ==================== Névjegyek ====================

    fun contactsPage(context: Context, msg: String? = null, error: String? = null): String {
        val contacts = try {
            ContactHelper.listAllWithPhone(context, limit = 300)
        } catch (e: Exception) {
            Log.w(TAG, "listAllWithPhone failed", e)
            emptyList()
        }

        val status = when {
            msg != null -> """<p class="ok" role="status">${esc(msg)}</p>"""
            error != null -> """<p class="err" role="alert">${esc(error)}</p>"""
            else -> ""
        }

        val list = if (contacts.isEmpty()) {
            "<p class='empty'>Nincs névjegy, vagy nincs jogosultság.</p>"
        } else {
            contacts.joinToString("\n") { c ->
                """
                <article class="msg">
                  <h3>${esc(c.name)}</h3>
                  <p class="time">${esc(c.phone)}</p>
                  <div class="actions">
                    <form method="POST" action="/contacts/share" class="inline">
                      <input type="hidden" name="name" value="${esc(c.name)}">
                      <input type="hidden" name="phone" value="${esc(c.phone)}">
                      <label for="to-${esc(c.phone)}" class="sr">Küldés kinek</label>
                      <input type="text" id="to-${esc(c.phone)}" name="to"
                             placeholder="Címzett száma vagy neve" required>
                      <button type="submit">Névjegy küldése: ${esc(c.name)}</button>
                    </form>
                    <form method="POST" action="/contacts/delete-confirm" class="inline">
                      <input type="hidden" name="id" value="${esc(c.id)}">
                      <button type="submit" class="danger">Törlés: ${esc(c.name)}</button>
                    </form>
                  </div>
                </article>
                """.trimIndent()
            }
        }

        // MIÉRT KÜLÖN ŰRLAP: a tömeges törléshez minden checkbox ugyanazt a
        // nevet (id) viseli, és egyetlen POST-ban kell megérkezniük. A fenti
        // névjegyenkénti űrlapok ezen kívül vannak, mert azok külön akciók.
        val bulkForm = if (contacts.isEmpty()) {
            ""
        } else {
            val checkboxes = contacts.joinToString("\n") { c ->
                """
                <div class="row">
                  <input type="checkbox" id="pick-${esc(c.id)}" name="id"
                         value="${esc(c.id)}" class="pick">
                  <label for="pick-${esc(c.id)}" class="picklabel">${esc(c.name)}, ${esc(c.phone)}</label>
                </div>
                """.trimIndent()
            }
            """
            <h2>Több névjegy törlése</h2>
            <p class="hint">Pipáld ki, kiket szeretnél törölni, majd nyomd meg a
              gombot a lista végén. A törlés előtt még megerősítést kérünk.</p>
            <form method="POST" action="/contacts/delete-confirm">
              <fieldset>
                <legend class="sr">Törlendő névjegyek kijelölése</legend>
                $checkboxes
              </fieldset>
              <button type="submit" class="danger">Kijelöltek törlése</button>
            </form>
            """.trimIndent()
        }

        return header("Névjegyek", "contacts") + """
        <h2>Összes névjegy mentése</h2>
        <p class="hint">Letölt egy vCard (.vcf) fájlt az összes névjegyeddel:
          minden szám, e-mail és cím benne van. Ezt bármelyik telefon, a Google
          Kapcsolatok és az iPhone is visszaimportálja. Jó ezt időnként elmenteni
          a gépre — akkor is megvan, ha a telefonnal történik valami.</p>
        <form method="GET" action="/contacts/export">
          <button type="submit">Összes névjegy letöltése (vCard)</button>
        </form>

        <h2>Új névjegy</h2>
        $status
        <form method="POST" action="/contacts/add">
          <label for="cname">Név</label>
          <input type="text" id="cname" name="name" required autocomplete="name">
          <button type="button" class="secondary" onclick="pasteInto('cname')">
            Beillesztés a vágólapról a név mezőbe
          </button>
          <label for="cphone">Telefonszám</label>
          <input type="text" id="cphone" name="phone" required autocomplete="tel">
          <button type="button" class="secondary" onclick="pasteInto('cphone')">
            Beillesztés a vágólapról a telefonszám mezőbe
          </button>
          <div id="paste-status" role="status" aria-live="polite" class="pastestatus"></div>
          <button type="submit">Hozzáadás</button>
        </form>

        <h2>Névjegyek (${contacts.size})</h2>
        $list
        $bulkForm
        ${clipboardScript()}
        """.trimIndent() + footer()
    }

    /**
     * Megerősítő oldal a névjegy-törléshez.
     *
     * MIÉRT KELL KÉT LÉPÉS: a névjegy-törlés VISSZAFORDÍTHATATLAN, és itt akár
     * több tucat is mehet egyszerre. Az SMS-nél egy üzenet vész el, itt a fél
     * telefonkönyv. Ezért előbb NÉV SZERINT felsoroljuk, kiket törölnénk —
     * képernyőolvasóval így hallható, mi fog történni, mielőtt megtörténik.
     */
    fun handleContactDeleteConfirm(context: Context, body: String): String {
        val ids = parseFormMulti(body)["id"].orEmpty().distinct()
        if (ids.isEmpty()) {
            return contactsPage(context, error = "Nem jelöltél ki egy névjegyet sem.")
        }

        val all = try {
            ContactHelper.listAllWithPhone(context, limit = 300)
        } catch (e: Exception) {
            Log.w(TAG, "listAllWithPhone failed", e)
            emptyList()
        }
        // MIÉRT distinctBy(id): egy névjegy több telefonszámmal több sorként
        // szerepel a listában (a kulcs id|phone). A törlés viszont a TELJES
        // névjegyet törli, ezért itt névjegyenként egyszer soroljuk fel —
        // különben ugyanaz a név kétszer hangzana el a megerősítésben.
        val picked = all.filter { it.id in ids }.distinctBy { it.id }
        if (picked.isEmpty()) {
            return contactsPage(context, error = "A kijelölt névjegyek már nem találhatók.")
        }

        val items = picked.joinToString("\n") { c ->
            """<li>${esc(c.name)}, ${esc(c.phone)}</li>"""
        }
        val hidden = picked.joinToString("\n") { c ->
            """<input type="hidden" name="id" value="${esc(c.id)}">"""
        }
        val count = picked.size
        val headline = if (count == 1) {
            "Biztosan törlöd ezt a névjegyet?"
        } else {
            "Biztosan törlöd ezt a $count névjegyet?"
        }

        return header("Névjegy törlése", "contacts") + """
        <h2>Megerősítés</h2>
        <p class="err" role="alert">$headline
          A törlés végleges, nem lehet visszavonni.</p>
        <ul class="confirm-list">
          $items
        </ul>
        <form method="POST" action="/contacts/delete">
          $hidden
          <button type="submit" class="danger">Igen, töröljem${if (count > 1) " mind a $count névjegyet" else ""}</button>
        </form>
        <form method="GET" action="/contacts">
          <button type="submit" class="secondary">Mégsem, vissza a névjegyekhez</button>
        </form>
        """.trimIndent() + footer()
    }

    /**
     * Az összes névjegy vCard szövege — a szerver ezt küldi le .vcf fájlként.
     *
     * MIÉRT itt: a WifiPortalServer csak a szöveget kéri, a HTTP-fejlécet
     * (Content-Disposition) ő teszi rá. Így a portál-oldalak nem függenek a
     * hálózati rétegtől.
     */
    fun contactsVCard(context: Context): String =
        try {
            VCardExporter.exportAll(context).vcard
        } catch (e: Exception) {
            Log.w(TAG, "vcard export failed", e)
            ""
        }

    /** A tényleges törlés — ide csak a megerősítő oldalról lehet eljutni. */
    fun handleContactDelete(context: Context, body: String): String {
        val ids = parseFormMulti(body)["id"].orEmpty().distinct()
        if (ids.isEmpty()) {
            return contactsPage(context, error = "Hiányzó azonosító.")
        }

        var deleted = 0
        var failed = 0
        ids.forEach { id ->
            val ok = try {
                ContactHelper.deleteContact(context, id)
            } catch (e: Exception) {
                Log.w(TAG, "contact delete failed for id=$id", e)
                false
            }
            if (ok) deleted++ else failed++
        }

        // MIÉRT SZÁMOLUNK KÜLÖN: ha 7-ből 1 nem sikerül, azt tudni kell.
        // A néma részleges siker itt rosszabb, mint a hiba.
        val message = when {
            deleted == 0 -> null
            deleted == 1 -> "1 névjegy törölve."
            else -> "$deleted névjegy törölve."
        }
        val errorText = when {
            failed == 0 -> null
            failed == 1 -> "1 névjegyet nem sikerült törölni."
            else -> "$failed névjegyet nem sikerült törölni."
        }
        return contactsPage(context, msg = message, error = errorText)
    }

    /** Névjegy küldése SMS-ben (név + szám szövegként). */
    fun handleContactShare(context: Context, body: String): String {
        val params = parseForm(body)
        val name = params["name"].orEmpty().trim()
        val phone = params["phone"].orEmpty().trim()
        val toRaw = params["to"].orEmpty().trim()

        if (name.isBlank() || phone.isBlank() || toRaw.isBlank()) {
            return contactsPage(context, error = "Add meg, kinek küldjem a névjegyet.")
        }

        // A címzett lehet szám vagy név.
        val to = if (toRaw.count { it.isDigit() } >= 6) {
            toRaw
        } else {
            val matches = try {
                ContactHelper.searchByName(context, toRaw)
            } catch (_: Exception) {
                emptyList()
            }
            when {
                matches.isEmpty() ->
                    return contactsPage(context, error = "Nincs ilyen névjegy: $toRaw")
                matches.size > 1 ->
                    return contactsPage(context, error = "Több találat erre: $toRaw. Írd be a teljes számot.")
                else -> matches.first().phone
            }
        }

        val message = "$name\n$phone"
        val ok = try {
            SmsHelper.send(context, to, message)
        } catch (e: Exception) {
            Log.w(TAG, "contact share failed", e)
            false
        }
        return if (ok) {
            contactsPage(context, msg = "Névjegy elküldve: $name → $to")
        } else {
            contactsPage(context, error = "Nem sikerült elküldeni a névjegyet.")
        }
    }

    fun handleContactAdd(context: Context, body: String): String {
        val params = parseForm(body)
        val name = params["name"].orEmpty().trim()
        val phone = params["phone"].orEmpty().trim()
        if (name.isBlank() || phone.isBlank()) {
            return contactsPage(context, error = "A név és a telefonszám is kötelező.")
        }
        val ok = try {
            ContactHelper.insertContact(context, name, phone)
        } catch (e: Exception) {
            Log.w(TAG, "insertContact failed", e)
            false
        }
        return if (ok) {
            contactsPage(context, msg = "Hozzáadva: $name")
        } else {
            contactsPage(context, error = "Nem sikerült hozzáadni.")
        }
    }

    // ==================== Jegyzetek ====================

    fun notesPage(context: Context, msg: String? = null): String {
        val notes = try {
            NoteStore.getAll(context)
        } catch (e: Exception) {
            Log.w(TAG, "notes getAll failed", e)
            emptyList()
        }

        val status = if (msg != null) """<p class="ok" role="status">${esc(msg)}</p>""" else ""

        val list = if (notes.isEmpty()) {
            "<p class='empty'>Még nincs jegyzet.</p>"
        } else {
            notes.joinToString("\n") { n ->
                """
                <article class="msg">
                  <h3>${esc(n.title)}</h3>
                  <p>${esc(n.body)}</p>
                </article>
                """.trimIndent()
            }
        }

        return header("Jegyzetek", "notes") + """
        <h2>Új jegyzet</h2>
        $status
        <form method="POST" action="/notes/add">
          <label for="ntitle">Cím</label>
          <input type="text" id="ntitle" name="title" required>
          <label for="nbody">Szöveg</label>
          <textarea id="nbody" name="body" rows="6" required></textarea>
          <button type="submit">Mentés</button>
        </form>

        <h2>Jegyzetek (${notes.size})</h2>
        $list
        """.trimIndent() + footer()
    }

    fun handleNoteAdd(context: Context, body: String): String {
        val params = parseForm(body)
        val title = params["title"].orEmpty().trim()
        val text = params["body"].orEmpty().trim()
        if (title.isBlank() || text.isBlank()) {
            return notesPage(context, msg = "A cím és a szöveg is kötelező.")
        }
        return try {
            NoteStore.add(context, title, text)
            notesPage(context, msg = "Jegyzet mentve: $title")
        } catch (e: Exception) {
            Log.w(TAG, "note add failed", e)
            notesPage(context, msg = "Nem sikerült menteni.")
        }
    }

    // ==================== Ébresztők ====================

    fun alarmsPage(context: Context, msg: String? = null, error: String? = null): String {
        val alarms = try {
            AlarmStore.getAll(context)
        } catch (e: Exception) {
            Log.w(TAG, "alarms getAll failed", e)
            emptyList()
        }

        val status = when {
            msg != null -> """<p class="ok" role="status">${esc(msg)}</p>"""
            error != null -> """<p class="err" role="alert">${esc(error)}</p>"""
            else -> ""
        }

        val list = if (alarms.isEmpty()) {
            "<p class='empty'>Nincs beállított ébresztő.</p>"
        } else {
            alarms.joinToString("\n") { a ->
                val time = "%02d:%02d".format(a.hour, a.minute)
                val state = if (a.enabled) "Bekapcsolva" else "Kikapcsolva"
                val repeat = when (a.repeatType.name) {
                    "DAILY" -> "minden nap"
                    "WEEKDAYS" -> "hétköznap"
                    "WEEKEND" -> "hétvégén"
                    "CUSTOM" -> "egyéni napokon"
                    else -> "egyszeri"
                }
                """
                <article class="msg">
                  <h3>$time – ${esc(a.label)}</h3>
                  <p>$state, $repeat${if (a.toneTitle != null) ", hang: ${esc(a.toneTitle)}" else ""}</p>
                  <form method="POST" action="/alarms/delete" class="inline">
                    <input type="hidden" name="id" value="${a.id}">
                    <button type="submit" class="danger">Törlés: $time ${esc(a.label)}</button>
                  </form>
                </article>
                """.trimIndent()
            }
        }

        return header("Ébresztők", "alarms") + """
        <h2>Új ébresztő</h2>
        $status
        <form method="POST" action="/alarms/add">
          <label for="atime">Időpont</label>
          <input type="time" id="atime" name="time" required value="07:00">
          <label for="alabel">Név</label>
          <input type="text" id="alabel" name="label" required placeholder="Például: gyógyszer">
          <label for="arepeat">Ismétlés</label>
          <select id="arepeat" name="repeat">
            <option value="ONCE">Egyszeri</option>
            <option value="DAILY">Minden nap</option>
            <option value="WEEKDAYS">Hétköznap</option>
            <option value="WEEKEND">Hétvégén</option>
          </select>
          <button type="submit">Ébresztő létrehozása</button>
        </form>

        <h2>Beállított ébresztők (${alarms.size})</h2>
        $list
        """.trimIndent() + footer()
    }

    fun handleAlarmAdd(context: Context, body: String): String {
        val params = parseForm(body)
        val time = params["time"].orEmpty().trim()
        val label = params["label"].orEmpty().trim()
        val repeat = params["repeat"].orEmpty().trim().ifBlank { "ONCE" }

        val parts = time.split(":")
        val hour = parts.getOrNull(0)?.toIntOrNull()
        val minute = parts.getOrNull(1)?.toIntOrNull()
        if (hour == null || minute == null || label.isBlank()) {
            return alarmsPage(context, error = "Az időpont és a név is kötelező.")
        }

        return try {
            val type = AlarmRepeatType.valueOf(repeat)
            val entry = AlarmStore.add(context, hour, minute, label, type)
            if (entry == null) {
                alarmsPage(context, error = "Nem sikerült létrehozni (elérted a maximumot?).")
            } else {
                AlarmScheduler.schedule(context, entry)
                alarmsPage(context, msg = "Ébresztő létrehozva: %02d:%02d – %s".format(hour, minute, label))
            }
        } catch (e: Exception) {
            Log.w(TAG, "alarm add failed", e)
            alarmsPage(context, error = "Nem sikerült létrehozni az ébresztőt.")
        }
    }

    fun handleAlarmDelete(context: Context, body: String): String {
        val id = parseForm(body)["id"]?.toIntOrNull()
            ?: return alarmsPage(context, error = "Hiányzó azonosító.")
        return try {
            val removed = AlarmStore.delete(context, id)
            if (removed != null) {
                AlarmScheduler.cancel(context, removed.id)
                alarmsPage(context, msg = "Ébresztő törölve: ${removed.label}")
            } else {
                alarmsPage(context, error = "Nincs ilyen ébresztő.")
            }
        } catch (e: Exception) {
            Log.w(TAG, "alarm delete failed", e)
            alarmsPage(context, error = "Nem sikerült törölni.")
        }
    }

    // ==================== Patika Őrangyal ====================

    /**
     * Gyógyszer-emlékeztetők kezelése a gépről.
     *
     * MIÉRT KELL: a diktálás sok gyógyszernevet nem ismer fel (Dedaxin,
     * Anti-pukitin, Fosadin...), mert nem köznyelvi szavak. Ezeket a gépen
     * begépelve pontosan fel lehet venni. Ez az oldal NEM helyettesíti a
     * telefonos flow-t, hanem kiegészíti ott, ahol az elakad.
     */
    fun medicationPage(context: Context, msg: String? = null, error: String? = null): String {
        val reminders = try {
            MedicationStore.getAll(context)
        } catch (e: Exception) {
            Log.w(TAG, "medication getAll failed", e)
            emptyList()
        }

        val status = when {
            msg != null -> """<p class="ok" role="status">${esc(msg)}</p>"""
            error != null -> """<p class="err" role="alert">${esc(error)}</p>"""
            else -> ""
        }

        val exactWarning = try {
            if (!MedicationScheduler.canScheduleExact(context)) {
                """<p class="err" role="alert">Figyelem: a pontos ébresztő engedély
                   hiányzik, ezért az emlékeztetők késhetnek. A telefonon, a
                   Beállítások menüben adható meg.</p>"""
            } else {
                ""
            }
        } catch (_: Exception) {
            ""
        }

        val list = if (reminders.isEmpty()) {
            "<p class='empty'>Nincs gyógyszer-emlékeztető.</p>"
        } else {
            reminders.joinToString("\n") { r ->
                val time = "%02d:%02d".format(r.hour, r.minute)
                val state = if (r.enabled) "Bekapcsolva" else "Kikapcsolva"
                val course = if (r.isCourse()) ", ${esc(r.speakCourse())}" else ", folyamatos"
                val toggleLabel = if (r.enabled) "Kikapcsolás" else "Bekapcsolás"
                """
                <article class="msg">
                  <h3>${esc(r.name)} – $time</h3>
                  <p>$state, ${esc(r.speakCycle())}$course</p>
                  <div class="actions">
                    <form method="POST" action="/medication/toggle" class="inline">
                      <input type="hidden" name="id" value="${r.id}">
                      <input type="hidden" name="enabled" value="${!r.enabled}">
                      <button type="submit" class="secondary">$toggleLabel: ${esc(r.name)}, $time</button>
                    </form>
                    <form method="POST" action="/medication/delete-confirm" class="inline">
                      <input type="hidden" name="id" value="${r.id}">
                      <button type="submit" class="danger">Törlés: ${esc(r.name)}, $time</button>
                    </form>
                  </div>
                </article>
                """.trimIndent()
            }
        }

        val bulkForm = if (reminders.isEmpty()) {
            ""
        } else {
            val checkboxes = reminders.joinToString("\n") { r ->
                val time = "%02d:%02d".format(r.hour, r.minute)
                """
                <div class="row">
                  <input type="checkbox" id="mpick-${r.id}" name="id" value="${r.id}" class="pick">
                  <label for="mpick-${r.id}" class="picklabel">${esc(r.name)}, $time, ${esc(r.speakCycle())}</label>
                </div>
                """.trimIndent()
            }
            """
            <h2>Több emlékeztető törlése</h2>
            <p class="hint">Pipáld ki, melyeket szeretnéd törölni, majd nyomd meg
              a gombot a lista végén. A törlés előtt még megerősítést kérünk.</p>
            <form method="POST" action="/medication/delete-confirm">
              <fieldset>
                <legend class="sr">Törlendő emlékeztetők kijelölése</legend>
                $checkboxes
              </fieldset>
              <button type="submit" class="danger">Kijelöltek törlése</button>
            </form>
            """.trimIndent()
        }

        val timeOfDayChecks = MedicationTimeOfDay.entries.joinToString("\n") { t ->
            val time = "%02d:%02d".format(t.hour, t.minute)
            """
            <div class="row">
              <input type="checkbox" id="tod-${t.name}" name="tod" value="${t.name}" class="pick">
              <label for="tod-${t.name}" class="picklabel">${esc(t.label)}, $time</label>
            </div>
            """.trimIndent()
        }

        val weekdayChecks = MedicationWeekdays.all.joinToString("\n") { d ->
            """
            <div class="row">
              <input type="checkbox" id="wd-${d.dayOfWeek}" name="weekday"
                     value="${d.dayOfWeek}" class="pick">
              <label for="wd-${d.dayOfWeek}" class="picklabel">${esc(d.label)}</label>
            </div>
            """.trimIndent()
        }

        return header("Patika Őrangyal", "medication") + """
        <h2>Új gyógyszer-emlékeztető</h2>
        $status
        $exactWarning
        <form method="POST" action="/medication/add">
          <label for="mname">Gyógyszer neve</label>
          <input type="text" id="mname" name="name" required
                 placeholder="Például: Dedaxin">
          <button type="button" class="secondary" onclick="pasteInto('mname')">
            Beillesztés a vágólapról a név mezőbe
          </button>
          <div id="paste-status" role="status" aria-live="polite" class="pastestatus"></div>

          <fieldset>
            <legend>Napszakok</legend>
            <p class="hint">Több is választható. Mindegyikből külön emlékeztető lesz.</p>
            $timeOfDayChecks
          </fieldset>

          <label for="mtime">Egyéni időpont (nem kötelező)</label>
          <p class="hint">Ha a napszakok nem jók, itt megadhatsz sajátot. A napszakokkal
            együtt is használható.</p>
          <input type="time" id="mtime" name="time">

          <label for="mcycle">Ismétlés</label>
          <select id="mcycle" name="cycle">
            <option value="DAILY">Naponta</option>
            <option value="WEEKLY">Hetente (egy nap)</option>
            <option value="CUSTOM">Egyéni napok</option>
          </select>

          <fieldset>
            <legend>Napok (csak Hetente vagy Egyéni napok esetén)</legend>
            <p class="hint">Naponta ismétlésnél hagyd üresen. Hetente esetén egy napot
              válassz.</p>
            $weekdayChecks
          </fieldset>

          <label for="mcourse">Kúra vége (nem kötelező)</label>
          <p class="hint">Ha megadod, az emlékeztető ezen a napon még szól, utána
            magától leáll. Például antibiotikumnál.</p>
          <input type="date" id="mcourse" name="courseEnd">

          <button type="submit">Emlékeztető létrehozása</button>
        </form>

        <h2>Gyógyszer-emlékeztetők (${reminders.size})</h2>
        $list
        $bulkForm
        ${clipboardScript()}
        """.trimIndent() + footer()
    }

    fun handleMedicationAdd(context: Context, body: String): String {
        val params = parseFormMulti(body)
        val name = params["name"]?.firstOrNull().orEmpty().trim()
        if (name.isBlank()) {
            return medicationPage(context, error = "A gyógyszer neve kötelező.")
        }

        // Napszakok és egyéni időpont ÖSSZEADÓDIK — mindkettő használható.
        val times = mutableListOf<Pair<Int, Int>>()
        params["tod"].orEmpty().forEach { raw ->
            MedicationTimeOfDay.entries.firstOrNull { it.name == raw }?.let {
                times.add(it.hour to it.minute)
            }
        }
        params["time"]?.firstOrNull()?.trim()?.takeIf { it.isNotBlank() }?.let { raw ->
            val parts = raw.split(":")
            val h = parts.getOrNull(0)?.toIntOrNull()
            val m = parts.getOrNull(1)?.toIntOrNull()
            if (h != null && m != null && h in 0..23 && m in 0..59) {
                times.add(h to m)
            }
        }
        // Ha ugyanaz az időpont napszakként és egyéniként is bejön, ne legyen
        // belőle két egyforma emlékeztető.
        val uniqueTimes = times.distinct()
        if (uniqueTimes.isEmpty()) {
            return medicationPage(
                context,
                error = "Válassz legalább egy napszakot, vagy adj meg egyéni időpontot."
            )
        }

        val cycleRaw = params["cycle"]?.firstOrNull().orEmpty().ifBlank { "DAILY" }
        val cycleType = MedicationCycleType.entries.firstOrNull { it.name == cycleRaw }
            ?: MedicationCycleType.DAILY

        val weekDays = params["weekday"].orEmpty().mapNotNull { it.toIntOrNull() }.toSet()
        if (cycleType != MedicationCycleType.DAILY && weekDays.isEmpty()) {
            return medicationPage(
                context,
                error = "A választott ismétléshez legalább egy napot ki kell jelölni."
            )
        }

        val courseEnd = params["courseEnd"]?.firstOrNull()?.trim()
            ?.takeIf { it.isNotBlank() }
            ?.let { parseCourseEndMillis(it) }

        return try {
            val added = MedicationStore.addMultipleTimes(
                context = context,
                name = name,
                times = uniqueTimes,
                cycleType = cycleType,
                weekDays = weekDays,
                courseEndMillis = courseEnd
            )
            if (added.isEmpty()) {
                return medicationPage(
                    context,
                    error = "Nem sikerült létrehozni. Elérted a maximumot (${MedicationStore.MAX_REMINDERS})?"
                )
            }
            // A mentés önmagában NEM ütemez — a MainActivity is külön hívja.
            // Enélkül a bejegyzés létezne, de sosem szólalna meg.
            var anyScheduled = false
            added.forEach {
                if (MedicationScheduler.scheduleAndReport(context, it)) anyScheduled = true
            }
            val timesText = added.joinToString(", ") { "%02d:%02d".format(it.hour, it.minute) }
            val note = if (anyScheduled) {
                ""
            } else {
                " Figyelem: pontos ébresztő engedély hiányzik, az emlékeztető késhet."
            }
            medicationPage(context, msg = "Emlékeztető létrehozva: $name, $timesText.$note")
        } catch (e: Exception) {
            Log.w(TAG, "medication add failed", e)
            medicationPage(context, error = "Nem sikerült létrehozni az emlékeztetőt.")
        }
    }

    /**
     * A kúra-vég dátumot a NAP VÉGÉRE állítjuk (23:59:59).
     *
     * MIÉRT: a MedicationScheduler úgy dönt, hogy a kúra lejárt-e, hogy a
     * következő riasztás időpontját hasonlítja ehhez. Ha a dátum éjfélre
     * mutatna, az aznapi utolsó adag már kimaradna — pont az, amit nem szabad.
     */
    private fun parseCourseEndMillis(raw: String): Long? {
        val parts = raw.split("-")
        val y = parts.getOrNull(0)?.toIntOrNull() ?: return null
        val mo = parts.getOrNull(1)?.toIntOrNull() ?: return null
        val d = parts.getOrNull(2)?.toIntOrNull() ?: return null
        return try {
            java.util.Calendar.getInstance().apply {
                set(java.util.Calendar.YEAR, y)
                set(java.util.Calendar.MONTH, mo - 1)
                set(java.util.Calendar.DAY_OF_MONTH, d)
                set(java.util.Calendar.HOUR_OF_DAY, 23)
                set(java.util.Calendar.MINUTE, 59)
                set(java.util.Calendar.SECOND, 59)
                set(java.util.Calendar.MILLISECOND, 0)
            }.timeInMillis
        } catch (_: Exception) {
            null
        }
    }

    fun handleMedicationToggle(context: Context, body: String): String {
        val params = parseForm(body)
        val id = params["id"]?.toIntOrNull()
            ?: return medicationPage(context, error = "Hiányzó azonosító.")
        val enabled = params["enabled"] == "true"
        return try {
            val updated = MedicationStore.setEnabled(context, id, enabled)
                ?: return medicationPage(context, error = "Nincs ilyen emlékeztető.")
            if (enabled) {
                MedicationScheduler.scheduleAndReport(context, updated)
                medicationPage(context, msg = "Bekapcsolva: ${updated.name}, ${updated.speakTime()}.")
            } else {
                // Kikapcsolásnál a beütemezett riasztást is vissza kell vonni,
                // különben megszólalna egy kikapcsolt emlékeztető.
                MedicationScheduler.cancel(context, updated.id)
                medicationPage(context, msg = "Kikapcsolva: ${updated.name}, ${updated.speakTime()}.")
            }
        } catch (e: Exception) {
            Log.w(TAG, "medication toggle failed", e)
            medicationPage(context, error = "Nem sikerült módosítani.")
        }
    }

    /**
     * Megerősítő oldal a gyógyszer-emlékeztető törléséhez.
     *
     * MIÉRT KELL ITT IS: ez egészségügyi funkció. Ha rossz sor törlődik, az
     * kimaradt adag — a lassabb, de biztos út itt megéri.
     */
    fun handleMedicationDeleteConfirm(context: Context, body: String): String {
        val ids = parseFormMulti(body)["id"].orEmpty().mapNotNull { it.toIntOrNull() }.distinct()
        if (ids.isEmpty()) {
            return medicationPage(context, error = "Nem jelöltél ki egy emlékeztetőt sem.")
        }

        val all = try {
            MedicationStore.getAll(context)
        } catch (e: Exception) {
            Log.w(TAG, "medication getAll failed", e)
            emptyList()
        }
        val picked = all.filter { it.id in ids }
        if (picked.isEmpty()) {
            return medicationPage(context, error = "A kijelölt emlékeztetők már nem találhatók.")
        }

        val items = picked.joinToString("\n") { r ->
            val time = "%02d:%02d".format(r.hour, r.minute)
            """<li>${esc(r.name)}, $time, ${esc(r.speakCycle())}</li>"""
        }
        val hidden = picked.joinToString("\n") { r ->
            """<input type="hidden" name="id" value="${r.id}">"""
        }
        val count = picked.size
        val headline = if (count == 1) {
            "Biztosan törlöd ezt a gyógyszer-emlékeztetőt?"
        } else {
            "Biztosan törlöd ezt a $count gyógyszer-emlékeztetőt?"
        }

        return header("Emlékeztető törlése", "medication") + """
        <h2>Megerősítés</h2>
        <p class="err" role="alert">$headline
          A törlés után ez a gyógyszer nem fog többé szólni. Nem lehet visszavonni.</p>
        <ul class="confirm-list">
          $items
        </ul>
        <form method="POST" action="/medication/delete">
          $hidden
          <button type="submit" class="danger">Igen, töröljem${if (count > 1) " mind a $count emlékeztetőt" else ""}</button>
        </form>
        <form method="GET" action="/medication">
          <button type="submit" class="secondary">Mégsem, vissza a Patika Őrangyalhoz</button>
        </form>
        """.trimIndent() + footer()
    }

    /** A tényleges törlés — ide csak a megerősítő oldalról lehet eljutni. */
    fun handleMedicationDelete(context: Context, body: String): String {
        val ids = parseFormMulti(body)["id"].orEmpty().mapNotNull { it.toIntOrNull() }.distinct()
        if (ids.isEmpty()) {
            return medicationPage(context, error = "Hiányzó azonosító.")
        }

        var deleted = 0
        var failed = 0
        val names = mutableListOf<String>()
        ids.forEach { id ->
            try {
                // SORREND: előbb a riasztás visszavonása, aztán a törlés.
                // Fordítva a bejegyzés eltűnne, de a beütemezett riasztás
                // megmaradna — kísértet-emlékeztető egy nem létező gyógyszerre.
                MedicationScheduler.cancel(context, id)
                val removed = MedicationStore.delete(context, id)
                if (removed != null) {
                    deleted++
                    names.add(removed.name)
                } else {
                    failed++
                }
            } catch (e: Exception) {
                Log.w(TAG, "medication delete failed for id=$id", e)
                failed++
            }
        }

        val message = when {
            deleted == 0 -> null
            deleted == 1 -> "Emlékeztető törölve: ${names.first()}."
            else -> "$deleted emlékeztető törölve: ${names.distinct().joinToString(", ")}."
        }
        val errorText = when {
            failed == 0 -> null
            failed == 1 -> "1 emlékeztetőt nem sikerült törölni."
            else -> "$failed emlékeztetőt nem sikerült törölni."
        }
        return medicationPage(context, msg = message, error = errorText)
    }

    // ==================== E-mail beállítások ====================

    /**
     * Az e-mail küldő és fogadó beállítása a gépről.
     *
     * MIÉRT KELL: a 16 karakteres Gmail alkalmazásjelszót gyakorlatilag
     * lehetetlen bediktálni — ez a portál eredeti indoka. Ráadásul a telefonos
     * flow CSAK Gmailt tud (gmailPreset van bedrótozva), itt viszont bármilyen
     * szolgáltató beállítható.
     *
     * A JELSZÓ SOHA nem íródik vissza az oldalra, még csillagozva sem.
     */
    fun emailPage(
        context: Context,
        msg: String? = null,
        error: String? = null,
        showAdvanced: Boolean = false
    ): String {
        val config = try {
            SmtpConfigStore.get(context)
        } catch (e: Exception) {
            Log.w(TAG, "smtp get failed", e)
            null
        }

        val status = when {
            msg != null -> """<p class="ok" role="status">${esc(msg)}</p>"""
            error != null -> """<p class="err" role="alert">${esc(error)}</p>"""
            else -> ""
        }

        val current = if (config == null) {
            "<p class='empty'>Nincs beállított e-mail fiók.</p>"
        } else {
            val tls = if (config.useTls) "igen" else "nem"
            """
            <article class="msg">
              <h3>Jelenlegi beállítás</h3>
              <p>Feladó: ${esc(config.fromName.ifBlank { "(nincs név)" })}, ${esc(config.fromEmail)}</p>
              <p>Küldő szerver: ${esc(config.host)}, port ${config.port}, titkosítás: $tls</p>
              <p>Bejövő szerver: ${esc(config.resolvedImapHost())}, port ${config.resolvedImapPort()}${
                if (config.imapHost.isBlank()) " (a küldő szerverből kitalálva)" else ""
            }</p>
              <p>Felhasználónév: ${esc(config.username)}</p>
              <p class="time">A jelszó mentve van. Biztonsági okból nem jelenik meg.</p>
              <div class="actions">
                <form method="POST" action="/email/test" class="inline">
                  <button type="submit" class="secondary">Kapcsolat tesztelése</button>
                </form>
                <form method="POST" action="/email/delete-confirm" class="inline">
                  <button type="submit" class="danger">Beállítás törlése</button>
                </form>
              </div>
            </article>
            """.trimIndent()
        }

        // MIÉRT FIGYELMEZTETÉS: a portál nem HTTPS, a jelszó nyílt szövegben
        // utazik a helyi hálózaton. Otthon ez vállalható, egy nyilvános WiFi-n
        // nem. Ezt a felhasználónak tudnia kell, MIELŐTT beírja.
        val securityNote = """
        <p class="err" role="note">Fontos: ez a portál a saját WiFi-den fut,
          titkosítás nélkül. A jelszót csak olyan hálózaton add meg, amiben
          megbízol (otthoni WiFi). Nyilvános WiFi-n inkább a telefonon állítsd be.
          A jelszó a telefonra érve titkosítva tárolódik.</p>
        """.trimIndent()

        val advancedForm = if (!showAdvanced) {
            """
            <h2>Haladó beállítás (nem Gmail)</h2>
            <p class="hint">Ha nem Gmailt használsz, itt megadhatod a szerver
              adatait kézzel. A telefonon ez nem állítható be, csak itt.</p>
            <form method="GET" action="/email">
              <input type="hidden" name="advanced" value="1">
              <button type="submit" class="secondary">Haladó beállítás megnyitása</button>
            </form>
            """.trimIndent()
        } else {
            val c = config
            """
            <h2>Haladó beállítás</h2>
            <form method="POST" action="/email/save-advanced">
              <label for="ehost">Küldő szerver (SMTP)</label>
              <input type="text" id="ehost" name="host" required
                     value="${esc(c?.host.orEmpty())}" placeholder="Például: smtp.freemail.hu">

              <label for="eport">Küldő port</label>
              <input type="number" id="eport" name="port" required min="1" max="65535"
                     value="${c?.port ?: 587}">

              <label for="etls">Titkosítás (STARTTLS)</label>
              <select id="etls" name="tls">
                <option value="true"${if (c == null || c.useTls) " selected" else ""}>Igen (ajánlott)</option>
                <option value="false"${if (c != null && !c.useTls) " selected" else ""}>Nem</option>
              </select>

              <label for="eimaphost">Bejövő szerver (IMAP)</label>
              <p class="hint">Ha üresen hagyod, a küldő szerverből próbáljuk kitalálni.</p>
              <input type="text" id="eimaphost" name="imapHost"
                     value="${esc(c?.imapHost.orEmpty())}" placeholder="Például: imap.freemail.hu">

              <label for="eimapport">Bejövő port</label>
              <input type="number" id="eimapport" name="imapPort" min="1" max="65535"
                     value="${c?.imapPort ?: 993}">

              <label for="euser">Felhasználónév</label>
              <input type="text" id="euser" name="username" required autocomplete="off"
                     value="${esc(c?.username.orEmpty())}">
              <button type="button" class="secondary" onclick="pasteInto('euser')">
                Beillesztés a vágólapról a felhasználónév mezőbe
              </button>

              <label for="epass">Jelszó</label>
              <input type="password" id="epass" name="password" required autocomplete="off"
                     placeholder="${if (c != null) "Hagyd üresen, ha nem változik" else ""}">
              <button type="button" class="secondary" onclick="pasteInto('epass')">
                Beillesztés a vágólapról a jelszó mezőbe
              </button>

              <label for="efrom">Feladó e-mail cím</label>
              <input type="text" id="efrom" name="fromEmail" required
                     value="${esc(c?.fromEmail.orEmpty())}">

              <label for="efromname">Feladó neve (nem kötelező)</label>
              <input type="text" id="efromname" name="fromName"
                     value="${esc(c?.fromName.orEmpty())}">

              <button type="submit">Mentés és tesztelés</button>
            </form>
            """.trimIndent()
        }

        return header("E-mail", "email") + """
        <h2>E-mail fiók</h2>
        $status
        $securityNote
        $current

        <h2>Gyors beállítás (Gmail)</h2>
        <p class="hint">Gmailhez alkalmazásjelszó kell, a rendes jelszó nem
          működik. A Google fiókod biztonsági beállításainál hozhatsz létre
          egyet: 16 karakter, szóközök nélkül is beírható.</p>
        <form method="POST" action="/email/save-gmail">
          <label for="gmailaddr">Gmail cím</label>
          <input type="text" id="gmailaddr" name="username" required autocomplete="off"
                 placeholder="valaki@gmail.com">
          <button type="button" class="secondary" onclick="pasteInto('gmailaddr')">
            Beillesztés a vágólapról a cím mezőbe
          </button>

          <label for="gmailpass">Alkalmazásjelszó</label>
          <input type="password" id="gmailpass" name="password" required autocomplete="off">
          <button type="button" class="secondary" onclick="pasteInto('gmailpass')">
            Beillesztés a vágólapról a jelszó mezőbe
          </button>

          <label for="gmailname">A neved (nem kötelező)</label>
          <input type="text" id="gmailname" name="fromName"
                 placeholder="Ez jelenik meg feladóként">

          <div id="paste-status" role="status" aria-live="polite" class="pastestatus"></div>
          <button type="submit">Mentés és tesztelés</button>
        </form>

        $advancedForm
        ${clipboardScript()}
        """.trimIndent() + footer()
    }

    fun handleEmailSaveGmail(context: Context, body: String): String {
        val params = parseForm(body)
        val username = params["username"].orEmpty().trim()
        val password = params["password"].orEmpty()
        val fromName = params["fromName"].orEmpty().trim()

        if (username.isBlank() || password.isBlank()) {
            return emailPage(context, error = "A Gmail cím és az alkalmazásjelszó is kötelező.")
        }
        if (!EmailHelper.isValidEmail(username)) {
            return emailPage(context, error = "A megadott cím nem érvényes e-mail cím: $username")
        }

        // A Gmail alkalmazásjelszót a Google 4-es csoportokban mutatja
        // ("abcd efgh ijkl mnop"), de szóközök nélkül kell. Ha valaki a
        // szóközökkel együtt másolja be, azt itt csendben rendbe tesszük —
        // különben egy láthatatlan szóköz miatt bukna a bejelentkezés.
        val cleanPassword = password.replace(" ", "")

        val config = SmtpConfigStore.gmailPreset(username, cleanPassword, fromName)
        return saveAndTest(context, config, "Gmail")
    }

    fun handleEmailSaveAdvanced(context: Context, body: String): String {
        val params = parseForm(body)
        val host = params["host"].orEmpty().trim()
        val port = params["port"]?.toIntOrNull()
        val imapHost = params["imapHost"].orEmpty().trim()
        val imapPort = params["imapPort"]?.toIntOrNull() ?: 993
        val username = params["username"].orEmpty().trim()
        val passwordRaw = params["password"].orEmpty()
        val fromEmail = params["fromEmail"].orEmpty().trim()
        val fromName = params["fromName"].orEmpty().trim()
        val useTls = params["tls"] != "false"

        if (host.isBlank() || port == null || port !in 1..65535) {
            return emailPage(context, error = "A küldő szerver és egy érvényes port kötelező.", showAdvanced = true)
        }
        if (username.isBlank()) {
            return emailPage(context, error = "A felhasználónév kötelező.", showAdvanced = true)
        }
        if (!EmailHelper.isValidEmail(fromEmail)) {
            return emailPage(context, error = "A feladó cím nem érvényes e-mail cím.", showAdvanced = true)
        }

        // Üres jelszó + létező beállítás = "ne változtass a jelszón".
        // Enélkül a felhasználónak minden apró módosításnál (pl. feladó név)
        // újra be kellene írnia a 16 karaktert.
        val existing = try {
            SmtpConfigStore.get(context)
        } catch (_: Exception) {
            null
        }
        val password = if (passwordRaw.isBlank()) {
            existing?.password.orEmpty()
        } else {
            passwordRaw.replace(" ", "")
        }
        if (password.isBlank()) {
            return emailPage(context, error = "A jelszó kötelező.", showAdvanced = true)
        }

        val config = SmtpConfig(
            host = host,
            port = port,
            username = username,
            password = password,
            fromEmail = fromEmail,
            fromName = fromName,
            useTls = useTls,
            imapHost = imapHost,
            imapPort = imapPort
        )
        return saveAndTest(context, config, "E-mail")
    }

    /**
     * Mentés, majd azonnali tesztelés.
     *
     * MIÉRT MENTÜNK TESZT ELŐTT: ha a teszt hibát talál, a beállítás akkor is
     * megmarad, és a haladó űrlapon javítható — nem kell mindent újra beírni.
     * A hibaüzenetet viszont kimondjuk, hogy tudja: van beállítás, de nem jó.
     */
    private fun saveAndTest(context: Context, config: SmtpConfig, label: String): String {
        return try {
            SmtpConfigStore.save(context, config)
            val result = SmtpTester.testAll(config)
            if (result.ok) {
                emailPage(context, msg = "$label beállítás mentve. ${result.message}")
            } else {
                emailPage(
                    context,
                    error = "A beállítás mentve, DE a teszt hibát talált: ${result.message}",
                    showAdvanced = true
                )
            }
        } catch (e: Exception) {
            Log.w(TAG, "smtp save failed", e)
            emailPage(context, error = "Nem sikerült menteni a beállítást.")
        }
    }

    fun handleEmailTest(context: Context): String {
        val config = try {
            SmtpConfigStore.get(context)
        } catch (e: Exception) {
            null
        } ?: return emailPage(context, error = "Nincs mit tesztelni: nincs beállított fiók.")

        return try {
            val result = SmtpTester.testAll(config)
            if (result.ok) {
                emailPage(context, msg = result.message)
            } else {
                emailPage(context, error = result.message)
            }
        } catch (e: Exception) {
            Log.w(TAG, "smtp test failed", e)
            emailPage(context, error = "A teszt nem futott le: ${e.message ?: "ismeretlen hiba"}")
        }
    }

    /**
     * Megerősítő oldal a beállítás törléséhez.
     *
     * MIÉRT: a jelszó titkosítva van tárolva, kiolvasni nem lehet. Ha törlöd,
     * elő kell venni újra a Google-tól — vagy új alkalmazásjelszót generálni.
     */
    fun handleEmailDeleteConfirm(context: Context): String {
        val config = try {
            SmtpConfigStore.get(context)
        } catch (e: Exception) {
            null
        } ?: return emailPage(context, error = "Nincs beállított fiók.")

        return header("E-mail törlése", "email") + """
        <h2>Megerősítés</h2>
        <p class="err" role="alert">Biztosan törlöd az e-mail beállítást?
          Ezután nem tudsz e-mailt küldeni és olvasni, amíg újra be nem
          állítod. A jelszó nem visszaszerezhető: újra be kell majd írnod.</p>
        <ul class="confirm-list">
          <li>Feladó: ${esc(config.fromEmail)}</li>
          <li>Küldő szerver: ${esc(config.host)}, port ${config.port}</li>
        </ul>
        <form method="POST" action="/email/delete">
          <button type="submit" class="danger">Igen, töröljem a beállítást</button>
        </form>
        <form method="GET" action="/email">
          <button type="submit" class="secondary">Mégsem, vissza az e-mail beállításokhoz</button>
        </form>
        """.trimIndent() + footer()
    }

    fun handleEmailDelete(context: Context): String {
        return try {
            SmtpConfigStore.clear(context)
            emailPage(context, msg = "Az e-mail beállítás törölve.")
        } catch (e: Exception) {
            Log.w(TAG, "smtp clear failed", e)
            emailPage(context, error = "Nem sikerült törölni.")
        }
    }

    // ==================== Beállítás állapot (setup) ====================

    /**
     * Mi hiányzik a telefonról — a gépről nézve.
     *
     * MIÉRT NINCS RAJTA KAPCSOLÓ: az Android SZÁNDÉKOSAN tiltja, hogy engedélyt
     * távolról, felhasználói érintés nélkül meg lehessen adni. Egy weboldal nem
     * kattinthat rá a rendszer engedélykérésére — ez biztonsági alapelv, nem
     * hiányosság. Ha ide kapcsolót tennénk, az hazugság lenne.
     *
     * AMIRE VISZONT JÓ: a segítő (családtag, támogató) LÁTJA, mi hiányzik, és
     * pontosan el tudja mondani telefonon, mit kell megnyomni. A telefonon a
     * Beállítás varázsló vezet végig — ez az oldal ahhoz ad térképet.
     */
    fun setupPage(context: Context): String {
        val all = try {
            SetupRequirements.all(context)
        } catch (e: Exception) {
            Log.w(TAG, "setup requirements failed", e)
            emptyList()
        }

        if (all.isEmpty()) {
            return header("Beállítás állapot", "setup") + """
            <h2>Beállítás állapot</h2>
            <p class="err" role="alert">Az állapot most nem kérdezhető le.</p>
            """.trimIndent() + footer()
        }

        val missing = all.filter { !it.granted }
        val granted = all.filter { it.granted }

        val summary = if (missing.isEmpty()) {
            """<p class="ok" role="status">Minden engedély megvan.
               A SuperDL teljes egészében működik.</p>"""
        } else {
            val essential = missing.count { it.severity == SetupRequirements.Severity.ESSENTIAL }
            val important = missing.count { it.severity == SetupRequirements.Severity.IMPORTANT }
            val optional = missing.count { it.severity == SetupRequirements.Severity.OPTIONAL }
            val parts = mutableListOf<String>()
            if (essential > 0) parts.add("$essential alapvető")
            if (important > 0) parts.add("$important fontos")
            if (optional > 0) parts.add("$optional kiegészítő")
            val cls = if (essential > 0) "err" else "hint"
            val role = if (essential > 0) "alert" else "status"
            """<p class="$cls" role="$role">Hiányzik ${parts.joinToString(", ")} engedély.</p>"""
        }

        val missingHtml = if (missing.isEmpty()) {
            ""
        } else {
            val items = missing.joinToString("\n") { req -> requirementCard(req) }
            """
            <h2>Hiányzó engedélyek (${missing.size})</h2>
            <p class="hint">Ezeket csak a telefonon lehet megadni — az Android
              biztonsági okból nem engedi távolról. A telefonon:
              Beállítások, Beállítás varázsló. Az alábbi útmutatók segítenek
              elmondani, mit keressen.</p>
            $items
            """.trimIndent()
        }

        val grantedHtml = if (granted.isEmpty()) {
            ""
        } else {
            val items = granted.joinToString("\n") { req ->
                """<li>${esc(req.title)} — ${esc(req.severityLabel())}</li>"""
            }
            """
            <h2>Megvan (${granted.size})</h2>
            <ul class="confirm-list">
              $items
            </ul>
            """.trimIndent()
        }

        return header("Beállítás állapot", "setup") + """
        <h2>Beállítás állapot</h2>
        $summary
        $missingHtml
        $grantedHtml
        """.trimIndent() + footer()
    }

    /** Egy hiányzó tétel: mi az, mi nem megy miatta, és hogyan adható meg. */
    private fun requirementCard(req: SetupRequirements.Requirement): String {
        val guideHtml = req.guide?.let { type ->
            val sections = try {
                PermissionGuideTexts.sections(type)
            } catch (e: Exception) {
                emptyList()
            }
            if (sections.isEmpty()) {
                ""
            } else {
                val body = sections.joinToString("\n") { s ->
                    """
                    <h4>${esc(s.title)}</h4>
                    <p>${esc(s.body)}</p>
                    """.trimIndent()
                }
                """
                <details>
                  <summary>Útmutató: hogyan adható meg</summary>
                  $body
                </details>
                """.trimIndent()
            }
        }.orEmpty()

        val where = when (req.kind) {
            SetupRequirements.RequestKind.RUNTIME ->
                "A telefon rákérdez, amikor a varázslóban jobbra söpörsz."
            SetupRequirements.RequestKind.ROLE ->
                "A rendszer szerepkör-választó képernyőjén kell kiválasztani a SuperDL-t."
            SetupRequirements.RequestKind.SYSTEM_SCREEN ->
                "A rendszer beállításai között kell bekapcsolni."
        }

        return """
        <article class="msg">
          <h3>${esc(req.title)} — ${esc(req.severityLabel())}</h3>
          <p>${esc(req.whatBreaks)}</p>
          <p class="time">${esc(where)}</p>
          $guideHtml
        </article>
        """.trimIndent()
    }

    // ==================== Mentés és visszaállítás ====================

    /**
     * A beállítások mentése fájlba és visszaállítása.
     *
     * MIÉRT A PORTÁLON: a mentés-fájlt valahová el kell tenni — a gép a
     * természetes hely. Innen letölthető, e-mailben elküldhető, pendrive-ra
     * másolható, és új telefonon visszatölthető.
     */
    fun backupPage(
        context: Context,
        msg: String? = null,
        error: String? = null
    ): String {
        val summary = try {
            BackupManager.exportSummary(context)
        } catch (e: Exception) {
            Log.w(TAG, "backup summary failed", e)
            null
        }

        val status = when {
            msg != null -> """<p class="ok" role="status">${esc(msg)}</p>"""
            error != null -> """<p class="err" role="alert">${esc(error)}</p>"""
            else -> ""
        }

        val what = if (summary == null) {
            """<p class="err" role="alert">A mentés most nem készíthető el.</p>"""
        } else {
            """
            <article class="msg">
              <h3>Mit tartalmaz a mentés</h3>
              <p>${summary.keyCount} beállítás, ${summary.fileCount} csoportban.</p>
              <p class="time">Ébresztők, gyógyszer emlékeztetők, jegyzetek, kedvencek,
                névjegyekhez rendelt csengőhangok, mentett helyek és útvonalak,
                könyvjelzők, hang- és őrség-beállítások.</p>
            </article>
            """.trimIndent()
        }

        return header("Mentés", "backup") + """
        <h2>Mentés és visszaállítás</h2>
        $status
        $what

        <h2>Mentés letöltése</h2>
        <p class="hint">A fájlt tedd biztos helyre: e-mail, felhő, pendrive.
          Ha elveszik vagy elromlik a telefon, ebből minden visszaállítható.</p>
        <form method="GET" action="/backup/download">
          <button type="submit">Mentés letöltése fájlba</button>
        </form>

        <h2>Visszaállítás</h2>
        <p class="err" role="note">Figyelem: a visszaállítás FELÜLÍRJA a telefon
          mostani beállításait azzal, ami a fájlban van. Amit a fájl nem tartalmaz,
          az érintetlen marad.</p>
        <p class="hint">Amit a mentés nem tud átvinni, mert a telefon hardveréhez
          kötött: az e-mail jelszó (újra be kell írni) és az engedélyek
          (a Beállítás varázslóval adhatók meg újra).</p>
        <form method="POST" action="/backup/restore-confirm" enctype="multipart/form-data">
          <label for="bfile">Mentés fájl kiválasztása</label>
          <input type="file" id="bfile" name="backup" accept=".json,application/json" required>
          <button type="submit" class="secondary">Fájl beolvasása</button>
        </form>
        """.trimIndent() + footer()
    }

    /** A mentés JSON szövege — a szerver ezt küldi le fájlként. */
    fun backupJson(context: Context): String =
        try {
            BackupManager.export(context).toString(2)
        } catch (e: Exception) {
            Log.w(TAG, "backup export failed", e)
            """{"error":"export failed"}"""
        }

    /**
     * Megerősítő oldal a visszaállítás előtt.
     *
     * MIÉRT KÉT LÉPÉS: a visszaállítás felülírja a működő beállításokat, és
     * nincs visszavonás. Előbb megmutatjuk, MI van a fájlban — melyik telefonról,
     * mikor, hány beállítás —, és csak utána írjuk vissza.
     */
    fun backupRestoreConfirm(context: Context, fileContent: String): String {
        if (fileContent.isBlank()) {
            return backupPage(context, error = "Nem érkezett fájl, vagy üres volt.")
        }

        val root = try {
            org.json.JSONObject(fileContent)
        } catch (e: Exception) {
            return backupPage(context, error = "A fájl nem érvényes SuperDL mentés.")
        }

        val format = root.optInt("format", -1)
        if (format < 1) {
            return backupPage(context, error = "A fájl nem SuperDL mentés, vagy sérült.")
        }

        val keyCount = root.optInt("key_count")
        val device = root.optString("device").ifBlank { "ismeretlen készülék" }
        val appVersion = root.optString("app_version").ifBlank { "ismeretlen verzió" }
        val createdAt = root.optLong("created_at")
        val created = if (createdAt > 0) {
            java.text.SimpleDateFormat("yyyy. MM. dd. HH:mm", java.util.Locale("hu"))
                .format(java.util.Date(createdAt))
        } else {
            "ismeretlen időpont"
        }

        // A fájl tartalmát rejtett mezőben visszük tovább, hogy ne kelljen
        // ideiglenesen a telefonra írni.
        val escaped = esc(fileContent)

        return header("Visszaállítás", "backup") + """
        <h2>Megerősítés</h2>
        <p class="err" role="alert">Biztosan visszaállítod ezt a mentést?
          A telefon mostani beállításai felülíródnak azzal, ami a fájlban van.
          Ez nem vonható vissza.</p>
        <ul class="confirm-list">
          <li>Készült: $created</li>
          <li>Készülék: ${esc(device)}</li>
          <li>SuperDL verzió: ${esc(appVersion)}</li>
          <li>Beállítások száma: $keyCount</li>
        </ul>
        <form method="POST" action="/backup/restore">
          <input type="hidden" name="payload" value="$escaped">
          <button type="submit" class="danger">Igen, állítsd vissza</button>
        </form>
        <form method="GET" action="/backup">
          <button type="submit" class="secondary">Mégsem, vissza</button>
        </form>
        """.trimIndent() + footer()
    }

    fun handleBackupRestore(context: Context, body: String): String {
        val params = parseForm(body)
        val payload = params["payload"].orEmpty()
        if (payload.isBlank()) {
            return backupPage(context, error = "Nem érkezett adat a visszaállításhoz.")
        }
        return try {
            val result = BackupManager.restore(context, payload)
            if (result.ok) {
                backupPage(context, msg = result.message)
            } else {
                backupPage(context, error = result.message)
            }
        } catch (e: Exception) {
            Log.w(TAG, "restore failed", e)
            backupPage(context, error = "A visszaállítás nem sikerült: ${e.message ?: "ismeretlen hiba"}")
        }
    }

    // ==================== Diagnosztika ====================

    /**
     * Mi NEM működik és miért — a gépről nézve.
     *
     * MIÉRT KÜLÖN A /setup-tól: a /setup azt mondja meg, mi HIÁNYZIK (engedély).
     * Ez azt, hogy mi NEM FOG MŰKÖDNI, akkor is, ha minden engedély megvan:
     * altatja-e a rendszer az appot, van-e élő gyógyszer-emlékeztető, van-e hely.
     */
    fun diagnosticsPage(context: Context): String {
        val checks = try {
            DiagnosticsReport.runAll(context)
        } catch (e: Exception) {
            Log.w(TAG, "diagnostics failed", e)
            emptyList()
        }

        if (checks.isEmpty()) {
            return header("Diagnosztika", "diagnostics") + """
            <h2>Diagnosztika</h2>
            <p class="err" role="alert">A diagnosztika most nem futtatható.</p>
            """.trimIndent() + footer()
        }

        val fails = checks.count { it.level == DiagnosticsReport.Level.FAIL }
        val warns = checks.count { it.level == DiagnosticsReport.Level.WARN }

        val summary = when {
            fails > 0 -> """<p class="err" role="alert">$fails hiba
                ${if (warns > 0) "és $warns figyelmeztetés" else ""} — ezek miatt
                bizonyos funkciók nem fognak működni.</p>"""
            warns > 0 -> """<p class="hint" role="status">$warns figyelmeztetés.</p>"""
            else -> """<p class="ok" role="status">Minden rendben. Nem találtam problémát.</p>"""
        }

        // A hibák előre: a sorrend maga is információ.
        val ordered = checks.sortedBy {
            when (it.level) {
                DiagnosticsReport.Level.FAIL -> 0
                DiagnosticsReport.Level.WARN -> 1
                DiagnosticsReport.Level.OK -> 2
            }
        }

        val items = ordered.joinToString("\n") { check ->
            val cls = when (check.level) {
                DiagnosticsReport.Level.FAIL -> "err"
                DiagnosticsReport.Level.WARN -> "hint"
                DiagnosticsReport.Level.OK -> "ok"
            }
            val actionHtml = check.action?.let {
                """<p class="time">Mit tegyél: ${esc(it)}</p>"""
            }.orEmpty()
            """
            <article class="msg">
              <h3>${esc(check.title)} — ${esc(check.levelLabel())}</h3>
              <p class="$cls">${esc(check.detail)}</p>
              $actionHtml
            </article>
            """.trimIndent()
        }

        return header("Diagnosztika", "diagnostics") + """
        <h2>Diagnosztika</h2>
        $summary
        <p class="hint">Ez az oldal azt mutatja, mi nem fog működni — akkor is,
          ha minden engedély megvan. Az engedélyekről a Beállítás fül szól.</p>
        $items
        """.trimIndent() + footer()
    }

    // ==================== Emlékhelyek ====================

    fun placesPage(context: Context, msg: String? = null): String {
        val places = try {
            SavedPoiStore.getAll(context)
        } catch (e: Exception) {
            Log.w(TAG, "places getAll failed", e)
            emptyList()
        }

        val status = if (msg != null) """<p class="ok" role="status">${esc(msg)}</p>""" else ""

        val list = if (places.isEmpty()) {
            "<p class='empty'>Még nincs mentett hely.</p>"
        } else {
            places.joinToString("\n") { p ->
                val voice = if (p.voiceNotePath != null) " – van hangjegyzet" else ""
                """
                <article class="msg">
                  <h3>${esc(p.name)}</h3>
                  <p class="time">${"%.5f".format(p.latitude)}, ${"%.5f".format(p.longitude)}$voice</p>
                  <form method="POST" action="/places/delete" class="inline">
                    <input type="hidden" name="id" value="${esc(p.id)}">
                    <button type="submit" class="danger">Törlés: ${esc(p.name)}</button>
                  </form>
                </article>
                """.trimIndent()
            }
        }

        return header("Emlékhelyek", "places") + """
        <h2>Mentett helyek (${places.size})</h2>
        $status
        $list
        <p class="hint">Új helyet a telefonon tudsz menteni (ott van a GPS).
        Itt átnézheted és törölheted őket.</p>
        """.trimIndent() + footer()
    }

    fun handlePlaceDelete(context: Context, body: String): String {
        val id = parseForm(body)["id"].orEmpty()
        if (id.isBlank()) return placesPage(context, msg = "Hiányzó azonosító.")
        return try {
            val ok = SavedPoiStore.remove(context, id)
            placesPage(context, msg = if (ok) "Hely törölve." else "Nem sikerült törölni.")
        } catch (e: Exception) {
            Log.w(TAG, "place delete failed", e)
            placesPage(context, msg = "Nem sikerült törölni.")
        }
    }

    // ==================== Podcast ====================

    fun podcastPage(context: Context, msg: String? = null): String {
        val subs = try {
            PodcastStore.getSubscriptions(context)
        } catch (e: Exception) {
            Log.w(TAG, "podcast subs failed", e)
            emptyList()
        }
        val country = try {
            PodcastStore.countryName(PodcastStore.getCountry(context))
        } catch (_: Exception) {
            "Magyarország"
        }

        val status = if (msg != null) """<p class="ok" role="status">${esc(msg)}</p>""" else ""

        val list = if (subs.isEmpty()) {
            "<p class='empty'>Még nincs feliratkozás.</p>"
        } else {
            subs.joinToString("\n") { p ->
                """
                <article class="msg">
                  <h3>${esc(p.title)}</h3>
                  <p class="time">${esc(p.author)}</p>
                </article>
                """.trimIndent()
            }
        }

        return header("Podcast", "podcast") + """
        <h2>Feliratkozás RSS címmel</h2>
        $status
        <p class="hint">Ha van egy podcast RSS címed, itt beillesztheted –
        gépelni sokkal könnyebb, mint bediktálni egy hosszú URL-t.</p>
        <form method="POST" action="/podcast/add">
          <label for="feed">RSS feed cím</label>
          <input type="url" id="feed" name="feed" required
                 placeholder="https://example.com/feed.xml">
          <label for="ptitle">Név (opcionális)</label>
          <input type="text" id="ptitle" name="title" placeholder="A podcast neve">
          <button type="submit">Feliratkozás</button>
        </form>

        <h2>Feliratkozásaim (${subs.size})</h2>
        $list
        <p class="hint">Beállított ország: $country</p>
        """.trimIndent() + footer()
    }

    fun handlePodcastAdd(context: Context, body: String): String {
        val params = parseForm(body)
        val feed = params["feed"].orEmpty().trim()
        val title = params["title"].orEmpty().trim().ifBlank { "Podcast" }
        if (feed.isBlank() || !feed.startsWith("http")) {
            return podcastPage(context, msg = "Érvényes RSS címet adj meg.")
        }
        return try {
            val podcast = com.superdl.launcher.podcast.Podcast(
                id = feed.hashCode().toString(),
                title = title,
                author = "",
                feedUrl = feed
            )
            PodcastStore.toggleSubscription(context, podcast)
            podcastPage(context, msg = "Feliratkozva: $title")
        } catch (e: Exception) {
            Log.w(TAG, "podcast add failed", e)
            podcastPage(context, msg = "Nem sikerült feliratkozni.")
        }
    }

    // ==================== Állapot ====================

    fun mediaPage(context: Context): String {
        val audio = try { PortalMediaHelper.listAudio(context) } catch (_: Exception) { emptyList() }
        val photos = try { PortalMediaHelper.listPhotos(context) } catch (_: Exception) { emptyList() }

        fun sizeLabel(bytes: Long): String = when {
            bytes >= 1024 * 1024 -> "%.1f MB".format(bytes / (1024.0 * 1024.0))
            bytes >= 1024 -> "%.0f KB".format(bytes / 1024.0)
            else -> "$bytes B"
        }

        fun row(e: PortalMediaHelper.MediaEntry): String = """
            <li class="media-item">
              <span class="media-name">${esc(e.displayName)}</span>
              <span class="media-size">${sizeLabel(e.sizeBytes)}</span>
              <a class="btn download" href="/media/download?token=${e.token}"
                 download aria-label="Letöltés: ${esc(e.displayName)}">Letöltés</a>
            </li>
        """.trimIndent()

        val photosSection = if (photos.isEmpty()) {
            "<p>Nincs a SuperDL kamerájával készült fotó.</p>"
        } else {
            "<ul class=\"media-list\">" + photos.joinToString("") { row(it) } + "</ul>"
        }
        val audioSection = if (audio.isEmpty()) {
            "<p>Nincs hangfelvétel (diktafon, hangjegyzet vagy rádió-felvétel).</p>"
        } else {
            "<ul class=\"media-list\">" + audio.joinToString("") { row(it) } + "</ul>"
        }

        return header("Fotók és hangok", "media") + """
            <h2>Fotók és hangok kimentése</h2>
            <p>Itt letöltheted a telefonon a SuperDL-lel készült fotókat és
               hangfelvételeket a számítógépedre.</p>
            <section aria-labelledby="photos-h">
              <h3 id="photos-h">Fotók (${photos.size})</h3>
              $photosSection
            </section>
            <section aria-labelledby="audio-h">
              <h3 id="audio-h">Hangfelvételek (${audio.size})</h3>
              $audioSection
            </section>
        """.trimIndent() + footer()
    }

    fun radioPage(context: Context, msg: String? = null, error: String? = null): String {
        val saved = try {
            com.superdl.launcher.radio.RadioStore.getStations(context)
        } catch (_: Exception) {
            emptyList()
        }

        val rows = if (saved.isEmpty()) {
            "<p>Még nincs saját mentett állomásod. Add hozzá alább egy URL-lel.</p>"
        } else {
            "<ul class=\"media-list\">" + saved.joinToString("") { s ->
                """
                <li class="media-item">
                  <span class="media-name">${esc(s.name)}</span>
                  <span class="media-size">${esc(s.streamUrl)}</span>
                  <form method="POST" action="/radio/delete" style="display:inline">
                    <input type="hidden" name="id" value="${esc(s.id)}">
                    <button type="submit" class="btn secondary"
                            aria-label="Törlés: ${esc(s.name)}">Törlés</button>
                  </form>
                </li>
                """.trimIndent()
            } + "</ul>"
        }

        return header("Rádió", "radio") + """
            <h2>Saját rádióállomások</h2>
            ${if (msg != null) "<p class=\"msg\">${esc(msg)}</p>" else ""}
            ${if (error != null) "<p class=\"err\">${esc(error)}</p>" else ""}
            <p>Itt vehetsz fel bármilyen internetes rádiót: közvetlen stream-címet
               (.mp3/.aac) vagy lejátszási listát (.m3u, .pls). A telefon a
               listákat automatikusan feloldja a valódi stream-címre.</p>
            <form method="POST" action="/radio/add" class="stack">
              <label class="lbl" for="rname">Állomás neve</label>
              <input type="text" id="rname" name="name" required
                     placeholder="Pl. Kedvenc Rádióm">
              <label class="lbl" for="rurl">Stream vagy lista URL</label>
              <input type="url" id="rurl" name="url" required
                     placeholder="https://pelda.hu/stream.mp3 vagy .m3u / .pls">
              <button type="submit" class="btn">Hozzáadás</button>
            </form>
            <h3>Mentett állomásaim (${saved.size})</h3>
            $rows
        """.trimIndent() + footer()
    }

    fun handleRadioAdd(context: Context, body: String): String {
        val form = parseForm(body)
        val name = form["name"]?.trim().orEmpty()
        val url = form["url"]?.trim().orEmpty()
        if (name.isBlank() || url.isBlank()) {
            return radioPage(context, error = "A név és az URL is kötelező.")
        }
        if (!url.startsWith("http://", true) && !url.startsWith("https://", true)) {
            return radioPage(context, error = "Az URL-nek http:// vagy https:// címmel kell kezdődnie.")
        }
        return try {
            com.superdl.launcher.radio.RadioStore.addStation(
                context,
                com.superdl.launcher.radio.RadioStation(
                    id = "user_" + System.currentTimeMillis(),
                    name = name,
                    streamUrl = url
                )
            )
            radioPage(context, msg = "Hozzáadva: $name. A telefonon a Kedvenc állomásaim menüben találod.")
        } catch (_: Exception) {
            radioPage(context, error = "Nem sikerült hozzáadni az állomást.")
        }
    }

    fun handleRadioDelete(context: Context, body: String): String {
        val id = parseForm(body)["id"]?.trim().orEmpty()
        if (id.isBlank()) return radioPage(context, error = "Hiányzó azonosító.")
        return try {
            com.superdl.launcher.radio.RadioStore.removeStation(context, id)
            radioPage(context, msg = "Állomás törölve.")
        } catch (_: Exception) {
            radioPage(context, error = "Nem sikerült törölni.")
        }
    }

    // ===== NAPTÁR (programok) =====
    // A telefonon a program felvétele diktálással megy, ami lassabb. A portálon
    // a segítő (vagy a haladó felhasználó) a gépről gyorsan összeállítja.

    private fun calDateFmt() = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale("hu"))
    private fun calTimeFmt() = java.text.SimpleDateFormat("HH:mm", java.util.Locale("hu"))
    private fun calHumanFmt() = java.text.SimpleDateFormat("yyyy. MMMM d. (EEEE) HH:mm", java.util.Locale("hu"))

    /** "2026-07-26" + "14:30" -> ezredmásodperc. Null, ha hibás. */
    private fun calParseDateTime(date: String, time: String): Long? = try {
        val f = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm", java.util.Locale("hu"))
        f.isLenient = false
        f.parse("${date.trim()} ${time.trim()}")?.time
    } catch (_: Exception) {
        null
    }

    fun calendarPage(
        context: Context,
        msg: String? = null,
        error: String? = null,
        editId: Long? = null
    ): String {
        val now = System.currentTimeMillis()
        val horizon = now - 24L * 60 * 60 * 1000      // tegnaptól
        val until = now + 60L * 24 * 60 * 60 * 1000   // 60 napra előre
        val events = try {
            com.superdl.launcher.calendar.CalendarHelper.getInstancesBetween(context, horizon, until)
        } catch (_: Exception) {
            emptyList()
        }

        val editing = editId?.let { id -> events.firstOrNull { it.eventId == id } }
        val dFmt = calDateFmt()
        val tFmt = calTimeFmt()
        val hFmt = calHumanFmt()

        // Előre kitöltött értékek: szerkesztésnél a meglévő program, különben ma.
        val fDate = dFmt.format(java.util.Date(editing?.begin ?: now))
        val fStart = tFmt.format(java.util.Date(editing?.begin ?: now))
        val fEnd = tFmt.format(java.util.Date(editing?.end ?: (now + 60L * 60 * 1000)))
        val fTitle = editing?.title ?: ""
        val fRec = editing?.recurrence ?: com.superdl.launcher.calendar.CalendarRecurrence.NONE

        val recOptions = com.superdl.launcher.calendar.CalendarRecurrence.selectable.joinToString("") { r ->
            val sel = if (r == fRec) " selected" else ""
            "<option value=\"${r.name}\"$sel>${esc(r.label)}</option>"
        }

        val rows = if (events.isEmpty()) {
            "<p>Nincs program a következő 60 napban.</p>"
        } else {
            "<ul class=\"media-list\">" + events.joinToString("") { e ->
                val whenTxt = hFmt.format(java.util.Date(e.begin)) + " – " + tFmt.format(java.util.Date(e.end))
                val recTxt = if (e.recurrence == com.superdl.launcher.calendar.CalendarRecurrence.NONE) ""
                    else " • ${esc(e.recurrence.label)}"
                """
                <li class="media-item">
                  <span class="media-name">${esc(e.title)}</span>
                  <span class="media-size">$whenTxt$recTxt</span>
                  <a class="btn" href="/calendar?edit=${e.eventId}">Szerkesztés</a>
                  <form method="POST" action="/calendar/delete" style="display:inline"
                        onsubmit="return confirm('Biztosan törlöd? ${esc(e.title)}');">
                    <input type="hidden" name="id" value="${e.eventId}">
                    <button type="submit" class="btn secondary">Törlés</button>
                  </form>
                </li>
                """.trimIndent()
            } + "</ul>"
        }

        val formTitle = if (editing != null) "Program szerkesztése" else "Új program felvétele"
        val formAction = if (editing != null) "/calendar/update" else "/calendar/add"
        val hiddenId = if (editing != null) "<input type=\"hidden\" name=\"id\" value=\"${editing.eventId}\">" else ""
        val cancelLink = if (editing != null) "<a class=\"btn secondary\" href=\"/calendar\">Mégse</a>" else ""

        return header("Naptár", "calendar") + """
            <h2>Naptár — programok</h2>
            ${if (msg != null) "<p class=\"msg\">${esc(msg)}</p>" else ""}
            ${if (error != null) "<p class=\"err\">${esc(error)}</p>" else ""}
            ${
                if (!com.superdl.launcher.calendar.CalendarHelper.hasWritePermission(context))
                    "<p class=\"err\">A telefonon nincs naptár írási engedély, ezért a mentés nem fog sikerülni. " +
                        "Add meg az engedélyt a telefonon (Beállítások, Beállítás varázsló), majd frissítsd ezt az oldalt.</p>"
                else ""
            }
            <p>Itt a számítógépről gyorsan felveheted, módosíthatod vagy törölheted
               a telefon naptárában lévő programokat. A telefon a beállított időben
               emlékeztet rájuk.</p>

            <section aria-labelledby="cal-form-h">
              <h3 id="cal-form-h">$formTitle</h3>
              <form method="POST" action="$formAction" class="stack">
                $hiddenId
                <label class="lbl" for="cal_title">Program neve</label>
                <input type="text" id="cal_title" name="title" required
                       value="${esc(fTitle)}" placeholder="Pl. orvos, találkozó, edzés">

                <label class="lbl" for="cal_date">Dátum</label>
                <input type="date" id="cal_date" name="date" required value="$fDate">

                <label class="lbl" for="cal_start">Kezdés</label>
                <input type="time" id="cal_start" name="start" required value="$fStart">

                <label class="lbl" for="cal_end">Befejezés</label>
                <input type="time" id="cal_end" name="end" required value="$fEnd">

                <label class="lbl" for="cal_rec">Ismétlődés</label>
                <select id="cal_rec" name="recurrence">$recOptions</select>

                <button type="submit" class="btn">${if (editing != null) "Módosítás mentése" else "Program felvétele"}</button>
                $cancelLink
              </form>
            </section>

            <h3>Közelgő programok (${events.size})</h3>
            $rows
        """.trimIndent() + footer()
    }

    fun handleCalendarAdd(context: Context, body: String): String {
        val form = parseForm(body)
        val title = form["title"]?.trim().orEmpty()
        val date = form["date"]?.trim().orEmpty()
        val start = form["start"]?.trim().orEmpty()
        val end = form["end"]?.trim().orEmpty()
        val rec = calRecurrenceOf(form["recurrence"])

        if (title.isBlank()) return calendarPage(context, error = "A program neve kötelező.")
        val beginMs = calParseDateTime(date, start)
            ?: return calendarPage(context, error = "Hibás dátum vagy kezdési idő.")
        var endMs = calParseDateTime(date, end)
            ?: return calendarPage(context, error = "Hibás befejezési idő.")
        // Ha a vég korábbi, mint a kezdés, a következő napra értjük (pl. 23:00-01:00).
        if (endMs <= beginMs) endMs += 24L * 60 * 60 * 1000

        return try {
            val id = com.superdl.launcher.calendar.CalendarHelper.insertEvent(
                context, title, beginMs, endMs, rec
            )
            if (id == null) {
                calendarPage(context, error = "Nem sikerült menteni. Van írható naptár a telefonon?")
            } else {
                calendarPage(context, msg = "Felvéve: $title.")
            }
        } catch (_: Exception) {
            calendarPage(context, error = "Nem sikerült menteni a programot.")
        }
    }

    fun handleCalendarUpdate(context: Context, body: String): String {
        val form = parseForm(body)
        val id = form["id"]?.trim()?.toLongOrNull()
            ?: return calendarPage(context, error = "Hiányzó program azonosító.")
        val title = form["title"]?.trim().orEmpty()
        val date = form["date"]?.trim().orEmpty()
        val start = form["start"]?.trim().orEmpty()
        val end = form["end"]?.trim().orEmpty()
        val rec = calRecurrenceOf(form["recurrence"])

        if (title.isBlank()) return calendarPage(context, error = "A program neve kötelező.", editId = id)
        val beginMs = calParseDateTime(date, start)
            ?: return calendarPage(context, error = "Hibás dátum vagy kezdési idő.", editId = id)
        var endMs = calParseDateTime(date, end)
            ?: return calendarPage(context, error = "Hibás befejezési idő.", editId = id)
        if (endMs <= beginMs) endMs += 24L * 60 * 60 * 1000

        return try {
            val ok = com.superdl.launcher.calendar.CalendarHelper.updateEvent(
                context, id, title, beginMs, endMs, rec
            )
            if (ok) calendarPage(context, msg = "Módosítva: $title.")
            else calendarPage(context, error = "Nem sikerült módosítani.", editId = id)
        } catch (_: Exception) {
            calendarPage(context, error = "Nem sikerült módosítani a programot.", editId = id)
        }
    }

    fun handleCalendarDelete(context: Context, body: String): String {
        val id = parseForm(body)["id"]?.trim()?.toLongOrNull()
            ?: return calendarPage(context, error = "Hiányzó program azonosító.")
        return try {
            if (com.superdl.launcher.calendar.CalendarHelper.deleteEvent(context, id)) {
                calendarPage(context, msg = "Program törölve.")
            } else {
                calendarPage(context, error = "Nem sikerült törölni.")
            }
        } catch (_: Exception) {
            calendarPage(context, error = "Nem sikerült törölni a programot.")
        }
    }

    private fun calRecurrenceOf(value: String?): com.superdl.launcher.calendar.CalendarRecurrence =
        com.superdl.launcher.calendar.CalendarRecurrence.selectable
            .firstOrNull { it.name == value?.trim() }
            ?: com.superdl.launcher.calendar.CalendarRecurrence.NONE

    // ===== BEVÁSÁRLÓLISTA =====
    // Telefonon diktálva lassabb; a gépről gyorsan bevihető egy egész heti lista.

    fun shoppingPage(context: Context, msg: String? = null, error: String? = null): String {
        val store = com.superdl.launcher.shopping.ShoppingListStore
        val names = try { store.getListNames(context) } catch (_: Exception) { emptyList() }
        val active = try { store.getActiveListName(context) } catch (_: Exception) { null }
        val items = if (active != null) {
            try { store.getItems(context, active) } catch (_: Exception) { emptyList() }
        } else emptyList()

        val listOptions = names.joinToString("") { n ->
            val sel = if (n == active) " selected" else ""
            "<option value=\"${esc(n)}\"$sel>${esc(n)}</option>"
        }

        val listPicker = if (names.isEmpty()) "" else """
            <form method="POST" action="/shopping/select" class="stack">
              <label class="lbl" for="shop_list">Lista választása</label>
              <select id="shop_list" name="list">$listOptions</select>
              <button type="submit" class="btn">Megnyitás</button>
            </form>
        """.trimIndent()

        val rows = if (active == null) {
            "<p>Még nincs bevásárlólistád. Hozz létre egyet alább.</p>"
        } else if (items.isEmpty()) {
            "<p>A(z) <strong>${esc(active)}</strong> lista üres. Adj hozzá tételeket alább.</p>"
        } else {
            "<ul class=\"media-list\">" + items.joinToString("") { it ->
                val priceTxt = it.priceHuf?.let { p -> "$p Ft" } ?: "—"
                val stateTxt = if (it.checked) "Megvan" else "Még nincs meg"
                val toggleLabel = if (it.checked) "Vissza" else "Megvan"
                """
                <li class="media-item">
                  <span class="media-name">${if (it.checked) "<s>" else ""}${esc(it.name)}${if (it.checked) "</s>" else ""}</span>
                  <span class="media-size">$priceTxt • $stateTxt</span>
                  <form method="POST" action="/shopping/toggle" style="display:inline">
                    <input type="hidden" name="id" value="${it.id}">
                    <button type="submit" class="btn">$toggleLabel</button>
                  </form>
                  <form method="POST" action="/shopping/delete" style="display:inline">
                    <input type="hidden" name="id" value="${it.id}">
                    <button type="submit" class="btn secondary"
                            aria-label="Törlés: ${esc(it.name)}">Törlés</button>
                  </form>
                </li>
                """.trimIndent()
            } + "</ul>"
        }

        val total = if (items.isEmpty()) "" else {
            val sum = store.totalPriceHuf(items)
            "<p><strong>Összesen: $sum forint</strong> (${items.count { it.checked }} / ${items.size} megvan)</p>"
        }

        val addForm = if (active == null) "" else """
            <section aria-labelledby="shop-add-h">
              <h3 id="shop-add-h">Új tétel a(z) ${esc(active)} listához</h3>
              <form method="POST" action="/shopping/add" class="stack">
                <label class="lbl" for="shop_item">Tétel neve</label>
                <input type="text" id="shop_item" name="name" required
                       placeholder="Pl. kenyér, tej, alma">
                <label class="lbl" for="shop_price">Ár (forint, nem kötelező)</label>
                <input type="number" id="shop_price" name="price" min="0" step="1"
                       placeholder="Pl. 450">
                <button type="submit" class="btn">Hozzáadás</button>
              </form>
              <p class="hint">Tipp: több tételt gyorsan felvehetsz egymás után —
                 a mező hozzáadás után újra üres lesz.</p>
            </section>
        """.trimIndent()

        val delListForm = if (active == null) "" else """
            <form method="POST" action="/shopping/dellist" style="display:inline"
                  onsubmit="return confirm('Biztosan törlöd a teljes listát? ${esc(active)}');">
              <button type="submit" class="btn secondary">A(z) ${esc(active)} lista törlése</button>
            </form>
        """.trimIndent()

        return header("Bevásárlólista", "shopping") + """
            <h2>Bevásárlólista</h2>
            ${if (msg != null) "<p class=\"msg\">${esc(msg)}</p>" else ""}
            ${if (error != null) "<p class=\"err\">${esc(error)}</p>" else ""}
            <p>Itt a gépről gyorsan összeállíthatod a listát. A telefonon a
               Bevásárlólista menüpontban ugyanez jelenik meg, felolvasva.</p>
            $listPicker
            <h3>${if (active != null) esc(active) else "Nincs megnyitott lista"}</h3>
            $rows
            $total
            $addForm
            <section aria-labelledby="shop-new-h">
              <h3 id="shop-new-h">Új lista létrehozása</h3>
              <form method="POST" action="/shopping/newlist" class="stack">
                <label class="lbl" for="shop_newlist">Lista neve</label>
                <input type="text" id="shop_newlist" name="name" required
                       placeholder="Pl. Heti nagybevásárlás">
                <button type="submit" class="btn">Létrehozás</button>
              </form>
              $delListForm
            </section>
        """.trimIndent() + footer()
    }

    fun handleShoppingSelect(context: Context, body: String): String {
        val name = parseForm(body)["list"]?.trim().orEmpty()
        if (name.isBlank()) return shoppingPage(context, error = "Nincs kiválasztott lista.")
        return try {
            com.superdl.launcher.shopping.ShoppingListStore.setActiveListName(context, name)
            shoppingPage(context, msg = "Megnyitva: $name.")
        } catch (_: Exception) {
            shoppingPage(context, error = "Nem sikerült megnyitni a listát.")
        }
    }

    fun handleShoppingNewList(context: Context, body: String): String {
        val name = parseForm(body)["name"]?.trim().orEmpty()
        if (name.isBlank()) return shoppingPage(context, error = "A lista neve kötelező.")
        return try {
            val store = com.superdl.launcher.shopping.ShoppingListStore
            if (store.createList(context, name)) {
                store.setActiveListName(context, name)
                shoppingPage(context, msg = "Létrehozva: $name.")
            } else {
                shoppingPage(context, error = "Ilyen nevű lista már van.")
            }
        } catch (_: Exception) {
            shoppingPage(context, error = "Nem sikerült létrehozni a listát.")
        }
    }

    fun handleShoppingDeleteList(context: Context): String {
        val store = com.superdl.launcher.shopping.ShoppingListStore
        val active = try { store.getActiveListName(context) } catch (_: Exception) { null }
            ?: return shoppingPage(context, error = "Nincs megnyitott lista.")
        return try {
            store.deleteList(context, active)
            shoppingPage(context, msg = "Lista törölve: $active.")
        } catch (_: Exception) {
            shoppingPage(context, error = "Nem sikerült törölni a listát.")
        }
    }

    fun handleShoppingAdd(context: Context, body: String): String {
        val form = parseForm(body)
        val name = form["name"]?.trim().orEmpty()
        val price = form["price"]?.trim()?.takeIf { it.isNotBlank() }?.toIntOrNull()
        if (name.isBlank()) return shoppingPage(context, error = "A tétel neve kötelező.")
        val store = com.superdl.launcher.shopping.ShoppingListStore
        val active = try { store.getActiveListName(context) } catch (_: Exception) { null }
            ?: return shoppingPage(context, error = "Előbb hozz létre vagy nyiss meg egy listát.")
        return try {
            store.addItem(context, active, name, price)
            shoppingPage(context, msg = "Hozzáadva: $name.")
        } catch (_: Exception) {
            shoppingPage(context, error = "Nem sikerült hozzáadni a tételt.")
        }
    }

    fun handleShoppingToggle(context: Context, body: String): String {
        val id = parseForm(body)["id"]?.trim()?.toIntOrNull()
            ?: return shoppingPage(context, error = "Hiányzó tétel azonosító.")
        val store = com.superdl.launcher.shopping.ShoppingListStore
        val active = try { store.getActiveListName(context) } catch (_: Exception) { null }
            ?: return shoppingPage(context, error = "Nincs megnyitott lista.")
        return try {
            val item = store.toggleChecked(context, active, id)
            shoppingPage(context, msg = item?.let {
                if (it.checked) "Megvan: ${it.name}." else "Visszavéve: ${it.name}."
            } ?: "Frissítve.")
        } catch (_: Exception) {
            shoppingPage(context, error = "Nem sikerült módosítani a tételt.")
        }
    }

    fun handleShoppingDelete(context: Context, body: String): String {
        val id = parseForm(body)["id"]?.trim()?.toIntOrNull()
            ?: return shoppingPage(context, error = "Hiányzó tétel azonosító.")
        val store = com.superdl.launcher.shopping.ShoppingListStore
        val active = try { store.getActiveListName(context) } catch (_: Exception) { null }
            ?: return shoppingPage(context, error = "Nincs megnyitott lista.")
        return try {
            store.removeItem(context, active, id)
            shoppingPage(context, msg = "Tétel törölve.")
        } catch (_: Exception) {
            shoppingPage(context, error = "Nem sikerült törölni a tételt.")
        }
    }

    fun statusPage(context: Context, findPhoneMsg: String? = null): String {
        val battery = try {
            val bm = context.getSystemService(Context.BATTERY_SERVICE) as android.os.BatteryManager
            val level = bm.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY)
            "$level százalék"
        } catch (_: Exception) {
            "ismeretlen"
        }

        val storage = try {
            val stat = android.os.StatFs(android.os.Environment.getExternalStorageDirectory().path)
            val freeGb = stat.availableBytes / 1024.0 / 1024 / 1024
            String.format("%.1f GB szabad", freeGb)
        } catch (_: Exception) {
            "ismeretlen"
        }

        return header("Állapot", "status") + """
        <h2>Telefon állapota</h2>
        <dl class="status-list">
          <dt>Akkumulátor</dt><dd>${esc(battery)}</dd>
          <dt>Szabad tárhely</dt><dd>${esc(storage)}</dd>
          <dt>Android verzió</dt><dd>${android.os.Build.VERSION.RELEASE}</dd>
          <dt>Eszköz</dt><dd>${esc(android.os.Build.MODEL)}</dd>
        </dl>
        <section aria-labelledby="find-h" class="find-phone">
          <h2 id="find-h">Hol a telóm?</h2>
          ${if (findPhoneMsg != null) "<p class=\"msg\">${esc(findPhoneMsg)}</p>" else ""}
          <p>Ha nem találod a telefont (pl. az ágy mögé csúszott), csörgesd meg
             hangosan. 30 másodperc múlva magától elhallgat.</p>
          <form method="POST" action="/find-phone/start" style="display:inline">
            <button type="submit" class="btn">📢 Csörgesd meg a telefont</button>
          </form>
          <form method="POST" action="/find-phone/stop" style="display:inline">
            <button type="submit" class="btn secondary">Elég, elhallgattatom</button>
          </form>
        </section>
        <p class="hint">A portál addig fut, amíg a telefonon ki nem kapcsolod
        a Zene és Média menü WiFi fájlportál pontjában.</p>
        """.trimIndent() + footer()
    }

    // ==================== Segédek ====================

    /** URL-kódolt űrlap-adat feldolgozása (name=value&name2=value2). */
    private fun parseForm(body: String): Map<String, String> =
        body.split("&").mapNotNull { pair ->
            val idx = pair.indexOf('=')
            if (idx <= 0) return@mapNotNull null
            val key = pair.substring(0, idx)
            val value = pair.substring(idx + 1).replace("+", " ")
            try {
                URLDecoder.decode(key, "UTF-8") to URLDecoder.decode(value, "UTF-8")
            } catch (_: Exception) {
                null
            }
        }.toMap()

    /**
     * Ugyanaz, mint a parseForm, de MINDEN azonos nevű mezőt megtart.
     *
     * MIÉRT KELL: a parseForm .toMap()-ot használ, ami azonos kulcsnál csak az
     * UTOLSÓT tartja meg. A checkboxos tömeges törlésnél viszont több azonos
     * nevű mező érkezik (id=12&id=15&id=31) — a parseForm ebből egyetlen
     * névjegyet látna, és a kijelölt húsz helyett egyet törölne. Ez a változat
     * listát ad vissza kulcsonként.
     */
    private fun parseFormMulti(body: String): Map<String, List<String>> {
        val result = mutableMapOf<String, MutableList<String>>()
        body.split("&").forEach { pair ->
            val idx = pair.indexOf('=')
            if (idx <= 0) return@forEach
            val rawKey = pair.substring(0, idx)
            val rawValue = pair.substring(idx + 1).replace("+", " ")
            try {
                val key = URLDecoder.decode(rawKey, "UTF-8")
                val value = URLDecoder.decode(rawValue, "UTF-8")
                result.getOrPut(key) { mutableListOf() }.add(value)
            } catch (_: Exception) {
                // Hibás kódolású mező: kihagyjuk, a többit feldolgozzuk.
            }
        }
        return result
    }

    private fun esc(text: String?): String = (text ?: "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")

    private fun css(): String = """
        * { box-sizing: border-box; }
        body { font-family: system-ui, -apple-system, Arial, sans-serif;
               max-width: 860px; margin: 0 auto; padding: 20px;
               background: #0f1115; color: #e8eaed; line-height: 1.6; }
        .skip { position: absolute; left: -9999px; }
        .skip:focus { position: static; display: block; padding: 10px;
                      background: #8ab4f8; color: #0f1115; }
        header { border-bottom: 1px solid #2a2e37; margin-bottom: 24px; }
        h1 { font-size: 1.5rem; color: #8ab4f8; margin: 0 0 12px; }
        h2 { font-size: 1.15rem; margin: 28px 0 12px; color: #e8eaed; }
        h3 { font-size: 1rem; margin: 0 0 4px; }
        nav { display: flex; flex-wrap: wrap; gap: 8px; padding-bottom: 12px; }
        .tab { padding: 10px 16px; background: #1a1d23; border: 1px solid #3c4043;
               border-radius: 8px; color: #e8eaed; text-decoration: none; }
        .tab.active { background: #8ab4f8; color: #0f1115; font-weight: 600; }
        .tab:focus { outline: 3px solid #8ab4f8; outline-offset: 2px; }
        label { display: block; margin: 14px 0 4px; color: #9aa0a6; font-weight: 600; }
        input, textarea, button, select {
          width: 100%; padding: 12px; font-size: 1rem; font-family: inherit;
          background: #1a1d23; border: 1px solid #3c4043; border-radius: 8px;
          color: #e8eaed; }
        input:focus, textarea:focus, button:focus {
          outline: 3px solid #8ab4f8; outline-offset: 2px; }
        button { background: #8ab4f8; color: #0f1115; font-weight: 700;
                 cursor: pointer; border: none; margin-top: 16px; }
        .msg { background: #1a1d23; border: 1px solid #2a2e37; border-radius: 8px;
               padding: 14px; margin-bottom: 10px; }
        .msg p { margin: 4px 0; }
        .dir { font-size: 0.8rem; color: #9aa0a6; font-weight: 400; }
        .time { font-size: 0.8rem; color: #9aa0a6; }
        .row { display: flex; gap: 12px; padding: 10px;
               border-bottom: 1px solid #2a2e37; }
        .name { flex: 1; }
        .phone { color: #9aa0a6; }
        .ok { background: #1e3a29; border: 1px solid #34a853; padding: 12px;
              border-radius: 8px; }
        .err { background: #3a1e1e; border: 1px solid #ea4335; padding: 12px;
               border-radius: 8px; }
        .empty, .hint { color: #9aa0a6; }
        .status-list dt { font-weight: 700; color: #9aa0a6; margin-top: 10px; }
        .status-list dd { margin: 0 0 8px; font-size: 1.1rem; }
        details { margin-top: 10px; border-top: 1px solid #2a2e37; padding-top: 8px; }
        details summary { cursor: pointer; padding: 6px 0; font-weight: 600;
          color: #8ab4f8; }
        details summary:focus { outline: 3px solid #8ab4f8; outline-offset: 2px; }
        details h4 { margin: 10px 0 4px; font-size: 1rem; color: #e8eaed; }
        details p { margin: 0 0 8px; color: #bdc1c6; line-height: 1.5; }
        .inline { margin-top: 8px; }
        .inline button { margin-top: 0; padding: 8px 12px; font-size: 0.9rem; }
        button.danger { background: #f28b82; color: #0f1115; }
        button.secondary { background: #2a2e37; color: #e8eaed; font-weight: 600;
                           margin-top: 6px; font-size: 0.9rem; padding: 8px 12px; }
        .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .actions form { flex: 1; min-width: 200px; }
        .pastestatus { color: #8ab4f8; margin-top: 8px; font-size: 0.9rem; }
        .pastestatus:empty { display: none; }
        .sr { position: absolute; left: -9999px; }
        fieldset { border: 1px solid #3c4043; border-radius: 8px; margin: 14px 0;
                   padding: 10px 14px; }
        legend { color: #9aa0a6; font-weight: 600; padding: 0 6px; }
        /* A checkbox ne nyúljon szét 100%-ra, mint a többi input. */
        input.pick { width: auto; flex: 0 0 auto; margin: 0; }
        .picklabel { display: inline; margin: 0; color: #e8eaed; font-weight: 400;
                     cursor: pointer; }
        .row { align-items: center; }
        .confirm-list { background: #1a1d23; border: 1px solid #2a2e37;
                        border-radius: 8px; padding: 14px 14px 14px 32px;
                        margin-bottom: 10px; }
        .confirm-list li { margin: 6px 0; }
    """.trimIndent()
}
