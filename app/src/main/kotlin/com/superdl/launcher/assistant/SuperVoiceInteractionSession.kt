package com.superdl.launcher.assistant

import android.app.KeyguardManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.service.voice.VoiceInteractionSession
import com.superdl.launcher.MainActivity

class SuperVoiceInteractionSession(context: Context) : VoiceInteractionSession(context) {

    private val handler = Handler(Looper.getMainLooper())

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        launchAssistant(fromKeyguard = isKeyguardLocked())
    }

    private fun isKeyguardLocked(): Boolean {
        val keyguard = context.getSystemService(KeyguardManager::class.java) ?: return false
        return keyguard.isKeyguardLocked
    }

    private fun launchAssistant(fromKeyguard: Boolean) {
        val launch = Intent(context, MainActivity::class.java).apply {
            action = MainActivity.ACTION_LAUNCH_VOICE_ASSISTANT
            addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP or
                    Intent.FLAG_ACTIVITY_REORDER_TO_FRONT
            )
            putExtra(MainActivity.EXTRA_LAUNCH_VOICE_ASSISTANT, true)
            putExtra(MainActivity.EXTRA_ASSISTANT_FROM_KEYGUARD, fromKeyguard)
        }
        try {
            context.startActivity(launch)
            handler.postDelayed({ hide() }, 1500)
        } catch (_: Exception) {
            hide()
        }
    }
}