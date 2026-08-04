package com.superdl.launcher.gps

import android.content.Context
import android.location.Location
import android.os.Handler
import android.os.Looper

object GpsAccuracyRefiner {

    const val TARGET_ACCURACY_M = 3
    const val ACCEPTABLE_ACCURACY_M = 5
    const val GOOD_ACCURACY_M = 12

    data class Result(
        val location: Location,
        val accuracyMeters: Int,
        val note: String? = null
    )

    private const val TIMEOUT_MS_DEFAULT = 18_000L
    private const val TIMEOUT_MS_HIGH_PRECISION = 25_000L
    private const val MIN_WAIT_MS = 4_000L
    private const val PROGRESS_INTERVAL_MS = 3_000L

    fun refine(
        context: Context,
        onProgress: (Int) -> Unit,
        onComplete: (Result?) -> Unit,
        targetAccuracyM: Int = GOOD_ACCURACY_M
    ): () -> Unit {
        var cancelled = false
        val handler = Handler(Looper.getMainLooper())
        val readings = mutableListOf<Location>()
        var listener: android.location.LocationListener? = null
        val startedAt = System.currentTimeMillis()
        var lastProgressAt = 0L
        var finished = false
        var timeoutRunnable: Runnable? = null
        val timeoutMs = if (targetAccuracyM <= TARGET_ACCURACY_M) {
            TIMEOUT_MS_HIGH_PRECISION
        } else {
            TIMEOUT_MS_DEFAULT
        }

        fun best(): Result? {
            val pick = readings
                .filter { it.hasAccuracy() && it.accuracy > 0f }
                .minByOrNull { it.accuracy }
                ?: readings.maxByOrNull { it.time }
                ?: return null
            return Result(pick, pick.accuracy.toInt().coerceAtLeast(1))
        }

        fun finish(timedOut: Boolean = false) {
            if (finished) return
            finished = true
            timeoutRunnable?.let { handler.removeCallbacks(it) }
            timeoutRunnable = null
            listener?.let { GpsLocationHelper.removeUpdates(context, it) }
            listener = null
            if (cancelled) return
            val result = best()
            if (result == null) {
                onComplete(null)
                return
            }
            if (timedOut) {
                val noted = when {
                    result.accuracyMeters <= ACCEPTABLE_ACCURACY_M ->
                        result.copy(note = "Időtúllépés, de elfogadható pontosság.")
                    else ->
                        result.copy(note = "Gyenge pontosság, kb. ${result.accuracyMeters} méter.")
                }
                onComplete(noted)
            } else {
                onComplete(result)
            }
        }

        GpsLocationHelper.getLastLocation(context)?.let { readings.add(it) }

        listener = GpsLocationHelper.requestUpdates(context, minIntervalMs = 1_000L) { loc ->
            if (cancelled) return@requestUpdates
            readings.add(loc)
            val acc = if (loc.hasAccuracy() && loc.accuracy > 0f) {
                loc.accuracy.toInt()
            } else {
                999
            }
            val now = System.currentTimeMillis()
            if (now - lastProgressAt >= PROGRESS_INTERVAL_MS) {
                lastProgressAt = now
                handler.post { if (!cancelled) onProgress(acc) }
            }
            val elapsed = now - startedAt
            val accurate = loc.hasAccuracy() &&
                loc.accuracy > 0f &&
                loc.accuracy <= targetAccuracyM
            if (accurate && elapsed >= MIN_WAIT_MS) {
                handler.post { finish(timedOut = false) }
            }
        }

        timeoutRunnable = Runnable { if (!cancelled) finish(timedOut = true) }
        handler.postDelayed(timeoutRunnable!!, timeoutMs)

        return {
            cancelled = true
            timeoutRunnable?.let { handler.removeCallbacks(it) }
            timeoutRunnable = null
            handler.removeCallbacksAndMessages(null)
            listener?.let { GpsLocationHelper.removeUpdates(context, it) }
            listener = null
        }
    }

    fun accuracyHint(meters: Int): String = when {
        meters <= TARGET_ACCURACY_M -> "Kiváló pontosság, kb. 3 méter alatt."
        meters <= ACCEPTABLE_ACCURACY_M -> "Nagyon jó pontosság."
        meters <= GOOD_ACCURACY_M -> "Jó pontosság, kb. $meters méter."
        meters <= 30 -> "Közepes pontosság, kb. $meters méter. Ha lehet, állj szabad ég alatt."
        else -> "Pontosság kb. $meters méter. Menj szabad ég alatt, vagy várj még a javulásra."
    }
}