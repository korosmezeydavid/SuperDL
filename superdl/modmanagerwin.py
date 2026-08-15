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
            # ha a TÉNYLEGES programverzió a kevés, mondjuk meg, mennyi kell
            need = getattr(e, "min_core_version", "")
            status = ("Újabb SuperDL kell (legalább " + need + ")"
                      if need and not modkit.core_version_ok(need)
                      else "Újabb SuperDL kell")
            rows.append(dict(id=e.id, name=e.name, category=e.category,
                             status=status, version=e.version,
                             entry=e, installable=False, removable=False))
    # telepítve, de a boltban nincs (helyi/levett modul)
    for mid, ver in installed.items():
        if mid not in seen:
            rows.append(dict(id=mid, name=mid, category="Egyéb",
                             status="Telepítve (helyi)", version=ver,
                             entry=None, installable=False, removable=True))
    rows.sort(key=lambda r: (r["status"] != "Frissíthető", r["name"].lower()))
    return rows


def frissitheto_sorok(rows) -> list:
    """Melyik sorokat érinti az „Összes frissítése"? CSAK a TELEPÍTETT, valóban
    frissíthető modulokat (TISZTA függvény, tesztelhető). Laci kérése pontosan
    ez volt: „természetesen csak azon modulokra vonatkoztatva, amiket a
    felhasználó már telepített korábban"."""
    return [r for r in (rows or [])
            if r.get("status") == "Frissíthető" and r.get("entry")
            and r.get("installable")]


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
        self.SetStatusText("Enter egy soron: telepítés/frissítés. Delete: "
                           "eltávolítás. „Összes frissítése”: mind egyben.")
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
        self.install_btn = wx.Button(p, label="&Telepítés / frissítés")
        self.install_btn.SetName("A kijelölt modul telepítése vagy frissítése")
        self.install_btn.Bind(wx.EVT_BUTTON, lambda e: self._install_selected())
        # Laci észrevétele: egyesével frissíteni sok modulnál kínszenvedés.
        # Ez a gomb VÉGIGMEGY az összes TELEPÍTETT, frissíthető modulon.
        self.update_all_btn = wx.Button(p, label="Összes f&rissítése")
        self.update_all_btn.SetName("Az összes telepített modul frissítése "
                                    "egyben")
        self.update_all_btn.Bind(wx.EVT_BUTTON, lambda e: self._update_all())
        self.remove_btn = wx.Button(p, label="&Eltávolítás")
        self.remove_btn.SetName("A kijelölt modul eltávolítása")
        self.remove_btn.Bind(wx.EVT_BUTTON, lambda e: self._remove_selected())
        # ÁTNEVEZVE: a régi „Frissítés a boltból" félrevezető volt – nem modult
        # frissít, hanem a KÍNÁLATOT tölti újra. Laci jelezte, hogy érthetetlen.
        self.refresh_btn = wx.Button(p, label="&Kínálat újratöltése")
        self.refresh_btn.SetName("A modulok listájának újratöltése a boltból – "
                                 "ez csak a kínálatot frissíti, modult nem")
        self.refresh_btn.SetToolTip("Csak a LISTÁT tölti újra: mi kapható, és "
                                    "melyik modulhoz van újabb verzió")
        self.refresh_btn.Bind(wx.EVT_BUTTON, lambda e: self._refresh_async())
        close_btn = wx.Button(p, label="Be&zárás")
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        for b in (self.install_btn, self.update_all_btn, self.remove_btn,
                  self.refresh_btn, close_btn):
            row.Add(b, 0, wx.RIGHT, 6)
        v.Add(row, 0, wx.ALL, 10)

        self.gauge = wx.Gauge(p, range=100)
        self.gauge.SetName("Letöltés folyamata")
        v.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        p.SetSizer(v)
        from superdl.uihelp import bind_help
        bind_help(self, "Súgó – Modulkezelő",
                  "MODULKEZELŐ\n\nItt telepíthetsz, frissíthetsz és "
                  "eltávolíthatsz modulokat (könyvek, rádió, játékok stb.).\n"
                  "• Fel/le nyíl: választás a listából.\n"
                  "• A gombokkal (vagy Enterrel) telepíted/frissíted a "
                  "kijelöltet; a modul saját ablaka a menüből nyílik.\n"
                  "• Ha egy modul újabb programverziót igényel, a lista jelzi.\n"
                  "• „Összes frissítése”: végigmegy az ÖSSZES telepített, "
                  "frissíthető modulon – nem kell egyesével.\n"
                  "• „Kínálat újratöltése”: csak a listát tölti újra a boltból "
                  "(nem frissít modult).")
        self.install_btn.Disable()
        self.remove_btn.Disable()
        self.update_all_btn.Disable()

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
            from . import netdialog
            if not netdialog.ensure_online(self, "a modullista frissítéséhez",
                                           speak=self._announce):
                wx.CallAfter(self._refresh_offline,
                             "Nincs internetkapcsolat.")
                return
            entries = coremod.fetch_index()
            wx.CallAfter(self._populate, entries, installed)
        threading.Thread(target=work, daemon=True).start()

    def _refresh_offline(self, msg):
        self._busy = False
        self._announce(msg)

    def _populate(self, entries, installed):
        self._busy = False
        self._rows = compute_rows(entries, installed)
        self.list.DeleteAllItems()
        for r in self._rows:
            i = self.list.InsertItem(self.list.GetItemCount(), r["name"])
            self.list.SetItem(i, 1, r["category"])
            self.list.SetItem(i, 2, r["status"])
            self.list.SetItem(i, 3, r["version"] or "")
        n_upd = len(frissitheto_sorok(self._rows))
        n_av = sum(1 for r in self._rows if r["status"] == "Elérhető")
        self.update_all_btn.Enable(bool(n_upd) and not self._busy)
        msg = f"{len(self._rows)} modul a listában"
        if n_upd:
            msg += f", ebből {n_upd} frissíthető"
        if n_av:
            msg += f", {n_av} új telepíthető"
        if not self._rows:
            msg = ("Nincs elérhető modul (a bolt-index még üres vagy nem "
                   "elérhető). Később próbáld újra.")
        elif n_upd:
            # FONTOS a felfedezhetőség miatt: aki nem böngészi végig a gombokat,
            # magától sosem tudná meg, hogy egyben is lehet frissíteni.
            msg += (f". Az „Összes frissítése” gombbal mind a(z) {n_upd} "
                    "elintézhető egyszerre")
        self._announce(msg + ".")
        if self._rows:
            self.list.Select(0)
            self.list.Focus(0)

    # ---- telepítés / frissítés ----------------------------------------

    def _forras_rendben(self) -> bool:
        """BIZTONSÁG: nem hivatalos modul-forrásból telepíteni csak kifejezett
        megerősítéssel lehet (Tibi-audit 3.5; a kérdést az olvasó felolvassa)."""
        from superdl import selfupdate
        if selfupdate.repo_is_official():
            return True
        return wx.MessageBox(
            "A modul NEM a hivatalos boltból jönne, hanem innen:\n\n"
            f"    {selfupdate.get_repo()}\n\n"
            "Csak akkor folytasd, ha ezt TE állítottad be (Fejlesztői "
            "mód). Biztosan telepíted?",
            "Nem hivatalos modul-forrás",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self) == wx.YES

    def _gombok(self, be: bool) -> None:
        self.install_btn.Enable(be)
        self.remove_btn.Enable(be)
        self.update_all_btn.Enable(be)
        self.refresh_btn.Enable(be)

    # ---- ÖSSZES frissítése (Laci kérése) -------------------------------

    def _update_all(self):
        """Végigmegy az ÖSSZES telepített, frissíthető modulon. Csak a
        telepítettekre – amit a felhasználó nem használ, azt nem tesszük fel."""
        if self._busy:
            return
        sorok = frissitheto_sorok(self._rows)
        if not sorok:
            self._announce("Most nincs frissíthető modul. Ha frissebb "
                           "kínálatra vagy kíváncsi, előbb töltsd újra a "
                           "kínálatot.")
            return
        if not self._forras_rendben():
            return
        nevek = ", ".join(r["name"] for r in sorok)
        kerdes = (f"{len(sorok)} modulhoz van újabb verzió:\n\n    {nevek}\n\n"
                  "Frissítsem mindet, egymás után?")
        self._announce(f"{len(sorok)} modulhoz van újabb verzió: {nevek}. "
                       "Frissítsem mindet, egymás után?")
        if wx.MessageBox(kerdes, "Összes modul frissítése",
                         wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            self._announce("A frissítés elmarad.")
            return

        self._busy = True
        self._gombok(False)
        osszes = len(sorok)

        def work():
            from . import netdialog
            if not netdialog.ensure_online(self, "a modulok frissítéséhez",
                                           speak=self._announce):
                wx.CallAfter(self._update_all_done, [], [],
                             "Nincs internetkapcsolat.")
                return
            sikeres, hibas = [], []
            for i, r in enumerate(sorok, 1):
                nev = r["name"]
                wx.CallAfter(self._announce,
                             f"{i} / {osszes}: {nev} frissítése…")

                def prog(frac, i=i):
                    egesz = (i - 1 + max(0.0, min(1.0, frac))) / osszes
                    wx.CallAfter(self.gauge.SetValue, int(egesz * 100))

                try:
                    man = coremod.install_entry(self.loader, r["entry"], prog,
                                                self.root)
                    sikeres.append(f"{man.name} {man.version}")
                    continue
                except Exception as ex:
                    elso_hiba = ex
                # TARTALÉK: a helyben-csere jellemzően FÁJLZÁR miatt bukik (a
                # vírusirtó/Windows fogja a betöltött modul mappáját). Kézzel az
                # „Eltávolítás majd Telepítés" mindig megoldotta – itt ezt
                # automatikusan megtesszük. A modul adatai nem vesznek el, mert
                # azok a ~/.superdl/modules_data mappában vannak.
                wx.CallAfter(self._announce,
                             f"{nev}: a helyben-frissítés nem ment, "
                             "újratelepítéssel próbálom…")
                try:
                    man = coremod.reinstall_entry(self.loader, r["entry"], prog,
                                                  self.root)
                    sikeres.append(f"{man.name} {man.version} (újratelepítve)")
                except Exception as ex2:
                    hibas.append(f"{nev}: {ex2 or elso_hiba}")
            wx.CallAfter(self._update_all_done, sikeres, hibas, "")

        threading.Thread(target=work, daemon=True).start()

    def _update_all_done(self, sikeres, hibas, hiba_uzenet):
        self._busy = False
        self.gauge.SetValue(0)
        self._gombok(True)
        if hiba_uzenet:
            self._announce(hiba_uzenet)
            return
        reszek = []
        if sikeres:
            reszek.append("%d modul frissítve: %s"
                          % (len(sikeres), ", ".join(sikeres)))
        if hibas:
            reszek.append("%d nem sikerült: %s" % (len(hibas), "; ".join(hibas)))
        uzenet = ". ".join(reszek) if reszek else "Nem történt frissítés."
        self._announce(uzenet + ".")
        self._refresh_async()
        if sikeres:
            self._ujraindit_ajanlat(uzenet)

    def _ujraindit_ajanlat(self, uzenet: str) -> None:
        """A friss modul-kód csak új indítás után él teljesen – ezt ne a
        felhasználónak kelljen tudnia."""
        kerdes = (uzenet + ".\n\nA frissítések teljes érvényesüléséhez a "
                  "SuperDL-t újra kell indítani. Újraindítsam most?")
        if wx.MessageBox(kerdes, "Frissítés kész",
                         wx.YES_NO | wx.ICON_INFORMATION, self) != wx.YES:
            self._announce("Rendben, a frissítések a következő indításkor "
                           "lépnek teljesen életbe.")
            return
        if coremod.restart_app():
            self._announce("Újraindítás…")
            wx.CallAfter(self.main.Close)
        else:
            self._announce("Az újraindítást most nem tudom elvégezni – zárd be "
                           "és indítsd el a SuperDL-t.")

    # ---- egyetlen modul telepítése / frissítése ------------------------

    def _install_selected(self):
        r = self._selected_row()
        if self._busy or not r or not r["installable"] or not r["entry"]:
            return
        if not self._forras_rendben():
            return
        self._busy = True
        self.install_btn.Disable()
        self.remove_btn.Disable()
        self._announce(f"{r['name']} letöltése és telepítése…")

        def prog(frac):
            wx.CallAfter(self.gauge.SetValue, int(max(0, min(1, frac)) * 100))

        def work():
            from . import netdialog
            if not netdialog.ensure_online(self, "a modul telepítéséhez",
                                           speak=self._announce):
                wx.CallAfter(self._install_done, False,
                             "Nincs internetkapcsolat.")
                return
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
