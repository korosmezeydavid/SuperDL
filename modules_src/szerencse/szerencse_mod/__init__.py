# -*- coding: utf-8 -*-
"""SuperDL modul – Szerencsesüti (Dávid ötlete, 2026-09-27).

Napközben 15 percenként érkezik egy szerencsesüti; Ctrl+Alt+S-sel lehet
kibontani: dobozkanyitás-hang, a felolvasó elmondja az üzenetet, utána
jön a hozzá illő hang (nevetés, kuncogás, huncut nevetés, punch). Néha
büntetés (1, 2, 10 vagy 24 óra sütiszünet), néha bónusz (még egy süti).
Beállítás: be/ki, éjszakai csend, és hogy az érkezést szóban is mondja-e.

Az üzenetek az uzenetek.txt-ben; a saját üzeneteid a
~/.superdl/szerencse_sajat.txt-be írhatod (frissítéskor nem vesznek el).
A hangok a hangok/<fajta>/ mappákban (.wav); ha egy mappa üres, az a
rész egyszerűen csendben marad."""
import time
import datetime as _dt
from pathlib import Path

_state = {}
MAPPA = Path(__file__).resolve().parent
SAJAT = Path.home() / ".superdl" / "szerencse_sajat.txt"
CSOMAG_CACHE = Path.home() / ".superdl" / "szerencse_csomagok.txt"
CSOMAG_FRISSITES_MP = 6 * 3600   # ennyi időnként nézzük meg a netet
MP_PER_KARAKTER = 0.075          # a felolvasás becsült tempója


def _uzenetek():
    from . import suti as S
    szoveg = ""
    for f in (MAPPA / "uzenetek.txt", SAJAT):
        try:
            szoveg += "\n" + f.read_text(encoding="utf-8-sig") + "\n"
        except OSError:
            pass
    return S.uzenetek_betolt(szoveg)


def _csomagok_cache():
    from . import suti as S
    try:
        return S.csomagok_betolt(CSOMAG_CACHE.read_text(encoding="utf-8-sig"))
    except OSError:
        return []


def _csomag_letolt():
    """Háttérszálon: a csomagok.txt a SuperDL tárolójából. Siker → cache
    + átadás; 404 (nincs csomag) → üres; hálózati hiba → marad a cache."""
    import threading
    import urllib.request
    import urllib.error
    from . import suti as S
    _state["csomag_ido"] = time.time()

    def munka():
        try:
            req = urllib.request.Request(
                S.CSOMAG_URL, headers={"User-Agent": "SuperDL-szerencse",
                                       "Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=20) as r:
                nyers = r.read(S.CSOMAG_MAX_BAJT + 1)
            if len(nyers) > S.CSOMAG_MAX_BAJT:
                return
            szoveg = nyers.decode("utf-8-sig")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                return
            szoveg = ""
        except Exception:
            return
        lista = S.csomagok_betolt(szoveg)
        try:
            CSOMAG_CACHE.parent.mkdir(parents=True, exist_ok=True)
            CSOMAG_CACHE.write_text(szoveg, encoding="utf-8")
        except OSError:
            pass
        try:
            import wx
            wx.CallAfter(_csomag_atad, lista)
        except Exception:
            pass
    threading.Thread(target=munka, daemon=True,
                     name="szerencse-csomag").start()


def _csomag_atad(lista):
    s = _state.get("suti")
    if s is not None:
        s.csomagok = lista


def _mondd(szoveg):
    """Képernyőolvasó ELŐBB, a beépített hang csak utána."""
    try:
        from superdl import screenreader
        if screenreader.speak(szoveg):
            return
    except Exception:
        pass
    main = _state.get("main")
    sv = getattr(main, "selfvoice", None)
    if sv:
        try:
            sv.speak(szoveg, force=True)
        except Exception:
            pass


def _hang(nev) -> float:
    """Lejátszik egy hangot a fajta mappájából; a hosszát adja vissza."""
    from . import suti as S
    f = S.hangfajl(MAPPA / "hangok", nev) if nev else None
    if f is None:
        return 0.0
    try:
        import winsound
        winsound.PlaySound(str(f), winsound.SND_FILENAME | winsound.SND_ASYNC
                           | winsound.SND_NODEFAULT)
    except Exception:
        return 0.0
    return S.wav_hossz(f)


def _ment():
    core, s = _state.get("core"), _state.get("suti")
    if core is not None and s is not None and core.store is not None:
        try:
            core.store.save("allapot", s.a.szotar())
        except Exception:
            core.log.exception("szerencse: mentés hiba")


def _utes(_e=None):
    s = _state.get("suti")
    if s is None:
        return
    if time.time() - _state.get("csomag_ido", 0) > CSOMAG_FRISSITES_MP:
        _csomag_letolt()
    uj = s.lepes(time.time(), _dt.datetime.now())
    if uj:
        _ment()
        _hang("erkezes")
        if s.a.erkezes_szoval:
            if s.a.varo > 1:
                _mondd("Szerencsesüti érkezett! %d süti vár rád. Ctrl+Alt+S."
                       % s.a.varo)
            else:
                _mondd("Megjött a szerencsesüti! Ctrl+Alt+S.")


def kibont():
    import wx
    s = _state.get("suti")
    if s is None:
        return
    most = time.time()
    s.lepes(most, _dt.datetime.now())      # ha épp most járt le, számoljon
    u = s.kibont(most)
    _ment()
    if u is None:
        _mondd(s.varakozo_szoveg(most))
        return
    szoveg = s.teljes_szoveg(u)
    hir = s.csomag_hir()
    if hir:
        szoveg = hir + " " + szoveg
        _ment()
    reakcio = s.reakcio_hang(u)
    nyitas = _hang("nyitas")
    kesleltet = int((nyitas + 0.15) * 1000) if nyitas else 0

    def beszel():
        _mondd(szoveg)
        if reakcio:
            wx.CallLater(int((len(szoveg) * MP_PER_KARAKTER + 0.4) * 1000),
                         lambda: _hang(reakcio))
    if kesleltet:
        wx.CallLater(kesleltet, beszel)
    else:
        beszel()


def beallitasok():
    from .sutiwin import BeallitasDialog
    s = _state.get("suti")
    main = _state.get("main")
    if s is None:
        return
    d = BeallitasDialog(main, s.a)
    if d.ShowModal() == d.GetAffirmativeId():
        d.alkalmaz(s.a)
        _ment()
        _mondd("Szerencsesüti beállítások elmentve.")
    d.Destroy()


def register(core):
    import wx
    from . import suti as S
    _state["core"] = core
    _state["main"] = core.main_frame
    adat = core.store.load("allapot", {}) if core.store is not None else {}
    _state["suti"] = S.Suti(S.Allapot.szotarbol(adat), _uzenetek())
    _state["suti"].csomagok = _csomagok_cache()
    # az első letöltés az első óraütéssel (20 mp) indul, nem az induláskor
    _state["csomag_ido"] = 0.0
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Eszközök", "&Szerencsesüti") if _sub \
        else core.add_menu("&Szerencsesüti")
    _state["itemek"] = [
        core.add_menu_item(menu, "Szerencsesüti &kibontása\tCtrl+Alt+S",
                           kibont, help="Kibont egy szerencsesütit, ha "
                           "van – különben megmondja, mikor jön a következő"),
        core.add_menu_item(menu, "Szerencsesüti &beállításai…", beallitasok,
                           help="Be- és kikapcsolás, éjszakai csend"),
    ]
    t = wx.Timer()
    t.Bind(wx.EVT_TIMER, _utes)
    t.Start(30 * 1000)
    _state["timer"] = t
    # az első ütés ne az indulás zajába essen
    _state["elso"] = wx.CallLater(20 * 1000, _utes)
    core.log.info("szerencse modul betöltve")


def unregister(core):
    for k in ("timer", "elso"):
        t = _state.pop(k, None)
        try:
            if t is not None:
                t.Stop()
        except Exception:
            pass
    _ment()
    for item in _state.pop("itemek", []) or []:
        try:
            core.remove_menu_item(item)
        except Exception:
            pass
    _state.pop("suti", None)
    core.log.info("szerencse modul leszerelve")
