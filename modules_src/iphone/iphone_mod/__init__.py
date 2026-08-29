# -*- coding: utf-8 -*-
"""SuperDL modul – iPhone: zene, fotó, videó és hangfelvétel MENTÉSE a gépre,
illetve TÖRLÉSE a telefonról, USB-kábelen.

Külön modul, nem az Átjáró része: az Átjáró a SuperDL saját telefonos
ökoszisztémájához (az Android launcherhez) tartozik, ez pedig egy idegen
készülékkel dolgozik, más protokollal.

register(core): „iPhone (zene, fotó, videó)" menüpont az Eszközök alatt."""

_state = {}


def register(core):
    from .iphonewin import IPhoneFrame

    opener = core.register_window("iphone_module", IPhoneFrame)
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Eszközök", "&iPhone") if _sub else core.add_menu("&iPhone")
    item = core.add_menu_item(
        menu, "&iPhone (zene, fotó, videó)\tCtrl+Shift+P", opener,
        help="Zene, fotó, videó és hangfelvétel mentése iPhone-ról a gépre, "
             "illetve törlése a telefonról")
    _state["item"] = item
    core.log.info("iphone modul betöltve")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
    core.log.info("iphone modul leszerelve")
