"""SuperDL modul – Felirat-felolvasó lejátszó.

Idegen nyelvű film (vagy hangfájl) lejátszása úgy, hogy a magyar (vagy bármely
szöveges) feliratot SZINKRONBAN, választható hanggal (SAPI / Edge neurális /
eSpeak) felolvassa – vakon is követhető az idegen film. A film hangját és a
felolvasást a Core lejátszó-motorja (audioengine.Player) adja; a felirat-logika
(subtitles.py) és a hang (narrator.py) a modulban.

register(core): „Felirat-felolvasó lejátszó" menüpont a Média menüben."""

_state = {}


def register(core):
    from .felolvasowin import FelolvasoFrame

    opener = core.register_window("felolvaso_module", FelolvasoFrame)
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Média", "Felirat-&felolvasó lejátszó") if _sub \
        else core.add_menu("Felirat-&felolvasó lejátszó")
    item = core.add_menu_item(
        menu, "Felirat-&felolvasó lejátszó\tCtrl+Shift+L", opener,
        help="Film lejátszása a magyar felirat szinkron felolvasásával")
    _state["item"] = item
    core.log.info("felolvaso modul betöltve")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
    core.log.info("felolvaso modul leszerelve")
