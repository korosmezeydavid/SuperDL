# -*- coding: utf-8 -*-
"""Távsegítség – a BIZTONSÁGI szövegek (beleegyezés, figyelmeztetés, pánik).

Minden munkamenet INDULÁSAKOR el kell fogadni a megfelelő szöveget – a felület
egy leokézható párbeszédben mutatja, és a képernyőolvasó felolvassa. A cél,
hogy a felügyelt, bizalmi jelleg mindig tudatos maradjon."""

# a PÁNIK: egy RENDSZERSZINTŰ gyorsbillentyű (a fókusztól függetlenül is
# működik, még ha épp az irányító gépel is) + egy jól látható gomb az ablakban.
PANIK_LEIRAS = ("a Ctrl+Alt+Szünet (Pause) gyorsbillentyű – ez a fókusztól "
                "függetlenül is működik –, vagy a „Vezérlés AZONNALI leállítása” "
                "gomb")

# A SEGÍTETT (akit irányítanak) beleegyező szövege – ezt KELL elfogadnia,
# mielőtt bárki átveheti az irányítást a gépe felett.
BELEEGYEZO_SEGITETT = (
    "FONTOS – OLVASD EL, MIELŐTT ENGEDÉLYEZED!\n\n"
    "Most azt készülsz engedélyezni, hogy egy MÁSIK ember TÁVOLRÓL irányítsa "
    "ezt a gépet: mozgassa az egeret, gépeljen, kattintson, és HALLJA, amit a "
    "géped felolvas.\n\n"
    "• CSAK MEGBÍZHATÓ irányítót engedj a gépedre! Akkor add ki a "
    "szoba-kódot, ha biztosan tudod, KI fog segíteni – telefonon, ismerősként "
    "egyeztetve. Ismeretlennek SOHA.\n"
    "• Ne feledd a PÁNIK-lehetőséget: " + PANIK_LEIRAS + " – bármikor "
    "megnyomva AZONNAL megszakad az irányítás, és visszakapod a géped.\n"
    "• Te végig itt ülsz, látod-hallod, mi történik, és bármikor leállíthatod. "
    "Felügyelet nélküli, rejtett hozzáférés NINCS.\n\n"
    "Ha bízol az irányítóban és folytatod, nyomd meg az „Elfogadom” gombot."
)

# Az IRÁNYÍTÓ (aki segít) figyelmeztető szövege – felelősség.
BELEEGYEZO_IRANYITO = (
    "IRÁNYÍTÓ LESZEL – BIZALMI FUNKCIÓ!\n\n"
    "Mindjárt egy másik ember gépét fogod távolról irányítani, hogy segíts "
    "neki. Ez BIZALMON alapul.\n\n"
    "• Csak azt tedd, amiben megállapodtatok, és amit ő is hall/követ.\n"
    "• NE élj vissza a hozzáféréssel: ne nyiss meg, ne módosíts, ne törölj "
    "semmit az ő tudta és beleegyezése nélkül.\n"
    "• Ő bármikor megszakíthatja a kapcsolatot – ez így helyes.\n\n"
    "Ha ezt megértetted és felelősséggel segítesz, nyomd meg az „Elfogadom” "
    "gombot."
)

# rövid, munkamenet közben ismételt jelzés (a segítettnek), hogy tudatos maradjon
IRANYITAS_AKTIV = ("FIGYELEM: most TÁVIRÁNYÍTÁS alatt vagy – {ki} irányítja a "
                   "gépedet. Leállítás: " + PANIK_LEIRAS + ".")
IRANYITAS_VEGE = "A távirányítás véget ért – újra csak te irányítod a gépedet."
