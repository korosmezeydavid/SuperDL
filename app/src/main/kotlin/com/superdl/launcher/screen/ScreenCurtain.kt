package com.superdl.launcher.screen

import android.content.Context
import android.graphics.Color
import android.graphics.PixelFormat
import android.os.Build
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.view.WindowManager

/**
 * SÖTÉT MÓD — a képernyő teljes elfüggönyözése.
 *
 * MIRE JÓ:
 *  - MAGÁNSZFÉRA: senki nem látja, mit csinálsz a telefonon
 *  - AKKUMULÁTOR: a kijelző a telefon legnagyobb fogyasztója; fekete képpel
 *    (főleg OLED kijelzőn) jelentősen kevesebbet fogyaszt
 *  - KÉNYELEM: nem világít bele a sötét szobába
 *
 * A LÉNYEG: a fekete réteg CSAK LÁTHATATLANNÁ tesz, de NEM FOGJA EL az
 * érintéseket — a telefon ugyanúgy kezelhető alatta. Ezt a
 * FLAG_NOT_TOUCHABLE és FLAG_NOT_FOCUSABLE együttes használata biztosítja.
 *
 * Mindenek FÖLÖTT jelenik meg (TYPE_APPLICATION_OVERLAY), tehát más
 * alkalmazásban, sőt a rendszer felületein is takar.
 */
object ScreenCurtain {

    private var curtainView: View? = null

    /** Aktív-e éppen a sötét mód? */
    fun isActive(): Boolean = curtainView != null

    /** Megvan-e a "más alkalmazások fölé rajzolás" engedély? */
    fun hasPermission(context: Context): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Settings.canDrawOverlays(context)
        } else {
            true
        }

    /**
     * A függöny felhúzása (sötét mód BE).
     * @return sikerült-e (hamis, ha hiányzik az engedély)
     */
    fun show(context: Context): Boolean {
        if (curtainView != null) return true
        if (!hasPermission(context)) return false

        val app = context.applicationContext
        return try {
            val wm = app.getSystemService(Context.WINDOW_SERVICE) as WindowManager
            val view = View(app).apply { setBackgroundColor(Color.BLACK) }

            val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            } else {
                @Suppress("DEPRECATION")
                WindowManager.LayoutParams.TYPE_SYSTEM_OVERLAY
            }

            val params = WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.MATCH_PARENT,
                type,
                // EZ A KULCS: a réteg NEM fogja el az érintéseket, nem kap
                // fókuszt, és a rendszersávok alá is benyúlik — így teljesen
                // takar, de a telefon alatta ugyanúgy kezelhető marad.
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                    WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
                PixelFormat.OPAQUE
            ).apply {
                gravity = Gravity.TOP or Gravity.START
                // A kijelző fényereje a minimumra — így OLED-en és LCD-n is
                // a lehető legkevesebbet fogyaszt.
                screenBrightness = 0.01f
            }

            wm.addView(view, params)
            curtainView = view
            true
        } catch (e: Exception) {
            android.util.Log.w(TAG, "A sotet mod nem kapcsolhato be: ${e.message}")
            false
        }
    }

    /** A függöny leengedése (sötét mód KI). */
    fun hide(context: Context) {
        val view = curtainView ?: return
        try {
            val wm = context.applicationContext
                .getSystemService(Context.WINDOW_SERVICE) as WindowManager
            wm.removeView(view)
        } catch (e: Exception) {
            android.util.Log.w(TAG, "A sotet mod kikapcsolasa hiba: ${e.message}")
        }
        curtainView = null
    }

    /** Váltás: ha be van kapcsolva, kikapcsol; különben be. */
    fun toggle(context: Context): Boolean {
        return if (isActive()) {
            hide(context)
            false
        } else {
            show(context)
        }
    }

    private const val TAG = "SDL_CURTAIN"
}
