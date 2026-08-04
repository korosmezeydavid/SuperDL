package com.superdl.launcher.tts

import android.content.Context
import android.os.Build
import android.speech.tts.TextToSpeech
import android.speech.tts.Voice
import java.util.Locale
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

object TtsVoiceCatalog {

    private const val PROBE_TIMEOUT_MS = 1800L

    fun getSelectableOptions(context: Context): List<TtsVoiceOption> {
        val engines = TtsEngineHelper.getInstalledEngines(context)
        val options = mutableListOf<TtsVoiceOption>()
        val seen = linkedSetOf<String>()

        fun add(option: TtsVoiceOption) {
            val key = "${option.enginePackage.orEmpty()}|${option.voiceName.orEmpty()}"
            if (seen.add(key)) options.add(option)
        }

        probeEngine(context, null, "Rendszer alapértelmezett").forEach(::add)
        engines.filter { !it.isSystemDefault }.forEach { engine ->
            probeEngine(context, engine.packageName, engine.label).forEach(::add)
        }
        return options.sortedBy { it.displayLabel.lowercase(Locale.getDefault()) }
    }

    fun findCurrentIndex(options: List<TtsVoiceOption>, context: Context): Int {
        val engine = TtsEngineStore.getSelectedPackage(context)
        val voice = TtsEngineStore.getSelectedVoiceName(context)
        val exact = options.indexOfFirst {
            it.enginePackage.orEmpty() == engine.orEmpty() &&
                it.voiceName.orEmpty() == voice.orEmpty()
        }
        if (exact >= 0) return exact
        val engineOnly = options.indexOfFirst {
            it.enginePackage.orEmpty() == engine.orEmpty() && it.voiceName.isNullOrBlank()
        }
        if (engineOnly >= 0) return engineOnly
        return 0
    }

    private fun probeEngine(
        context: Context,
        enginePackage: String?,
        engineLabel: String
    ): List<TtsVoiceOption> {
        val appContext = context.applicationContext
        val latch = CountDownLatch(1)
        val holder = arrayOf<TextToSpeech?>(null)
        var initOk = false
        var voices: Set<Voice>? = null

        val listener = TextToSpeech.OnInitListener { status ->
            initOk = status == TextToSpeech.SUCCESS
            if (initOk) {
                voices = holder[0]?.voices
            }
            latch.countDown()
        }

        holder[0] = if (enginePackage.isNullOrBlank()) {
            TextToSpeech(appContext, listener)
        } else {
            TextToSpeech(appContext, listener, enginePackage)
        }

        latch.await(PROBE_TIMEOUT_MS, TimeUnit.MILLISECONDS)
        holder[0]?.shutdown()

        val discovered = voices.orEmpty()
            .sortedWith(compareBy({ it.locale?.toLanguageTag().orEmpty() }, { it.name.orEmpty() }))
            .map { voice ->
                TtsVoiceOption(
                    enginePackage = enginePackage,
                    engineLabel = engineLabel,
                    voiceName = voice.name,
                    displayLabel = formatVoiceLabel(engineLabel, voice)
                )
            }

        if (discovered.isNotEmpty()) return discovered
        return listOf(
            TtsVoiceOption(
                enginePackage = enginePackage,
                engineLabel = engineLabel,
                voiceName = null,
                displayLabel = engineLabel
            )
        )
    }

    private fun formatVoiceLabel(engineLabel: String, voice: Voice): String {
        val locale = voice.locale?.let { locale ->
            val language = locale.getDisplayLanguage(Locale("hu", "HU"))
            val country = locale.country.takeIf { it.isNotBlank() }?.let { " ($it)" }.orEmpty()
            "$language$country"
        } ?: voice.name.orEmpty()
        val quality = when {
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && voice.quality >= Voice.QUALITY_VERY_HIGH -> "nagyon jó minőség"
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && voice.quality >= Voice.QUALITY_HIGH -> "jó minőség"
            else -> null
        }
        return buildString {
            append(engineLabel)
            append(" – ")
            append(locale.ifBlank { voice.name.orEmpty() })
            if (!quality.isNullOrBlank()) append(", $quality")
        }
    }
}