package com.superdl.launcher.keyboard

/**
 * A 3x4-es telefonbillentyűzet gombjai és a hozzájuk tartozó karakterek.
 *
 * A hagyományos SMS-kiosztást követi, magyar ékezetekkel kiegészítve — így aki
 * valaha nyomógombos telefonon írt, annak ismerős lesz, és NEM kell hozzá
 * Braille-tudás.
 *
 * A gombok elhelyezkedése a kalibrált középponthoz (az 5-ös) képest:
 *
 *      1   2   3
 *      4  [5]  6
 *      7   8   9
 *      *   0   #
 */
enum class MatrixKey(
    /** Oszlop a középponthoz képest: -1 bal, 0 közép, +1 jobb. */
    val col: Int,
    /** Sor a középponthoz képest: -1 fent, 0 közép, +1 alatta, +2 legalul. */
    val row: Int,
    /** Felolvasható név (amikor a felhasználó ráérkezik). */
    val label: String,
    /** A gomb karakterei, ebben a sorrendben pörögnek. */
    val chars: List<Char>
) {
    KEY_1(-1, -1, "egyes", listOf('1', '.', ',', '?', '!')),
    KEY_2(0, -1, "kettes", listOf('a', 'á', 'b', 'c', '2')),
    KEY_3(1, -1, "hármas", listOf('d', 'e', 'é', 'f', '3')),
    KEY_4(-1, 0, "négyes", listOf('g', 'h', 'i', 'í', '4')),
    KEY_5(0, 0, "ötös", listOf('j', 'k', 'l', '5')),
    KEY_6(1, 0, "hatos", listOf('m', 'n', 'o', 'ó', 'ö', 'ő', '6')),
    KEY_7(-1, 1, "hetes", listOf('p', 'q', 'r', 's', '7')),
    KEY_8(0, 1, "nyolcas", listOf('t', 'u', 'ú', 'ü', 'ű', 'v', '8')),
    KEY_9(1, 1, "kilences", listOf('w', 'x', 'y', 'z', '9')),
    KEY_STAR(-1, 2, "csillag", listOf('-', ':', ';', '(', ')', '"', '\'')),
    KEY_0(0, 2, "nulla", listOf(' ', '0')),
    KEY_HASH(1, 2, "kettőskereszt", emptyList());

    companion object {
        /** Melyik gomb van ezen a rács-koordinátán? */
        fun at(col: Int, row: Int): MatrixKey? =
            entries.firstOrNull { it.col == col && it.row == row }
    }
}
