package com.superdl.launcher.feedback

import android.media.RingtoneManager

enum class AlertSoundPreset(
    val label: String,
    val ringtoneType: Int? = null,
    val toneSequence: List<Pair<Int, Int>>? = null
) {
    ALARM(
        "Ébresztő hang",
        RingtoneManager.TYPE_ALARM,
        toneSequence = listOf(
            880 to 220,
            0 to 200,
            1100 to 280,
            0 to 350,
            880 to 220
        )
    ),
    RINGTONE(
        "Csengőhang",
        RingtoneManager.TYPE_RINGTONE,
        toneSequence = listOf(
            784 to 180,
            0 to 100,
            988 to 220,
            0 to 120,
            1175 to 200
        )
    ),
    NOTIFICATION(
        "Értesítés hang",
        RingtoneManager.TYPE_NOTIFICATION,
        toneSequence = listOf(
            1046 to 140,
            0 to 80,
            1318 to 160
        )
    ),
    BELL(
        "Csengő – három hang",
        toneSequence = listOf(523 to 140, 659 to 140, 784 to 200)
    ),
    SOFT_CHIME(
        "Lágy csengő",
        toneSequence = listOf(880 to 120, 1175 to 180)
    ),
    DOUBLE_BEEP(
        "Dupla síp",
        toneSequence = listOf(880 to 100, 0 to 80, 880 to 100)
    );

    companion object {
        val selectable: List<AlertSoundPreset> = entries.toList()
    }
}