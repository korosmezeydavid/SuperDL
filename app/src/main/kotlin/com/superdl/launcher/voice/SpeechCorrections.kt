package com.superdl.launcher.voice

import com.superdl.launcher.assistant.VoiceAssistantHelper

/**
 * Gyakori magyar ASR tévesztések javítása a szabályalapú parancsértelmezés előtt.
 */
object SpeechCorrections {

    private val phraseReplacements = listOf(
        "hany ora van" to "hany ora",
        "mennyi az ido most" to "mennyi az ido",
        "mondd az idot most" to "mondd az idot",
        "ebresztes be" to "ebreszto",
        "ebresztem" to "ebreszto",
        "ebresztesem" to "ebreszto",
        "uzenetet kuldj" to "uzenet kuldes",
        "uzenetet kul" to "uzenet kuldes",
        "sms-t kuldj" to "sms kuldes",
        "sms-t irj" to "sms iras",
        "olvasd az uzeneteket" to "olvasd az uzenet",
        "hivas naplo" to "hivasnaplo",
        "hivas naplot" to "hivasnaplo",
        "nevjegyzek" to "nevjegy",
        "nevjegybol" to "nevjegy",
        "kedvenceket hiv" to "kedvenc hivas",
        "tarcsazz" to "tarcsaz",
        "telefonalj meg" to "hivd fel",
        "hivj meg fel" to "hivd fel",
        "hivd meg fel" to "hivd fel",
        "jutjubon" to "youtube",
        "jutyubon" to "youtube",
        "jutubon" to "youtube",
        "be vasarlo lista" to "bevasarlolista",
        "be vasarlolista" to "bevasarlolista",
        "idojaras most" to "idojaras",
        "pontos idot" to "pontos ido",
        "gyalog utvonal" to "gyalogos utvonal",
        "gps kitekinto" to "gps kitekinto",
        "asszisztens inditsd" to "asszisztens indit",
        "segitseg kerek" to "segitseg",
        "mit tudsz csinalni" to "mit tudsz",
        "nema modot" to "nema mod",
        "csendes modot" to "csendes mod",
        "zseb lampa" to "zseblampa",
        "szamologepek" to "szamologep",
        "konyv keres" to "konyv keres",
        "internet keres" to "internet kereso",
        "web kereses" to "internet kereso",
        "szia helena" to "szia elena",
        "kerlek helena" to "kerlek elena",
        "hello helena" to "hello elena",
        "elena figyel" to "elena figyelo",
        "elena figyelj" to "elena figyelo",
        "elena tanits" to "elena tanitas",
        "felebeszto" to "felebeszto",
        "felebesztes" to "felebeszto",
        "hot spot" to "hotspot",
        "hotspotot" to "hotspot",
        "megosztott net" to "megosztott internet"
    )

    private val wordReplacements = mapOf(
        "ebresztes" to "ebreszto",
        "ebresztok" to "ebresztok",
        "uzenetek" to "uzenet",
        "sms-t" to "sms",
        "smst" to "sms",
        "hivj" to "hivd",
        "hivas" to "hivas",
        "nevjegyzek" to "nevjegy",
        "idozitot" to "idozito",
        "idozitokat" to "idozitok",
        "gyogyszert" to "gyogyszer",
        "naptarat" to "naptar",
        "programot" to "program",
        "vifi" to "wifi",
        "wify" to "wifi",
        "bluetoot" to "bluetooth",
        "asszisztenst" to "asszisztens",
        "asszisztenszt" to "asszisztens",
        "tarcsazz" to "tarcsaz",
        "zenebol" to "zene",
        "zenet" to "zene",
        "lampat" to "lampa",
        "diktafont" to "diktafon",
        "konyvet" to "konyv",
        "konyvot" to "konyv",
        "helena" to "elena",
        "ellen" to "elena",
        "ilona" to "elena"
    )

    fun apply(raw: String): String {
        var text = VoiceAssistantHelper.normalize(raw)
        if (text.isBlank()) return text

        for ((wrong, right) in phraseReplacements) {
            if (text.contains(wrong)) {
                text = text.replace(wrong, right)
            }
        }

        val words = text.split(" ").map { word ->
            wordReplacements[word] ?: word
        }
        return words.joinToString(" ").trim()
    }
}