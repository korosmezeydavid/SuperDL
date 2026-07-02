"""SuperDL modul – Szervezés (hírek, podcastok, naptár, napi infó).

Egy use-case-be tartozó szervezés-eszközök EGY modulban (a menübuborék
elkerülésére): akadálymentes Hírolvasó (RSS), Podcast-felfedező, Naptár/teendők/
jegyzetek és Napi infó (időjárás, névnap). A megosztott runtime (AI-kliens,
AI-segédablak, feliratkozás-rendszer, médialista, tároló) és a Core-ban maradó
BACKENDEK (a naptár-kezelő `_organizer` az asszisztens-agendához és az
indító-üdvözléshez, a `_compose_dayinfo`/időjárás az üdvözléshez) a Core-ból
jönnek; az ablakok saját kódja a modulban van.
"""

_state = {"items": []}


def _add(core, menu, key, factory, label, help):
    """Egy ablakos eszköz hozzáadása a modul-menühöz (egyablakos megnyitóval).
    A `factory` lehet ablak-osztály VAGY `main -> ablak` függvény."""
    opener = core.register_window(key, factory)
    item = core.add_menu_item(menu, label, opener, help=help)
    _state["items"].append(item)


def register(core):
    from .newswin import NewsFrame
    from .podcastwin import PodcastFrame
    from .organizerwin import OrganizerFrame
    from .dayinfowin import DayInfoDialog

    # Szervezés = nem média, nem könyv → az Eszközök menü alá (almenüként).
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Eszközök", "Szer&vezés") if _sub else core.add_menu("Szer&vezés")
    _add(core, menu, "news_module", NewsFrame,
         "&Hírolvasó\tCtrl+Shift+H",
         "Reklámmentes RSS hírgyűjtő és letisztított cikkolvasó")
    _add(core, menu, "podcast_module", PodcastFrame,
         "&Podcastok felfedezése...\tCtrl+Shift+P",
         "Podcast-keresés és ország-toplista, feliratkozással")
    # Naptár: a kezelő (_organizer) a Core-ban marad (agenda + indítás); az ablak
    # a Core-példányt kapja konstruktor-argumentumként.
    _add(core, menu, "organizer_module",
         lambda main: OrganizerFrame(main, main._organizer),
         "Naptár, teen&dők, jegyzetek\tCtrl+Shift+N",
         "Események emlékeztetővel, teendők, jegyzetek és külső "
         "naptár-szinkron (ICS-link)")

    # Napi infó: MODÁLIS párbeszéd, a Core üdvözlés-összeállítóját és időjárás-
    # lekérőjét használja (ezek a Core-ban maradnak az indító-üdvözléshez).
    def open_dayinfo():
        main = core.frame
        dlg = DayInfoDialog(main, main._compose_dayinfo,
                            main._fetch_weather_async, main.speaker)
        dlg.ShowModal()
        dlg.Destroy()
    item = core.add_menu_item(
        menu, "Napi in&fó (időjárás, névnap)\tCtrl+Shift+W", open_dayinfo,
        help="Mai dátum, névnap és időjárás a megadott városra")
    _state["items"].append(item)
    core.log.info("szervezes modul betöltve")


def unregister(core):
    for item in _state.pop("items", []):
        core.remove_menu_item(item)
    _state["items"] = []
    core.log.info("szervezes modul leszerelve")
