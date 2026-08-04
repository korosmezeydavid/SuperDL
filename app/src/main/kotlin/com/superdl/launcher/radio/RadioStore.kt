package com.superdl.launcher.radio

import android.content.Context
import com.superdl.launcher.storage.JsonPrefsHelper
import org.json.JSONArray
import org.json.JSONObject

/**
 * Elmentett (kedvenc) rádióállomások tára. A projekt szokásos JSON-SharedPrefs
 * mintáját követi (JsonPrefsHelper), ahogy a podcast-feliratkozások is.
 */
object RadioStore {

    private const val PREFS = "superdl_radio"
    private const val KEY_STATIONS = "radio_stations"
    private const val KEY_SCHEMA = "radio_schema"
    private const val SCHEMA_VERSION = 1

    /**
     * Beépített magyar állomások — hálózat nélkül is kilistázhatók, valódi
     * stream-címekkel (a Radio Browser adatbázisából). Ha egy URL idővel
     * elévül, a keresés (RadioHelper) mindig friss, ellenőrzött címet ad.
     */
    val BUILTIN: List<RadioStation> = listOf(
        RadioStation("builtin_kossuth", "Kossuth Rádió",
            "https://icast.connectmedia.hu/4736/mr1.mp3", builtin = true),
        RadioStation("builtin_petofi", "Petőfi Rádió",
            "https://icast.connectmedia.hu/4738/mr2.mp3", builtin = true),
        RadioStation("builtin_klubradio", "Klubrádió",
            "https://a7.asurahosting.com:8160/radio.mp3", builtin = true),
        RadioStation("builtin_dancewave", "Dance Wave",
            "https://dancewave.online/dance.mp3", builtin = true),
        RadioStation("builtin_dancewave_retro", "Dance Wave Retro",
            "https://retro.dancewave.online/retrodance.mp3", builtin = true),
    )

    fun getStations(context: Context): List<RadioStation> {
        val arr = JsonPrefsHelper.readJsonArray(context, PREFS, KEY_STATIONS, KEY_SCHEMA, SCHEMA_VERSION)
        val list = mutableListOf<RadioStation>()
        for (i in 0 until arr.length()) {
            val o = arr.optJSONObject(i) ?: continue
            list.add(
                RadioStation(
                    id = o.optString("id"),
                    name = o.optString("name"),
                    streamUrl = o.optString("streamUrl"),
                    builtin = o.optBoolean("builtin", false)
                )
            )
        }
        return list
    }

    fun addStation(context: Context, station: RadioStation) {
        val current = getStations(context).toMutableList()
        // Ne duplikáljon: azonos id vagy azonos stream-URL esetén nem adjuk hozzá újra.
        if (current.any { it.id == station.id || it.streamUrl == station.streamUrl }) return
        current.add(station)
        save(context, current)
    }

    fun removeStation(context: Context, stationId: String) {
        val current = getStations(context).filterNot { it.id == stationId }
        save(context, current)
    }

    fun isSaved(context: Context, station: RadioStation): Boolean =
        getStations(context).any { it.id == station.id || it.streamUrl == station.streamUrl }

    private fun save(context: Context, stations: List<RadioStation>) {
        val arr = JSONArray()
        stations.forEach { s ->
            arr.put(
                JSONObject()
                    .put("id", s.id)
                    .put("name", s.name)
                    .put("streamUrl", s.streamUrl)
                    .put("builtin", s.builtin)
            )
        }
        JsonPrefsHelper.saveJsonArray(context, PREFS, KEY_STATIONS, KEY_SCHEMA, SCHEMA_VERSION, arr)
    }
}
