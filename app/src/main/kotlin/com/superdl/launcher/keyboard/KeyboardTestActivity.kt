package com.superdl.launcher.keyboard

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.MotionEvent
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import com.superdl.launcher.gestures.SwipeGestureListener
import com.superdl.launcher.tts.TtsManager

/**
 * BILLENTYŰZET VÁLASZTÓ ÉS PRÓBAPAD.
 *
 * KÉT SZAKASZBAN működik:
 *
 *  1. VÁLASZTÁS: egy lista a SuperDL billentyűzeteiről (mátrix, Braille).
 *     Fel-le lépkedsz, jobbra söpréssel megnyitod a próbát azzal.
 *     Korábban itt AZONNAL betöltött az aktuális billentyűzet, és nem lehetett
 *     mást választani — ez volt a "zsákutca".
 *
 *  2. PRÓBA: megnyílik egy szövegmező, ahol írhatsz vele. A billentyűzeten
 *     belül HÁROM UJJAL (mátrix) vagy KÉT UJJAL FELFELÉ (Braille) átválthatsz
 *     a másikra — programból csak a futó billentyűzet tud váltani.
 */
class KeyboardTestActivity : Activity() {

    private lateinit var tts: TtsManager
    private lateinit var gestureListener: SwipeGestureListener
    private lateinit var root: LinearLayout
    private lateinit var label: TextView
    private var input: EditText? = null

    /** Melyik szakaszban vagyunk. */
    private var inTestMode = false
    private var choiceIndex = 0

    private val choices = listOf(
        "Mátrix billentyűzet" to "egy ujjal, telefonszám elrendezés"
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(Color.BLACK)
            setPadding(32, 32, 32, 32)
        }
        label = TextView(this).apply {
            textSize = 24f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        }
        root.addView(label)
        setContentView(root)

        tts = TtsManager(this)
        gestureListener = SwipeGestureListener(
            context = this,
            onSwipeUp = { onUp() },
            onSwipeDown = { onDown() },
            onSwipeRight = { onRight() },
            onSwipeLeft = { onLeft() }
        )

        showChoice()
    }

    // ── 1. SZAKASZ: választás ───────────────────────────────────────────────

    private fun showChoice() {
        inTestMode = false
        input = null
        root.removeAllViews()
        root.addView(label)
        updateChoiceLabel()
        tts.speak(
            "Billentyűzet választása. ${choices.size} lehetőség. " +
                "Fel-le válogatás, jobbra a kipróbálás, balra kilépés."
        )
        tts.speakAdd(speakChoice())
    }

    private fun updateChoiceLabel() {
        label.text = "${choices[choiceIndex].first}\n${choices[choiceIndex].second}"
    }

    private fun speakChoice(): String =
        "${choices[choiceIndex].first}: ${choices[choiceIndex].second}."

    private fun moveChoice(delta: Int) {
        choiceIndex = (choiceIndex + delta + choices.size) % choices.size
        updateChoiceLabel()
        tts.speak(speakChoice())
    }

    // ── 2. SZAKASZ: próba ───────────────────────────────────────────────────

    /** A kiválasztott billentyűzettel megnyitjuk a próbamezőt. */
    private fun startTest() {
        inTestMode = true
        val chosen = choices[choiceIndex].first

        root.removeAllViews()
        val field = EditText(this).apply {
            textSize = 22f
            setTextColor(Color.WHITE)
            hint = getString(com.superdl.launcher.R.string.keyboard_test_hint)
            setHintTextColor(Color.GRAY)
        }
        input = field
        root.addView(
            field,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
        )

        field.requestFocus()
        field.postDelayed({
            val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
            imm.showSoftInput(field, InputMethodManager.SHOW_IMPLICIT)
        }, 300L)

        tts.speak(
            "$chosen kipróbálása. Ha nem ez jött elő, a billentyűzeten belül " +
                "HÁROM ujjal előhívhatod a választót."
        )
    }

    // ── Gesztusok ───────────────────────────────────────────────────────────

    private fun onUp() {
        if (inTestMode) {
            // Próba közben: a rendszer választója (tartalék lehetőség).
            try {
                val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
                imm.showInputMethodPicker()
            } catch (_: Exception) {
            }
        } else {
            moveChoice(-1)
        }
    }

    private fun onDown() {
        if (inTestMode) speakContent() else moveChoice(+1)
    }

    private fun onRight() {
        if (inTestMode) speakContent() else startTest()
    }

    private fun onLeft() {
        if (inTestMode) {
            // Vissza a választáshoz, nem ki az egészből.
            speakContent()
            showChoice()
        } else {
            tts.speak("Kilépés.")
            finish()
        }
    }

    private fun speakContent() {
        val text = input?.text?.toString().orEmpty()
        if (text.isBlank()) tts.speak("A mező üres.") else tts.speak("Beírva: $text")
    }

    override fun onTouchEvent(event: MotionEvent): Boolean =
        gestureListener.detector.onTouchEvent(event) || super.onTouchEvent(event)

    override fun onDestroy() {
        try {
            tts.shutdown()
        } catch (_: Exception) {
        }
        super.onDestroy()
    }
}
