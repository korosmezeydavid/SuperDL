"""SuperDL PILOT modul – Dokumentum-konverter.

Ez az ELSŐ, modulként szállított SuperDL-funkció: bemutatja a teljes moduláris
betöltést. A `register(core)` a Core↔Modul SZERZŐDÉSEN (CoreContext) át ad egy
menüt és egy menüpontot, ami a dokumentum-konvertert nyitja (EGYABLAKOSAN, a
core.register_window-on át). A tényleges konverziós kód (booktext, extratools,
ocr, fpdf, python-docx, ebooklib) a Core FUTTATÓKÖRNYEZETÉBEN van – a modul ezt
a Core csomagjain át éri el, nem importál más MODULT.

A modul SEMMIT nem hagy maga után: az `unregister(core)` leszereli a menüt (a
frissítéshez/eltávolításhoz)."""

# modul-szintű állapot (a leszereléshez); a modul SOHA nem nyúl a Core belső
# szerkezetéhez, csak a `core`-on és a Core futtatókörnyezetén át
_state = {}


def register(core):
    # a beépített konverter-ablak a Core futtatókörnyezetéből (a Core bundle-ölte)
    from superdl.docconvertwin import DocConvertFrame

    opener = core.register_window("docconvert_module", DocConvertFrame)
    menu = core.add_menu("Modu&l: Dokumentumok")
    item = core.add_menu_item(
        menu, "Dokumentum-&konverter (modul)\tCtrl+Alt+D", opener,
        help="Dokumentum átalakítása más formátumba (modulként)")
    _state["item"] = item
    core.log.info("docconvert modul betöltve: menüpont hozzáadva")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
    core.log.info("docconvert modul leszerelve")
