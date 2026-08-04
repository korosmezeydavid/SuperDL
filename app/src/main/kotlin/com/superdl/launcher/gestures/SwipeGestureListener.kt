package com.superdl.launcher.gestures

import android.content.Context
import android.view.GestureDetector
import android.view.MotionEvent
import kotlin.math.abs

class SwipeGestureListener(
    context: Context,
    private val onSwipeUp: () -> Unit,
    private val onSwipeDown: () -> Unit,
    private val onSwipeRight: () -> Unit,
    private val onSwipeLeft: () -> Unit,
    private val onLongPress: (() -> Unit)? = null,
    private val onDoubleTap: (() -> Unit)? = null
) : GestureDetector.SimpleOnGestureListener() {

    companion object {
        private const val SWIPE_THRESHOLD = 100       // minimum px elmozdulás
        private const val SWIPE_VELOCITY_THRESHOLD = 100  // minimum px/s sebesség
    }

    val detector = GestureDetector(context, this)

    override fun onDown(e: MotionEvent): Boolean = true  // kötelező true!

    override fun onLongPress(e: MotionEvent) {
        onLongPress?.invoke()
    }

    override fun onDoubleTap(e: MotionEvent): Boolean {
        onDoubleTap?.invoke()
        return onDoubleTap != null
    }

    override fun onFling(
        e1: MotionEvent?,
        e2: MotionEvent,
        velocityX: Float,
        velocityY: Float
    ): Boolean {
        val e1 = e1 ?: return false

        val diffX = e2.x - e1.x
        val diffY = e2.y - e1.y

        return if (abs(diffX) > abs(diffY)) {
            // Vízszintes söprés
            if (abs(diffX) > SWIPE_THRESHOLD && abs(velocityX) > SWIPE_VELOCITY_THRESHOLD) {
                if (diffX > 0) onSwipeRight() else onSwipeLeft()
                true
            } else false
        } else {
            // Függőleges söprés
            if (abs(diffY) > SWIPE_THRESHOLD && abs(velocityY) > SWIPE_VELOCITY_THRESHOLD) {
                if (diffY > 0) onSwipeDown() else onSwipeUp()
                true
            } else false
        }
    }
}
