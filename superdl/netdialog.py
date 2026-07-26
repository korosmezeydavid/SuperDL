"""Akadálymentes „Nincs internet” felugró, kétgombos újrateszteléssel.

Minden net-igényes GUI-művelet ELEJÉN egy villámgyors, adatküldés nélküli próba
(``netcheck.online`` – gyorsítótárazva → általában azonnali). Ha van net, semmi
nem történik és a művelet fut tovább. Ha nincs, ez a modális párbeszéd nyílik:

  • Újratesztelés (Enter, alapértelmezett): újrapróbál. Siker → bezárul és a
    művelet folytatódik. Ha még mindig nincs → hangosan jelzi, nyitva marad.
  • OK (Esc): teszt nélkül eltűnik, a művelet lemondva.

A képernyőolvasós felhasználót nem hagyjuk magára: a párbeszéd megnyíltakor és a
teszt eredményekor is felolvassuk az üzenetet (a hívó ``speak`` visszahívásával,
vagy tartalékként a képernyőolvasó-hídon át).
"""

import threading

import wx

from superdl import netcheck

try:
    from superdl import screenreader as _sr
except Exception:                       # pragma: no cover - a híd hiánya sose bukjon
    _sr = None


class NoInternetDialog(wx.Dialog):
    def __init__(self, parent, mihez="ehhez a művelethez", speak=None):
        super().__init__(parent, title="Nincs internetkapcsolat",
                         size=(460, 260))
        self._speak = speak
        self.online = False
        self._busy = False
        mihez = (mihez or "ehhez a művelethez").strip()
        self._base = (f"Úgy tűnik, most nincs internetkapcsolat. "
                      f"A(z) {mihez} internet szükséges.\n\n"
                      "Ellenőrizd a wifit vagy a mobilnetet, majd válaszd az "
                      "Újratesztelést.")

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        self.msg = wx.StaticText(p, label=self._base)
        self.msg.SetName("Internet-figyelmeztetés")
        self.msg.Wrap(420)
        v.Add(self.msg, 1, wx.ALL | wx.EXPAND, 14)

        btns = wx.BoxSizer(wx.HORIZONTAL)
        self.retry_btn = wx.Button(p, wx.ID_ANY, "Ú&jratesztelés")
        self.retry_btn.SetName("Újratesztelés")
        self.retry_btn.SetDefault()                 # Enter → újratesztelés
        self.retry_btn.Bind(wx.EVT_BUTTON, self._on_retry)
        # Az OK gomb ID_CANCEL, így az Esc is bezárja – teszt nélkül, lemondva.
        ok_btn = wx.Button(p, wx.ID_CANCEL, "&OK")
        ok_btn.SetName("OK, bezárás teszt nélkül")
        btns.Add(self.retry_btn, 0, wx.RIGHT, 8)
        btns.Add(ok_btn, 0)
        v.Add(btns, 0, wx.ALL | wx.ALIGN_RIGHT, 12)

        p.SetSizer(v)
        self.retry_btn.SetFocus()
        # a párbeszéd megnyíltakor olvassuk fel az üzenetet (a fókusz beáll)
        wx.CallAfter(self._say, self._base)

    # ---- felolvasás (hívó visszahívása, vagy a képernyőolvasó-híd) --------

    def _say(self, text):
        said = False
        if self._speak:
            try:
                self._speak(text)
                said = True
            except Exception:
                said = False
        if not said and _sr is not None:
            try:
                _sr.speak(text, interrupt=True)
            except Exception:
                pass

    # ---- újratesztelés (háttérszálon, hogy a modális ne fagyjon) ----------

    def _on_retry(self, _evt):
        if self._busy:
            return
        self._busy = True
        self.retry_btn.Enable(False)
        self.msg.SetLabel("Tesztelés folyamatban…")
        self._say("Tesztelés folyamatban…")
        threading.Thread(target=self._probe, daemon=True).start()

    def _probe(self):
        ok = False
        try:
            ok = netcheck.online(force=True)
        except Exception:
            ok = False
        wx.CallAfter(self._probe_done, ok)

    def _probe_done(self, ok):
        self._busy = False
        if ok:
            self.online = True
            self._say("Van internetkapcsolat, folytatom.")
            self.EndModal(wx.ID_OK)
            return
        self.msg.SetLabel(self._base + "\n\nTovábbra sincs internetkapcsolat.")
        self.msg.Wrap(420)
        self._say("Továbbra sincs internetkapcsolat.")
        self.retry_btn.Enable(True)
        self.retry_btn.SetFocus()


def _show(parent, mihez, speak) -> bool:
    """A modális párbeszéd megjelenítése – MINDIG a GUI-szálon fut."""
    dlg = NoInternetDialog(parent, mihez=mihez, speak=speak)
    try:
        dlg.ShowModal()
        return bool(dlg.online)
    finally:
        dlg.Destroy()


def ensure_online(parent, mihez="ehhez a művelethez", speak=None,
                  timeout: float = 2.0) -> bool:
    """Igaz, ha van net (ekkor NINCS felugró). Ha nincs, felnyitja a kétgombos
    párbeszédet; True-t ad, ha az újratesztelés végül sikerült, False-t, ha a
    felhasználó az OK-kal teszt nélkül lemondott.

    Bárhonnan hívható: ha nem a GUI-szálon vagyunk (pl. letöltés-worker), a
    párbeszédet a GUI-szálra marsallja, és megvárja a felhasználó döntését."""
    try:
        if netcheck.online(timeout=timeout):
            return True
    except Exception:
        return True             # a próba maga sose blokkolja a programot
    if wx.IsMainThread():
        return _show(parent, mihez, speak)
    # worker-szál: a modálist a GUI-szálon nyitjuk, itt megvárjuk az eredményt
    box = {"v": False}
    done = threading.Event()

    def run():
        try:
            box["v"] = _show(parent, mihez, speak)
        finally:
            done.set()

    wx.CallAfter(run)
    done.wait()
    return box["v"]
