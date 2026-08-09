# -*- coding: utf-8 -*-
"""SuperDL modul – Super Mail: akadálymentes e-mail kliens.

Kizárólag emailezés: fogadás (IMAP/POP3), küldés (SMTP), keresés. Semmit nem
továbbít sehová; a fiók-adatok a gépen, DPAPI-val titkosítva élnek, és egyetlen
céljuk az e-mail működése. Az első indításkor hozzájárulást kérünk.

register(core): „Super Mail" menüpont a Kommunikáció menü alatt + az ablak."""

_state = {}


def register(core):
    from .mailwin import MailFrame

    opener = core.register_window("mail_module", MailFrame)
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Kommunikáció", "Super &Mail") if _sub else core.add_menu(
        "Super &Mail")
    item = core.add_menu_item(
        menu, "Super &Mail\tCtrl+Shift+M", opener,
        help="Akadálymentes e-mail: olvasás, küldés, keresés (IMAP/POP3/SMTP)")
    _state["item"] = item
    core.log.info("mail modul betöltve")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
    core.log.info("mail modul leszerelve")
