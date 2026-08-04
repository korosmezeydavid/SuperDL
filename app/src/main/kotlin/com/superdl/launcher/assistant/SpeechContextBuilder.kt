package com.superdl.launcher.assistant

import android.content.Context
import com.superdl.launcher.menu.MenuAction
import com.superdl.launcher.menu.MenuTree

object SpeechContextBuilder {

    private val coreCommands = listOf(
        "Szia Elena",
        "Kérlek Elena",
        "Elena figyelő",
        "Elena tanítás",
        "hány óra van",
        "pontos idő",
        "ébresztő",
        "üzenet küldés",
        "üzenet olvasás",
        "hívd fel",
        "hívásnapló",
        "névjegy",
        "névjegyzék",
        "kedvencek",
        "időjárás",
        "naptár",
        "zene",
        "WiFi",
        "Hotspot",
        "Bluetooth",
        "S O S",
        "segítség",
        "napi üdvözlés",
        "akkumulátor",
        "időzítő",
        "bevásárlólista",
        "hol vagyok",
        "GPS kitekintő",
        "internet kereső",
        "könyvtár",
        "diktafon",
        "számológép",
        "zseblámpa",
        "értesítések",
        "hangerő fel",
        "hangerő le"
    )

    fun assistantHints(context: Context? = null): ArrayList<String> {
        val hints = linkedSetOf<String>()
        hints.addAll(coreCommands)
        if (context != null) {
            hints.addAll(ElenaWakeHelper.wakeHints(context))
        }
        for (item in MenuTree.allItems()) {
            if (item.action == MenuAction.SUBMENU || item.id.endsWith("_back")) continue
            if (item.label.length <= 40) hints.add(item.label)
        }
        return ArrayList(hints.take(120))
    }
}