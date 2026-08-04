package com.superdl.launcher.email

data class SmtpConfig(
    val host: String,
    val port: Int,
    val username: String,
    val password: String,
    val fromEmail: String,
    val fromName: String,
    val useTls: Boolean = true,
    // IMAP (bejövő levelek) szerver.
    //
    // MIÉRT KÜLÖN: korábban az ImapReader-be volt drótozva az imap.gmail.com:993,
    // így egy nem-Gmail fiókkal a KÜLDÉS működött, az OLVASÁS viszont csendben
    // üres listát adott. A néma féllábon állás rosszabb, mint a hiba, ezért
    // az IMAP szerver is beállítható.
    //
    // Üres host = "találd ki a küldő szerverből" (lásd resolvedImapHost), így a
    // régi, csak SMTP-vel mentett beállítások is működnek.
    val imapHost: String = "",
    val imapPort: Int = 993
) {
    fun isValid(): Boolean =
        host.isNotBlank() && port in 1..65535 &&
            username.isNotBlank() && password.isNotBlank() &&
            EmailHelper.isValidEmail(fromEmail)

    /**
     * A ténylegesen használandó IMAP szerver.
     *
     * Ha nincs megadva, a küldő szerverből próbáljuk kitalálni (smtp.X -> imap.X),
     * mert a szolgáltatók túlnyomó többsége így nevezi. Ez csak tipp: ha nem jó,
     * a felhasználó a portálon felülírhatja.
     */
    fun resolvedImapHost(): String {
        if (imapHost.isNotBlank()) return imapHost.trim()
        val h = host.trim().lowercase()
        return when {
            h.startsWith("smtp.") -> "imap." + h.removePrefix("smtp.")
            h.startsWith("mail.") -> h
            else -> h
        }
    }

    fun resolvedImapPort(): Int = if (imapPort in 1..65535) imapPort else 993

    /** Van-e értelmes IMAP beállítás (a bejövő levelek olvasásához). */
    fun canReadInbox(): Boolean = isValid() && resolvedImapHost().isNotBlank()

    fun speakSummary(): String {
        val namePart = if (fromName.isNotBlank()) "$fromName, " else ""
        return "Küldő: $namePart${EmailHelper.speakAddress(fromEmail)}. " +
            "Szerver: $host, port $port. Felhasználó: ${EmailHelper.speakAddress(username)}."
    }
}
