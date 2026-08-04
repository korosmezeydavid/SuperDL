package com.superdl.launcher.assistant

import android.service.voice.VoiceInteractionService
import android.service.voice.VoiceInteractionSession

class SuperVoiceInteractionService : VoiceInteractionService() {

    override fun onReady() {
        super.onReady()
    }

    override fun onLaunchVoiceAssistFromKeyguard() {
        launchAssistSession()
    }

    fun launchAssistSession() {
        showSession(
            null,
            VoiceInteractionSession.SHOW_WITH_ASSIST
        )
    }
}