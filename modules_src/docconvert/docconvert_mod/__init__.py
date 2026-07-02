"""SuperDL modul – Dokumentum-konverter (az ELSŐ, VALÓDIBAN kiemelt funkció).

A converter TELJES kódja (docconvert.py + docconvertwin.py) ITT, a MODULBAN van;
a Core csak a MEGOSZTOTT segédeket (booktext, extratools, ocr, fpdf, python-docx,
ebooklib) adja a `superdl` csomagon át. Így a konverter ÖNÁLLÓAN frissíthető, a
Core (a nagy exe) újraépítése nélkül – ez a moduláris katalógus lényege.

A `register(core)` hozzáadja a „Dokumentumok" menüt a konverterrel (egyablakosan,
a core.register_window-on át); az `unregister(core)` mindent leszerel."""

_state = {}


def register(core):
    from .docconvertwin import DocConvertFrame    # a converter-ablak a MODULBAN

    opener = core.register_window("docconvert_module", DocConvertFrame)
    # Minden, ami dokumentum/szöveg = a Könyvek menü alá.
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Könyvek", "&Dokumentum-konverter") if _sub else core.add_menu("&Dokumentumok")
    item = core.add_menu_item(
        menu, "Dokumentum-&konverter\tCtrl+Shift+D", opener,
        help="Dokumentum átalakítása más formátumba (TXT, DOCX, EPUB, PDF, "
             "HTML, RTF, ODT, Markdown…), beépített PDF-fel és OCR-rel")
    _state["item"] = item
    core.log.info("docconvert modul betöltve")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
    core.log.info("docconvert modul leszerelve")
