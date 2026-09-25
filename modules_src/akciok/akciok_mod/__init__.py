# -*- coding: utf-8 -*-
"""SuperDL modul – Akciós újság: a boltok heti akciói olvasható listában,
saját bevásárlólistával, ami összefésülhető a telefonéval.

register(core): „Akciós újság” menüpont az Eszközök alatt + az ablak."""

_state = {}


def register(core):
    from .akciokwin import AkciokFrame

    opener = core.register_window(
        "akciok_module", lambda parent: AkciokFrame(parent, core))
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Eszközök", "Akciós új&ság") if _sub \
        else core.add_menu("Akciós új&ság")
    item = core.add_menu_item(
        menu, "Akciós új&ság (Penny, Lidl, Aldi)\tCtrl+Alt+A", opener,
        help="A boltok heti akciói felolvasható listában, bevásárlólistával")
    _state["item"] = item
    core.log.info("akciok modul betöltve")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
    core.log.info("akciok modul leszerelve")
