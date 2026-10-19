"""Supergram Windows modul."""

_item = None


def register(core):
    global _item
    from .window import SupergramFrame

    opener = core.register_window(
        "supergram_module", lambda parent: SupergramFrame(parent, core))
    submenu = getattr(core, "add_submenu", None)
    menu = submenu("&Kommunikáció", "&Supergram") if submenu else core.add_menu("&Supergram")
    _item = core.add_menu_item(
        menu, "&Supergram – Telegram…", opener,
        help="Akadálymentes Telegram-beszélgetések és üzenetek")


def unregister(core):
    global _item
    if _item is not None:
        core.remove_menu_item(_item)
        _item = None
