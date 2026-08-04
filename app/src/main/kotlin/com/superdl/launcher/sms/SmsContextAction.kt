package com.superdl.launcher.sms

enum class SmsContextAction(val label: String) {
    READ("Üzenet felolvasása"),
    REPLY("Válasz küldése"),
    FORWARD("Üzenet továbbítása"),
    DELETE("Üzenet törlése");

    companion object {
        val all: List<SmsContextAction> = entries.toList()
    }
}