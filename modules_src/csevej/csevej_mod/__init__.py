# -*- coding: utf-8 -*-
"""SuperDL modul – Csevejcenter: akadálymentes, valós idejű csevegő.

Gépek közötti csevegés szoba-kóddal, szerver és beállítás nélkül (Ably-alapú
szoba, csak internet kell). Semmit nem tárolunk sehol. Ez az M1 (szöveges
csevegés + jelenlét); később térbeli, sztereó hangos konferencia épül rá.

register(core): „Csevejcenter” menüpont a Kommunikáció menü alatt + az ablak."""

_state = {}


def register(core):
    from .csevejwin import CsevejFrame

    # a core-t a keretbe injektáljuk (a voice/store eléréséhez)
    opener = core.register_window(
        "csevej_module", lambda parent: CsevejFrame(parent, core))
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Kommunikáció", "&Csevejcenter") if _sub else core.add_menu(
        "&Csevejcenter")
    item = core.add_menu_item(
        menu, "&Csevejcenter\tCtrl+Shift+C", opener,
        help="Akadálymentes valós idejű csevegő gépek között, szoba-kóddal")
    _state["item"] = item
    core.log.info("csevej modul betöltve")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
    core.log.info("csevej modul leszerelve")
