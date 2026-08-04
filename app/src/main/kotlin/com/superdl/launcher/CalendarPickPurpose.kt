package com.superdl.launcher

/**
 * A "Program szerkesztése" és "Program törlése" menüpontok szándéka: a közös
 * programlista-választó (CalendarPick) ez alapján dönti el, mit tegyen a
 * kiválasztott programmal (jobbra söpréskor).
 */
enum class CalendarPickPurpose {
    EDIT,
    DELETE
}
