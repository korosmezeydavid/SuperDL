"""SuperDL modul – AI hangalámondás (audio description).

A videó KÉPI tartalmát AI írja le, hanggá alakítva beleszövi → vakon „nézhető"
videó. A teljes kód (videodescribe.py + videodescribewin.py) a modulban; a
megosztott runtime (ffmpeg, AI-kliens, TTS, self-voice, hangjelzések) a Core
`superdl` csomagjából jön.

register(core): „AI hangalámondás" menü + az ablak (egyablakosan)."""

_state = {}


def register(core):
    from .videodescribewin import VideoDescribeFrame

    opener = core.register_window("videodescribe_module", VideoDescribeFrame)
    # Audiodeszkripció videóhoz = MÉDIA-funkció, ezért a Média menü alá kerül.
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Média", "AI &hangalámondás") if _sub else core.add_menu("AI &hangalámondás")
    item = core.add_menu_item(
        menu, "AI hangalá&mondás videóhoz…", opener,
        help="A videó képi tartalmát AI írja le és hanggal mondja el "
             "(vakon „nézhető” videó); az eredeti hang alatta halkítva")
    _state["item"] = item
    core.log.info("hangalamondas modul betöltve")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
    core.log.info("hangalamondas modul leszerelve")
