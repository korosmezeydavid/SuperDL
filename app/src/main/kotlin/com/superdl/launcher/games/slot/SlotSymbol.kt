package com.superdl.launcher.games.slot

enum class SlotSymbol(
    val labelHu: String,
    val tripleMultiplier: Int
) {
    CHERRY("Cseresznye", 5),
    LEMON("Citrom", 8),
    PLUM("Szilva", 12),
    BELL("Harang", 18),
    STAR("Csillag", 30),
    DIAMOND("Gyémánt", 60),
    SEVEN("Hetes", 120);

    fun speak(): String = labelHu
}