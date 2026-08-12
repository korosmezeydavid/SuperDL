# -*- coding: utf-8 -*-
"""Super Mail – HELYESÍRÁS-ELLENŐRZŐ a levélíráshoz (Windows Spell Check API).

A Windows BEÉPÍTETT helyesírás-ellenőrzőjét használjuk (comtypes-szal), így
NINCS letöltendő szótár, nincs új függőség, és a magyar ragozott alakokat is
helyesen kezeli (a rendszer hu-HU szótárával). Ha a rendszeren nincs magyar
ellenőrző, azt megmondjuk – néma hiba nincs.

A felület vak-first: a hibás szavakat FELSOROLJUK (nem aláhúzással jelöljük),
és minden hibához javaslatokat adunk, amiket Enterrel be lehet cserélni.
"""
import ctypes
from ctypes import HRESULT, POINTER
from ctypes import wintypes

_OK = True
try:
    import comtypes
    from comtypes import GUID, IUnknown, COMMETHOD, CoCreateInstance, CLSCTX_ALL
except Exception:                       # nem-Windows / nincs comtypes
    _OK = False


ALAP_NYELV = "hu-HU"

if _OK:
    _CLSID_FACTORY = GUID("{7AB36653-1796-484B-BDFA-E74F1DB7C1DC}")

    class IEnumString(IUnknown):
        _iid_ = GUID("{00000101-0000-0000-C000-000000000046}")
        _methods_ = [
            COMMETHOD([], HRESULT, "RemoteNext",
                      (['in'], wintypes.ULONG, "celt"),
                      (['out'], POINTER(wintypes.LPWSTR), "rgelt"),
                      (['out'], POINTER(wintypes.ULONG), "pceltFetched")),
        ]

    class ISpellingError(IUnknown):
        _iid_ = GUID("{B7C82D61-FBE8-4B47-9B27-6C0D2E0DE0A3}")
        _methods_ = [
            COMMETHOD([], HRESULT, "get_StartIndex",
                      (['out'], POINTER(wintypes.ULONG), "value")),
            COMMETHOD([], HRESULT, "get_Length",
                      (['out'], POINTER(wintypes.ULONG), "value")),
            COMMETHOD([], HRESULT, "get_CorrectiveAction",
                      (['out'], POINTER(ctypes.c_int), "value")),
            COMMETHOD([], HRESULT, "get_Replacement",
                      (['out'], POINTER(wintypes.LPWSTR), "value")),
        ]

    class IEnumSpellingError(IUnknown):
        _iid_ = GUID("{803E3BD4-2828-4410-8290-418D1D73C762}")
        _methods_ = [
            COMMETHOD([], HRESULT, "Next",
                      (['out'], POINTER(POINTER(ISpellingError)), "value")),
        ]

    class ISpellChecker(IUnknown):
        _iid_ = GUID("{B6FD0B71-E2BC-4653-8D05-F197E412770B}")
        _methods_ = [
            COMMETHOD([], HRESULT, "get_LanguageTag",
                      (['out'], POINTER(wintypes.LPWSTR), "value")),
            COMMETHOD([], HRESULT, "Check",
                      (['in'], wintypes.LPCWSTR, "text"),
                      (['out'], POINTER(POINTER(IEnumSpellingError)), "value")),
            COMMETHOD([], HRESULT, "Suggest",
                      (['in'], wintypes.LPCWSTR, "word"),
                      (['out'], POINTER(POINTER(IEnumString)), "value")),
            COMMETHOD([], HRESULT, "Add",
                      (['in'], wintypes.LPCWSTR, "word")),
            COMMETHOD([], HRESULT, "Ignore",
                      (['in'], wintypes.LPCWSTR, "word")),
        ]

    class ISpellCheckerFactory(IUnknown):
        _iid_ = GUID("{8E018A9D-2415-4677-BF08-794EA61F94BB}")
        _methods_ = [
            COMMETHOD([], HRESULT, "get_SupportedLanguages",
                      (['out'], POINTER(POINTER(IEnumString)), "value")),
            COMMETHOD([], HRESULT, "IsSupported",
                      (['in'], wintypes.LPCWSTR, "languageTag"),
                      (['out'], POINTER(wintypes.VARIANT_BOOL), "value")),
            COMMETHOD([], HRESULT, "CreateSpellChecker",
                      (['in'], wintypes.LPCWSTR, "languageTag"),
                      (['out'], POINTER(POINTER(ISpellChecker)), "value")),
        ]


class Hiba:
    """Egy helyesírási hiba: hol van, mi a szó, és mik a javaslatok."""

    __slots__ = ("kezdet", "hossz", "szo", "javaslatok", "csere")

    def __init__(self, kezdet, hossz, szo, javaslatok, csere=""):
        self.kezdet, self.hossz = kezdet, hossz
        self.szo = szo
        self.javaslatok = javaslatok
        self.csere = csere            # a Windows által ajánlott automatikus csere

    def felolvasva(self):
        if self.javaslatok:
            return "%s – javaslatok: %s" % (self.szo,
                                            ", ".join(self.javaslatok[:5]))
        return "%s – nincs javaslat" % self.szo


class Ellenorzo:
    """A rendszer helyesírás-ellenőrzője egy nyelvhez."""

    def __init__(self, nyelv=ALAP_NYELV):
        self.nyelv = nyelv
        self.elerheto = False
        self.hiba_oka = ""
        self._sc = None
        self._init(nyelv)

    def _init(self, nyelv):
        if not _OK:
            self.hiba_oka = ("Ehhez a funkcióhoz Windows kell (a rendszer "
                             "beépített helyesírás-ellenőrzőjét használjuk).")
            return
        try:
            comtypes.CoInitialize()
        except Exception:
            pass
        try:
            gyar = CoCreateInstance(_CLSID_FACTORY, ISpellCheckerFactory,
                                    CLSCTX_ALL)
        except Exception as ex:
            self.hiba_oka = ("A Windows helyesírás-ellenőrzője nem érhető el "
                             "ezen a gépen (%s)." % ex)
            return
        try:
            if not gyar.IsSupported(nyelv):
                elerheto = self._nyelvek(gyar)
                self.hiba_oka = (
                    "A(z) %s helyesírás-ellenőrző nincs telepítve a Windowsban. "
                    "Telepíthető: Beállítások → Idő és nyelv → Nyelv és régió → "
                    "a nyelvnél a három pont → Nyelvi beállítások → Alapszintű "
                    "gépelés. %s" % (
                        nyelv,
                        ("Most elérhető: " + ", ".join(elerheto)) if elerheto
                        else ""))
                return
            self._sc = gyar.CreateSpellChecker(nyelv)
            self.elerheto = True
        except Exception as ex:
            self.hiba_oka = "A helyesírás-ellenőrző indítása nem sikerült: %s" % ex

    @staticmethod
    def _nyelvek(gyar):
        try:
            en = gyar.get_SupportedLanguages()
            ki = []
            for _ in range(60):
                s, db = en.RemoteNext(1)
                if not db:
                    break
                ki.append(s)
            return ki
        except Exception:
            return []

    # ------------------------------------------------------------ ellenőrzés
    def ellenoriz(self, szoveg, max_hiba=200):
        """A szöveg helyesírási hibái (Hiba-lista). Üres lista = nincs hiba."""
        if not (self.elerheto and szoveg):
            return []
        ki = []
        try:
            en = self._sc.Check(szoveg)
        except Exception:
            return []
        for _ in range(max_hiba):
            try:
                h = en.Next()
            except Exception:
                break
            if not h:
                break
            try:
                kezd = int(h.get_StartIndex())
                hossz = int(h.get_Length())
            except Exception:
                break
            szo = szoveg[kezd:kezd + hossz]
            csere = ""
            try:
                csere = h.get_Replacement() or ""
            except Exception:
                pass
            ki.append(Hiba(kezd, hossz, szo, self.javaslatok(szo), csere))
        return ki

    def javaslatok(self, szo, max_db=8):
        """Javítási javaslatok egy szóra."""
        if not (self.elerheto and szo):
            return []
        try:
            en = self._sc.Suggest(szo)
        except Exception:
            return []
        ki = []
        for _ in range(max_db):
            try:
                s, db = en.RemoteNext(1)
            except Exception:
                break
            if not db or not s:
                break
            ki.append(s)
        return ki

    def hozzaad(self, szo):
        """A szó felvétele a felhasználó saját szótárába (a Windowséba)."""
        if self.elerheto and szo:
            try:
                self._sc.Add(szo)
                return True
            except Exception:
                pass
        return False
