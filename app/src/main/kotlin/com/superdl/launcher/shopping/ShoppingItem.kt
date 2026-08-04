package com.superdl.launcher.shopping

data class ShoppingItem(
    val id: Int,
    val name: String,
    val checked: Boolean = false,
    val priceHuf: Int? = null
) {
    fun speakPreview(): String {
        val pricePart = priceHuf?.let { ", $it forint" }.orEmpty()
        return if (checked) "$name$pricePart. Megvan." else "$name$pricePart. Még nincs meg."
    }

    fun speakPrice(): String =
        if (priceHuf != null) "$priceHuf forint" else "ár nincs megadva"
}