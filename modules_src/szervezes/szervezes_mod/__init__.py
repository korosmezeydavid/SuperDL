"""SuperDL modul – Szervezés (hírek, podcastok, naptár, napi infó, óra).

Egy use-case-be tartozó szervezés-eszközök EGY modulban (a menübuborék
elkerülésére): akadálymentes Hírolvasó (RSS), Podcast-felfedező, Naptár/teendők/
jegyzetek, Napi infó (időjárás, névnap) és a BESZÉLŐ ÓRA időzítő-profilokkal.
A megosztott runtime (AI-kliens, AI-segédablak, feliratkozás-rendszer,
médialista, tároló) és a Core-ban maradó BACKENDEK (a naptár-kezelő
`_organizer` az asszisztens-agendához és az indító-üdvözléshez, a
`_compose_dayinfo`/időjárás az üdvözléshez, az óra motorja `superdl.idoora`
és hangrétege `superdl.orahang`) a Core-ból jönnek; az ablakok saját kódja a
modulban van.

⚠️ AZ ÓRA MOTORJA A `register()`-BEN INDUL, NEM AZ ABLAKBAN. Aki 20 percenként
kér időt, az nem akar hozzá ablakot nyitva tartani. Az ablak csak beállít.
"""

import wx

_state = {"items": []}

TAROLO_KULCS = "ora"


def _add(core, menu, key, factory, label, help):
    """Egy ablakos eszköz hozzáadása a modul-menühöz (egyablakos megnyitóval).
    A `factory` lehet ablak-osztály VAGY `main -> ablak` függvény."""
    opener = core.register_window(key, factory)
    item = core.add_menu_item(menu, label, opener, help=help)
    _state["items"].append(item)


# ─────────────────────────── a beszélő óra ──────────────────────────

def _ora_betolt(core):
    """A mentett óra-beállítás és időzítő-profilok betöltése."""
    from superdl import idoora

    adat = core.store.load(TAROLO_KULCS, None) or {}
    beall = dict(idoora.ALAP)
    if isinstance(adat.get("ora"), dict):
        beall.update(adat["ora"])
    profilok = adat.get("idozitok")
    if not isinstance(profilok, list):
        # Első indulás: Dávid használati esete készen, hogy legyen mit
        # elindítani, és hogy a hang-azonosítás rögtön látszódjon.
        profilok = [
            {"nev": "munkaidő", "hossz_perc": 480, "kozbenso_perc": 60,
             "valtozat": "m3", "veg_jingle": True, "kimondja_a_nevet": True},
            {"nev": "ebédszünet", "hossz_perc": 20, "kozbenso_perc": 5,
             "valtozat": "f2", "veg_jingle": True, "kimondja_a_nevet": True},
            {"nev": "meeting", "hossz_perc": 60, "kozbenso_perc": 20,
             "valtozat": "boris", "veg_jingle": True,
             "kimondja_a_nevet": True},
        ]
    return beall, profilok


def _ora_ment(core):
    def ment(beall=None, profilok=None):
        if beall is not None:
            _state["beall"] = dict(beall)
            motor = _state.get("motor")
            if motor is not None:
                motor.beallit(_state["beall"])
            _hang_frissit(core)
        if profilok is not None:
            _state["profilok"] = list(profilok)
        core.store.save(TAROLO_KULCS, {"ora": _state.get("beall", {}),
                                       "idozitok": _state.get("profilok", [])})
    return ment


def _hang_frissit(core):
    """A bemondó tempóját/hangerejét a program saját hangbeállításából
    vesszük át – egy külön hangerő-csúszka csak zavar lenne."""
    beszelo = _state.get("beszelo")
    if beszelo is None:
        return
    main = core.frame
    sv = getattr(main, "selfvoice", None)
    beall = getattr(main, "settings", {}) or {}
    beszelo.beallit(
        rate=getattr(sv, "rate", 0), pitch=getattr(sv, "pitch", 0),
        volume=getattr(sv, "volume", 100),
        kepernyoolvaso=bool(beall.get("screenreader_only", False)))


def _ora_indit(core):
    from superdl import idoora, orahang

    beall, profilok = _ora_betolt(core)
    _state["beall"] = beall
    _state["profilok"] = profilok
    _state["beszelo"] = orahang.Beszelo()
    _hang_frissit(core)

    def ertesito(esemeny, adat):
        # ⚠️ 4.6.7: a motor SZÁLÁBÓL jövünk – a felület felé CSAK CallAfter.
        def biztonsagos():
            panel = _state.get("idozito_panel")
            if panel is None:
                return
            try:
                panel._allapotok()
            except (RuntimeError, AttributeError):
                _state["idozito_panel"] = None
        wx.CallAfter(biztonsagos)

    motor = idoora.OraMotor(_state["beszelo"], beall, ertesito=ertesito)
    motor.indul()
    _state["motor"] = motor
    return motor


def _ora_leallit():
    motor = _state.pop("motor", None)
    if motor is not None:
        motor.leall()
    beszelo = _state.pop("beszelo", None)
    if beszelo is not None:
        beszelo.kikapcsol()


def _kilepes_or():
    """⚠️ Csendben elveszíteni egy futó időzítőt rosszabb a semminél.

    A Core kérdez (`kilepes_or_hozzaad`), mi csak a KÉRDÉST adjuk. Így
    háttérmódban (tálcára minimalizálás) nem szólunk feleslegesen: ott a
    program nem lép ki, az időzítő tovább fut."""
    motor = _state.get("motor")
    if motor is None:
        return ""
    szoveg = motor.futo_osszefoglalo()
    if not szoveg:
        return ""
    return ("%s\n\nA futó időzítők a kilépéssel megszűnnek "
            "(a profilok megmaradnak).\n\nBiztosan kilépsz?" % szoveg)


def register(core):
    from .newswin import NewsFrame
    from .podcastwin import PodcastFrame
    from .organizerwin import OrganizerFrame
    from .dayinfowin import DayInfoDialog
    from .orawin import OraDialog

    # Szervezés = nem média, nem könyv → az Eszközök menü alá (almenüként).
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Eszközök", "Szer&vezés") if _sub else core.add_menu("Szer&vezés")
    _add(core, menu, "news_module", NewsFrame,
         "&Hírolvasó\tCtrl+Shift+F",
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

    # ── beszélő óra ──────────────────────────────────────────────────
    motor = _ora_indit(core)
    ment = _ora_ment(core)

    def open_ora(lap=0):
        """A beszélő óra ablaka. KÉT LAPFÜL: Óra és Időzítők (Dávid kérése).
        `lap` csak azt dönti el, melyik legyen elöl."""
        dlg = OraDialog(core.frame, motor, _state.get("beszelo"),
                        _state.get("profilok", []),
                        lambda b: ment(beall=b),
                        lambda pr: ment(profilok=pr))
        _state["idozito_panel"] = dlg.idozitok
        try:
            dlg.lapra(lap)
            dlg.ShowModal()
        finally:
            _state["idozito_panel"] = None
            # ⚠️ ÖV ÉS NADRÁGTARTÓ. Ha a wx valamiért már eltakarította az
            # ablakot, a `Destroy()` RuntimeError-t dob a fő szálon –
            # élesben pont ez omlasztotta össze a programot. A `if dlg:`
            # a wx dokumentált módja a „él-e még a natív objektum?"
            # kérdésre.
            if dlg:
                dlg.Destroy()

    item = core.add_menu_item(
        menu, "Beszélő &óra...", open_ora,
        help="Időbemondás és időzítő-profilok egy ablakban, két lapfülön")
    _state["items"].append(item)

    # ugyanaz az ablak, de az Időzítők lapfülön nyitva – hogy a menüből is
    # egy lépés legyen odajutni
    item = core.add_menu_item(
        menu, "Idő&zítők...", lambda: open_ora(1),
        help="Elmenthető időzítő-profilok: több is futhat egyszerre, "
             "mindegyik saját hanggal (a Beszélő óra ablak lapfüle)")
    _state["items"].append(item)

    # ⚠️ A gyorsbillentyűk LEMÉRVE szabadok: a tervezetben javasolt
    # Ctrl+Shift+O-t a Könyvek modul már elvitte.
    _state["_ketszer"] = [0.0]

    def mennyi_az_ido():
        import time as _t
        most = _t.monotonic()
        ketszer = (most - _state["_ketszer"][0]) < 1.5
        _state["_ketszer"][0] = most
        motor.mennyi_az_ido(reszletes=ketszer)

    item = core.add_menu_item(
        menu, "Mennyi az i&dő?\tCtrl+Shift+X", mennyi_az_ido,
        help="Bemondja a pontos időt. Kétszer egymás után megnyomva a "
             "dátumot és a névnapot is")
    _state["items"].append(item)

    def mennyi_van_hatra():
        b = _state.get("beszelo")
        if b is not None:
            b.mond(motor.idozitok_allapota(), surgos=True)

    item = core.add_menu_item(
        menu, "Mennyi van &hátra?\tCtrl+Alt+X", mennyi_van_hatra,
        help="Bemondja, mennyi van hátra a futó időzítőkből")
    _state["items"].append(item)

    hozzaad = getattr(core.frame, "kilepes_or_hozzaad", None)
    if hozzaad is not None:
        hozzaad(_kilepes_or)
        _state["kilepes_or"] = True
    else:                      # régebbi Core – a többi funkció így is megy
        core.log.warning("ez a Core még nem ismeri a kilépés-őröket; "
                         "a futó időzítőkre nem fog figyelmeztetni")
    core.log.info("szervezes modul betöltve (beszélő órával)")


def unregister(core):
    if _state.pop("kilepes_or", None):
        eltavolit = getattr(core.frame, "kilepes_or_eltavolit", None)
        if eltavolit is not None:
            eltavolit(_kilepes_or)
    _ora_leallit()
    _state.pop("idozito_panel", None)
    for item in _state.pop("items", []):
        core.remove_menu_item(item)
    _state["items"] = []
    core.log.info("szervezes modul leszerelve")
