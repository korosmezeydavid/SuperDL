"""SuperDL modul – Fájlküldés gépről gépre (P2P).

A P2P-fájlküldés TELJES kódja (p2p.py + p2pwin.py) ITT, a modulban van. A
tényleges átvitelt a Core futtatókörnyezetébe csomagolt magic-wormhole végzi (a
modul a `wormhole` futtatókönyvtárat használja, a Core `--wh` indítóján át). A
modul SEMMILYEN más SuperDL-modult nem importál.

register(core): „Fájlküldés" menü + a P2P-ablak (egyablakosan); unregister leszerel."""

_state = {}


def register(core):
    from .p2pwin import P2PFrame

    opener = core.register_window("p2p_module", P2PFrame)
    # Nem média, nem könyv → a meglévő Eszközök menübe (új Core-on egyetlen
    # elemként); régi Core-on saját „Fájlküldés" felső menü.
    menu = core.add_menu("&Eszközök" if hasattr(core, "add_submenu") else "Fá&jlküldés")
    item = core.add_menu_item(
        menu, "Fájlküldés gépről gé&pre (P2P)\tCtrl+Shift+T", opener,
        help="Nagy fájl küldése egy másik gépre felhő nélkül, bemondható "
             "kóddal, titkosítva")
    _state["item"] = item

    # MÁSODIK belépő (2026-09-06): egyenesen a mappaküldésbe.
    # Eredetileg a Core fájlválasztójába terveztük — a lemez-ellenőrzés viszont
    # kiderítette, hogy a `fajlvalaszto.py` VÁLASZTÓ párbeszéd, nem fájlkezelő
    # (az Androidon a fájlKEZELŐből indul a megosztás, itt olyan nincs).
    # Egy második menüpont a természetes windowsos megfelelője — és így a
    # funkció MODULFRISSÍTÉSSEL kimehet, Core-kiadás nélkül.
    from .p2pwin import mappa_kuldes_inditasa

    def mappa_menu(*_a):
        opener()
        mappa_kuldes_inditasa()

    _state["mappa"] = core.add_menu_item(
        menu, "&Mappa küldése és megosztás…\tCtrl+Shift+M", mappa_menu,
        help="Egy egész mappa becsomagolása és elküldése – gépről gépre vagy "
             "ideiglenes tárhelyre")
    core.log.info("p2p modul betöltve")


def unregister(core):
    # MINDKÉT menüpontot le kell szerelni – egy ottfelejtett menüpont a modul
    # eltávolítása után hibára futna, és a felhasználó azt hinné, elromlott.
    for kulcs in ("item", "mappa"):
        item = _state.pop(kulcs, None)
        if item is not None:
            core.remove_menu_item(item)
    core.log.info("p2p modul leszerelve")
