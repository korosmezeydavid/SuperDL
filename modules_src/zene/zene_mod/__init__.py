# -*- coding: utf-8 -*-
"""SuperDL modul – Zene: a lehető legegyszerűbb lejátszó.

Egy mappát adsz meg, minden alatta lévő szám bekerül egy listába, fel-le
nyíllal lépkedsz, és szól. Semmi mást nem tud – ez nem hiányosság, hanem a
feladat.
"""

_state = {"items": []}


def register(core):
    from .zenewin import ZeneFrame

    menu = core.add_menu("&Zene")
    opener = core.register_window("zene_module", ZeneFrame)
    item = core.add_menu_item(
        menu, "&Zenelejátszó\tCtrl+Shift+Z", opener,
        help="Egyszerű zenelejátszó: egy mappa minden száma egy listában, "
             "fel-le nyíllal lépkedve")
    _state["items"].append(item)
    core.log.info("zene modul betöltve")


def unregister(core):
    for item in _state.pop("items", []):
        core.remove_menu_item(item)
    _state["items"] = []
    core.log.info("zene modul leszerelve")
