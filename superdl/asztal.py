"""Asztal – minden modul és a fő Core-funkciók egy helyen (Petrus József ötlete).

Egy ikonos lista ABC-sorrendben. Betűre ugrik az első ilyen kezdetűre, újabb
lenyomásra a következőre (körbeér); Enter megnyitja. A lista a menüsorból épül:
a modulok által felvett menüpontokat a WxHost `modul_menu_idk` halmaza jelöli,
így egyetlen modulhoz sem kell hozzányúlni.

A tiszta segédfüggvények (cimke, gyorsbill, kovetkezo, rendezo_kulcs) wx
nélkül is tesztelhetők.
"""
import unicodedata

CIM = "Asztal"


def ekezet_nelkul(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def cimke(label: str) -> str:
    """A menüpont szövegéből a megjelenő név: & nélkül, a tab utáni
    gyorsbillentyű és a záró három pont nélkül."""
    s = (label or "").split("\t", 1)[0]
    s = s.replace("&&", "\0").replace("&", "").replace("\0", "&")
    s = s.strip()
    for vege in ("…", "..."):
        if s.endswith(vege):
            s = s[: -len(vege)].rstrip()
    return s


def gyorsbill(label: str) -> str:
    """A menüpont gyorsbillentyűje (a tab utáni rész), vagy üres."""
    if "\t" not in (label or ""):
        return ""
    return label.split("\t", 1)[1].strip()


def megjelenes(nev: str, bill: str) -> str:
    return f"{nev} ({bill})" if bill else nev


def rendezo_kulcs(nev: str):
    return (ekezet_nelkul(nev), nev)


def kovetkezo(nevek, jelenlegi: int, betu: str) -> int:
    """A `jelenlegi` UTÁNI első olyan elem indexe, amelyik `betu`-vel kezdődik
    (ékezet- és kisbetű-függetlenül), körbeérve. Ha nincs ilyen: -1."""
    b = ekezet_nelkul(betu)[:1]
    if not b:
        return -1
    n = len(nevek)
    for lepes in range(1, n + 1):
        i = (jelenlegi + lepes) % n if n else 0
        if ekezet_nelkul(nevek[i]).startswith(b):
            return i
    return -1


# ---- wx rész ---------------------------------------------------------------

_IKON_MENU = {
    "Fájl": "wxART_FOLDER", "Letöltések": "wxART_GO_DOWN",
    "Feliratkozások": "wxART_REPORT_VIEW", "Média": "wxART_CDROM",
    "Könyvek": "wxART_HELP_BOOK", "Eszközök": "wxART_EXECUTABLE_FILE",
    "AI": "wxART_TIP", "Súgó": "wxART_HELP",
}


def _bejar(menu, felso, szulo, ki):
    for it in menu.GetMenuItems():
        sm = it.GetSubMenu()
        if sm is not None:
            _bejar(sm, felso, cimke(it.GetItemLabel()), ki)
        elif not it.IsSeparator():
            ki.append((it, felso, szulo))


def egyertelmusit(sorok):
    """[(nev, bill, szulo, ...)] → a megjelenő szövegek; ha egy név többször
    is előfordul (pl. két modul „Beállítások" pontja), a szülőmenü neve is
    mögé kerül: „Beállítások – Super M"."""
    db = {}
    for s in sorok:
        db[ekezet_nelkul(s[0])] = db.get(ekezet_nelkul(s[0]), 0) + 1
    ki = []
    for nev, bill, szulo in (s[:3] for s in sorok):
        if db[ekezet_nelkul(nev)] > 1 and szulo:
            nev = f"{nev} – {szulo}"
        ki.append((nev, megjelenes(nev, bill)))
    return ki


def elemek(frame, modul_idk, core_idk):
    """[(megjelenő szöveg, név, menüpont-azonosító, felső menü)] ABC-sorrendben.
    Modul-menüpontok + a Core fő funkciói; a jelölőnégyzetes kapcsolók, a
    letiltott pontok és maga az Asztal kimarad."""
    mb = frame.GetMenuBar()
    if mb is None:
        return []
    kell = set(modul_idk or ()) | set(core_idk or ())
    sajat = getattr(frame, "_asztal_menu_id", None)
    osszes = []
    for i in range(mb.GetMenuCount()):
        cim = mb.GetMenuLabelText(i)
        _bejar(mb.GetMenu(i), cim, cim, osszes)
    nyers, latott = [], set()
    for it, felso, szulo in osszes:
        iid = it.GetId()
        if iid not in kell or iid == sajat or iid in latott:
            continue
        if it.IsCheckable() or not it.IsEnabled():
            continue
        nev = cimke(it.GetItemLabel())
        if not nev:
            continue
        latott.add(iid)
        nyers.append((nev, gyorsbill(it.GetItemLabel()), szulo, iid, felso))
    ki = [(szoveg, nev, n[3], n[4])
          for (nev, szoveg), n in zip(egyertelmusit(nyers), nyers)]
    ki.sort(key=lambda e: rendezo_kulcs(e[1]))
    return ki


def _ikonlista(felsok):
    import wx
    il = wx.ImageList(32, 32)
    idx = {}
    for f in sorted(set(felsok)):
        art = _IKON_MENU.get(f, "wxART_NORMAL_FILE")
        bmp = wx.ArtProvider.GetBitmap(art, wx.ART_OTHER, (32, 32))
        if not bmp.IsOk():
            bmp = wx.ArtProvider.GetBitmap("wxART_NORMAL_FILE", wx.ART_OTHER,
                                           (32, 32))
        idx[f] = il.Add(bmp)
    return il, idx


def AsztalAblak(frame, host):
    """Létrehozza (vagy előhozza) az Asztal ablakot. Egy példány."""
    import wx

    regi = getattr(frame, "_asztal_win", None)
    if regi:
        try:
            regi.Raise()
            regi.lista.SetFocus()
            return regi
        except Exception:
            frame._asztal_win = None

    class _Asztal(wx.Frame):
        def __init__(self):
            super().__init__(frame, title="SuperDL – Asztal",
                             size=(760, 520))
            self.SetName("Asztal – minden modul egy helyen")
            p = wx.Panel(self)
            v = wx.BoxSizer(wx.VERTICAL)
            felirat = wx.StaticText(
                p, label="&Modulok és funkciók (betű: ugrás, Enter: megnyitás, "
                         "Escape: bezárás):")
            v.Add(felirat, 0, wx.ALL, 8)
            self.lista = wx.ListCtrl(
                p, style=wx.LC_ICON | wx.LC_SINGLE_SEL | wx.LC_AUTOARRANGE)
            self.lista.SetName("Asztal")
            v.Add(self.lista, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
            p.SetSizer(v)
            self._elemek = elemek(frame, getattr(host, "modul_menu_idk", ()),
                                  getattr(frame, "_asztal_core_idk", ()))
            self._il, idx = _ikonlista([e[3] for e in self._elemek])
            self.lista.SetImageList(self._il, wx.IMAGE_LIST_NORMAL)
            for i, (szoveg, _nev, _iid, felso) in enumerate(self._elemek):
                self.lista.InsertItem(i, szoveg, idx.get(felso, 0))
            if self._elemek:
                self._jelol(0)
            self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED,
                            lambda e: self._nyit(e.GetIndex()))
            self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
            self.Bind(wx.EVT_CLOSE, self._on_close)
            self.CentreOnParent()

        def _nevek(self):
            return [e[0] for e in self._elemek]

        def _jelol(self, i):
            allapot = wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED
            self.lista.SetItemState(i, allapot, allapot)
            self.lista.EnsureVisible(i)

        def _on_key(self, e):
            k = e.GetKeyCode()
            if k == wx.WXK_ESCAPE:
                self.Close()
                return
            if k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                i = self.lista.GetFirstSelected()
                if i >= 0:
                    self._nyit(i)
                return
            mod = e.GetModifiers()
            uk = e.GetUnicodeKey()
            # Az ablakban egyetlen fókuszálható vezérlő van: a lista.
            if (mod in (wx.MOD_NONE, wx.MOD_SHIFT) and uk != wx.WXK_NONE
                    and uk > 32):
                betu = chr(uk)
                if betu.isalnum():
                    j = kovetkezo(self._nevek(), self.lista.GetFirstSelected(),
                                  betu)
                    if j >= 0:
                        self._jelol(j)
                    else:
                        wx.Bell()
                    return
            e.Skip()

        def _nyit(self, i):
            if not (0 <= i < len(self._elemek)):
                return
            iid = self._elemek[i][2]
            self.Close()

            def _kuld():
                ev = wx.CommandEvent(wx.wxEVT_MENU, iid)
                ev.SetEventObject(frame)
                frame.GetEventHandler().ProcessEvent(ev)
            wx.CallAfter(_kuld)

        def _on_close(self, e):
            frame._asztal_win = None
            e.Skip()

    w = _Asztal()
    frame._asztal_win = w
    w.Show()
    w.Raise()
    w.lista.SetFocus()
    return w
