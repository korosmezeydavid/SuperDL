# -*- coding: utf-8 -*-
"""A megírt játékok REGISZTERE: kulcs → generátor-korutin.

Egy játék akkor indítható a felületről, ha a kulcsa itt szerepel. A még meg
nem írt játékok egyszerűen kimaradnak innen, és a felület tisztességesen
közli, hogy „még készül" – SOHA nincs hamis siker.

Új játék bekötése: írd meg a generátort a megfelelő modulban, majd vedd fel
ide egy sorral.
"""
from . import kaland, kartya, kviz, logika, mini, terkep

REGISZTER = {
    # logika / stratégia
    "nim": logika.jatek_nim,
    "mastermind": logika.jatek_mastermind,
    "torpedo": logika.jatek_torpedo,
    "teke": logika.jatek_teke,
    "parbaj": logika.jatek_parbaj,
    "horstep": terkep.jatek_horstep,
    "labirint": terkep.jatek_labirint,
    # kártya / kocka / szerencse
    "huszonegy": kartya.jatek_huszonegy,
    "hazard": kartya.jatek_hazard,
    "snobli": kartya.jatek_snobli,
    "kocka3": kartya.jatek_kocka3,
    "kocka1": kartya.jatek_kocka1,
    "kockadob": kartya.jatek_kockadob,
    "rulett": kartya.jatek_rulett,
    "rulibuli": kartya.jatek_rulibuli,
    "gyufa": kartya.jatek_gyufa,
    # kvíz / oktató
    "allatism": kviz.jatek_allatism,
    "fovaros": kviz.jatek_fovaros,
    "atomvad": kviz.jatek_atomvad,
    "braille": kviz.jatek_braille,
    "morse": kviz.jatek_morse,
    "kitalal": kviz.jatek_kitalal,
    "szamtan": kviz.jatek_szamtan,
    "memoria": kviz.jatek_memoria,
    "memory": kviz.jatek_memory,
    "parver": kviz.jatek_parver,
    # kaland / egyéb
    "csata": kaland.jatek_csata,
    "harcos": kaland.jatek_harcos,
    "allah": kaland.jatek_allah,
    "zongora": kaland.jatek_zongora,
    "szindbad": kaland.jatek_szindbad,
    # a JATEK.EXE gyűjtemény mini-játékai
    "domino": mini.jatek_domino,
    "tozsde": mini.jatek_tozsde,
    "korong": mini.jatek_korong,
    "nyulfarm": mini.jatek_nyulfarm,
    "hamurabi": mini.jatek_hamurabi,
    "mokita": mini.jatek_mokita,
}


def van(kulcs: str) -> bool:
    return kulcs in REGISZTER


def get(kulcs: str):
    return REGISZTER.get(kulcs)
