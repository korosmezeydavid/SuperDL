package com.superdl.launcher.environment

enum class ObjectCategory(
    val id: String,
    val hungarianName: String,
    val cocoLabels: Set<String>
) {
    DOOR("door", "Ajtó", emptySet()),
    CHAIR(
        "chair",
        "Szék",
        setOf("chair", "couch", "bench")
    ),
    TABLE("table", "Asztal", setOf("dining table")),
    PERSON("person", "Személy", setOf("person")),
    FLOOR_OBJECT(
        "floor_object",
        "Földön lévő tárgy",
        setOf(
            "bottle",
            "cup",
            "book",
            "backpack",
            "handbag",
            "suitcase",
            "laptop",
            "umbrella"
        )
    ),
    PHONE("phone", "Telefon", setOf("cell phone")),
    ANIMAL(
        "animal",
        "Állat",
        setOf("dog", "cat", "bird", "horse", "sheep", "cow")
    ),
    VEHICLE(
        "vehicle",
        "Jármű",
        setOf("car", "bus", "truck", "bicycle", "motorcycle", "train")
    ),
    SCREEN("screen", "Képernyő", setOf("tv")),
    BED("bed", "Ágy", setOf("bed")),
    PLANT("plant", "Növény", setOf("potted plant"));

    companion object {
        private val labelToCategory: Map<String, ObjectCategory> =
            entries.flatMap { category ->
                category.cocoLabels.map { label -> label.lowercase() to category }
            }.toMap()

        fun fromCocoLabel(label: String): ObjectCategory? =
            labelToCategory[label.trim().lowercase()]
    }
}