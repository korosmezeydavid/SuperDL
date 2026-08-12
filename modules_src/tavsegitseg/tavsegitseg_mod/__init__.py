# -*- coding: utf-8 -*-
"""SuperDL modul – Távsegítség: akadálymentes távvezérlés/távsegítség.

Egy megbízható ember távolról segíthet a gépeden (irányítás + a géped hangját,
benne a képernyőolvasót, hallja), vagy te segíthetsz valakinek – szoba-kóddal,
szerver nélkül, csak internettel. SZIGORÚAN felügyelt, beleegyezés-alapú:
minden munkamenetet a segített indít, minden irányítást ő engedélyez, és pánikkal
(Ctrl+Alt+Pause) bármikor azonnal bontható. NINCS néma/rejtett hozzáférés.

register(core): „Távsegítség" menüpont a Kommunikáció menü alatt + az ablak."""

_state = {}


def register(core):
    from .tavsegitseg_win import TavsegitsegWin

    opener = core.register_window(
        "tavsegitseg_module", lambda parent: TavsegitsegWin(parent, core))
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Kommunikáció", "&Távsegítség") if _sub else core.add_menu(
        "&Távsegítség")
    item = core.add_menu_item(
        menu, "&Távsegítség\tCtrl+Alt+T", opener,
        help="Akadálymentes távsegítség/távvezérlés – megbízható segítővel, "
             "szoba-kóddal, felügyelt módban")
    _state["item"] = item
    core.log.info("tavsegitseg modul betöltve")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
    core.log.info("tavsegitseg modul leszerelve")
