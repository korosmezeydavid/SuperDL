package com.superdl.launcher.games.millebornes

enum class SafetyType(val labelHu: String) {
    RIGHT_OF_WAY("Behajtási elsőbbség"),
    PUNCTURE_PROOF("Defekttűrő"),
    GAS_TANK("Üzemanyagtartály"),
    DRIVING_ACE("Vezető ász");

    fun counters(hazard: HazardType): Boolean = when (this) {
        RIGHT_OF_WAY -> hazard == HazardType.STOP
        PUNCTURE_PROOF -> hazard == HazardType.FLAT_TIRE
        GAS_TANK -> hazard == HazardType.OUT_OF_GAS
        DRIVING_ACE -> hazard == HazardType.ACCIDENT
    }
}

enum class HazardType(val labelHu: String) {
    STOP("Stop"),
    SPEED_LIMIT("Sebességkorlát"),
    OUT_OF_GAS("Benzin fogyott"),
    FLAT_TIRE("Defekt"),
    ACCIDENT("Baleset");

    fun toCard(): MilleBornesCard = when (this) {
        STOP -> MilleBornesCard.Stop
        SPEED_LIMIT -> MilleBornesCard.SpeedLimit
        OUT_OF_GAS -> MilleBornesCard.OutOfGas
        FLAT_TIRE -> MilleBornesCard.FlatTire
        ACCIDENT -> MilleBornesCard.Accident
    }
}

sealed class MilleBornesCard {
    abstract val labelHu: String

    data class Distance(val km: Int) : MilleBornesCard() {
        override val labelHu: String = "$km km"
    }

    data object Stop : MilleBornesCard() {
        override val labelHu: String = "Stop"
    }

    data object SpeedLimit : MilleBornesCard() {
        override val labelHu: String = "Sebességkorlát 50"
    }

    data object OutOfGas : MilleBornesCard() {
        override val labelHu: String = "Benzin fogyott"
    }

    data object FlatTire : MilleBornesCard() {
        override val labelHu: String = "Defekt"
    }

    data object Accident : MilleBornesCard() {
        override val labelHu: String = "Baleset"
    }

    data object Roll : MilleBornesCard() {
        override val labelHu: String = "Indulás"
    }

    data object EndOfLimit : MilleBornesCard() {
        override val labelHu: String = "Korlát vége"
    }

    data object Gasoline : MilleBornesCard() {
        override val labelHu: String = "Benzin"
    }

    data object SpareTire : MilleBornesCard() {
        override val labelHu: String = "Pótkerék"
    }

    data object Repairs : MilleBornesCard() {
        override val labelHu: String = "Javítás"
    }

    data class Safety(val type: SafetyType) : MilleBornesCard() {
        override val labelHu: String = type.labelHu
    }

    fun hazardType(): HazardType? = when (this) {
        Stop -> HazardType.STOP
        SpeedLimit -> HazardType.SPEED_LIMIT
        OutOfGas -> HazardType.OUT_OF_GAS
        FlatTire -> HazardType.FLAT_TIRE
        Accident -> HazardType.ACCIDENT
        else -> null
    }

    fun speak(): String = labelHu
}