package com.superdl.launcher.dictaphone

import android.media.AudioFormat

enum class DictaphoneChannels(val count: Int, val label: String, val inputConfig: Int) {
    MONO(1, "Monó, egy csatorna", AudioFormat.CHANNEL_IN_MONO),
    STEREO(2, "Sztereó, két csatorna", AudioFormat.CHANNEL_IN_STEREO);

    fun speakSummary(): String = label
}