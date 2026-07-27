# -*- coding: utf-8 -*-
"""A megírt játékok REGISZTERE: kulcs → generátor-korutin.

Egy játék akkor indítható a felületről, ha a kulcsa itt szerepel. A még meg
nem írt játékok egyszerűen kimaradnak innen, és a felület tisztességesen
közli, hogy „még készül" – SOHA nincs hamis siker.

Új játék bekötése: írd meg a generátort a megfelelő modulban, majd vedd fel
ide egy sorral.
"""
from . import homelab, kaland, kartya, kviz, logika, milliomos, mini, sajat, terkep

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
    "huszonegy": homelab.jatek_huszonegy,   # Ócsvári Áron hiteles verziója
    "hazard": kartya.jatek_hazard,
    "snobli": kartya.jatek_snobli,
    "kocka3": kartya.jatek_kocka3,
    "kocka1": kartya.jatek_kocka1,
    "kockadob": kartya.jatek_kockadob,
    "rulett": kartya.jatek_rulett,
    "rulibuli": kartya.jatek_rulibuli,
    "gyufa": homelab.jatek_gyufapoc,   # forráshű GYUFAPOC (a régi általános helyett)
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
    # SuperDL SAJÁT játékok (nem retró)
    "slot": sajat.jatek_slot,
    "uno": sajat.jatek_uno,
    "milliomos": milliomos.jatek_milliomos,   # LOIM-inspirált kvíz, saját, jogtiszta
    "enektanito": sajat.jatek_enektanito,     # a gép a saját hangján énekel
    # HITELES portok a hivatalos Homelab/Brailab gyűjteményből
    "blackjack": homelab.jatek_blackjack,
    "szamkit1": homelab.jatek_szamkit1,
    "amoba": homelab.jatek_amoba,
    "nimjatek": homelab.jatek_nimjatek,
    "memteszt": homelab.jatek_memteszt,
    "lotto": homelab.jatek_lotto,
    "foldrajz": homelab.jatek_foldrajz,
    "szamkit2": homelab.jatek_szamkit2,
    "dobokoc": homelab.jatek_dobokoc,
    "kocka": homelab.jatek_kocka,
    "fejtoro": homelab.jatek_fejtoro,
    "kockaparti": homelab.jatek_kockaparti,
    "celozz": homelab.jatek_celozz,
    "tizfeles": homelab.jatek_tizfeles,
    "fogadas": homelab.jatek_fogadas,
    "szokita": homelab.jatek_szokita,
    "szofajok": homelab.jatek_szofajok,
    "reszeg": homelab.jatek_reszeg,
    "betpoker": homelab.jatek_betpoker,
    "felkaru": homelab.jatek_felkaru,
    "randi": homelab.jatek_randi,
    "loverseny": homelab.jatek_loverseny,
    "nurmi": homelab.jatek_nurmi,
    "penzfel": homelab.jatek_penzfel,
    "kincs": homelab.jatek_kincs,
    "apollo": homelab.jatek_apollo,
    "simon15": homelab.jatek_simon15,
    "jvelem": homelab.jatek_jvelem,
    "atlantisz": homelab.jatek_atlantisz,
    "szammem": homelab.jatek_szammem,
    "hajocsata": homelab.jatek_hajocsata,
}


def van(kulcs: str) -> bool:
    return kulcs in REGISZTER


def get(kulcs: str):
    return REGISZTER.get(kulcs)
