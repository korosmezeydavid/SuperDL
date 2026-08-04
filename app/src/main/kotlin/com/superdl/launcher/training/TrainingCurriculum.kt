package com.superdl.launcher.training

import com.superdl.launcher.menu.MenuAction
import com.superdl.launcher.menu.MenuItem
import com.superdl.launcher.menu.MenuTree

object TrainingCurriculum {

    private const val PRACTICE_CALLS = "Telefon és Hívások"
    private const val PRACTICE_TOOLS = "Eszközök"
    private const val PRACTICE_COLOR = "Színfelismerő kamerával"

    val steps: List<TrainingStep> = buildList {
        add(
            TrainingStep.Explain(
                "Super DL tanuló mód. Itt végigmegyünk a program összes funkcióján, semmi nem indul el élesben. " +
                    "Kilépés: két gyors balra söprés. Jobbra söprés: következő rész."
            )
        )
        add(
            TrainingStep.Explain(
                "Négy gesztus: söprés fel előző, söprés le következő, söprés jobbra kiválasztás és megerősítés, " +
                    "söprés balra vissza és mégse. Diktálásnál is balra szakít meg. Megerősítéshez elég a jobbra söprés."
            )
        )

        val mainItems = MenuTree.root
        add(mainMenuPractice(mainItems, PRACTICE_CALLS, "Jó! Így navigálsz a főmenüben is."))
        add(mainMenuPractice(mainItems, PRACTICE_TOOLS, "Szuper! Az Eszközök alatt diktafon, színfelismerő, Q R olvasó és több található."))

        mainItems.forEach { item ->
            add(TrainingStep.Explain(describeSection(item)))
            if (item.id == "tools") {
                add(toolsColorDetectorPractice())
                add(dictaphoneFeaturesExplain())
            }
        }

        add(
            TrainingStep.Explain(
                "További tudnivalók. Elena a menüből vagy az oldalsó gomb hosszú nyomásával érhető el. " +
                    "Mondd: Szia Elena, vagy Kérlek Elena. Beállítható háttérfigyelő és saját felébresztő mondat. " +
                    "A program hangjait külön a Névjegy menü Hangok betanítása pontjában hallgathatod meg. " +
                    "A diktafon induláskor csak egy rövid pittyenést ad, nem beszél bele a felvételbe."
            )
        )
        add(
            TrainingStep.Explain(
                "Kész vagy! A tanuló módot bármikor újraindíthatod a Névjegy menüből. Kilépés: két gyors balra söprés."
            )
        )
    }

    private fun mainMenuPractice(
        mainItems: List<MenuItem>,
        target: String,
        successText: String
    ): TrainingStep.Practice =
        TrainingStep.Practice(
            instruction = "Gyakoroljuk a főmenü navigációt! Keresd meg: $target. Ha megvan, söprés jobbra!",
            choices = mainItems.map { it.label },
            correctIndex = mainItems.indexOfFirst { it.label == target }.coerceAtLeast(0),
            successText = successText
        )

    private fun toolsColorDetectorPractice(): TrainingStep.Practice {
        val toolsSection = MenuTree.root.first { it.id == "tools" }
        val choices = toolsSection.children.filter { child -> !isBackItem(child) }.map { it.label }
        return TrainingStep.Practice(
            instruction = "Gyakoroljuk az Eszközök menüt! Keresd meg: $PRACTICE_COLOR. Söpörj fel-le, majd jobbra ha megvan!",
            choices = choices,
            correctIndex = choices.indexOfFirst { it == PRACTICE_COLOR }.coerceAtLeast(0),
            successText = "Jó! A színfelismerő kamerával felolvassa a domináns színt. Jobbra söprés ismétli, balra kilép."
        )
    }

    private fun dictaphoneFeaturesExplain(): TrainingStep.Explain =
        TrainingStep.Explain(
            "Profi Diktafon: Eszközök, Profi Diktafon, Mentett felvételek. Válassz felvételt, jobbra söprés a műveletekhez. " +
                "Lejátszás, e-mail küldés, Bluetooth vagy más app megosztás, és felvétel törlése is elérhető."
        )

    private fun describeSection(item: MenuItem): String {
        val features = collectFeatures(item)
        return if (features.isEmpty()) {
            "Főmenü: ${item.label}. Jobbra söprés az indításhoz."
        } else {
            "Főmenü: ${item.label}. Funkciók: $features."
        }
    }

    private fun collectFeatures(item: MenuItem): String {
        if (item.children.isEmpty()) return ""
        return item.children
            .filter { child -> !isBackItem(child) }
            .joinToString(separator = ", ") { child -> describeFeature(child) }
    }

    private fun describeFeature(item: MenuItem): String {
        if (item.children.isEmpty() || item.children.all { isBackItem(it) }) {
            return item.label
        }
        val subs = item.children
            .filter { child -> !isBackItem(child) }
            .joinToString(separator = ", ") { it.label }
        return "${item.label} ($subs)"
    }

    private fun isBackItem(item: MenuItem): Boolean =
        item.action == MenuAction.SUBMENU && item.label.contains("Vissza", ignoreCase = true)
}