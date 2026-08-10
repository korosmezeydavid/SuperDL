# -*- coding: utf-8 -*-
"""Átjáró – akadálymentes ablak a PC↔telefon kapcsolathoz (wxPython).

Csatlakozás a SuperDL telefon (Android launcher) beépített WiFi-portáljához a
helyi hálózaton, majd zene és könyv küldése a telefonra. Minden a felhasználó
saját gépei között marad; semmit nem továbbítunk sehová.
"""
import os
import threading

import wx

from . import atjaro_core as AC


_SUGO = (
    "ÁTJÁRÓ – SÚGÓ\n\n"
    "Ez az ablak a PC-t köti össze a SuperDL telefonoddal a HELYI WiFi-n, hogy "
    "zenét és könyvet küldhess a telefonra. Semmit nem továbbítunk sehová – a "
    "PC közvetlenül a telefonod portáljához kapcsolódik.\n\n"
    "CSATLAKOZÁS\n"
    "1. A telefonon: Zene és Média → WiFi fájlportál → BE. A telefon bemond egy "
    "CÍMET (pl. http://192.168.0.20:8080) és egy 4 jegyű PIN-t.\n"
    "2. Itt írd be a telefon IP-címét (a cím egészét is beillesztheted) és a "
    "PIN-t, majd Kapcsolat tesztelése. Az IP-t megjegyzem; a PIN a portál "
    "minden bekapcsolásakor új, azt mindig újra beírod.\n\n"
    "KÜLDÉS\n"
    "• Zene küldése: kiválasztod a zenefájlokat, és a telefon Zene mappájába "
    "kerülnek (a lejátszó azonnal látja).\n"
    "• Könyv küldése: választhatsz EGYETLEN fájlt (könyv vagy hangfájl – mp3, "
    "m4a, m4b stb.) VAGY egy EGÉSZ MAPPÁT. A mappa a telefonon is egy mappa "
    "(azaz egy hangoskönyv) marad, a benne lévő hangfájlokkal együtt.\n\n"
    "TELEFON ADATAI (szinkron)\n"
    "• 📥 Telefon adatai: beolvassa a telefon gyógyszer-emlékeztetőit és a "
    "könyv-pozícióit. Megmutatja, mely könyvek vannak meg a PC-n is.\n"
    "• ➕ Gyógyszerek a Szervezésbe: a telefon bekapcsolt gyógyszer-"
    "emlékeztetőit beviszi a PC Szervezés (naptár) moduljába, napi ismétléssel. "
    "A már meglévőket nem duplázza, így többször is futtathatod.\n\n"
    "KÖNYVJELZŐK SZINKRONIZÁLÁSA (kétirányú)\n"
    "• 🔖 Könyvjelzők szinkronizálása: összeéri a PC és a telefon könyvjelzőit "
    "– a telefonéi bekerülnek a PC Könyvek moduljába, a PC-éit pedig felküldi a "
    "telefonra. A párosítás a könyv FÁJLNEVE alapján megy, így az eltérő "
    "elérési utak nem zavarnak. A Könyvolvasóban Ctrl+B tesz le könyvjelzőt, "
    "Ctrl+Shift+B listázza őket. Ha egy PC-n olvasott könyv nincs a telefonon, "
    "a Könyvolvasó felajánlja az átküldést. Szinkronkor a program ellenőrzi, "
    "hogy a könyvjelzőhöz tartozó hangoskönyv megvan-e a telefonon; ha nincs, "
    "felajánlja, hogy magát a könyvet (mappát) is átküldi.\n\n"
    "NAPTÁR ÖSSZEKÖTÉSE (telefon → PC)\n"
    "• 📅 Naptár összekötése: a telefonod a naptár-eseményeket a Google-fiókod "
    "naptárába írja. Itt feliratkoztathatod a PC Szervezését ennek a naptárnak a "
    "TITKOS iCal-címével (Google Naptár → Beállítások → a naptárad → „Titkos cím "
    "iCal formátumban” → …/basic.ics). Ezután a telefon eseményei maguktól "
    "megjelennek a Szervezés naptáradban (olvasásra). A titkos címet titkosítva "
    "tároljuk, sehol nem jelenítjük meg.\n\n"
    "HAMAROSAN (ugyanitt)\n"
    "• A naptár PC → telefon iránya és a pontos olvasási pozíció (%) átvétele.\n\n"
    "Csak a SAJÁT telefonodhoz, a saját WiFi-den. F1: ez a súgó. Escape: bezárás."
)


def _mondd(main, szoveg):
    if not (szoveg or "").strip():
        return
    try:
        from superdl import screenreader
        if screenreader.speak(szoveg):
            return
    except Exception:
        pass
    sv = getattr(main, "selfvoice", None)
    if sv:
        try:
            sv.speak(szoveg, force=True)
        except Exception:
            pass


def _hatterben(munka, kesz, hiba):
    def fut():
        try:
            e = munka()
        except Exception as ex:
            wx.CallAfter(hiba, ex)
        else:
            wx.CallAfter(kesz, e)
    threading.Thread(target=fut, daemon=True).start()


class NaptarDialog(wx.Dialog):
    """Vezetett naptár-összekötés: a telefon Google-naptárának titkos iCal-
    címével feliratkoztatja a PC Szervezését, így a telefon eseményei maguktól
    megjelennek. A titkos címet sehol nem jelenítjük meg és nem naplózzuk – azt
    a Szervezés DPAPI-titkosítva tárolja; a listán csak biztonságos címke van."""

    def __init__(self, parent, mgr):
        super().__init__(parent, title="Naptár összekötése (telefon → PC)",
                         size=(640, 520))
        self._frame = parent
        self._mgr = mgr
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        v.Add(wx.StaticText(p, label=(
            "A telefonod a naptár-eseményeket a Google-fiókod naptárába írja. Ha "
            "a PC ide feliratkozik ennek a naptárnak a TITKOS iCal-címével, a "
            "telefon eseményei maguktól megjelennek a Szervezés naptáradban "
            "(olvasásra). Semmit nem továbbítunk – a PC közvetlenül a Google "
            "naptár-linkjéről olvas.\n\n"
            "1. Nyisd meg a Google Naptár beállításait, válaszd ki a naptárad, "
            "és a „Naptár összeépítése” résznél másold ki a „Titkos cím iCal "
            "formátumban” linket (…/basic.ics).\n"
            "2. Illeszd be ide, és kattints a Feliratkozás gombra.")),
            0, wx.ALL, 10)

        b_open = wx.Button(p, label="Google Naptár &megnyitása a böngészőben")
        b_open.Bind(wx.EVT_BUTTON, self._google_nyit)
        v.Add(b_open, 0, wx.LEFT | wx.BOTTOM, 10)

        # cím-beviteli sor (címke a mező ELŐTT – helyes felolvasás)
        st = wx.StaticText(p, label="A naptár titkos i&Cal-címe (…/basic.ics):")
        v.Add(st, 0, wx.LEFT, 10)
        self.url_mezo = wx.TextCtrl(p)
        self.url_mezo.SetName("A naptár titkos iCal-címe")
        v.Add(self.url_mezo, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        b_fel = wx.Button(p, label="&Feliratkozás")
        b_fel.Bind(wx.EVT_BUTTON, self._feliratkozas)
        v.Add(b_fel, 0, wx.LEFT | wx.BOTTOM, 10)

        v.Add(wx.StaticText(p, label="&Feliratkozott naptárak:"), 0, wx.LEFT, 10)
        self.lista = wx.ListBox(p)
        self.lista.SetName("Feliratkozott naptárak")
        v.Add(self.lista, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        also = wx.BoxSizer(wx.HORIZONTAL)
        b_torol = wx.Button(p, label="A kijelölt feliratkozás &törlése")
        b_torol.Bind(wx.EVT_BUTTON, self._torol)
        also.Add(b_torol, 0, wx.RIGHT, 8)
        b_be = wx.Button(p, wx.ID_CLOSE, label="&Bezárás")
        b_be.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        also.Add(b_be, 0)
        v.Add(also, 0, wx.ALL, 10)

        p.SetSizer(v)
        self._frissit()
        wx.CallAfter(self.url_mezo.SetFocus)

    def _mond(self, szoveg):
        _mondd(getattr(self._frame, "main", None), szoveg)

    def _frissit(self):
        self._ids = []
        self.lista.Clear()
        for s in getattr(self._mgr, "ics_subs", []):
            self._ids.append(s.id)
            try:
                cimke = s.safe_label()
            except Exception:
                cimke = s.name or "naptár"
            self.lista.Append(f"{s.name}  –  {cimke}")

    def _google_nyit(self, e):
        import webbrowser
        try:
            webbrowser.open(AC.GOOGLE_NAPTAR_BEALLITAS_URL)
            self._mond("Megnyitottam a Google Naptár beállításait a böngészőben. "
                       "Ott másold ki a naptárad titkos iCal-címét.")
        except Exception:
            self._mond("Nem sikerült megnyitni a böngészőt. Nyisd meg kézzel a "
                       "Google Naptár beállításait.")

    def _feliratkozas(self, e):
        url = AC.normalizal_ical_url(self.url_mezo.GetValue())
        if not AC.ical_url_ok(url):
            self._mond("Ez nem tűnik érvényes iCal-címnek. Egy https-címet várok, "
                       "ami .ics-re végződik (a Google Naptár „Titkos cím iCal "
                       "formátumban” linkje).")
            self.url_mezo.SetFocus()
            return
        nev = AC.naptar_nev_javaslat(url)
        try:
            self._mgr.add_ics(nev, url)
        except Exception as ex:
            self._mond(f"A feliratkozás nem sikerült: {ex}")
            return
        self.url_mezo.SetValue("")
        self._frissit()
        self._mond(f"Feliratkozva: {nev}. A telefon eseményei hamarosan "
                   "megjelennek a Szervezés naptáradban. A titkos címet "
                   "biztonságosan, titkosítva tároltam.")

    def _torol(self, e):
        i = self.lista.GetSelection()
        if i < 0 or i >= len(self._ids):
            self._mond("Előbb jelölj ki egy feliratkozást a listában.")
            return
        try:
            self._mgr.remove_ics(self._ids[i])
        except Exception as ex:
            self._mond(f"A törlés nem sikerült: {ex}")
            return
        self._frissit()
        self._mond("A feliratkozást töröltem.")


class AtjaroFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(None, title="Átjáró – PC és telefon összekötése",
                         size=(720, 520))
        self.main = main
        self._closing = False
        self._pending_konyv = None      # a Könyvolvasóból átküldésre váró könyv
        self._panel = wx.Panel(self)
        self._build()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Centre()
        wx.CallAfter(self._indul)

    def _build(self):
        p = self._panel
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label=(
            "Kösd össze a PC-t a SuperDL telefonoddal a helyi WiFi-n, és küldj "
            "zenét vagy könyvet a telefonra. A telefonon kapcsold be: Zene és "
            "Média → WiFi fájlportál. Súgó: F1.")), 0, wx.ALL, 10)

        def sor(cimke, **kw):
            s = wx.BoxSizer(wx.HORIZONTAL)
            st = wx.StaticText(p, label=cimke)
            ctrl = wx.TextCtrl(p, **kw)
            ctrl.SetName(cimke.replace("&", "").rstrip(":"))
            s.Add(st, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
            s.Add(ctrl, 1)
            v.Add(s, 0, wx.EXPAND | wx.ALL, 6)
            return ctrl

        # IP-BEÍRÓ sor – ez látszik ELSŐ alkalommal; ha már megjegyeztük, ELTŰNIK
        self._ip_sor = wx.BoxSizer(wx.HORIZONTAL)
        self._ip_cimke = wx.StaticText(p, label="A telefon &IP-címe "
                                       "(pl. 192.168.0.20):")
        self.ip_mezo = wx.TextCtrl(p)
        self.ip_mezo.SetName("A telefon IP-címe")
        self.ip_mezo.Bind(wx.EVT_KILL_FOCUS, self._ip_ment)
        self._ip_sor.Add(self._ip_cimke, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self._ip_sor.Add(self.ip_mezo, 1)
        v.Add(self._ip_sor, 0, wx.EXPAND | wx.ALL, 6)

        # TÖMÖR „megjegyzett telefon" sor – ez látszik, ha már van mentett IP
        self._ip_info_sor = wx.BoxSizer(wx.HORIZONTAL)
        self.ip_info = wx.StaticText(p, label="")
        self.ip_info.SetName("Megjegyzett telefon")
        b_mod = wx.Button(p, label="Másik telefon / IP &módosítása")
        b_mod.Bind(wx.EVT_BUTTON, self._ip_modosit)
        self._ip_info_sor.Add(self.ip_info, 0,
                              wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        self._ip_info_sor.Add(b_mod, 0)
        v.Add(self._ip_info_sor, 0, wx.EXPAND | wx.ALL, 6)

        self.pin_mezo = sor("A telefon &PIN-je (4 számjegy):")
        b_teszt = wx.Button(p, label="Kapcsolat &tesztelése")
        b_teszt.Bind(wx.EVT_BUTTON, self._teszt)
        v.Add(b_teszt, 0, wx.ALL, 6)

        gs = wx.BoxSizer(wx.HORIZONTAL)
        self.b_zene = wx.Button(p, label="🎵 &Zene küldése a telefonra")
        self.b_zene.Bind(wx.EVT_BUTTON, self._zene)
        gs.Add(self.b_zene, 0, wx.RIGHT, 8)
        self.b_konyv = wx.Button(p, label="📖 &Könyv küldése a telefonra")
        self.b_konyv.Bind(wx.EVT_BUTTON, self._konyv)
        gs.Add(self.b_konyv, 0, wx.RIGHT, 8)
        self.b_adatok = wx.Button(
            p, label="📥 Te&lefon adatai (gyógyszer, könyvjelzők)")
        self.b_adatok.Bind(wx.EVT_BUTTON, self._telefon_adatok)
        gs.Add(self.b_adatok, 0, wx.RIGHT, 8)
        self.b_import = wx.Button(
            p, label="➕ &Gyógyszerek a Szervezésbe")
        self.b_import.Bind(wx.EVT_BUTTON, self._gyogyszer_import)
        self.b_import.Enable(False)         # csak beolvasott adatok után
        gs.Add(self.b_import, 0)
        v.Add(gs, 0, wx.ALL, 6)

        cs = wx.BoxSizer(wx.HORIZONTAL)
        b_naptar = wx.Button(p, label="📅 &Naptár összekötése (telefon → PC)")
        b_naptar.Bind(wx.EVT_BUTTON, self._naptar)
        cs.Add(b_naptar, 0, wx.RIGHT, 8)
        self.b_jelzo = wx.Button(p, label="🔖 Könyv&jelzők szinkronizálása")
        self.b_jelzo.Bind(wx.EVT_BUTTON, self._konyvjelzo_sync)
        cs.Add(self.b_jelzo, 0)
        v.Add(cs, 0, wx.LEFT | wx.BOTTOM, 6)

        v.Add(wx.StaticText(p, label="Á&llapot:"), 0, wx.LEFT, 8)
        self.atirat = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.atirat.SetName("Állapot")
        v.Add(self.atirat, 1, wx.EXPAND | wx.ALL, 8)

        footer = wx.BoxSizer(wx.HORIZONTAL)
        b_sugo = wx.Button(p, label="&Súgó (F1)")
        b_sugo.Bind(wx.EVT_BUTTON, lambda e: self._sugo())
        footer.Add(b_sugo, 0, wx.RIGHT, 6)
        b_tam = wx.Button(p, label="❤ &Támogatás")
        b_tam.Bind(wx.EVT_BUTTON, self._tamogatas)
        footer.Add(b_tam, 0)
        v.Add(footer, 0, wx.ALL, 8)
        p.SetSizer(v)

    def _ip_mod_nezet(self, van_mentett, ip=""):
        """Ha van mentett IP: ELREJTI a beíró sort, és a tömör sort mutatja
        (és fordítva) – így megjegyzés után nincs felesleges IP-mező."""
        self.ip_info.SetLabel(f"Telefon: {ip}  (megjegyezve)" if ip else "")
        self._ip_sor.ShowItems(not van_mentett)
        self._ip_info_sor.ShowItems(van_mentett)
        self._panel.Layout()

    def _indul(self):
        b = AC.beallitas_betolt()
        ip = b.get("ip", "")
        if ip:
            self.ip_mezo.SetValue(ip)
            self._ip_mod_nezet(True, ip)
            self.pin_mezo.SetFocus()
            self._mond(f"Átjáró. A telefon megjegyezve: {ip}. Már csak a PIN-t "
                       "kell beírnod (a telefon minden portál-bekapcsoláskor "
                       "újat mond), aztán Kapcsolat tesztelése.")
        else:
            self._ip_mod_nezet(False)
            self._mond("Átjáró. A telefonon kapcsold be a WiFi fájlportált, majd "
                       "írd be az IP-címet és a PIN-t. Az IP-t megjegyzem, "
                       "legközelebb már csak a PIN kell.")

    def _ip_ment(self, e):
        ip = self.ip_mezo.GetValue().strip()
        if ip:
            AC.beallitas_ment(ip)
            # megjegyeztük → az IP-mező eltűnik, marad a tömör sor + a PIN
            wx.CallAfter(self._ip_mod_nezet, True, ip)
        if e:
            e.Skip()

    def _ip_modosit(self, e):
        self._ip_mod_nezet(False, self.ip_mezo.GetValue().strip())
        self.ip_mezo.SetFocus()
        self._mond("Írd be az új telefon IP-címét, majd lépj tovább – megjegyzem.")

    def _telefon_adatok(self, e):
        ip, pin = self._adatok()
        if not ip or not pin:
            self._mond("Előbb add meg a telefon IP-címét és a PIN-t.")
            return
        AC.beallitas_ment(ip)
        self._mond("A telefon adatainak beolvasása…")
        _hatterben(lambda: AC.backup_letolt(ip, pin),
                   self._telefon_adatok_kesz, self._hiba)

    def _telefon_adatok_kesz(self, backup):
        if self._closing:
            return
        gy = AC.gyogyszer_aktivak(AC.kigyujt_gyogyszerek(backup))
        poz = AC.kigyujt_konyv_poziciok(backup)
        # a PC-könyvtár útjai a fájlnév-egyeztetéshez
        pc_utak = []
        lib = getattr(self.main, "library", None)
        if lib is not None:
            pc_utak = [b.path for b in getattr(lib, "items", [])]
        egyezes = AC.konyv_egyezes(poz, pc_utak)
        self._gyogyszerek = gy          # az importhoz eltesszük
        AC.telefon_konyvek_ment(list(poz.keys()))   # a Könyvolvasó tudja, mi van a telefonon

        reszek = [f"A telefonon {len(gy)} bekapcsolt gyógyszer-emlékeztető van."]
        for g in gy[:10]:
            napi = str(g.get("cycleType", "DAILY")).upper() == "DAILY"
            reszek.append(f"• {g.get('name', '?')} – "
                          f"{int(g.get('hour', 0) or 0):02d}:"
                          f"{int(g.get('minute', 0) or 0):02d}"
                          f"{'  (naponta)' if napi else ''}")
        if gy:
            reszek.append("Az ➕ Gyógyszerek a Szervezésbe gombbal beviheted "
                          "őket a PC naptáradba/emlékeztetőidbe.")

        reszek.append("")
        reszek.append(f"Könyv-pozíció {len(egyezes)} könyvhöz a telefonon:")
        for r in egyezes[:10]:
            ott = "✓ megvan a PC-n is" if r["pc_ut"] else "csak a telefonon"
            reszek.append(f"• {r['nev']} – {ott}")
        if any(r["pc_ut"] for r in egyezes):
            reszek.append("A közös könyvek pozíciójának pontos átvételéhez a "
                          "telefon a százalékos állást is elküldi majd – ez a "
                          "mobil-oldali bővítés a következő lépés.")

        self._mond("\n".join(reszek))
        self.b_import.Enable(bool(gy))
        if gy:
            self.b_import.SetFocus()

    def _gyogyszer_import(self, e):
        gy = getattr(self, "_gyogyszerek", None)
        if not gy:
            self._mond("Előbb olvasd be a telefon adatait (📥 Telefon adatai).")
            return
        mgr = getattr(self.main, "_organizer", None)
        if mgr is None:
            self._mond("A Szervezés nem érhető el ebben az ablakban.")
            return
        try:
            from superdl import organizer as O
        except Exception:
            self._mond("A Szervezés modul nem tölthető be.")
            return
        import datetime
        mai = datetime.date.today().isoformat()

        # már meglévő „telefonos" gyógyszer-esemény: cím+idő alapján ne duplázzunk
        meglevo = {(ev.title, ev.time) for ev in getattr(mgr, "events", [])}
        uj, kihagyva = 0, 0
        for g in gy:
            d = AC.gyogyszer_esemeny_adat(g, mai)
            if (d["title"], d["time"]) in meglevo:
                kihagyva += 1
                continue
            ev = O.Event(id=O.new_id(), title=d["title"], date=d["date"],
                         time=d["time"], note=d["note"], reminder_min=0,
                         repeat=d["repeat"], source="local")
            mgr.add_event(ev)
            meglevo.add((d["title"], d["time"]))
            uj += 1
        self._mond(f"Kész: {uj} gyógyszer-emlékeztető bekerült a Szervezésbe"
                   + (f", {kihagyva} már ott volt." if kihagyva else ".")
                   + " Megnyithatod: Eszközök → Szervezés.")
        self.b_import.Enable(False)

    def _naptar(self, e):
        mgr = getattr(self.main, "_organizer", None)
        if mgr is None:
            self._mond("A Szervezés (naptár) nem érhető el ebben az ablakban.")
            return
        dlg = NaptarDialog(self, mgr)
        dlg.ShowModal()
        dlg.Destroy()

    def _konyvjelzo_sync(self, e):
        ip, pin = self._adatok()
        if not ip or not pin:
            self._mond("Előbb add meg a telefon IP-címét és a PIN-t.")
            return
        store = getattr(self.main, "bookmarks", None)
        if store is None:
            self._mond("A könyvjelző-tár nem érhető el ebben az ablakban.")
            return
        AC.beallitas_ment(ip)
        self._mond("Könyvjelzők szinkronizálása a telefonnal…")
        # a kiküldendő PC-könyvjelzők pillanatképe (a hálózat háttérszálon fut)
        pc_ki = AC.pc_konyvjelzo_androidra([b.to_record() for b in store.all()])

        def munka():
            telefon = AC.konyvjelzok_le(ip, pin)          # a telefon könyvjelzői
            valasz = AC.konyvjelzok_fel(ip, pin, pc_ki)   # a PC-éi a telefonra
            konyvek = AC.telefon_konyvek_le(ip, pin)      # mely könyvek vannak a telefonon
            return telefon, valasz, konyvek

        _hatterben(munka, self._konyvjelzo_sync_kesz, self._hiba)

    def _konyvjelzo_sync_kesz(self, eredmeny):
        if self._closing:
            return
        telefon, valasz, telefon_konyvek = eredmeny
        store = self.main.bookmarks
        be = AC.android_konyvjelzo_be(telefon)
        # a telefon-könyvcache bővítése a könyvjelzők könyveivel (nincs-a-telefonon őr)
        try:
            megvan = AC.telefon_konyvek_betolt()
            megvan |= {r["book"] for r in be if r.get("book")}
            AC.telefon_konyvek_ment(list(megvan))
        except Exception:
            pass
        uj = store.merge(be)                                  # a PC-re bekerülők
        added = valasz.get("added", 0) if isinstance(valasz, dict) else 0
        total = valasz.get("total", "?") if isinstance(valasz, dict) else "?"
        self._mond(
            "Könyvjelző-szinkron kész. A telefonon "
            f"{len(telefon)} könyvjelző volt, ebből {uj} új került a PC-re. "
            f"A telefonra {max(0, added)} új könyvjelzőt küldtem "
            f"(a telefonon most összesen {total}). "
            "A könyvjelzőket a Könyvek modulban éred el.")
        # ha egy hang-könyvjelző könyve nincs a telefonon, ajánljuk fel a küldést
        self._ajanld_hianyzo_konyvek(telefon_konyvek)

    def _ajanld_hianyzo_konyvek(self, telefon_konyvek):
        """A hang-könyvjelzők könyvei közül azok, amik NINCSENEK a telefonon, de
        a PC hangoskönyv-polcán megvannak (mappa vagy fájl) – felajánlja a
        küldést, hogy a telefonon is folytatható legyen."""
        store = getattr(self.main, "bookmarks", None)
        if store is None:
            return
        hang = {}
        for b in store.all():
            if getattr(b, "kind", "text") == "audio":
                hang.setdefault(b.kulcs(), getattr(b, "title", "") or b.book)
        if not hang:
            return
        telefonon = {n.lower() for n in (telefon_konyvek or {}).get("audiobooks", [])}
        polc = AC.pc_hangoskonyv_polc()
        kuldheto = []
        for kulcs, cim in hang.items():
            if kulcs in telefonon:
                continue
            it = polc.get(kulcs)
            ut = (it or {}).get("path")
            if ut and os.path.exists(ut):
                kuldheto.append((cim, ut, bool((it or {}).get("is_dir", True))))
        if not kuldheto:
            return
        nevek = ", ".join(c for c, _, _ in kuldheto)
        valasz = wx.MessageBox(
            "A következő hangoskönyv(ek) könyvjelzőjét szinkronizáltuk, de maga a "
            f"könyv nincs a telefonon: {nevek}. Átküldjem a telefonra is, hogy ott "
            "is folytathasd, ahol a PC-n abbahagytad?",
            "Hiányzó hangoskönyv átküldése?", wx.YES_NO | wx.ICON_QUESTION, self)
        if valasz != wx.YES:
            return
        ip, pin = self._adatok()
        self._kuld_kovetkezo_konyv(list(kuldheto), ip, pin)

    def _kuld_kovetkezo_konyv(self, lista, ip, pin):
        if not lista:
            self._mond("A hiányzó hangoskönyvek átküldve. Most már a telefonon is "
                       "folytathatod a könyvjelzőidből.")
            return
        cim, ut, is_dir = lista.pop(0)
        self._utolso_mf = -1
        self._mond(f"„{cim}” küldése a telefonra…")

        def munka():
            if is_dir:
                return AC.mappa_kuld(ip, pin, ut, csak_hang=True,
                                     on_progress=self._kuldes_halad)
            return AC.feltolt_egyenkent(ip, pin, [ut], dest=AC.DEST_KONYV,
                                        on_progress=self._kuldes_halad)

        def kesz(eredmeny):
            if self._closing:
                return
            db, hiba = eredmeny
            if hiba:
                self._mond(f"„{cim}” küldése nem sikerült: {hiba}")
            else:
                self._mond(f"„{cim}” átküldve ({db} fájl).")
            wx.CallAfter(self._kuld_kovetkezo_konyv, lista, ip, pin)

        _hatterben(munka, kesz, self._hiba)

    # ---- műveletek ----
    def _adatok(self):
        ip = self.ip_mezo.GetValue().strip()
        pin = self.pin_mezo.GetValue().strip()
        return ip, pin

    def _teszt(self, e):
        ip, pin = self._adatok()
        if not ip or not pin:
            self._mond("Előbb add meg a telefon IP-címét és a PIN-t.")
            return
        AC.beallitas_ment(ip)
        self._mond("Kapcsolat tesztelése…")
        _hatterben(lambda: AC.csatlakozas_teszt(ip, pin),
                   self._teszt_kesz, self._hiba)

    def _teszt_kesz(self, ok):
        if self._closing:
            return
        if ok:
            self._mond("A kapcsolat rendben! Küldhetsz zenét vagy könyvet.")
        else:
            self._mond("Nem sikerült a kapcsolat: ellenőrizd az IP-t, a PIN-t "
                       "(a portál minden bekapcsolásakor új PIN-t mond), és hogy "
                       "a PC és a telefon UGYANAZON a WiFi-n van.")

    def _kuldes(self, dest, cimke, wildcard, utak=None):
        ip, pin = self._adatok()
        if not ip or not pin:
            self._mond("Előbb add meg a telefon IP-címét és a PIN-t.")
            return
        if utak is None:
            with wx.FileDialog(self, cimke, wildcard=wildcard,
                               style=wx.FD_OPEN | wx.FD_MULTIPLE
                               | wx.FD_FILE_MUST_EXIST) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                utak = dlg.GetPaths()
        if not utak:
            return
        AC.beallitas_ment(ip)
        self._utolso_mf = -1
        self._mond(f"{len(utak)} fájl küldése a telefonra…")
        _hatterben(lambda: AC.feltolt_egyenkent(ip, pin, utak, dest=dest,
                                                on_progress=self._kuldes_halad),
                   self._kuldes_kesz, self._hiba)

    def _kuldes_halad(self, kesz, osszes, nev, sikeres=0):
        """A háttérszálról hívódik minden elküldött fájl után: rövid pittyegés +
        élő állapot, és a százalék felolvasása mérföldköveknél (nem túl bőbeszédűen)."""
        def ui():
            if self._closing:
                return
            pct = int(kesz * 100 / max(1, osszes))
            self.SetStatusText(f"Küldés: {kesz}/{osszes} – {nev} ({pct}%)")
            try:
                wx.Bell()                       # rövid „pittyegés" fájlonként
            except Exception:
                pass
            mf = pct // 25
            if osszes <= 6 or kesz == osszes or mf != getattr(self, "_utolso_mf", -1):
                self._utolso_mf = mf
                self._mond(f"{kesz} / {osszes}. {pct} százalék."
                           + (" Kész." if kesz == osszes else ""))
        wx.CallAfter(ui)

    def _kuldes_kesz(self, eredmeny):
        if self._closing:
            return
        db, hiba = eredmeny
        if hiba:
            self._mond("A küldés nem sikerült: " + hiba)
        else:
            self._mond(f"Kész! {db} fájl a telefonra került.")

    def _zene(self, e):
        self._kuldes(AC.DEST_ZENE, "Zene küldése a telefonra",
                     "Hang (*.mp3;*.m4a;*.flac;*.ogg;*.wav)|"
                     "*.mp3;*.m4a;*.flac;*.ogg;*.wav|Minden fájl|*.*")

    _KONYV_WILDCARD = (
        "Könyv és hangfájl (epub, txt, pdf, docx, mobi, mp3, m4a, m4b…)|"
        "*.epub;*.txt;*.pdf;*.docx;*.mobi;*.mp3;*.m4a;*.m4b;*.aac;*.ogg;*.oga;"
        "*.opus;*.wav;*.flac;*.wma;*.mp2;*.mka|Minden fájl|*.*")

    def _konyv(self, e):
        fuggo = getattr(self, "_pending_konyv", None)
        if fuggo:
            self._pending_konyv = None
            if os.path.isdir(fuggo):
                self._mappa_kuldes(fuggo)
            else:
                self._kuldes(AC.DEST_KONYV, "", "", utak=[fuggo])
            return
        # kinyíló választás: egyetlen fájl VAGY egy egész mappa (hangoskönyv
        # kötetekkel VAGY több normál könyv együtt)
        valasztek = ["Egyetlen fájl (könyv vagy hangfájl)",
                     "Egy egész mappa (hangoskönyv vagy több normál könyv együtt)"]
        dlg = wx.SingleChoiceDialog(
            self, "Mit küldesz át a telefonra?", "Könyv küldése", valasztek)
        rc = dlg.ShowModal()
        mit = dlg.GetSelection()
        dlg.Destroy()
        if rc != wx.ID_OK:
            return
        if mit == 0:
            self._kuldes(AC.DEST_KONYV,
                         "Könyv vagy hangfájl küldése a telefonra",
                         self._KONYV_WILDCARD)
        else:
            self._mappa_kuldes()

    def _mappa_kuldes(self, ut=None):
        ip, pin = self._adatok()
        if not ip or not pin:
            self._mond("Előbb add meg a telefon IP-címét és a PIN-t.")
            return
        if ut is None:
            with wx.DirDialog(self, "Könyv-mappa küldése a telefonra (a mappa "
                              "könyvei ÉS hangfájljai átmennek – hangoskönyv "
                              "kötetekkel vagy több normál könyv is)") as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                ut = dlg.GetPath()
        AC.beallitas_ment(ip)
        nev = os.path.basename(ut.rstrip("/\\"))
        self._utolso_mf = -1
        self._mond(f"A(z) {nev} mappa küldése a telefonra…")
        # konyv_is=True: nemcsak hangoskönyvet, normál könyveket (epub, txt, pdf,
        # docx…) is átküld a mappából, a kötet-almappák szerkezetét megőrizve
        _hatterben(lambda: AC.mappa_kuld(ip, pin, ut, csak_hang=False,
                                         konyv_is=True,
                                         on_progress=self._kuldes_halad),
                   self._kuldes_kesz, self._hiba)

    def konyv_kuldes_elokeszit(self, path):
        """A Könyvolvasó hívja („nincs a telefonon → átküldöm”). Ha már megvan a
        PIN, egyből küldi; különben megkéri a PIN-t, és a 📖 Könyv küldése gomb
        ezt a könyvet küldi."""
        self._pending_konyv = path
        nev = os.path.basename(path)
        ip, pin = self._adatok()
        if ip and pin:
            self._pending_konyv = None
            self._mond(f"A(z) {nev} könyvet küldöm a telefonra…")
            self._kuldes(AC.DEST_KONYV, "", "", utak=[path])
        else:
            try:
                self.pin_mezo.SetFocus()
            except Exception:
                pass
            self._mond(f"A(z) {nev} könyvet küldöm a telefonra. Add meg a PIN-t, "
                       "majd nyomd meg a 📖 Könyv küldése gombot.")

    # ---- segédek ----
    def _mond(self, szoveg):
        if self._closing:
            return
        self.atirat.AppendText((szoveg or "") + "\n")
        _mondd(self.main, szoveg)

    def _hiba(self, ex):
        if self._closing:
            return
        self._mond(f"Hiba: {ex}. Ellenőrizd a WiFit, az IP-t és a PIN-t.")

    def _sugo(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Súgó – Átjáró", _SUGO)
        except Exception:
            wx.MessageBox(_SUGO, "Súgó – Átjáró", wx.OK | wx.ICON_INFORMATION,
                          self)

    def _tamogatas(self, e):
        try:
            from superdl.supportwin import SupportDialog
            d = SupportDialog(self)
            d.ShowModal()
            d.Destroy()
        except Exception:
            wx.MessageBox("Köszönöm, hogy támogatnál! Sosem kötelező.",
                          "Támogatás", wx.OK | wx.ICON_INFORMATION, self)

    def _on_key(self, e):
        k = e.GetKeyCode()
        if k == wx.WXK_F1:
            self._sugo()
        elif k == wx.WXK_ESCAPE:
            self.Close()
        else:
            e.Skip()

    def _on_close(self, e):
        self._closing = True
        if getattr(self.main, "_atjaro_win", None) is self:
            self.main._atjaro_win = None
        e.Skip()
