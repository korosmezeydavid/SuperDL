package com.superdl.launcher.legal

data class LegalSection(
    val title: String,
    val body: String
) {
    fun speakPreview(): String = title

    fun speakFull(): String = "$title. $body"
}

object LegalTexts {

    const val APP_VERSION = "1.54.9"
    const val DEVELOPER_NAME = "Kőrösmezey Dávid"
    const val DEVELOPER_EMAIL = "korosmezey.david.richard@gmail.com"
    const val APP_FULL_NAME = "Super Digital Launcher"
    const val APP_SHORT_NAME = "Super DL"

    fun speakEmail(): String =
        "korosmezey pont dávid pont richard kukac gmail pont com"

    fun aboutApp(): String = """
        $APP_FULL_NAME, röviden $APP_SHORT_NAME.
        Vak és gyengénlátó felhasználók számára készült Android launcher.
        Gesztusokkal és hanggal vezérelhető: hívás, üzenet, ébresztő, időzítő, profi diktafon, G P S kitekintő, környezeti kitekintő, S.O.S., hírek, YouTube, könyvolvasás, akkumulátor őrség, PIN zárolás és tömegközlekedés.
        Verzió: $APP_VERSION.
    """.trim().replace(Regex("\\s+"), " ")

    fun aboutDeveloper(): String = """
        Fejlesztő: $DEVELOPER_NAME.
        A $APP_SHORT_NAME alkalmazást $DEVELOPER_NAME készítette, hogy a mindennapi telefonhasználat
        önállóbb és biztonságosabb legyen látássérült felhasználók számára.
        Elérhetőség e-mailben: ${speakEmail()}.
    """.trim().replace(Regex("\\s+"), " ")

    fun contactDeveloper(): String =
        "Kapcsolat a fejlesztővel: $DEVELOPER_NAME. E-mail cím: ${speakEmail()}."

    fun privacyPolicy(): List<LegalSection> = listOf(
        LegalSection(
            "Bevezetés",
            "A $APP_FULL_NAME ($APP_SHORT_NAME) tiszteletben tartja a magánéletet. " +
                "Ez az alkalmazás elsősorban a készüléken fut, és nem üzemeltet saját felhőszerverét."
        ),
        LegalSection(
            "Milyen adatokhoz fér hozzá",
            "Az alkalmazás a működéséhez szükséges Android engedélyeket használ: telefonhívás, névjegyek, " +
                "SMS, e-mail, helymeghatározás, mikrofon, értesítések, naptár, kamera a zseblámpához, és Bluetooth/WiFi beállítások. " +
                "Ezeket kizárólag a kért funkciókhoz használja, például híváshoz, üzenetküldéshez, e-mailhez, S.O.S.-hoz vagy közeli megállók felolvasásához."
        ),
        LegalSection(
            "Hol tárolódnak az adatok",
            "Az S.O.S. telefonszámok, ébresztők és egyéb beállítások a telefonon, helyi tárolóban maradnak. " +
                "Az alkalmazás nem gyűjt személyes adatokat marketing célra, és nem értékesít adatot harmadik félnek."
        ),
        LegalSection(
            "Külső szolgáltatások",
            "Egyes funkciók internetes szolgáltatásokat használnak, például a BKK FUTÁR nyílt adatait, " +
                "OpenStreetMapot, YouTube-ot, hírforrásokat vagy böngészőt. " +
                "Ezekre a szolgáltatásokra a saját adatvédelmi szabályaik vonatkoznak."
        ),
        LegalSection(
            "Értesítések olvasása",
            "Ha engedélyezed, az alkalmazás az értesítéseket helyben dolgozza fel és felolvassa. " +
                "Az értesítések tartalma nem kerül külső szerverre."
        ),
        LegalSection(
            "Felhasználói jogok",
            "Az engedélyeket bármikor visszavonhatod az Android beállításaiban. " +
                "Az alkalmazás eltávolításával a hozzá tartozó helyi beállítások is törlődnek."
        ),
        LegalSection(
            "Kapcsolat",
            "Adatvédelmi kérdés esetén fordulj a fejlesztőhöz: $DEVELOPER_NAME. " +
                "E-mail: $DEVELOPER_EMAIL, felolvashatóan: ${speakEmail()}."
        )
    )

    fun termsOfUse(): List<LegalSection> = listOf(
        LegalSection(
            "Általános feltételek",
            "A $APP_SHORT_NAME használatával elfogadod, hogy az alkalmazást saját felelősségedre használod. " +
                "Az alkalmazás célja az akadálymentesített telefonhasználat megkönnyítése."
        ),
        LegalSection(
            "S.O.S. és vészhelyzet",
            "Az S.O.S. funkció segít gyors hívásindításban, de nem garantál hálózati lefedettséget, " +
                "és nem helyettesíti a hivatalos segélyszolgálati rendszereket. Vészhelyzetben mindig a helyi segélyhívó számot is használd."
        ),
        LegalSection(
            "Pontosság",
            "Az időjárás, hírek, tömegközlekedés, YouTube-találatok és egyéb külső tartalmak pontosságáért " +
                "harmadik fél szolgáltatók felelnek. Az alkalmazás ezeket csak elérhetővé teszi."
        ),
        LegalSection(
            "Felelősségkorlátozás",
            "A fejlesztő mindent megtesz a megbízható működésért, de az alkalmazást jelen formájában, garancia nélkül biztosítja. " +
                "A felhasználó felelős a telefon, SIM-kártya, engedélyek és hálózati kapcsolat rendben tartásáért."
        ),
        LegalSection(
            "Módosítások",
            "A fejlesztő jogosult az alkalmazás és ezen feltételek frissítésére. A telepített verzió az aktuális buildben látható."
        )
    )

    fun legalNotice(): List<LegalSection> = listOf(
        LegalSection(
            "Szerzői jog",
            "A $APP_FULL_NAME ($APP_SHORT_NAME) szoftver és felhasználói felület szerzői joga $DEVELOPER_NAME-t illeti meg."
        ),
        LegalSection(
            "Védjegy",
            "A Super Digital Launcher és Super DL megnevezések az alkalmazás védjegyei. " +
                "Harmadik fél védjegyei, például a Google, YouTube és Google Térkép a megfelelő tulajdonosoké."
        ),
        LegalSection(
            "Nyílt forrású komponensek",
            "Az alkalmazás Android és Kotlin nyílt ökoszisztéma komponenseit használja. " +
                "A külső könyvtárakra a saját licenceik vonatkoznak."
        ),
        LegalSection(
            "Irányadó jog",
            "A jogvitákra a felhasználó lakóhelye szerinti irányadó jog az elsődleges, " +
                "a vonatkozó fogyasztóvédelmi szabályok figyelembevételével."
        )
    )
}