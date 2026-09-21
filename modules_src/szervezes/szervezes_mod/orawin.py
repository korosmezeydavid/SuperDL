"""Beszélő óra és időzítő-profilok – a KEZELŐFELÜLET.

A motor (`superdl.idoora`) és a hangréteg (`superdl.orahang`) a Core-ban van;
itt csak wx van. Ez a felosztás szándékos: a viselkedés (ütemezés, csendes
sáv, alvás-szabály, sorba állítás) így egységtesztelhető wx nélkül.

EGY ABLAK, KÉT LAPFÜL (Dávid kérése, 2026-09-20): a „Beszélő óra" ablakon
belül külön lapfül az ÓRÁnak és az IDŐZÍTŐKnek. Nem külön ablak: az időzítő
is az óra része, és vakon egy Ctrl+Tab olcsóbb, mint egy másik ablakot
megkeresni.

AKADÁLYMENTESSÉG – AMI ITT NEM ELHAGYHATÓ
  • Minden hangválasztó mellett „Meghallgatom" gomb. Vakon 22 hang közül
    listából választani lehetetlen, ha nem lehet meghallgatni.
  • Az időzítő-lista sorai FELOLVASHATÓ szöveget adnak (név, hossz,
    figyelmeztetés, hang, hátralévő idő) – nem csak oszlopszíneket.
  • A prefix mező kitölthető és KIÜRÍTHETŐ; üresen csak az idő szól.
"""

import wx

from superdl import idoora as I
from superdl import orahang as H

HELP_ORA = """BESZÉLŐ ÓRA

MIRE VALÓ
Beállítható időnként bemondja a pontos időt, a te hangodon, a te
szövegeddel. Nem harangoz – röviden szól. Az ablaknak két lapfüle van:
„Óra” és „Időzítők”, köztük Ctrl+Tabbal válthatsz.

ÓRA LAPFÜL – LÉPÉSRŐL LÉPÉSRE (vakon is)
1. „Időbemondás bekapcsolva” – ezt pipáld ki, különben néma marad.
2. „Milyen gyakran” – 5, 10, 15, 20, 30 vagy 60 perc. Csak ezek vannak,
   mert csak ezek esnek kerek pontokra: 20 percnél mindig :00, :20, :40 –
   bármikor indítod a programot.
3. „Jingle” – rövid hangjel a bemondás előtt, hogy tudd, most az óra szól.
4. „Bevezető szöveg” – alapból „A pontos idő”. Átírhatod („az idő”, „idő”),
   vagy a pipát kiveheted, és akkor csak az időt mondja.
5. „Stílus” – háromféleképpen tudja mondani ugyanazt az időpontot.
6. „Csendes sáv” – például 22:00-tól 07:00-ig néma. Átnyúlhat éjfélen.
7. „Hang” – 22 eSpeak-hangból választhatsz. A „Meghallgatom” gombbal
   ki is próbálhatod, mielőtt eldöntöd.

IDŐZÍTŐK LAPFÜL
Elmentett időzítő-profilok, amikből EGYSZERRE TÖBB is futhat, mindegyik
saját hanggal és saját figyelmeztetési ritmussal.

  munkaidő   – 8 óra, 60 percenként szól, m3 hangon
  ebédszünet – 20 perc, 5 percenként szól, f2 hangon
  meeting    – 1 óra, 20 percenként szól, boris hangon

A munkaidő fut, és közben elindítod az ebédszünetet. A HANGBÓL tudod,
melyik szól hozzád.

1. „Új időzítő profil” – nevet, a bemondás gyakoriságát, a teljes hosszt
   és a bemondó hangot adod meg. A hangot meghallgathatod.
2. „Indít” – a kijelölt profil elindul. Többet is indíthatsz.
3. „Mennyi van hátra” – megmondja mindegyikről.
4. „Megállít” – leállítja a kijelölt futó időzítőt.

A LISTÁN HELYI MENÜ IS VAN
Állj rá egy profilra, és nyomd meg az Alkalmazás billentyűt vagy a
Shift+F10-et (egérrel: jobb gomb). A menüből: Szerkesztés, Indítás,
Megállítás, Új profil, Másolat készítése, Törlés, Mennyi van hátra.
Ami épp nem értelmes (például „Megállítás” egy nem futó időzítőn),
az szürkén látszik, hogy tudd, hogy létezik.
Enter a listán = szerkesztés.
A „Másolat készítése” a legrövidebb út egy hasonló időzítőhöz: a
20 perces ebédszünetből egy mozdulattal lesz egy 25 perces is, és az
eredeti megmarad.

AMIT TUDNOD KELL
Az utolsó percben sűrűbben szól (1 percnél, 30 és 10 másodpercnél).
A FUTÁS nem éli túl a program bezárását – a PROFIL igen. Kilépéskor
figyelmeztet, ha fut időzítő.
Ha a gép alvás közben túlfutotta az időzítőt, ébredés után megmondja,
hogy letelt – az esemény nem évül el.
⚠️ Az időzítő-profilok AZONNAL mentődnek (a saját „Mentés” gombjukkal),
az óra beállításai viszont csak az ablak alján lévő „Mentés”-sel.

GYORSBILLENTYŰK
Ctrl+Shift+X – mennyi az idő (kétszer egymás után: dátum és névnap is).
Ctrl+Alt+X – mennyi van hátra.  Ctrl+Tab – lapfülváltás.
F1 – súgó.  Esc – bezárás."""

HELP_IDOZITO = HELP_ORA


def _sugo(szulo, cim, szoveg):
    try:
        from superdl.helpdialog import show_help
        show_help(szulo, cim, szoveg)
    except Exception:
        wx.MessageBox(szoveg, "Súgó – " + cim,
                      wx.OK | wx.ICON_INFORMATION, szulo)


class HangValaszto(wx.BoxSizer):
    """Hangválasztó + „mind mutatása" + „Meghallgatom".

    ⚠️ A próba gomb NEM kényelmi funkció: e nélkül a 22 elemű lista vakon
    használhatatlan. A minta a SAJÁT szöveggel szólal meg, hogy azt halld,
    amit élesben is hallani fogsz."""

    def __init__(self, szulo, beszelo, *, cimke="&Hang:",
                 minta="A pontos idő tizenegy óra húsz perc", mind=False):
        super().__init__(wx.HORIZONTAL)
        self._beszelo = beszelo
        self._minta = minta
        self.cimke = wx.StaticText(szulo, label=cimke)
        self.valaszto = wx.Choice(szulo, choices=[])
        self.valaszto.SetName("Beszédhang")
        self.mind = wx.CheckBox(szulo, label="mind m&utatása")
        self.mind.SetName("Mind a több mint száz eSpeak-hang mutatása")
        self.mind.SetValue(bool(mind))
        self.mind.Bind(wx.EVT_CHECKBOX, lambda e: self._feltolt())
        self.proba = wx.Button(szulo, label="&Meghallgatom")
        self.proba.Bind(wx.EVT_BUTTON, lambda e: self._proba())
        self.Add(self.cimke, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.Add(self.valaszto, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.Add(self.mind, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.Add(self.proba, 0, wx.ALIGN_CENTER_VERTICAL)
        self._nevek = []
        self._feltolt()

    def _feltolt(self, kivalaszt=None):
        kivalaszt = kivalaszt if kivalaszt is not None else self.valtozat()
        parok = H.keszlet(mind=self.mind.GetValue())
        self._nevek = [n for n, _ in parok]
        self.valaszto.Set([c for _, c in parok])
        self.allit(kivalaszt)

    def valtozat(self) -> str:
        i = self.valaszto.GetSelection()
        if i < 0 or i >= len(self._nevek):
            return ""
        return self._nevek[i]

    def allit(self, valtozat: str) -> None:
        try:
            self.valaszto.SetSelection(self._nevek.index(valtozat or ""))
        except ValueError:
            self.valaszto.SetSelection(0)

    def minta_szoveg(self, szoveg: str) -> None:
        self._minta = szoveg

    def _proba(self):
        if self._beszelo is None:
            wx.MessageBox("A beszédhang most nem elérhető.", "Meghallgatás",
                          wx.OK | wx.ICON_INFORMATION)
            return
        self._beszelo.mond(self._minta, self.valtozat(), surgos=True)


class OraPanel(wx.Panel):
    """Az „Óra" lapfül: a periodikus időbemondás beállításai."""

    def __init__(self, szulo, motor, beszelo):
        super().__init__(szulo)
        self._motor = motor
        b = dict(motor.utemezo.beall)
        v = wx.BoxSizer(wx.VERTICAL)

        self.be = wx.CheckBox(self, label="&Időbemondás bekapcsolva")
        self.be.SetValue(bool(b.get("bemondas")))
        v.Add(self.be, 0, wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(wx.StaticText(self, label="Milyen g&yakran:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.periodus = wx.Choice(
            self, choices=["%d perc" % x for x in I.PERIODUSOK])
        self.periodus.SetName("Bemondás gyakorisága")
        self.periodus.SetToolTip(
            "Csak a 60 osztói szerepelnek: így a bemondások mindig kerek "
            "pontokra esnek. 20 percnél :00, :20, :40 – bármikor indítod "
            "a programot.")
        try:
            self.periodus.SetSelection(
                I.PERIODUSOK.index(int(b.get("periodus_perc", 20))))
        except (ValueError, TypeError):
            self.periodus.SetSelection(I.PERIODUSOK.index(20))
        sor.Add(self.periodus, 0, wx.ALIGN_CENTER_VERTICAL)
        v.Add(sor, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.jingle = wx.CheckBox(
            self, label="&Jingle (rövid hangjel) a bemondás előtt")
        self.jingle.SetValue(bool(b.get("jingle", True)))
        v.Add(self.jingle, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.prefix_be = wx.CheckBox(self, label="Be&vezető szöveg:")
        self.prefix_be.SetValue(bool(b.get("prefix_be", True)))
        self.prefix = wx.TextCtrl(self, value=b.get("prefix_szoveg") or "")
        self.prefix.SetName("Bevezető szöveg a bemondás előtt")
        self.prefix.SetHint("pl. A pontos idő")
        self.prefix.SetToolTip(
            "Ezt mondja az idő ELŐTT. Írd át, ahogy neked jó, vagy vedd ki "
            "a pipát, és akkor csak az időt mondja. Az időt akkor is "
            "kimondott alakban mondja, sosem számjegyenként.")
        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(self.prefix_be, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        sor.Add(self.prefix, 1, wx.ALIGN_CENTER_VERTICAL)
        v.Add(sor, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(wx.StaticText(self, label="&Stílus:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._stilus_kulcs = [k for k, _ in I.STILUSOK]
        self.stilus = wx.Choice(self, choices=[c for _, c in I.STILUSOK])
        self.stilus.SetName("Bemondási stílus")
        try:
            self.stilus.SetSelection(
                self._stilus_kulcs.index(b.get("stilus", "pontos")))
        except ValueError:
            self.stilus.SetSelection(0)
        sor.Add(self.stilus, 1, wx.ALIGN_CENTER_VERTICAL)
        v.Add(sor, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # ⚠️ Itt is a CÍMKE JÖN ELŐBB, és mindkét mezőnek SAJÁT címkéje van.
        # A korábbi „Csendes sáv: [   ] -tól [   ] -ig" szerkezetben a
        # második mező előtti statikus szöveg a „-tól" volt – a
        # képernyőolvasó azt olvasta volna a „vége" mezőre.
        sor = wx.BoxSizer(wx.HORIZONTAL)
        cim = wx.StaticText(self, label="&Csendes sáv kezdete:")
        self.csend_tol = wx.TextCtrl(self, value=b.get("csend_tol") or "22:00",
                                     size=(70, -1))
        self.csend_tol.SetName("Csendes sáv kezdete, óra kettőspont perc")
        self.csend_tol.SetHint("22:00")
        sor.Add(cim, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        sor.Add(self.csend_tol, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        cim2 = wx.StaticText(self, label="vé&ge:")
        self.csend_ig = wx.TextCtrl(self, value=b.get("csend_ig") or "07:00",
                                    size=(70, -1))
        self.csend_ig.SetName("Csendes sáv vége, óra kettőspont perc")
        self.csend_ig.SetHint("07:00")
        sor.Add(cim2, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        sor.Add(self.csend_ig, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        sor.Add(wx.StaticText(self, label="(átnyúlhat éjfélen)"), 0,
                wx.ALIGN_CENTER_VERTICAL)
        v.Add(sor, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.hang = HangValaszto(self, beszelo,
                                 mind=bool(b.get("minden_hang")))
        self.hang.allit(b.get("valtozat") or I.ALAP["valtozat"])
        v.Add(self.hang, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(wx.StaticText(self, label="&Ülés-emlékeztető:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.ules = wx.SpinCtrl(self, min=0, max=600,
                                initial=int(b.get("ules_emlekezteto_perc")
                                            or 0))
        self.ules.SetName(
            "Ülés-emlékeztető percben, nulla egyenlő kikapcsolva")
        sor.Add(self.ules, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        sor.Add(wx.StaticText(self, label="perc (0 = kikapcsolva)"), 0,
                wx.ALIGN_CENTER_VERTICAL)
        v.Add(sor, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        b_most = wx.Button(self, label="Mennyi az i&dő? (próba)")
        b_most.Bind(wx.EVT_BUTTON, lambda e: self._most())
        v.Add(b_most, 0, wx.ALL, 8)
        self.SetSizer(v)

    def _most(self):
        """A próba az ÉPP BEÁLLÍTOTT (még nem mentett) értékekkel szóljon –
        különben a stílust és a prefixet csak mentés után lehetne kipróbálni."""
        self._motor.beallit(self.ertekek())
        self._motor.mennyi_az_ido()

    def ertekek(self) -> dict:
        return {
            "bemondas": self.be.GetValue(),
            "periodus_perc": I.PERIODUSOK[max(0, self.periodus.GetSelection())],
            "jingle": self.jingle.GetValue(),
            "prefix_be": self.prefix_be.GetValue(),
            "prefix_szoveg": self.prefix.GetValue(),
            "stilus": self._stilus_kulcs[max(0, self.stilus.GetSelection())],
            "csend_tol": self.csend_tol.GetValue().strip(),
            "csend_ig": self.csend_ig.GetValue().strip(),
            "valtozat": self.hang.valtozat(),
            "minden_hang": self.hang.mind.GetValue(),
            "ules_emlekezteto_perc": int(self.ules.GetValue()),
        }

    def hibas_mezo(self):
        """(vezérlő, üzenet) az első hibás mezőre, vagy (None, "")."""
        for mezo, nev in ((self.csend_tol, "kezdete"),
                          (self.csend_ig, "vége")):
            ertek = mezo.GetValue().strip()
            if ertek and not I.ido_ertheto(ertek):
                return mezo, ("A csendes sáv %s nem érthető: %r.\n\nÓra "
                              "kettőspont perc alakban add meg, például "
                              "22:00." % (nev, ertek))
        return None, ""


class ProfilDialog(wx.Dialog):
    """Egy időzítő-profil: név, bemondás gyakorisága, teljes hossz, hang."""

    def __init__(self, szulo, beszelo, profil=None):
        uj = profil is None
        super().__init__(szulo,
                         title=("SuperDL – Új időzítő profil" if uj
                                else "SuperDL – Időzítő profil"),
                         size=(620, 340))
        p0 = dict(I.IDOZITO_ALAP)
        p0.update(profil or {})
        if uj:
            p0["nev"] = ""
        v = wx.BoxSizer(wx.VERTICAL)

        # ⚠️ A CÍMKE MINDIG A VEZÉRLŐ ELŐTT JÖJJÖN LÉTRE.
        # A képernyőolvasó a vezérlőt a Z-SORRENDBEN (= létrehozási
        # sorrendben) ELŐTTE álló statikus szöveggel párosítja, nem azzal,
        # amit a sizerben mellé teszünk. Az első változat a vezérlőt hozta
        # létre előbb, ezért MINDEN címke eggyel elcsúszott: a „Bemondás
        # gyakorisága" mező „Időzítő neve"-ként szólalt meg. Dávid élesben
        # fogta meg. A `sor()` ezért a címkét MAGA hozza létre, és a
        # vezérlőt egy FÜGGVÉNNYEL kéri, hogy a sorrend ne fordulhasson meg.
        def sor(cimke, keszit, utan=""):
            cim = wx.StaticText(self, label=cimke)       # 1. a címke
            vezerlo = keszit()                           # 2. csak azután
            s = wx.BoxSizer(wx.HORIZONTAL)
            s.Add(cim, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
            s.Add(vezerlo, 1 if utan == "" else 0,
                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
            if utan:
                s.Add(wx.StaticText(self, label=utan), 0,
                      wx.ALIGN_CENTER_VERTICAL)
            v.Add(s, 0, wx.EXPAND | wx.ALL, 8)
            return vezerlo

        def _nev():
            t = wx.TextCtrl(self, value=p0["nev"])
            t.SetName("Az időzítő neve")
            t.SetHint("pl. ebédszünet")
            return t
        self.nev = sor("Időzítő &neve:", _nev)

        def _kozbenso():
            sp = wx.SpinCtrl(self, min=0, max=24 * 60,
                             initial=int(p0.get("kozbenso_perc") or 0))
            sp.SetName(
                "Bemondás gyakorisága percben, nulla egyenlő csak a végén")
            sp.SetToolTip(
                "Ennyi percenként szól közben. 0 = csak a végén. Az utolsó "
                "percben mindenképp sűrűbben szól: 1 percnél, 30 és 10 "
                "másodpercnél.")
            return sp
        self.kozbenso = sor("&Bemondás gyakorisága:", _kozbenso,
                            "percenként (0 = csak a végén)")

        def _hossz():
            sp = wx.SpinCtrl(self, min=1, max=24 * 60,
                             initial=int(p0["hossz_perc"]))
            sp.SetName("Az időzítő teljes hossza percben")
            return sp
        self.hossz = sor("&Teljes hossz:", _hossz, "perc")

        self.hang = HangValaszto(self, beszelo, cimke="Bemondó &hang:")
        self.hang.allit(p0.get("valtozat") or "")
        v.Add(self.hang, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.nev.Bind(wx.EVT_TEXT, lambda e: (self._minta(), e.Skip()))
        self._minta()

        self.veg_jingle = wx.CheckBox(self, label="&Jingle a lejáratkor")
        self.veg_jingle.SetValue(bool(p0.get("veg_jingle", True)))
        v.Add(self.veg_jingle, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.nevet_mond = wx.CheckBox(
            self, label="Mondja ki a nevét min&den bemondásban")
        self.nevet_mond.SetValue(bool(p0.get("kimondja_a_nevet", True)))
        self.nevet_mond.SetToolTip(
            "A hang a gyors azonosító, de ha három hónapja nem használtad, "
            "nem fogod fejből tudni, melyik hang melyik időzítő. Ezért ez "
            "alapból be van kapcsolva.")
        v.Add(self.nevet_mond, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        s = wx.BoxSizer(wx.HORIZONTAL)
        b_ok = wx.Button(self, wx.ID_OK, "M&entés")
        b_ok.Bind(wx.EVT_BUTTON, lambda e: self._mentes())
        s.Add(b_ok, 0, wx.RIGHT, 6)
        s.Add(wx.Button(self, wx.ID_CANCEL, "Mé&gse"), 0)
        v.Add(s, 0, wx.ALL, 8)
        self.SetSizer(v)
        self.nev.SetFocus()
        self.Bind(wx.EVT_CHAR_HOOK, self._billentyu)

    def _billentyu(self, e):
        if e.GetKeyCode() == wx.WXK_F1:
            _sugo(self, "Időzítők", HELP_IDOZITO)
        else:
            e.Skip()

    def _minta(self):
        """A próba a SAJÁT szövegével szóljon – azt halld, ami élesben jön."""
        nev = self.nev.GetValue().strip() or "időzítő"
        self.hang.minta_szoveg("%s: letelt az idő." % nev)

    def ertekek(self) -> dict:
        return {
            "nev": self.nev.GetValue().strip(),
            "hossz_perc": int(self.hossz.GetValue()),
            "kozbenso_perc": int(self.kozbenso.GetValue()),
            "valtozat": self.hang.valtozat(),
            "veg_jingle": self.veg_jingle.GetValue(),
            "kimondja_a_nevet": self.nevet_mond.GetValue(),
        }

    def _mentes(self):
        ok, uzenet = I.profil_rendben(self.ertekek())
        if not ok:
            wx.MessageBox(uzenet, "Így nem menthető",
                          wx.OK | wx.ICON_WARNING, self)
            self.nev.SetFocus()
            return
        self.EndModal(wx.ID_OK)


class IdozitoPanel(wx.Panel):
    """Az „Időzítők" lapfül: elmentett profilok, egyszerre több is futhat."""

    def __init__(self, szulo, motor, beszelo, profilok, ment_fn):
        super().__init__(szulo)
        self._motor = motor
        self._beszelo = beszelo
        self._profilok = list(profilok or [])
        self._ment = ment_fn
        self._halott = False          # zárás után a visszahívások kilépnek

        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(self, label="Időzítő-&profilok:"), 0, wx.ALL, 8)
        self.lista = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN)
        self.lista.SetName("Időzítő-profilok listája")
        for i, (cim, szel) in enumerate((("Név", 150), ("Bemondás", 130),
                                         ("Teljes hossz", 100),
                                         ("Hang", 130), ("Állapot", 190))):
            self.lista.InsertColumn(i, cim, width=szel)
        self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED,
                        lambda e: self._szerkeszt())
        # HELYI MENÜ a listán. ⚠️ `EVT_CONTEXT_MENU`-t kötünk, nem
        # `EVT_RIGHT_DOWN`-t: ez jön a jobb kattintásra ÉS az Alkalmazás
        # billentyűre / Shift+F10-re is. Vakon épp az utóbbi a fontos –
        # egérrel senki nem keres helyi menüt, aki nem lát.
        self.lista.Bind(wx.EVT_CONTEXT_MENU, self._helyi_menu)
        v.Add(self.lista, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        s = wx.BoxSizer(wx.HORIZONTAL)
        # ⚠️ Az Alt+betűk az EGÉSZ ablakban keresnek, a lapfül nem határolja
        # el őket – ezért ezek nem ütközhetnek az Óra lap betűivel sem.
        # Gépi őr: tests/test_ora_cimkek.py.
        for cimke, fv in (("&Új időzítő profil", self._uj),
                          ("I&ndít", self._indit),
                          ("Megá&llít", self._megallit),
                          ("Szerkes&zt", self._szerkeszt),
                          ("&Töröl", self._torol),
                          ("Mennyi van hátr&a", self._hatra)):
            b = wx.Button(self, label=cimke)
            b.Bind(wx.EVT_BUTTON, lambda e, f=fv: f())
            s.Add(b, 0, wx.RIGHT, 6)
        v.Add(s, 0, wx.ALL, 8)
        self.SetSizer(v)

        self._feltolt()
        # a hátralévő idő másodpercenként frissül a listában.
        # ⚠️ 4.6.7: ebből a visszahívásból CSAK szöveget írunk – se modális
        # ablak, se COM, se beszéd nem indulhat innen.
        self._ora = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self._allapotok(), self._ora)
        self._ora.Start(1000)

    # ---- lista -----------------------------------------------------

    def leall(self):
        """A szülő párbeszéd zárásakor hívandó."""
        self._halott = True
        try:
            self._ora.Stop()
        except Exception:
            pass

    def _feltolt(self):
        kijelolt = self.lista.GetFirstSelected()
        self.lista.DeleteAllItems()
        for i, pr in enumerate(self._profilok):
            kozb = int(pr.get("kozbenso_perc") or 0)
            self.lista.InsertItem(i, pr.get("nev") or "időzítő")
            self.lista.SetItem(i, 1, ("%d percenként" % kozb) if kozb
                               else "csak a végén")
            self.lista.SetItem(i, 2, "%d perc" % int(pr.get("hossz_perc", 0)))
            self.lista.SetItem(i, 3, H.cimke(pr.get("valtozat") or ""))
        if 0 <= kijelolt < self.lista.GetItemCount():
            self.lista.Select(kijelolt)
            self.lista.Focus(kijelolt)
        elif self.lista.GetItemCount():
            self.lista.Select(0)
        self._allapotok()

    def _allapotok(self):
        if self._halott or not self:
            return
        try:
            futok = {}
            for f in self._motor.futok():
                futok.setdefault(f.nev, []).append(f)
            for i, pr in enumerate(self._profilok):
                fs = futok.get(pr.get("nev") or "időzítő") or []
                if not fs:
                    self.lista.SetItem(i, 4, "áll")
                    continue
                self.lista.SetItem(i, 4, "FUT – %s van hátra" %
                                   I.hatralevo_szoveg(fs[0].hatralevo()))
        except RuntimeError:
            self._halott = True       # a natív vezérlő már nem él

    def _valasztott(self):
        i = self.lista.GetFirstSelected()
        if i < 0:
            wx.MessageBox("Előbb válassz ki egy időzítőt a listából.",
                          "Nincs kijelölés", wx.OK | wx.ICON_INFORMATION, self)
            return None, -1
        return self._profilok[i], i

    # ---- helyi menü -------------------------------------------------

    def helyi_menu_tetelek(self):
        """A helyi menü tételei: [(felirat, függvény vagy None), …].
        A None elválasztót jelent. Külön metódus, hogy tesztelhető legyen
        wx-es menümegnyitás nélkül."""
        i = self.lista.GetFirstSelected()
        van = i >= 0
        fut = False
        if van:
            nev = self._profilok[i].get("nev") or "időzítő"
            fut = any(f.nev == nev for f in self._motor.futok())
        return [
            ("&Szerkesztés…", self._szerkeszt if van else None),
            ("&Indítás", self._indit if van and not fut else None),
            ("&Megállítás", self._megallit if fut else None),
            ("", None),
            ("Ú&j időzítő profil…", self._uj),
            ("&Másolat készítése", self._masolat if van else None),
            ("&Törlés", self._torol if van else None),
            ("", None),
            ("Mennyi van &hátra", self._hatra),
        ]

    def _helyi_menu(self, e):
        """Jobb kattintás / Alkalmazás billentyű / Shift+F10 a listán.

        ⚠️ Egérrel érkezve a kurzor ALATTI sort jelöljük ki előbb – enélkül
        a menü a korábbi kijelölésre vonatkozna, és a felhasználó mást
        törölne, mint amire kattintott. Billentyűvel érkezve a pozíció
        (-1, -1): olyankor a meglévő kijelölés a helyes."""
        poz = e.GetPosition()
        if poz != wx.DefaultPosition and poz.x >= 0 and poz.y >= 0:
            helyi = self.lista.ScreenToClient(poz)
            sor, _ = self.lista.HitTest(helyi)
            if sor >= 0:
                self.lista.Select(sor)
                self.lista.Focus(sor)
        menu = wx.Menu()
        for felirat, fv in self.helyi_menu_tetelek():
            if not felirat:
                menu.AppendSeparator()
                continue
            tetel = menu.Append(wx.ID_ANY, felirat)
            if fv is None:
                tetel.Enable(False)          # látszik, de szürke – így a
                continue                     # képernyőolvasó is elmondja
            self.lista.Bind(wx.EVT_MENU, lambda ev, f=fv: f(), tetel)
        self.lista.PopupMenu(menu)
        menu.Destroy()

    def _masolat(self):
        """A kijelölt profil másolata – így egy 20 perces ebédszünetből
        egyetlen mozdulattal lesz 25 perces, a régi elvesztése nélkül."""
        pr, i = self._valasztott()
        if pr is None:
            return
        uj = dict(pr)
        nevek = {p.get("nev") for p in self._profilok}
        alap = uj.get("nev") or "időzítő"
        n = 2
        while "%s %d" % (alap, n) in nevek:
            n += 1
        uj["nev"] = "%s %d" % (alap, n)
        self._profilok.insert(i + 1, uj)
        self._ment(self._profilok)
        self._feltolt()
        self.lista.Select(i + 1)
        self.lista.Focus(i + 1)

    # ---- műveletek -------------------------------------------------

    def _uj(self):
        d = ProfilDialog(self, self._beszelo)
        try:
            if d.ShowModal() == wx.ID_OK:
                self._profilok.append(d.ertekek())
                self._ment(self._profilok)
                self._feltolt()
                self.lista.Select(len(self._profilok) - 1)
                self.lista.Focus(len(self._profilok) - 1)
        finally:
            d.Destroy()

    def _indit(self):
        pr, i = self._valasztott()
        if pr is None:
            return
        self._motor.idozito_indit(pr)
        self._allapotok()
        self._beszelo.mond("%s elindult, %s." % (
            pr.get("nev") or "időzítő",
            I.hatralevo_szoveg(int(pr.get("hossz_perc", 0)) * 60)),
            pr.get("valtozat") or "", surgos=True)

    def _megallit(self):
        pr, i = self._valasztott()
        if pr is None:
            return
        nev = pr.get("nev") or "időzítő"
        talalt = [f for f in self._motor.futok() if f.nev == nev]
        if not talalt:
            wx.MessageBox("Ez az időzítő most nem fut.", "Nem fut",
                          wx.OK | wx.ICON_INFORMATION, self)
            return
        for f in talalt:
            self._motor.idozito_leallit(f.azon)
        self._allapotok()
        self._beszelo.mond("%s leállítva." % nev, surgos=True)

    def _szerkeszt(self):
        pr, i = self._valasztott()
        if pr is None:
            return
        d = ProfilDialog(self, self._beszelo, pr)
        try:
            if d.ShowModal() == wx.ID_OK:
                self._profilok[i] = d.ertekek()
                self._ment(self._profilok)
                self._feltolt()
        finally:
            d.Destroy()

    def _torol(self):
        pr, i = self._valasztott()
        if pr is None:
            return
        nev = pr.get("nev") or "időzítő"
        if wx.MessageBox("Törlöd a(z) „%s” időzítőt?" % nev,
                         "Törlés", wx.YES_NO | wx.ICON_QUESTION,
                         self) != wx.YES:
            return
        for f in self._motor.futok():
            if f.nev == nev:
                self._motor.idozito_leallit(f.azon)
        del self._profilok[i]
        self._ment(self._profilok)
        self._feltolt()

    def _hatra(self):
        self._beszelo.mond(self._motor.idozitok_allapota(), surgos=True)


class OraDialog(wx.Dialog):
    """A beszélő óra ablaka: „Óra" és „Időzítők" lapfül.

    Modális – de SOHA nem időzítő-visszahívásból nyílik (4.6.7-es szabály).

    ⚠️ A KÉT LAPFÜL MENTÉSE KÜLÖNBÖZŐ, és ez szándékos:
      • az ÓRA beállításai az ablak alján lévő „Mentés"-sel mennek el
        (a „Mégse" eldobja őket);
      • az IDŐZÍTŐ-PROFILOK viszont AZONNAL mentődnek, amikor a saját
        párbeszédükben a „Mentés"-t nyomod. Egy elindított időzítő és egy
        eldobott profil együtt értelmetlen állapot lenne.
    A súgó ezt kimondja."""

    def __init__(self, szulo, motor, beszelo, profilok, ora_ment_fn,
                 profil_ment_fn):
        super().__init__(szulo, title="SuperDL – Beszélő óra",
                         size=(760, 600))
        self._ment = ora_ment_fn
        v = wx.BoxSizer(wx.VERTICAL)
        self.fulek = wx.Notebook(self)
        self.fulek.SetName("Beszélő óra lapfülek")
        self.ora = OraPanel(self.fulek, motor, beszelo)
        self.idozitok = IdozitoPanel(self.fulek, motor, beszelo, profilok,
                                     profil_ment_fn)
        # ⚠️ A lapfülek Alt+betűje is ugyanabban a közös készletben van,
        # mint a bennük lévő vezérlőké – az „&Időzítők" ütközött volna az
        # „&Időbemondás bekapcsolva" jelölőnégyzettel.
        self.fulek.AddPage(self.ora, "&Óra")
        self.fulek.AddPage(self.idozitok, "Időzítő&k")
        v.Add(self.fulek, 1, wx.EXPAND | wx.ALL, 6)

        s = wx.BoxSizer(wx.HORIZONTAL)
        b_ok = wx.Button(self, wx.ID_OK, "M&entés")
        b_ok.Bind(wx.EVT_BUTTON, lambda e: self._mentes())
        s.Add(b_ok, 0, wx.RIGHT, 6)
        s.Add(wx.Button(self, wx.ID_CANCEL, "M&égse"), 0)
        v.Add(s, 0, wx.ALL, 8)
        self.SetSizer(v)

        self.fulek.SetFocus()
        self.Bind(wx.EVT_CHAR_HOOK, self._billentyu)
        self.Bind(wx.EVT_CLOSE, self._zaras)

    def lapra(self, index: int) -> None:
        """Megnyitáskor melyik lapfül legyen elöl (0 = Óra, 1 = Időzítők)."""
        if 0 <= index < self.fulek.GetPageCount():
            self.fulek.SetSelection(index)

    def _billentyu(self, e):
        if e.GetKeyCode() == wx.WXK_F1:
            _sugo(self, "Beszélő óra", HELP_ORA)
        else:
            e.Skip()

    def ertekek(self) -> dict:
        return self.ora.ertekek()

    def _mentes(self):
        mezo, uzenet = self.ora.hibas_mezo()
        if mezo is not None:
            self.fulek.SetSelection(0)
            wx.MessageBox(uzenet, "Hibás időpont", wx.OK | wx.ICON_WARNING,
                          self)
            mezo.SetFocus()
            return
        self._ment(self.ora.ertekek())
        self.idozitok.leall()
        self.EndModal(wx.ID_OK)

    def _zaras(self, e):
        """⚠️ ÉLES ÖSSZEOMLÁS JAVÍTÁSA (2026-09-20, Dávid próbája).

        Ha az Esc/X az alapértelmezett EVT_CLOSE-kezelőhöz jut (`e.Skip()`),
        a wx MAGA hívja a `Destroy()`-t. A hívó `finally: dlg.Destroy()`-ja
        ezután egy már törölt objektumra fut:
            RuntimeError: wrapped C/C++ object of type OraDialog
                          has been deleted
        Modális párbeszédnél a zárás az `EndModal` dolga, a `Destroy` pedig
        a HÍVÓÉ – így pontosan egyszer törlődik."""
        self.idozitok.leall()
        if self.IsModal():
            self.EndModal(wx.ID_CANCEL)
        else:
            e.Skip()
