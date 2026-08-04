package com.superdl.launcher.gps

/**
 * A mentett helyekhez ("hangos emlékhely") tartozó műveletek.
 * A műveletek listája dinamikus: a hangjegyzet lejátszása/törlése csak
 * akkor jelenik meg, ha van rögzített hangjegyzet.
 */
enum class SavedPoiContextAction(val label: String) {
    GUIDE("Útmutatás ide"),
    PLAY_VOICE_NOTE("Hangjegyzet lejátszása"),
    RECORD_VOICE_NOTE("Hangjegyzet rögzítése"),
    DELETE_VOICE_NOTE("Hangjegyzet törlése"),
    DELETE_POI("Hely törlése");

    companion object {
        fun forPoi(hasVoiceNote: Boolean): List<SavedPoiContextAction> = buildList {
            add(GUIDE)
            if (hasVoiceNote) {
                add(PLAY_VOICE_NOTE)
                add(RECORD_VOICE_NOTE) // felülírás
                add(DELETE_VOICE_NOTE)
            } else {
                add(RECORD_VOICE_NOTE)
            }
            add(DELETE_POI)
        }
    }
}
