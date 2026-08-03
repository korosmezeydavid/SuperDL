# -*- coding: utf-8 -*-
"""Ország-Város-Fiú-Lány indító- és TANÍTÓ-ablak, lapfülekkel.

- „Játszunk!" fül: elindítja a játékot a közös JatekKonzolban.
- „A játék tanítása" fül: a bővíthető szótár akadálymentes szerkesztője.
  Kategória- és betűválasztóval, soronként egy szóval bővíthető, amit a játék
  ezután ismer (két pont). Menthető JSON-ba, importálható/exportálható –
  közkinccsé tehető (nincs benne személyes adat, csak szavak és nevek).

Ötlet: Mezei Géza (a játék) és Kőrösmezey Anita, Wildcath (a bővíthető
kategóriák és szótár).
"""
import json

import wx

from .jatekok import orszagvaros as OV

# a szerkesztőben választható betűk (a magyar ábécé)
_BETUK = ("a", "á", "b", "c", "d", "e", "é", "f", "g", "h", "i", "í", "j", "k",
          "l", "m", "n", "o", "ó", "ö", "ő", "p", "r", "s", "t", "u", "ú", "ü",
          "ű", "v", "z")


def _norm1(s):
    """Egy szó normalizált KEZDŐBETŰJE (ékezet/kisbetű nélkül)."""
    n = OV.ekezet_nelkul(s)
    return n[:1]


class OrszagVarosAblak(wx.Dialog):
    def __init__(self, main, jatek, gep_getter):
        super().__init__(main, title=f"Játék – {jatek.nev}", size=(720, 560),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main = main
        self.jatek = jatek
        self.gep_getter = gep_getter
        self._kulcsok = list(OV.ALAP_KULCSOK) + list(OV.EXTRA_KULCSOK)
        self._custom = OV.load_custom()
        self._cur = None                 # (kulcs, betu), ami épp be van töltve

        nb = wx.Notebook(self)
        nb.AddPage(self._play_lap(nb), "Játszunk!")
        nb.AddPage(self._tanit_lap(nb), "A játék tanítása")
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(nb, 1, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(s)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        wx.CallAfter(self._betolt)       # az első kategória/betű betöltése

    # ---- „Játszunk!" fül ----------------------------------------------

    def _play_lap(self, parent):
        p = wx.Panel(parent)
        v = wx.BoxSizer(wx.VERTICAL)
        txt = wx.StaticText(p, label=(
            "Ország-Város-Fiú-Lány – Mezei Géza ötlete.\n\n"
            "A gép másodpercenként sorolja az ábécét, te a SZÓKÖZZEL vagy az "
            "ENTERrel megállítod egy betűn, és arra a betűre mondasz szavakat.\n"
            "A játék elején választhatsz klasszikus (4 kategória) vagy bővített "
            "módot, és beállíthatod, hány játékos és hány kör legyen.\n\n"
            "A Tanítás fülön bővítheted a szótárt saját szavakkal!"))
        v.Add(txt, 0, wx.ALL, 12)
        b = wx.Button(p, label="Ú&j játék indítása")
        b.Bind(wx.EVT_BUTTON, self._jatek_indit)
        v.Add(b, 0, wx.ALL, 12)
        p.SetSizer(v)
        return p

    def _jatek_indit(self, e):
        from .jatekkonzol import JatekKonzol
        try:
            kon = JatekKonzol(self.main, self.jatek, self.gep_getter)
            kon.Show()
        except Exception as ex:
            wx.MessageBox(f"A játék nem indult el: {ex}", "Hiba",
                          wx.OK | wx.ICON_ERROR, self)

    # ---- „A játék tanítása" fül ----------------------------------------

    def _tanit_lap(self, parent):
        p = wx.Panel(parent)
        v = wx.BoxSizer(wx.VERTICAL)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(wx.StaticText(p, label="&Kategória:"),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.kat = wx.ComboBox(
            p, style=wx.CB_READONLY,
            choices=[OV.KATEGORIA_NEVEK[k] for k in self._kulcsok])
        self.kat.SetName("Kategória")
        self.kat.SetSelection(0)
        self.kat.Bind(wx.EVT_COMBOBOX, self._valt)
        sor.Add(self.kat, 1, wx.RIGHT, 12)
        sor.Add(wx.StaticText(p, label="&Betű:"),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.betu = wx.ComboBox(p, style=wx.CB_READONLY, choices=list(_BETUK))
        self.betu.SetName("Betű")
        self.betu.SetSelection(0)
        self.betu.Bind(wx.EVT_COMBOBOX, self._valt)
        sor.Add(self.betu, 0)
        v.Add(sor, 0, wx.EXPAND | wx.ALL, 8)

        self.beep_lbl = wx.StaticText(p, label="")
        v.Add(self.beep_lbl, 0, wx.LEFT | wx.RIGHT, 8)

        v.Add(wx.StaticText(p, label="&Szavak (soronként egy, a választott "
                            "betűvel):"), 0, wx.LEFT | wx.TOP, 8)
        self.szavak = wx.TextCtrl(p, style=wx.TE_MULTILINE)
        self.szavak.SetName("Szavak listája")
        v.Add(self.szavak, 1, wx.EXPAND | wx.ALL, 8)

        gs = wx.BoxSizer(wx.HORIZONTAL)
        b_ment = wx.Button(p, label="&Mentés")
        b_ment.Bind(wx.EVT_BUTTON, lambda e: (self._commit(), self._jelez(
            "Elmentve. A játék mostantól ismeri ezeket a szavakat.")))
        gs.Add(b_ment, 0, wx.RIGHT, 6)
        b_imp = wx.Button(p, label="&Importálás fájlból")
        b_imp.Bind(wx.EVT_BUTTON, self._import)
        gs.Add(b_imp, 0, wx.RIGHT, 6)
        b_exp = wx.Button(p, label="&Exportálás fájlba")
        b_exp.Bind(wx.EVT_BUTTON, self._export)
        gs.Add(b_exp, 0)
        v.Add(gs, 0, wx.ALL, 8)

        self.tanit_allapot = wx.StaticText(p, label="")
        self.tanit_allapot.SetName("Állapot")
        v.Add(self.tanit_allapot, 0, wx.LEFT | wx.BOTTOM, 8)
        p.SetSizer(v)
        return p

    # ---- a szerkesztő működése ----------------------------------------

    def _valasztott(self):
        kulcs = self._kulcsok[max(0, self.kat.GetSelection())]
        betu = _BETUK[max(0, self.betu.GetSelection())]
        return kulcs, betu

    def _betolt(self):
        """A kiválasztott kategória+betű TANÍTOTT szavai a mezőbe, és a
        beépített szavak referenciaként."""
        kulcs, betu = self._valasztott()
        self._cur = (kulcs, betu)
        nb = OV.ekezet_nelkul(betu)[:1]
        tanitott = [w for w in self._custom.get(kulcs, [])
                    if _norm1(w) == nb]
        self.szavak.SetValue("\n".join(tanitott))
        beepitett = sorted(w for w in OV._BUILTIN_NYERS.get(kulcs, ())
                           if _norm1(w) == nb)
        cimke = OV.KATEGORIA_NEVEK[kulcs]
        if beepitett:
            self.beep_lbl.SetLabel(
                f"{cimke} – {betu.upper()}: beépítve már ismerem: "
                + ", ".join(beepitett))
        else:
            self.beep_lbl.SetLabel(
                f"{cimke} – {betu.upper()}: ehhez a betűhöz még nincs beépített "
                "szavam – írd be a sajátjaidat!")

    def _commit(self):
        """A mező tartalmát bemásolja a tanított szótárba (memória + lemez)."""
        if not self._cur:
            return
        kulcs, betu = self._cur
        nb = OV.ekezet_nelkul(betu)[:1]
        ujak = []
        latott = set()
        for sor in self.szavak.GetValue().splitlines():
            w = sor.strip()
            if not w or _norm1(w) != nb:      # üres vagy más betű → kihagyjuk
                continue
            kul = OV.ekezet_nelkul(w)
            if kul not in latott:
                latott.add(kul)
                ujak.append(w)
        # a kategória többi betűjéhez tartozó szavakat megtartjuk
        megmarad = [w for w in self._custom.get(kulcs, []) if _norm1(w) != nb]
        if ujak:
            self._custom[kulcs] = megmarad + ujak
        elif kulcs in self._custom:
            self._custom[kulcs] = megmarad
        try:
            OV.save_custom(self._custom)
        except Exception as ex:
            self._jelez(f"Mentési hiba: {ex}")

    def _valt(self, e):
        """Kategória/betű váltás: előbb elmentjük az eddigit, majd betöltjük az
        újat (így semmi nem vész el)."""
        self._commit()
        self._betolt()

    def _import(self, e):
        with wx.FileDialog(self, "Szótár importálása", wildcard="JSON (*.json)|*.json",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            ut = dlg.GetPath()
        try:
            with open(ut, encoding="utf-8") as f:
                be = json.load(f)
            if not isinstance(be, dict):
                raise ValueError("nem szótár szerkezetű fájl")
        except Exception as ex:
            self._jelez(f"Importálás sikertelen: {ex}")
            return
        # UNIÓ kategóriánként (a meglévő tanított szavak megmaradnak)
        db = 0
        for kulcs, szavak in be.items():
            if kulcs not in OV.KATEGORIA_NEVEK or not isinstance(szavak, list):
                continue
            meglevo = list(self._custom.get(kulcs, []))
            latott = {OV.ekezet_nelkul(w) for w in meglevo}
            for w in szavak:
                w = str(w).strip()
                k = OV.ekezet_nelkul(w)
                if w and k not in latott:
                    latott.add(k)
                    meglevo.append(w)
                    db += 1
            self._custom[kulcs] = meglevo
        OV.save_custom(self._custom)
        self._betolt()
        self._jelez(f"Importálva: {db} új szó került a szótárba.")

    def _export(self, e):
        self._commit()
        with wx.FileDialog(self, "Szótár exportálása",
                           defaultFile="orszagvaros_szotar.json",
                           wildcard="JSON (*.json)|*.json",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            ut = dlg.GetPath()
        try:
            with open(ut, "w", encoding="utf-8") as f:
                json.dump(self._custom, f, ensure_ascii=False, indent=2)
            self._jelez(f"Exportálva ide: {ut}. Nyugodtan megoszthatod!")
        except Exception as ex:
            self._jelez(f"Exportálás sikertelen: {ex}")

    def _jelez(self, szoveg):
        self.tanit_allapot.SetLabel(szoveg)
        try:
            from superdl import screenreader
            screenreader.speak(szoveg)
        except Exception:
            pass

    def _on_close(self, e):
        try:
            self._commit()               # a mentetlen mező-tartalom se vesszen el
        except Exception:
            pass
        e.Skip()
