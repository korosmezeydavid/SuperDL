"""SuperDL modul – Média-eszközök (médiakészítés és -elemzés).

Egy use-case-be tartozó eszközök EGY modulban (a menübuborék elkerülésére):
egyelőre a Beszélő médiaelemző; bővül csengőhang/videókészítő/videóvágóval. A
megosztott runtime (ffmpeg) a Core `superdl` csomagjából jön; az eszközök saját
kódja a modulban van."""

_state = {"items": []}


def _add(core, menu, key, frame_cls, label, help):
    """Egy eszköz hozzáadása a modul-menühöz (egyablakos megnyitóval)."""
    opener = core.register_window(key, frame_cls)
    item = core.add_menu_item(menu, label, opener, help=help)
    _state["items"].append(item)


def register(core):
    from .convertwin import BatchConvertFrame
    from .mediaanalyzewin import MediaAnalyzeFrame
    from .ringtonewin import RingtoneFrame
    from .videowin import VideoComposeFrame
    from .videoeditwin import VideoEditFrame

    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Média", "&Média-eszközök") if _sub else core.add_menu("&Média-eszközök")
    _add(core, menu, "convert_module", BatchConvertFrame,
         "Médiakonvertá&ló (kötegelt)\tCtrl+Shift+K",
         "Hang/videó fájlok átalakítása más formátumba, egyszerre többet is")
    _add(core, menu, "mediaanalyze_module", MediaAnalyzeFrame,
         "Beszélő média&elemző\tCtrl+Shift+Q",
         "Médiafájl ellenőrzése és hangtechnikai elemzése (LUFS, csúcs, "
         "torzítás), valamint EBU R128 hangerő-normalizálás profilonként")
    _add(core, menu, "ringtone_module", RingtoneFrame,
         "iPhone &csengőhang-készítő\tCtrl+Shift+G",
         "Csengőhang (.m4r) vagy MP3 készítése egy zene részletéből")
    _add(core, menu, "video_module", VideoComposeFrame,
         "&Videókészítő (kép + zene)\tCtrl+Shift+V",
         "Videó készítése állóképből és zenéből, idővonalra helyezett "
         "szöveg- és kép-overlay-ekkel")
    _add(core, menu, "videoedit_module", VideoEditFrame,
         "Videóvá&gó és összefűző\tCtrl+Shift+E",
         "Videó vágása füllel (markerek), magyarázó szöveg ráégetése, "
         "videók összefűzése")
    core.log.info("mediatools modul betöltve")


def unregister(core):
    for item in _state.pop("items", []):
        core.remove_menu_item(item)
    _state["items"] = []
    core.log.info("mediatools modul leszerelve")
