package com.superdl.launcher.tts

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ResolveInfo
import android.os.Build
import android.speech.tts.TextToSpeech
import java.util.Locale

object TtsEngineHelper {

    private val defaultEngine = TtsEngine(null, "Rendszer alapértelmezett")

    fun getInstalledEngines(context: Context): List<TtsEngine> {
        val pm = context.packageManager
        val discovered = linkedMapOf<String, TtsEngine>()

        fun addEngine(packageName: String, label: String) {
            if (packageName.isBlank()) return
            discovered.putIfAbsent(
                packageName,
                TtsEngine(packageName, label.ifBlank { packageName })
            )
        }

        val intent = Intent(TextToSpeech.Engine.INTENT_ACTION_TTS_SERVICE)
        queryTtsServices(pm, intent).forEach { resolve ->
            val pkg = resolve.serviceInfo?.packageName ?: return@forEach
            val label = resolve.loadLabel(pm)?.toString()?.trim().orEmpty()
            addEngine(pkg, label)
        }

        // Fallback: scan installed packages for embedded TTS service declarations.
        pm.getInstalledPackages(PackageManager.GET_SERVICES).forEach { pkgInfo ->
            val pkg = pkgInfo.packageName
            if (discovered.containsKey(pkg)) return@forEach
            val probe = Intent(TextToSpeech.Engine.INTENT_ACTION_TTS_SERVICE).apply {
                setPackage(pkg)
            }
            if (queryTtsServices(pm, probe).isNotEmpty()) {
                val label = pm.getApplicationLabel(pkgInfo.applicationInfo).toString()
                addEngine(pkg, label)
            }
        }

        val engines = discovered.values.sortedBy { it.label.lowercase(Locale.getDefault()) }
        return listOf(defaultEngine) + engines
    }

    private fun queryTtsServices(pm: PackageManager, intent: Intent): List<ResolveInfo> {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            pm.queryIntentServices(
                intent,
                PackageManager.ResolveInfoFlags.of(PackageManager.MATCH_ALL.toLong())
            )
        } else {
            @Suppress("DEPRECATION")
            pm.queryIntentServices(intent, PackageManager.MATCH_ALL)
        }
    }

    fun findCurrentIndex(engines: List<TtsEngine>, selectedPackage: String?): Int {
        if (selectedPackage.isNullOrBlank()) return 0
        val index = engines.indexOfFirst { it.packageName == selectedPackage }
        return if (index >= 0) index else 0
    }

    fun getCurrentEngine(context: Context): TtsEngine {
        val engines = getInstalledEngines(context)
        val index = findCurrentIndex(engines, TtsEngineStore.getSelectedPackage(context))
        return engines[index]
    }
}