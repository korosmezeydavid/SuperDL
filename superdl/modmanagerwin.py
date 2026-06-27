"""Akadálymentes Modulkezelő („bolt") – a SuperDL opcionális moduljainak
telepítése, frissítése és eltávolítása (moduláris rendszer, It.2).

A lista a TELEPÍTETT modulokat és a távoli index (modules.json) ELÉRHETŐ
moduljait mutatja, állapottal (Telepítve / Frissíthető / Elérhető / Újabb
SuperDL kell). A letöltés SHA-256-tal ellenőrzött (install_module_zip), a
betöltés hibatűrő. Minden vezérlőnek olvasható neve van; az állapotot kimondjuk.
"""

import json
import threading

import wx

from . import coremod
from . import modkit


def compute_rows(entries, installed: dict, core_api: str = modkit.CORE_API):
    """A megjelenítendő sorok összeállítása (TISZTA függvény, tesztelhető).

    `entries`: a bolt ModuleEntry-listája; `installed`: {id: verzió} a
    telepítettekről. Visszaad: sor-szótárak listája (id, name, category,
    status, version, entry, installable, removable)."""
    rows = []
    by_id = {e.id: e for e in entries}
    seen = set()
    for e in entries:
        seen.add(e.id)
        compat = e.compatible(core_api)
        inst = installed.get(e.id)
        if inst is not None:
            # SZEMANTIKUS összevetés: csak akkor „Frissíthető", ha az online
            # verzió SZIGORÚAN ÚJABB (a puszta != egy RÉGEBBI online verziót is
            # frissítésnek vett volna)
            updatable = bool(compat and e.version
                             and modkit.version_gt(e.version, inst))
            status = "Frissíthető" if updatable else "Telepítve"
            rows.append(dict(id=e.id, name=e.name, category=e.category,
                             status=status, version=e.version or inst,
                             entry=e, installable=updatable, removable=True))
        elif compat:
            rows.append(dict(id=e.id, name=e.name, category=e.category,
                             status="Elérhető", version=e.version,
                             entry=e, installable=True, removable=False))
        else:
            rows.append(dict(id=e.id, name=e.name, category=e.category,
                             status="Újabb SuperDL kell", version=e.version,
                             entry=e, installable=False, removable=False))
    # telepítve, de a boltban nincs (helyi/levett modul)
    for mid, ver in installed.items():
        if mid not in seen:
            rows.append(dict(id=mid, name=mid, category="Egyéb",
                             status="Telepítve (helyi)", version=ver,
                             entry=None, installable=False, removable=True))
    rows.sort(key=lambda r: (r["status"] != "Frissíthető", r["name"].lower()))
    return rows


class ModuleManagerFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Modulkezelő", size=(760, 520))
        self.main = main
        self.loader = (getattr(main, "_module_loader", None)
                       or coremod.init_modules(main))
        self.root = modkit.modules_root()
        self._rows = []
        self._busy = False

        self._build()
        self.CreateStatusBar()
        self.SetStatusText("A boltból frissíthető a lista. Enter egy soron: "
                           "telepítés/frissítés. Delete: eltávolítás.")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        wx.CallAfter(self._refresh_async)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label=(
            "Itt kezelheted a SuperDL opcionális moduljait. A modulok a "
            "hivatalos forrásból, SHA-256-tal ellenőrizve töltődnek le.")),
            0, wx.ALL, 10)

        self.list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.list.SetName("Modulok listája")
        for i, (h, w) in enumerate([("Modul", 260), ("Kategória", 140),
                                    ("Állapot", 160), ("Verzió", 120)]):
            self.list.InsertColumn(i, h, width=w)
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._install_selected())
        self.list.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.list.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda e: self._say_selected())
        v.Add(self.list, 1, wx.EXPAND | wx.ALL, 10)

        row = wx.BoxSizer(wx.HORIZONTAL)
        self.refresh_btn = wx.Button(p, label="&Frissítés a boltból")
        self.refresh_btn.Bind(wx.EVT_BUTTON, lambda e: self._refresh_async())
        self.install_btn = wx.Button(p, label="&Telepítés / frissítés")
        self.install_btn.Bind(wx.EVT_BUTTON, lambda e: self._install_selected())
        self.remove_btn = wx.Button(p, label="&Eltávolítás")
        self.remove_btn.Bind(wx.EVT_BUTTON, lambda e: self._remove_selected())
        close_btn = wx.Button(p, label="Be&zárás")
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        for b in (self.refresh_btn, self.install_btn, self.remove_btn, close_btn):
            row.Add(b, 0, wx.RIGHT, 6)
        v.Add(row, 0, wx.ALL, 10)

        self.gauge = wx.Gauge(p, range=100)
        self.gauge.SetName("Letöltés folyamata")
        v.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        p.SetSizer(v)
        self.install_btn.Disable()
        self.remove_btn.Disable()

    # ---- segédek ------------------------------------------------------

    def _announce(self, text):
        self.SetStatusText(text)
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(text, force=True)
            except Exception:
                pass

    def _installed_map(self) -> dict:
        out = {}
        for d in self.loader.discover(self.root):
            try:
                data = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
                man = modkit.parse_manifest(data)
                out[man.id] = man.version
            except Exception:
                out[d.name] = "?"
        return out

    def _selected_row(self):
        i = self.list.GetFirstSelected()
        return self._rows[i] if 0 <= i < len(self._rows) else None

    def _say_selected(self):
        r = self._selected_row()
        if r:
            self.install_btn.Enable(bool(r["installable"]) and not self._busy)
            self.remove_btn.Enable(bool(r["removable"]) and not self._busy)
            self._announce(f"{r['name']} – {r['status']}"
                           + (f", verzió {r['version']}" if r['version'] else ""))

    def _on_key(self, e):
        if e.GetKeyCode() == wx.WXK_DELETE:
            self._remove_selected()
        else:
            e.Skip()

    # ---- bolt-frissítés (index) ---------------------------------------

    def _refresh_async(self):
        if self._busy:
            return
        self._busy = True
        self._announce("Modullista frissítése a boltból…")
        installed = self._installed_map()

        def work():
            entries = coremod.fetch_index()
            wx.CallAfter(self._populate, entries, installed)
        threading.Thread(target=work, daemon=True).start()

    def _populate(self, entries, installed):
        self._busy = False
        self._rows = compute_rows(entries, installed)
        self.list.DeleteAllItems()
        for r in self._rows:
            i = self.list.InsertItem(self.list.GetItemCount(), r["name"])
            self.list.SetItem(i, 1, r["category"])
            self.list.SetItem(i, 2, r["status"])
            self.list.SetItem(i, 3, r["version"] or "")
        n_upd = sum(1 for r in self._rows if r["status"] == "Frissíthető")
        n_av = sum(1 for r in self._rows if r["status"] == "Elérhető")
        msg = f"{len(self._rows)} modul a listában"
        if n_upd:
            msg += f", ebből {n_upd} frissíthető"
        if n_av:
            msg += f", {n_av} új telepíthető"
        if not self._rows:
            msg = ("Nincs elérhető modul (a bolt-index még üres vagy nem "
                   "elérhető). Később próbáld újra.")
        self._announce(msg + ".")
        if self._rows:
            self.list.Select(0)
            self.list.Focus(0)

    # ---- telepítés / frissítés ----------------------------------------

    def _install_selected(self):
        r = self._selected_row()
        if self._busy or not r or not r["installable"] or not r["entry"]:
            return
        self._busy = True
        self.install_btn.Disable()
        self.remove_btn.Disable()
        self._announce(f"{r['name']} letöltése és telepítése…")

        def prog(frac):
            wx.CallAfter(self.gauge.SetValue, int(max(0, min(1, frac)) * 100))

        def work():
            try:
                man = coremod.install_entry(self.loader, r["entry"], prog, self.root)
                wx.CallAfter(self._install_done, True,
                             f"Telepítve: {man.name} ({man.version}). A teljes "
                             "érvényesüléshez indítsd újra a SuperDL-t.")
            except Exception as ex:
                wx.CallAfter(self._install_done, False,
                             f"A telepítés nem sikerült: {ex}")
        threading.Thread(target=work, daemon=True).start()

    def _install_done(self, ok, msg):
        self._busy = False
        self.gauge.SetValue(0)
        self._announce(msg)
        self._refresh_async()

    # ---- eltávolítás --------------------------------------------------

    def _remove_selected(self):
        r = self._selected_row()
        if self._busy or not r or not r["removable"]:
            return
        if wx.MessageBox(f"Biztosan eltávolítod a(z) „{r['name']}” modult?",
                         "Modul eltávolítása", wx.YES_NO | wx.ICON_QUESTION,
                         self) != wx.YES:
            return
        ok = coremod.remove_module(self.loader, r["id"], self.root)
        self._announce(f"Eltávolítva: {r['name']}." if ok
                       else f"Nem sikerült eltávolítani: {r['name']}.")
        self._refresh_async()

    def _on_close(self, e):
        if getattr(self.main, "_modmgr_win", None) is self:
            self.main._modmgr_win = None
        self.Destroy()
