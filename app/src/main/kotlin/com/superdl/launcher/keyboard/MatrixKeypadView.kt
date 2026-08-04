package com.superdl.launcher.keyboard

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.os.Handler
import android.os.Looper
import android.view.MotionEvent
import android.view.View

/**
 * A mátrix-billentyűzet beviteli felülete.
 *
 * MŰKÖDÉS EGY UJJAL:
 *  1. Leteszed az ujjad -> a mátrix KÖZEPE (az 5-ös) oda kerül.
 *  2. Elcsúsztatod a kívánt gomb felé -> a billentyűzet bemondja a gomb nevét,
 *     majd PÖRGETNI kezdi a gomb karaktereit (m, n, o, ó, ö, ő, 6...).
 *  3. Felengeded -> az ÉPPEN kimondott karakter íródik be.
 *  4. Ha közben meggondolod magad, átcsúszol egy másik gombra: az újratölti a
 *     saját karaktereit elölről.
 *  5. Újra letéve az ujjad a mátrix ÚJRAKALIBRÁLÓDIK az új pozíció köré.
 *
 * Nincs multi-touch, nincs pontos célzás — ezért működik ott is, ahol a
 * Braille-bevitel elakadna.
 */
@SuppressLint("ViewConstructor")
class MatrixKeypadView(
    context: Context,
    private val listener: Listener
) : View(context) {

    interface Listener {
        /** Ráérkeztünk egy gombra (bemondandó: a gomb neve). */
        fun onKeyEntered(key: MatrixKey)
        /** A pörgetés következő karaktere (bemondandó). */
        fun onCharCycled(ch: Char)
        /** Felengedés: ez a karakter íródjon be. */
        fun onCharCommitted(ch: Char)
        /** Felengedés karakter nélkül (nem volt érvényes gomb). */
        fun onReleasedWithoutChar()
        /** Az ujj lehelyezése — a mátrix kalibrálva. */
        fun onCalibrated()
        /** A módváltó (kettőskereszt) gomb elengedve. */
        fun onModeKeyReleased()
        /** SZÖVEGTÁR módban: erre a helyre engedték fel az ujjat. */
        fun onTextBankKeyReleased(slot: MatrixKey)
        /** KÉT UJJAS gesztus (ezek nem keverednek az egyujjas írással). */
        fun onTwoFingerGesture(gesture: Gesture)
    }

    /**
     * Két ujjal végezhető parancsok.
     *
     * MIÉRT KÉT UJJAL: a mátrixban az EGYUJJAS mozgás maga a gombválasztás —
     * balra csúszni ugyanaz, mintha a hatosról a négyesre lépnél. Ezért a
     * parancsokhoz KÉT ujj kell, azok sosem keverednek az írással.
     */
    enum class Gesture { BACKSPACE, ENTER, CLOSE, HELP, DICTATE, SWITCH_KEYBOARD, TEXT_BANK }

    /**
     * SZÖVEGTÁR MÓD: ilyenkor a gombok nem betűket, hanem elmentett szövegeket
     * jelentenek. A mozgás UGYANAZ — csak a tartalom más.
     */
    var textBankMode = false
        private set

    fun setTextBank(on: Boolean) {
        textBankMode = on
        stopCycling()
        currentKey = null
        charIndex = 0
    }

    private val layout = MatrixLayout(
        MatrixKeyboardPrefs.getCellSizeDp(context) * resources.displayMetrics.density
    )
    private val handler = Handler(Looper.getMainLooper())

    private var currentKey: MatrixKey? = null
    private var charIndex = 0
    private var cycleMs = MatrixKeyboardPrefs.getCycleMs(context)

    // ── Két ujjas gesztusok állapota ────────────────────────────────────────
    /** Két ujj van-e éppen a képernyőn (ilyenkor NEM írunk). */
    private var twoFingerMode = false
    /** A két ujj kiindulási középpontja és távolsága. */
    private var startCenterX = 0f
    private var startCenterY = 0f
    private var startSpread = 0f
    /** Volt-e három ujj a képernyőn (billentyűzet-váltás). */
    private var threeFingerUsed = false

    /** Kétujjas koppintások számlálása (a hármas koppintáshoz). */
    private var twoFingerTaps = 0
    private var lastTwoFingerTapAt = 0L

    private val background = Paint().apply { color = Color.BLACK }

    companion object {
        /** Ennyi időn belüli újabb koppintás számít "többszörösnek". */
        private const val MULTI_TAP_MS = 600L
    }

    /** A karakter-pörgetést végző ismétlődő feladat. */
    private val cycleRunnable = object : Runnable {
        override fun run() {
            val key = currentKey ?: return
            if (key.chars.isEmpty()) return
            charIndex = (charIndex + 1) % key.chars.size
            listener.onCharCycled(key.chars[charIndex])
            handler.postDelayed(this, cycleMs)
        }
    }

    override fun onDraw(canvas: Canvas) {
        // A felület szándékosan üres és fekete: vak használatra készült, a
        // visszajelzés hangban és beszédben érkezik.
        canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), background)
    }

    /**
     * Elég MAGAS beviteli felület ahhoz, hogy a 3x4-es mátrix elférjen az ujj
     * köré kalibrálva. A rendszer alapértelmezett billentyűzet-sávja szűk lenne
     * a szélső gombok eléréséhez.
     */
    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val screenHeight = resources.displayMetrics.heightPixels
        setMeasuredDimension(
            MeasureSpec.getSize(widthMeasureSpec),
            (screenHeight * 0.6f).toInt()
        )
    }

    @SuppressLint("ClickableViewAccessibility")
    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {

            MotionEvent.ACTION_DOWN -> {
                // ÚJRAKALIBRÁLÁS minden lehelyezéskor: a mátrix közepe oda kerül,
                // ahová az ujj leért. Így nem kell megkeresni a billentyűzetet.
                cycleMs = MatrixKeyboardPrefs.getCycleMs(context)
                layout.setCellSize(
                    MatrixKeyboardPrefs.getCellSizeDp(context) * resources.displayMetrics.density
                )
                layout.calibrate(event.x, event.y)
                currentKey = null
                charIndex = 0
                listener.onCalibrated()
                // A középső gomb (5-ös) azonnal aktív lesz, hiszen ott az ujj.
                enterKey(MatrixKey.KEY_5)
                return true
            }

            MotionEvent.ACTION_POINTER_DOWN -> {
                // MÁSODIK UJJ: parancs-módba váltunk, az írás felfüggesztve.
                if (event.pointerCount == 2) {
                    stopCycling()
                    twoFingerMode = true
                    startCenterX = (event.getX(0) + event.getX(1)) / 2f
                    startCenterY = (event.getY(0) + event.getY(1)) / 2f
                    startSpread = spreadOf(event)
                    // KOPPINTÁS-SZÁMLÁLÁS: a gyors, egymás utáni kétujjas
                    // érintések számából derül ki a hármas koppintás.
                    val now = System.currentTimeMillis()
                    twoFingerTaps = if (now - lastTwoFingerTapAt < MULTI_TAP_MS) {
                        twoFingerTaps + 1
                    } else 1
                    lastTwoFingerTapAt = now
                }
                // HÁROM UJJ: váltás a másik SuperDL billentyűzetre.
                if (event.pointerCount >= 3) {
                    stopCycling()
                    threeFingerUsed = true
                }
                return true
            }

            MotionEvent.ACTION_MOVE -> {
                if (twoFingerMode) return true      // parancs közben nem írunk
                val key = layout.keyAt(event.x, event.y)
                if (key != currentKey) {
                    // Másik gombra csúsztunk: annak a karakterei kezdenek elölről.
                    if (key != null) enterKey(key) else leaveKey()
                }
                return true
            }

            MotionEvent.ACTION_POINTER_UP -> {
                // A két ujjas parancs a MÁSODIK UJJ felemelésekor dől el.
                if (twoFingerMode && event.pointerCount == 2) {
                    detectTwoFingerGesture(event)?.let { listener.onTwoFingerGesture(it) }
                }
                return true
            }

            MotionEvent.ACTION_UP -> {
                stopCycling()
                // HÁROM UJJ volt: billentyűzet-váltás, semmit nem írunk.
                if (threeFingerUsed) {
                    threeFingerUsed = false
                    twoFingerMode = false
                    currentKey = null
                    charIndex = 0
                    layout.reset()
                    listener.onTwoFingerGesture(Gesture.SWITCH_KEYBOARD)
                    return true
                }
                if (twoFingerMode) {
                    // Parancs volt, nem írás — semmit nem ütünk be.
                    twoFingerMode = false
                    currentKey = null
                    charIndex = 0
                    layout.reset()
                    return true
                }
                val key = currentKey
                when {
                    key == null -> listener.onReleasedWithoutChar()
                    // SZÖVEGTÁR MÓDBAN a felengedés a mentett szöveget illeszti be
                    // (vagy üres helynél felajánlja a feltöltést).
                    textBankMode -> listener.onTextBankKeyReleased(key)
                    key == MatrixKey.KEY_HASH -> listener.onModeKeyReleased()
                    key.chars.isEmpty() -> listener.onReleasedWithoutChar()
                    else -> listener.onCharCommitted(key.chars[charIndex])
                }
                currentKey = null
                charIndex = 0
                layout.reset()
                return true
            }

            MotionEvent.ACTION_CANCEL -> {
                stopCycling()
                twoFingerMode = false
                currentKey = null
                charIndex = 0
                layout.reset()
                return true
            }
        }
        return super.onTouchEvent(event)
    }

    /** A két ujj távolsága — a csípés felismeréséhez. */
    private fun spreadOf(event: MotionEvent): Float {
        if (event.pointerCount < 2) return 0f
        val dx = event.getX(0) - event.getX(1)
        val dy = event.getY(0) - event.getY(1)
        return kotlin.math.sqrt(dx * dx + dy * dy)
    }

    /**
     * Melyik két ujjas parancs történt?
     *
     * CSÍPÉS (az ujjak közelítése) = billentyűzet bezárása — ez a felhasználó
     * ötlete, és jó, mert semmi máshoz nem hasonlít.
     * A söprések iránya adja a többi parancsot.
     */
    private fun detectTwoFingerGesture(event: MotionEvent): Gesture? {
        // HÁRMAS KOPPINTÁS két ujjal: a szövegtár megnyitása/bezárása.
        // Ezt előbb vizsgáljuk, mert nem mozgás-alapú.
        if (twoFingerTaps >= 3) {
            twoFingerTaps = 0
            return Gesture.TEXT_BANK
        }
        val endSpread = spreadOf(event)
        val cellSize = layout.getCellSize()

        // 1. CSÍPÉS: az ujjak érdemben közeledtek egymáshoz -> bezárás.
        if (startSpread > 0 && endSpread < startSpread - cellSize) {
            return Gesture.CLOSE
        }
        // 2. SZÉTHÚZÁS: az ujjak érdemben távolodtak -> DIKTÁLÁS.
        // Szimmetrikus a csípéssel: összehúzod = bezár, széthúzod = beszélsz.
        if (startSpread > 0 && endSpread > startSpread + cellSize) {
            return Gesture.DICTATE
        }

        val endCenterX = (event.getX(0) + event.getX(1)) / 2f
        val endCenterY = (event.getY(0) + event.getY(1)) / 2f
        val dx = endCenterX - startCenterX
        val dy = endCenterY - startCenterY
        val threshold = cellSize * 1.2f

        return when {
            kotlin.math.abs(dx) > threshold && kotlin.math.abs(dx) > kotlin.math.abs(dy) ->
                if (dx < 0) Gesture.BACKSPACE else Gesture.ENTER
            dy > threshold -> Gesture.CLOSE          // két ujjal lefelé: bezárás
            dy < -threshold -> Gesture.HELP          // két ujjal felfelé: súgó
            else -> null
        }
    }

    /** Belépés egy gombra: bemondjuk a nevét, és indul a karakter-pörgetés. */
    private fun enterKey(key: MatrixKey) {
        stopCycling()
        currentKey = key
        charIndex = 0
        listener.onKeyEntered(key)
        // SZÖVEGTÁR MÓDBAN nincs pörgetés: a gomb egyetlen dolgot jelent,
        // a hozzá mentett szöveget. Azt a szolgáltatás mondja be.
        if (textBankMode) return
        if (key.chars.isNotEmpty()) {
            // Az ELSŐ karakter azonnal elhangzik, a többi a pörgetéssel.
            listener.onCharCycled(key.chars[0])
            handler.postDelayed(cycleRunnable, cycleMs)
        }
    }

    /** Kicsúsztunk a mátrixból: nincs aktív gomb. */
    private fun leaveKey() {
        stopCycling()
        currentKey = null
        charIndex = 0
    }

    private fun stopCycling() {
        handler.removeCallbacks(cycleRunnable)
    }

    override fun onDetachedFromWindow() {
        stopCycling()
        super.onDetachedFromWindow()
    }
}
