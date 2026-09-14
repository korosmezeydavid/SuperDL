# -*- coding: utf-8 -*-
"""SuperDL modul – Super Edit: szövegszerkesztő, amiben a formázás HALLHATÓ.

Az ablak kulcsa `superedit_module`: a Core FÁJLTÁRSÍTÁSA erre a kulcsra
irányítja a rákattintott szövegfájlokat, és az ablak `open_file()`-ját hívja.

A menüpont az ESZKÖZÖK almenübe kerül – aki letölti a modult, ott találja meg.
"""

_state = {"items": []}


def register(core):
    from .szerkesztowin import SuperEditFrame

    opener = core.register_window("superedit_module", SuperEditFrame)
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Eszközök", "Super &Edit") if _sub \
        else core.add_menu("Super &Edit")
    item = core.add_menu_item(
        menu, "Super &Edit – szövegszerkesztő\tCtrl+Shift+E", opener,
        help="Formázott szövegszerkesztő, amiben a formázás hallható; "
             "Word, szövegfájl, weblap, Markdown, PDF-export és AI-funkciók")
    _state["items"].append(item)
    core.log.info("superedit modul betöltve")


def unregister(core):
    for item in _state.pop("items", []):
        core.remove_menu_item(item)
    _state["items"] = []
    core.log.info("superedit modul leszerelve")
