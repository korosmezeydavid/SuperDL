package com.superdl.launcher.gps

/**
 * A hang-iránytű "söprő mód" logikája: eldönti, melyik környező hely van
 * éppen előtted (amerre nézel), és mikor kell újra kimondani.
 *
 * A vak felhasználó forgatja a telefont, és ahogy egy hely a nézési irányba
 * kerül, az app kimondja: "Nyugati pályaudvar, 11 óra, 300 méter". Amíg felé
 * nézel, páronként (néhány másodpercenként) megismétli, de nem darálja.
 */
class CompassScanHelper {

    companion object {
        // Mekkora sávban számít egy hely "előtted lévőnek" (fok, +/- irányban).
        private const val FACING_TOLERANCE_DEG = 22f
        // Ennyi időnként ismételjük ugyanazt a helyet, amíg felé nézel.
        private const val REPEAT_INTERVAL_MS = 4_000L
        // Ha másik helyre fordulsz, ennyi idő után szólalhat meg (rövid, hogy gyors legyen).
        private const val SWITCH_DEBOUNCE_MS = 600L
    }

    private var lastSpokenPoiId: String? = null
    private var lastSpokenAtMs: Long = 0L
    private var facingSinceMs: Long = 0L

    fun reset() {
        lastSpokenPoiId = null
        lastSpokenAtMs = 0L
        facingSinceMs = 0L
    }

    /**
     * A megadott POI-k és az aktuális nézési irány alapján visszaadja azt a
     * helyet, amit most ki kell mondani – vagy null-t, ha semmi újat.
     *
     * @param pois a környező helyek, MÁR a jelenlegi helyhez/irányhoz dúsítva
     *             (distanceMeters, bearingDegrees kitöltve)
     * @param headingDegrees az aktuális nézési irány (iránytű)
     * @param nowMs a jelenlegi idő
     */
    fun pickAnnouncement(
        pois: List<GpsPoi>,
        headingDegrees: Float,
        nowMs: Long
    ): GpsPoi? {
        if (pois.isEmpty()) return null

        // A hozzád legközelebbi hely, ami éppen a nézési irányban (sávon belül) van.
        val facing = pois
            .map { poi ->
                val relative = GpsRadarMath.relativeBearing(poi.bearingDegrees, headingDegrees)
                poi to relative
            }
            .filter { (_, relative) ->
                relative <= FACING_TOLERANCE_DEG || relative >= 360f - FACING_TOLERANCE_DEG
            }
            .minByOrNull { (poi, _) -> poi.distanceMeters }
            ?.first
            ?: run {
                // Semmi nincs előtted: elfelejtjük az utolsót, hogy visszafordulva újra szóljon.
                lastSpokenPoiId = null
                facingSinceMs = 0L
                return null
            }

        val isSamePoi = facing.id == lastSpokenPoiId
        return if (isSamePoi) {
            // Ugyanaz a hely: csak az ismétlési időköz után mondjuk újra.
            if (nowMs - lastSpokenAtMs >= REPEAT_INTERVAL_MS) {
                lastSpokenAtMs = nowMs
                facing
            } else {
                null
            }
        } else {
            // Új helyre fordultál: rövid késleltetés, hogy a forgatás közben ne darálja.
            if (facingSinceMs == 0L) {
                facingSinceMs = nowMs
                return null
            }
            if (nowMs - facingSinceMs >= SWITCH_DEBOUNCE_MS) {
                lastSpokenPoiId = facing.id
                lastSpokenAtMs = nowMs
                facingSinceMs = 0L
                facing
            } else {
                null
            }
        }
    }

    /** A kimondandó szöveg: "Nyugati pályaudvar, 11 óra, 300 méter". */
    fun speakText(poi: GpsPoi, headingDegrees: Float): String {
        val relative = GpsRadarMath.relativeBearing(poi.bearingDegrees, headingDegrees)
        val clock = GpsRadarMath.clockDirection(relative)
        val distance = formatDistance(poi.distanceMeters)
        return "${poi.name}, $clock, $distance"
    }

    private fun formatDistance(meters: Int): String = when {
        meters >= 1000 -> {
            val km = meters / 1000.0
            val rounded = (km * 10).toInt() / 10.0
            "$rounded kilométer"
        }
        else -> "$meters méter"
    }
}
