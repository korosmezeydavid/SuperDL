# -*- coding: utf-8 -*-
"""SuperDL modul – Átjáró: a PC és a SuperDL telefon összekötése.

Csatlakozás a telefon beépített WiFi-portáljához a helyi hálózaton, majd zene és
könyv küldése a telefonra. Minden a saját gépeid között marad; semmit nem
továbbítunk sehová.

register(core): „Átjáró (telefon)" menüpont az Eszközök alatt + az ablak."""

_state = {}


def register(core):
    from .atjarowin import AtjaroFrame

    opener = core.register_window("atjaro_module", AtjaroFrame)
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Eszközök", "&Átjáró (telefon)") if _sub else core.add_menu(
        "&Átjáró (telefon)")
    item = core.add_menu_item(
        menu, "&Átjáró (telefon)\tCtrl+Shift+A", opener,
        help="Zene és könyv küldése a SuperDL telefonra a helyi WiFi-n")
    _state["item"] = item
    core.log.info("atjaro modul betöltve")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
    core.log.info("atjaro modul leszerelve")
