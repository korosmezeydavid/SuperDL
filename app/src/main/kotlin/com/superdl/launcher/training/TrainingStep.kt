package com.superdl.launcher.training

sealed class TrainingStep {

    /** Magyarázó szöveg – jobbra söprés: tovább */
    data class Explain(val text: String) : TrainingStep()

    /** Gyakorló feladat – fel/le választás, jobbra: válasz */
    data class Practice(
        val instruction: String,
        val choices: List<String>,
        val correctIndex: Int,
        val successText: String,
        val wrongText: String = "Ez nem az. Söpörj fel vagy le tovább keresni."
    ) : TrainingStep()
}