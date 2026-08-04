package com.superdl.launcher.games.uno

enum class UnoColor(val labelHu: String) {
    RED("piros"),
    YELLOW("sárga"),
    GREEN("zöld"),
    BLUE("kék"),
    WILD("színválasztó");

    companion object {
        val PLAY_COLORS = listOf(RED, YELLOW, GREEN, BLUE)
    }
}

enum class UnoKind {
    NUMBER,
    SKIP,
    REVERSE,
    DRAW_TWO,
    WILD,
    WILD_DRAW_FOUR
}

data class UnoCard(
    val color: UnoColor,
    val kind: UnoKind,
    val number: Int = 0
) {
    fun speak(): String = when (kind) {
        UnoKind.NUMBER -> "${color.labelHu} ${number}"
        UnoKind.SKIP -> "${color.labelHu} kihagyás"
        UnoKind.REVERSE -> "${color.labelHu} irányváltás"
        UnoKind.DRAW_TWO -> "${color.labelHu} kettőt húz"
        UnoKind.WILD -> "színválasztó"
        UnoKind.WILD_DRAW_FOUR -> "színválasztó plusz négyet húz"
    }

    fun matches(top: UnoCard, currentColor: UnoColor): Boolean {
        if (kind == UnoKind.WILD || kind == UnoKind.WILD_DRAW_FOUR) return true
        if (color == currentColor) return true
        if (kind == top.kind && kind != UnoKind.NUMBER) return true
        if (kind == UnoKind.NUMBER && top.kind == UnoKind.NUMBER && number == top.number) return true
        return false
    }
}