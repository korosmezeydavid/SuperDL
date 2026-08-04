package com.superdl.launcher.games

enum class PlayerMode(val labelHu: String, val botCount: Int) {
    TWO_PLAYER("Kétszemélyes", 1),
    FOUR_PLAYER("Négyszemélyes", 3);

    companion object {
        val OPTIONS = entries.toList()
    }
}