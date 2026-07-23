# -*- coding: utf-8 -*-
"""A játékok KATALÓGUSA – ide kerülnek be az egyes játékok.

Ez a keretrendszer „nyilvántartása": a felület ebből építi a két listát. Egy
játék hozzáadásához elég ide egy sor, és megírni az indító függvényét.

FONTOS ELV: ha egy játék még NINCS kész, az `indit=None` marad. A felület
ilyenkor MEGMONDJA, hogy még készül – SOHA nem tesz úgy, mintha elindult
volna. (Ugyanaz az elv, mint a program többi részében: nincs hamis siker.)
"""
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class Jatek:
    kulcs: str
    nev: str
    leiras: str
    indit: Optional[Callable] = None      # indit(szulo_ablak) -> None


# ---------------------------------------------------------------- RETRÓ
# A 80-as/90-es évek magyar beszélő gépeinek hangulatában, korhű retró
# beszédhanggal. A szerzőkkel egyeztetett, engedélyezett tartalom.
RETRO: tuple[Jatek, ...] = (
    Jatek("akaszto", "Akasztófa",
          "Klasszikus betűkitalálós játék: magyar szavak, korhű gépi hanggal."),
    Jatek("mastermind", "Mastermind (kódtörő)",
          "Találd ki a rejtett számsort a visszajelzések alapján."),
    Jatek("nim", "Nim-játék",
          "Gyufaszálas logikai játék a gép ellen – aki az utolsót elveszi, nyer."),
    Jatek("torpedo", "Torpedó",
          "Hajókeresés hangalapú rácson, bemondott koordinátákkal."),
    Jatek("kockapoker", "Kockapóker",
          "Kockadobós szerencsejáték, bemondott dobásokkal és pontokkal."),
    Jatek("szojatek", "Szójáték",
          "Szókincsfejlesztő betű- és szófejtő feladatok."),
)

# ------------------------------------------------------- SUPERDL SAJÁT
SAJAT: tuple[Jatek, ...] = (
    Jatek("hangmemoria", "Hangmemória",
          "Párosítsd a hangokat! Tisztán hallás utáni memóriajáték."),
    Jatek("iranyerzek", "Iránytű",
          "Térbeli hallás gyakorlása: honnan jön a hang?"),
    Jatek("reakcio", "Reakcióidő",
          "Milyen gyorsan reagálsz a jelre? Napi eredménykövetéssel."),
)


def mind() -> tuple[Jatek, ...]:
    return RETRO + SAJAT


def keres(kulcs: str) -> Optional[Jatek]:
    for j in mind():
        if j.kulcs == kulcs:
            return j
    return None
