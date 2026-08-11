# -*- coding: utf-8 -*-
"""SuperDL modul – TV műsor: akadálymentes, felolvasott tévéújság.

Mi megy MOST, mi lesz MA ESTE, és mikor adják a kedvencedet – a földi/ingyenes
adókról is (RTL, TV2, m1, m2, Duna…). IPTV-előfizetés NEM kell hozzá: a
műsoradat egy nyilvános műsorújság-forrásból (XMLTV) jön, amit a felhasználó
felül is írhat. A SuperDL a műsoradatot nem tárolja és nem terjeszti.

register(core): „TV műsor" menüpont a Média menü alatt + az ablak."""

_state = {}


def register(core):
    from .tvmusorwin import TvMusorFrame

    opener = core.register_window(
        "tvmusor_module", lambda parent: TvMusorFrame(parent, core))
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Média", "&TV műsor") if _sub else core.add_menu("&TV műsor")
    item = core.add_menu_item(
        menu, "&TV műsor (tévéújság)\tCtrl+Shift+U", opener,
        help="Akadálymentes tévéújság: mi megy most, mi lesz ma este, és mikor "
             "adják a kedvencedet – előfizetés nélkül is")
    _state["item"] = item
    core.log.info("tvmusor modul betöltve")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
    core.log.info("tvmusor modul leszerelve")
