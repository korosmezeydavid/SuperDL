package com.superdl.launcher.timer

import android.content.Context
import android.content.Intent
import android.os.Build
import com.superdl.launcher.patrol.PatrolAnnouncer

object TimerManager {

    fun isRunning(context: Context): Boolean {
        val session = TimerStore.getActiveSession(context) ?: return false
        return !session.isFinished()
    }

    fun start(context: Context, timer: TimerEntry) {
        stop(context)
        val session = ActiveTimerSession(
            timerId = timer.id,
            label = timer.label,
            durationMinutes = timer.durationMinutes,
            announceIntervalMinutes = timer.announceIntervalMinutes,
            startedAtMillis = System.currentTimeMillis(),
            lastAnnouncedElapsedMinutes = 0
        )
        TimerStore.saveActiveSession(context, session)
        startService(context)
    }

    fun stop(context: Context) {
        TimerStore.clearActiveSession(context)
        context.stopService(Intent(context, TimerService::class.java))
    }

    fun resumeIfNeeded(context: Context) {
        val session = TimerStore.getActiveSession(context) ?: return
        if (session.isFinished()) {
            PatrolAnnouncer.announce(context, TimerSpeech.speakFinished(session.label)) {
                TimerStore.clearActiveSession(context)
            }
            return
        }
        startService(context)
    }

    fun speakActiveStatus(context: Context): String? {
        val session = TimerStore.getActiveSession(context) ?: return null
        if (session.isFinished()) return null
        return TimerSpeech.speakProgress(
            session.label,
            session.elapsedMinutes(),
            session.remainingMinutes()
        )
    }

    private fun startService(context: Context) {
        val intent = Intent(context, TimerService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        } catch (_: Exception) {}
    }
}