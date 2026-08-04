package com.superdl.launcher.feedback

import com.superdl.launcher.R

enum class GameSoundType(
    val resId: Int,
    val label: String
) {
    CARD_FLICK(R.raw.snd_card_flick, "Kártya húzás"),
    CARD_PLACE(R.raw.snd_card_place, "Kártya lerakás"),
    CARD_DEAL(R.raw.snd_card_deal, "Kártya osztás"),
    GAME_WIN(R.raw.snd_game_win, "Győzelem"),
    GAME_LOSE(R.raw.snd_game_lose, "Vereség"),
    SLOT_LEVER(R.raw.snd_slot_lever, "Félkarú rabló kar"),
    SLOT_SPIN(R.raw.snd_slot_spin, "Pörgetés"),
    SLOT_REEL_STOP(R.raw.snd_slot_reel_stop, "Tárcsa megáll"),
    SLOT_WIN(R.raw.snd_slot_win, "Nyeremény"),
    SLOT_JACKPOT(R.raw.snd_slot_jackpot, "Jackpot"),
    SLOT_LOSE(R.raw.snd_slot_lose, "Nem nyert"),
    MB_GREEN_LIGHT(R.raw.snd_mb_green_light, "Zöld lámpa"),
    MB_STOP(R.raw.snd_mb_stop, "Stop"),
    MB_FLAT_TIRE(R.raw.snd_mb_flat_tire, "Defekt"),
    MB_ACCIDENT(R.raw.snd_mb_accident, "Baleset"),
    MB_OUT_OF_GAS(R.raw.snd_mb_out_of_gas, "Benzin fogyott"),
    MB_SPEED_LIMIT(R.raw.snd_mb_speed_limit, "Sebességkorlát"),
    MB_MILEAGE(R.raw.snd_mb_mileage, "Kilométer"),
    MB_SAFETY(R.raw.snd_mb_safety, "Biztonsági lap");
}