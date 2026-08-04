package com.superdl.launcher.environment

/**
 * "Mi van előttem?" – egyetlen folyékony magyar mondatba sűríti egy kamera-
 * pillanatkép összes felismert tárgyát, térbeli leírással.
 *
 * Példa: "Egy személy közvetlenül előtted. Két szék, a legközelebbi egy
 * méterre balra. Egy asztal távolabb jobbra."
 *
 * Elvek vak felhasználónak:
 * - A SZEMÉLY mindig első (társas helyzet a legfontosabb információ)
 * - Utána a közelebbi tárgyak (nagyobb terület = közelebb)
 * - Azonos kategóriák csoportosítva ("két szék"), a legközelebbi pozíciójával
 * - Legfeljebb 4 kategória, hogy ne legyen fárasztó
 */
object SceneSummarizer {

    private const val MAX_CATEGORIES = 4

    fun summarize(detections: List<DetectionResult>): String {
        if (detections.isEmpty()) {
            return "Nem látok felismerhető tárgyat előtted. " +
                "Fordulj kicsit más irányba, és próbáld újra jobbra söpréssel."
        }

        // Kategóriánként csoportosítjuk, a legnagyobb (legközelebbi) példánnyal.
        val groups = detections
            .groupBy { it.category }
            .map { (category, items) ->
                CategoryGroup(
                    category = category,
                    count = items.size,
                    nearest = items.maxByOrNull { it.area } ?: items.first()
                )
            }
            .sortedWith(
                compareByDescending<CategoryGroup> { it.category == ObjectCategory.PERSON }
                    .thenByDescending { it.nearest.area }
            )
            .take(MAX_CATEGORIES)

        val parts = groups.map { group -> describeGroup(group) }
        return parts.joinToString(" ")
    }

    private data class CategoryGroup(
        val category: ObjectCategory,
        val count: Int,
        val nearest: DetectionResult
    )

    private fun describeGroup(group: CategoryGroup): String {
        val position = SpatialDescriber.describe(group.nearest.boundingBox)
        val name = group.category.hungarianName.lowercase()
        return if (group.count == 1) {
            "Egy $name $position."
        } else {
            "${countWord(group.count).replaceFirstChar { it.uppercase() }} $name, " +
                "a legközelebbi $position."
        }
    }

    private fun countWord(count: Int): String = when (count) {
        2 -> "két"
        3 -> "három"
        4 -> "négy"
        5 -> "öt"
        else -> "több"
    }
}
