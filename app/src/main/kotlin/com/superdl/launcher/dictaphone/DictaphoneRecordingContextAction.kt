package com.superdl.launcher.dictaphone

enum class DictaphoneRecordingContextAction(val label: String) {
    PLAY("Lejátszás"),
    SHARE_EMAIL("Megosztás e-mailben"),
    SHARE_SYSTEM("Megosztás Bluetooth vagy más app"),
    DELETE("Felvétel törlése");

    companion object {
        val all: List<DictaphoneRecordingContextAction> = entries.toList()
    }
}