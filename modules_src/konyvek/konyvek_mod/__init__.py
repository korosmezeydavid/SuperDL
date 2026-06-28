"""SuperDL modul – Könyvek (olvasás és hangoskönyv-készítés).

Egy use-case-be tartozó könyv-eszközök EGY modulban (a menübuborék elkerülésére):
akadálymentes Könyvolvasó (élő felolvasás könyvjelzővel, folytatható) és
Hangoskönyv-készítő (könyv → MP3). A megosztott runtime (szövegkinyerés,
TTS, hangmotor, tároló) a Core `superdl` csomagjából jön; az eszközök és a
felolvasó-motor saját kódja a modulban van.
"""

_state = {"items": []}


def _add(core, menu, key, frame_cls, label, help):
    """Egy eszköz hozzáadása a modul-menühöz (egyablakos megnyitóval)."""
    opener = core.register_window(key, frame_cls)
    item = core.add_menu_item(menu, label, opener, help=help)
    _state["items"].append(item)


def register(core):
    from .readerwin import ReaderFrame
    from .bookwin import BookFrame

    menu = core.add_menu("&Könyvek")
    _add(core, menu, "reader_module", ReaderFrame,
         "Könyv&olvasó (élő felolvasás)\tCtrl+Shift+O",
         "Könyv felolvasása a programban, könyvjelzővel (folytatható)")
    _add(core, menu, "audiobook_module", BookFrame,
         "&Hangoskönyv készítő\tCtrl+Shift+B",
         "Könyv (TXT/DOCX/EPUB/PDF) átalakítása MP3 hangoskönyvvé")
    core.log.info("konyvek modul betöltve")


def unregister(core):
    for item in _state.pop("items", []):
        core.remove_menu_item(item)
    _state["items"] = []
    core.log.info("konyvek modul leszerelve")
