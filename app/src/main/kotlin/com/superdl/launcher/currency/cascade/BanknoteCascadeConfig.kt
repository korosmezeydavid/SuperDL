package com.superdl.launcher.currency.cascade

/**
 * Prioritásos hibrid kaszkád konfiguráció.
 *
 * KÖTELEZŐ sorrend (nem módosítható a fő útvonalon):
 *   1. Szín + geometria előszűrés (< 8 ms / frame cél)
 *   2. OCR a címlet számjegyére (szín által leszűkített jelöltek)
 *   3. YOLO csak legvégső fallback — alapból KIKAPCSOLVA
 *
 * MIÉRT: a szintetikus képeken tanult YOLO valós körülmények között
 * használhatatlan; a téves valutaazonosítás katasztrófa vak felhasználónál.
 */
object BanknoteCascadeConfig {

    /**
     * Ha false: a YOLO soha nem fut a fő útvonalon.
     * Ha true: csak akkor, ha Stage1 és Stage2 is alacsony bizalmú.
     */
    const val YOLO_FALLBACK_ENABLED: Boolean = false

    /** Minimum egymást követő azonos eredmény TTS előtt. */
    // Ennyi EGYMÁS UTÁNI azonos eredmény kell a bemondáshoz. Az 5 túl szigorú
    // volt: egyetlen bizonytalan képkocka is nullázta a sorozatot, ezért csak
    // tökéletesen tartott bankjegynél szólalt meg. A 4 még mindig erős védelem
    // (a szín-sávok átfedésmentesek), de sokkal engedékenyebb kézben tartásnál.
    const val TEMPORAL_WINDOW: Int = 5
    const val TEMPORAL_REQUIRED: Int = 4

    // ── Stage 1: szín + geometria ──────────────────────────────────────────
    /** Cél: frame-enként < 8 ms low-end eszközön. */
    const val COLOR_STAGE_BUDGET_MS: Long = 8L
    const val COLOR_SAMPLE_SIZE: Int = 48
    // Enyhébb küszöbök: a bankjegy lehet távolabb, gyűrött, részben takart.
    // A téves címlet ellen NEM ezek védenek, hanem az ÁTFEDÉSMENTES szín-sávok
    // (BanknoteBuiltinColorReference) és a margó-ellenőrzés.
    const val COLOR_MIN_SCORE: Float = 0.48f
    const val COLOR_STRONG_SCORE: Float = 0.62f
    const val COLOR_MIN_MARGIN: Float = 0.14f
    // Elég, ha a kép ~12%-a színes: így a bankjegyet nem kell a kamera elé
    // tolni, kartávolságból is működik.
    const val COLOR_MIN_COLORFUL_FRACTION: Float = 0.12f

    /**
     * Bankjegy jellegű arány a színes maszk bounding box-án.
     * Ferde tartás, részleges takarás, ujjal félig fogott bankjegy esetén a
     * látható rész aránya bármi lehet — ezért tág a tartomány.
     */
    const val ASPECT_MIN: Float = 1.05f
    const val ASPECT_MAX: Float = 4.20f

    /**
     * Élsűrűség a színes régión: nyomtatott bankjegy > egyszínű papír.
     * Elmosódott (nem tökéletesen fókuszált) képen kevesebb él látszik.
     */
    const val EDGE_DENSITY_MIN: Float = 0.007f

    // ── Stage 2: OCR ───────────────────────────────────────────────────────
    /** OCR nem minden frame-en: low-end + ML Kit terhelés. */
    const val OCR_EVERY_N_FRAMES: Int = 2
    const val OCR_RESULT_MAX_AGE_MS: Long = 900L
    const val OCR_MIN_CONFIDENCE: Float = 0.62f
    const val OCR_WITH_COLOR_AGREE_CONFIDENCE: Float = 0.92f

    // ── Stage 3: YOLO fallback (ha engedélyezett) ──────────────────────────
    const val YOLO_ONLY_IF_COLOR_SCORE_BELOW: Float = 0.50f
    const val YOLO_ONLY_IF_NO_OCR: Boolean = true
}
