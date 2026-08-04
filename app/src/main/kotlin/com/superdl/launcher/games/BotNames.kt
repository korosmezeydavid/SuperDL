package com.superdl.launcher.games

import kotlin.random.Random

object BotNames {

    private val POOL = listOf(
        "Anna", "Ádám", "Béla", "Bori", "Cili", "Csaba", "Dénes", "Dóra",
        "Elemér", "Eszter", "Feri", "Flóra", "Gabi", "Gergő", "Hanna", "Helga",
        "Imre", "Iván", "János", "Judit", "Károly", "Kata", "László", "Lili",
        "Márk", "Mira", "Norbi", "Nóra", "Olivér", "Orsolya", "Panni", "Péter",
        "Réka", "Róbert", "Sándor", "Szilvi", "Tamás", "Tímea", "Viktor", "Zoltán"
    )

    fun pick(count: Int, random: Random = Random.Default): List<String> =
        POOL.shuffled(random).take(count)
}