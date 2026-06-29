"""SuperDL modul – Super Media (műsorszóró stúdió + multistream).

Egy use-case-be tartozó hang-műsorszóró eszközök EGY modulban: Super M
(akadálymentes rádió-stúdió + médialejátszó – lejátszás, keverés, mikrofon,
jingle-pad, effekt-rack, Shoutcast/Icecast, BASS-motor) és Super Stream (élő
multistream egyszerre több platformra). A BASS-DLL-ek a Core bin/-jéből töltődnek
(a futtatókörnyezet a Core-ban van); a self-voice és az ffmpeg is a Core-ból jön;
a Super M/Stream teljes kódja a modulban van.
"""

_state = {"items": []}


def _add(core, menu, key, factory, label, help):
    opener = core.register_window(key, factory)
    item = core.add_menu_item(menu, label, opener, help=help)
    _state["items"].append(item)


def register(core):
    from .supermwin import SuperMFrame
    from .superstreamwin import SuperStreamFrame
    from .superrecwin import SuperRecorderFrame
    from .supereditwin import SuperEditorFrame

    menu = core.add_menu("Su&per Media")
    _add(core, menu, "superm_module", SuperMFrame,
         "Super &M – műsorszóró stúdió\tCtrl+Shift+M",
         "Rádió-műsorszórás: lejátszás, keverés, mikrofon, jingle-pad, "
         "effekt-rack, Shoutcast/Icecast (BASS motor)")
    _add(core, menu, "superrec_module", SuperRecorderFrame,
         "Super &Recorder – felvevő…",
         "Akadálymentes hangfelvevő: felvétel mikrofonból, kimondott "
         "szintmérővel, mentés WAV/MP3-ba normalizálással")
    _add(core, menu, "superedit_module", SuperEditorFrame,
         "Super Recorder – fülre-sz&erkesztő…",
         "Akadálymentes hangszerkesztő: markeres navigáció, szakasz "
         "törlése/némítása/trim, csend-beszúrás, undo/redo – mind kimondva")
    _add(core, menu, "superstream_module", SuperStreamFrame,
         "Super &Stream – élő multistream…",
         "Élő adás egyszerre több platformra (YouTube, Facebook, TikTok) a "
         "saját stream-kulcsoddal")
    core.log.info("supermedia modul betöltve")


def unregister(core):
    for item in _state.pop("items", []):
        core.remove_menu_item(item)
    _state["items"] = []
    core.log.info("supermedia modul leszerelve")
