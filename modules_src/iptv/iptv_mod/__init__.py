"""SuperDL modul – Internetes TV (legális IPTV).

Az IPTV TELJES kódja (iptv.py + iptvwin.py) ITT, a modulban van: saját, legális
m3u/Xtream forrás csatornái akadálymentesen, felolvasott műsorújsággal (EPG),
felvétellel és emlékeztetővel. A megosztott runtime (ffmpeg, lejátszó, naptár/
emlékeztető, tároló) a Core `superdl` csomagjából jön.

register(core): „Internetes TV" menü + az IPTV-ablak (egyablakosan); unregister leszerel."""

_state = {}


def register(core):
    from .iptvwin import IPTVFrame

    opener = core.register_window("iptv_module", IPTVFrame)
    menu = core.add_menu("Internetes &TV")
    item = core.add_menu_item(
        menu, "Internetes &TV (legális IPTV)\tCtrl+Shift+I", opener,
        help="Saját, legális m3u/Xtream forrás csatornái akadálymentesen, "
             "felolvasott műsorújsággal (EPG), felvétellel és emlékeztetővel")
    _state["item"] = item
    core.log.info("iptv modul betöltve")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
    core.log.info("iptv modul leszerelve")
