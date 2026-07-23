"""SuperDL modul – Játékok (Retró játékok + SuperDL saját játékok).

A modul saját ablakot ad, két szekcióval:
  • Retró játékok – a 80-as/90-es évek magyar beszélő gépeinek hangulatában,
    korhű RETRÓ BESZÉDHANGGAL;
  • SuperDL saját játékok – a program saját, akadálymentes játékai.

A retró hangot a Core `retrospeech` formáns-motorja adja: SAJÁT kód, saját
táblák – semmilyen idegen ROM-ot vagy chip-kódot nem használ.

register(core): „Játékok" menü + a Játékok ablak; unregister leszerel."""

_state = {}


def register(core):
    from .jatekokwin import JatekokFrame

    opener = core.register_window("jatekok_module", JatekokFrame)
    menu = core.add_menu("&Játékok")
    item = core.add_menu_item(
        menu, "&Játékok…\tCtrl+Shift+J", opener,
        help="Retró játékok korhű beszédhanggal és a SuperDL saját játékai")
    _state["item"] = item
    core.log.info("jatekok modul betöltve")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
    core.log.info("jatekok modul leszerelve")
