package com.superdl.launcher.email

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Az e-mail (SMTP) beállítások tárolása.
 *
 * A JELSZÓ TITKOSÍTVA tárolódik: az EncryptedSharedPreferences az eszköz
 * hardveres kulcstárolójával (Android Keystore) titkosít, így a jelszó
 * akkor sem olvasható ki, ha valaki hozzáfér a telefon fájljaihoz.
 *
 * A korábbi, titkosítatlan beállításokat első használatkor automatikusan
 * átköltöztetjük a titkosított tárolóba (a felhasználónak nem kell újra
 * beírnia semmit), majd a régi, olvasható másolatot töröljük.
 */
object SmtpConfigStore {

    private const val TAG = "SuperDL.SmtpStore"
    private const val PREFS = "smtp_prefs"           // régi, titkosítatlan
    private const val SECURE_PREFS = "smtp_prefs_secure"

    private var securePrefs: SharedPreferences? = null

    /**
     * A titkosított tároló. Ha bármiért nem hozható létre (nagyon régi vagy
     * sérült Keystore), visszaesünk a sima tárolóra, hogy az e-mail funkció
     * ne álljon le teljesen – de ilyenkor is működik az app.
     */
    private fun prefs(context: Context): SharedPreferences {
        securePrefs?.let { return it }
        val created = try {
            val masterKey = MasterKey.Builder(context.applicationContext)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            EncryptedSharedPreferences.create(
                context.applicationContext,
                SECURE_PREFS,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        } catch (e: Exception) {
            Log.w(TAG, "Encrypted prefs unavailable, falling back", e)
            context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        }
        securePrefs = created
        migrateLegacyIfNeeded(context, created)
        return created
    }

    /** A régi, olvasható jelszó átköltöztetése a titkosított tárolóba. */
    private fun migrateLegacyIfNeeded(context: Context, target: SharedPreferences) {
        try {
            val legacy = context.applicationContext
                .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val legacyHost = legacy.getString("host", null)
            if (legacyHost.isNullOrBlank()) return
            if (target === legacy) return // nincs titkosított tároló, nincs mit tenni
            if (!target.getString("host", null).isNullOrBlank()) return // már megvan

            target.edit()
                .putString("host", legacyHost)
                .putInt("port", legacy.getInt("port", 587))
                .putString("username", legacy.getString("username", null))
                .putString("password", legacy.getString("password", null))
                .putString("from_email", legacy.getString("from_email", null))
                .putString("from_name", legacy.getString("from_name", null))
                .putBoolean("use_tls", legacy.getBoolean("use_tls", true))
                .apply()

            // A régi, olvasható másolat törlése – ez a lényeg.
            legacy.edit().clear().apply()
            Log.i(TAG, "Legacy SMTP config migrated to encrypted storage")
        } catch (e: Exception) {
            Log.w(TAG, "Legacy migration failed", e)
        }
    }

    fun isConfigured(context: Context): Boolean = get(context)?.isValid() == true

    fun get(context: Context): SmtpConfig? {
        val p = prefs(context)
        val host = p.getString("host", null)?.trim().orEmpty()
        val port = p.getInt("port", 587)
        val username = p.getString("username", null)?.trim().orEmpty()
        val password = p.getString("password", null).orEmpty()
        val fromEmail = p.getString("from_email", null)?.trim().orEmpty()
        val fromName = p.getString("from_name", null)?.trim().orEmpty()
        val useTls = p.getBoolean("use_tls", true)
        // Régi mentésekben nincs IMAP mező: üres host = az SmtpConfig kitalálja
        // a küldő szerverből. Így a meglévő beállítás változatlanul működik.
        val imapHost = p.getString("imap_host", null)?.trim().orEmpty()
        val imapPort = p.getInt("imap_port", 993)
        if (host.isBlank()) return null
        return SmtpConfig(
            host, port, username, password, fromEmail, fromName, useTls,
            imapHost, imapPort
        )
    }

    fun save(context: Context, config: SmtpConfig) {
        prefs(context).edit()
            .putString("host", config.host)
            .putInt("port", config.port)
            .putString("username", config.username)
            .putString("password", config.password)
            .putString("from_email", config.fromEmail)
            .putString("from_name", config.fromName)
            .putBoolean("use_tls", config.useTls)
            .putString("imap_host", config.imapHost)
            .putInt("imap_port", config.imapPort)
            .apply()
    }

    fun clear(context: Context) {
        prefs(context).edit().clear().apply()
        // A biztonság kedvéért a régi tárolót is takarítjuk.
        try {
            context.applicationContext
                .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().clear().apply()
        } catch (_: Exception) {
        }
    }

    fun gmailPreset(username: String, password: String, fromName: String = ""): SmtpConfig =
        SmtpConfig(
            host = "smtp.gmail.com",
            port = 587,
            username = username.trim(),
            password = password,
            fromEmail = username.trim(),
            fromName = fromName.trim(),
            useTls = true,
            imapHost = "imap.gmail.com",
            imapPort = 993
        )
}
