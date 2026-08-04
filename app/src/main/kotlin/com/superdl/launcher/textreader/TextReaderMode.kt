package com.superdl.launcher.textreader

enum class TextReaderMode(
    val extraValue: String,
    val menuLabel: String
) {
    MEDICATION_BOX("medication", "Gyógyszerdoboz olvasó"),
    PRODUCT_LABEL("label", "Címke olvasó"),
    GENERAL_TEXT("text", "Szöveg olvasó"),
    CONTINUOUS("continuous", "Folyamatos szövegolvasó");

    companion object {
        const val EXTRA_MODE = "text_reader_mode"

        fun fromExtra(value: String?): TextReaderMode =
            entries.firstOrNull { it.extraValue == value } ?: GENERAL_TEXT
    }
}