package com.superdl.launcher.shopping

enum class ShoppingContextAction(val label: String) {
    TOGGLE_CHECKED("Megvan jelölés"),
    ADD_ITEM("Új tétel hozzáadása"),
    EDIT_NAME("Név módosítása"),
    EDIT_PRICE("Ár módosítása"),
    DELETE_ITEM("Tétel törlése"),
    DELETE_LIST("Lista törlése");

    companion object {
        val itemActions: List<ShoppingContextAction> = listOf(
            TOGGLE_CHECKED,
            ADD_ITEM,
            EDIT_NAME,
            EDIT_PRICE,
            DELETE_ITEM,
            DELETE_LIST
        )
        val summaryActions: List<ShoppingContextAction> = listOf(ADD_ITEM, DELETE_LIST)
    }
}

enum class ShoppingListContextAction(val label: String) {
    OPEN("Lista megnyitása"),
    ADD_ITEM("Új tétel"),
    RENAME("Lista átnevezése"),
    DELETE("Lista törlése");

    companion object {
        val all: List<ShoppingListContextAction> = entries.toList()
    }
}