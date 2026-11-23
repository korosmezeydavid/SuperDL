"""Super Fájlok: tallózó, másolás, tömörítés, társítás, FTP és SFTP."""

_state = {}


def register(core):
    from .fajlokwin import FajlokFrame
    from .helywin import HelyFrame
    from .tallozowin import TallozoFrame, TarsitasListaFrame

    menu = core.add_menu("Fá&jlok")
    masolo = core.register_window("fajlok_module", FajlokFrame)
    tallozo = core.register_window("fajlok_tallozo", TallozoFrame)
    tarsitas = core.register_window("fajlok_tarsitas", TarsitasListaFrame)
    helyek = core.register_window("fajlok_helyek", HelyFrame)
    _state["items"] = [
        core.add_menu_item(
            menu, "&Másolás és áthelyezés\tCtrl+Alt+Y", masolo,
            help="Fájlok és mappák másolása vagy áthelyezése, egyenként, "
                 "százalékkal és hátralévő idővel"),
        core.add_menu_item(
            menu, "&Tallózó\tCtrl+Alt+U", tallozo,
            help="Meghajtók és mappák. Az Enter a társítás szerint nyitja a fájlt"),
        core.add_menu_item(
            menu, "&Helyek, FTP és SFTP\tCtrl+Alt+H", helyek,
            help="FTP és SFTP csatolása. A jelszó titkosítva tárolódik"),
        core.add_menu_item(
            menu, "Tá&rsítások", tarsitas,
            help="Melyik kiterjesztést a Zene, a feliratolvasó, a Super Edit, "
                 "a Könyvolvasó vagy egy külső program nyissa"),
    ]
    core.log.info("fajlok modul betöltve")


def unregister(core):
    for item in _state.pop("items", []):
        core.remove_menu_item(item)
    core.log.info("fajlok modul leszerelve")
