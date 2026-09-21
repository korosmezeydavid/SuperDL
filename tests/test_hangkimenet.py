"""HANGKIMENET-VÁLASZTÁS a lejátszóban — Stolmár Barbi és Nagy Károly,
2026-09-21.

Barbi: „A zene lejátszóban bluetooth fejhallgatóra váltáskor nincs átváltás,
továbbra is az alapértelmezetten marad. Pedig jó lenne, ha lehetne bármilyen
hangkártyán, fejhallgatón hallgatni."

Karcsi: „Nem lehetne azt megcsinálni vele, hogy amikor a windows átváltja az
alapértelmezett hangkártyát, akkor váltson a program is?"

AZ OK. A `Player._feed` a lejátszás ELEJÉN nyitott egy kimeneti streamet, és
ott is hagyta: `sd.RawOutputStream(...)` `device=` nélkül. Nem lehetett
másik kimenetet választani, és a menet közbeni váltásról nem is tudott.
"""

import re

import pytest

from superdl import audioengine as A


# ───────── a Windows bluetooth-neveit fel kell olvasni tudni ────────

WINDOWS_BT = ("Fejbeszélő (@System32\\drivers\\bthhfenum.sys,#2;"
              "%1 Hands-Free%0\r\n;(WI-C100))")


def test_a_bluetooth_eszkoz_neve_felolvashatova_valik():
    """⚠️ A nyers nevet a képernyőolvasó karakterenként mondaná ki —
    egy ilyen listából vakon választani lehetetlen."""
    szep = A.eszkoz_nev(WINDOWS_BT)
    assert szep == "WI-C100 (kihangosító)"
    assert "System32" not in szep
    assert "\\" not in szep and "#" not in szep and "%" not in szep


def test_a_sortores_is_eltunik_a_nevbol():
    assert "\n" not in A.eszkoz_nev(WINDOWS_BT)
    assert "\r" not in A.eszkoz_nev(WINDOWS_BT)


@pytest.mark.parametrize("nyers", [
    "Hangszórók (Realtek(R) Audio)",
    "Fejhallgató (WI-C100)",
    "Speakers (Realtek HDA Primary output with SST)",
    "Elsődleges hangillesztő",
])
def test_a_rendes_neveket_nem_bantjuk(nyers):
    """Ami már olvasható, az maradjon úgy."""
    assert A.eszkoz_nev(nyers) == nyers


def test_ures_nevre_nem_szall_el():
    assert A.eszkoz_nev("") == ""
    assert A.eszkoz_nev(None) == ""


# ───────────────────── az eszközlista alakja ────────────────────────

def test_az_elso_elem_mindig_a_rendszer_alapertelmezettje():
    lista = A.eszkozok()
    assert lista[0][0] == A.RENDSZER_ESZKOZ == ""
    assert "alapértelmezett" in lista[0][1].lower()


def test_az_azonosito_a_NYERS_nev_a_cimke_a_szep(monkeypatch):
    """Az azonosító a sounddevice-nak megy, a címke a felhasználónak."""
    monkeypatch.setattr(A, "eszkoz_nev", lambda n: "SZÉP")

    class HamisSd:
        @staticmethod
        def query_devices():
            return [{"name": "NYERS", "max_output_channels": 2}]
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", HamisSd)
    lista = A.eszkozok()
    assert ("NYERS", "SZÉP") in lista


def test_a_bemeneti_eszkozok_kimaradnak(monkeypatch):
    class HamisSd:
        @staticmethod
        def query_devices():
            return [{"name": "Mikrofon", "max_output_channels": 0},
                    {"name": "Hangszóró", "max_output_channels": 2}]
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", HamisSd)
    nevek = [n for _a, n in A.eszkozok()]
    assert "Mikrofon" not in nevek
    assert "Hangszóró" in nevek


def test_ugyanaz_az_eszkoz_csak_egyszer_szerepel(monkeypatch):
    """⚠️ Ugyanaz a hangkártya megjelenik MME, DirectSound és WASAPI alatt
    is. Vakon egy háromszorosan felsorolt lista használhatatlan."""
    class HamisSd:
        @staticmethod
        def query_devices():
            return [{"name": "Hangszórók (Realtek(R) Audio)",
                     "max_output_channels": 2}] * 3
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", HamisSd)
    lista = A.eszkozok()
    assert len(lista) == 2, "a rendszer-alapértelmezett + EGY hangszóró"


def test_hangkartya_nelkul_sem_szall_el(monkeypatch):
    class Robbano:
        @staticmethod
        def query_devices():
            raise OSError("nincs hangeszköz")
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", Robbano)
    assert A.eszkozok() == [(A.RENDSZER_ESZKOZ,
                             "Rendszer alapértelmezett kimenete")]


# ─────────────────── a Player eszközválasztása ──────────────────────

def test_a_lejatszo_alapbol_a_rendszerre_bizza():
    p = A.Player()
    assert p.device == A.RENDSZER_ESZKOZ


def test_az_eszkozvaltas_jelzore_all(monkeypatch):
    """A váltás a KÖVETKEZŐ pufferrel érvényesül – nem kell megállítani
    és újraindítani a zenét."""
    p = A.Player()
    assert p._device_valt is False
    p.set_device("Fejhallgató (WI-C100)")
    assert p.device == "Fejhallgató (WI-C100)"
    assert p._device_valt is True


def test_a_rendszerre_visszaallas_is_valtas():
    p = A.Player()
    p.set_device("valami")
    p._device_valt = False
    p.set_device("")
    assert p.device == A.RENDSZER_ESZKOZ
    assert p._device_valt is True


def test_a_nev_koruli_szokozok_nem_szamitanak():
    p = A.Player()
    p.set_device("  Fejhallgató (WI-C100)  ")
    assert p.device == "Fejhallgató (WI-C100)"


# ───────── a stream a KÍVÁNT eszközre nyílik, és hibatűrően ─────────

class HamisStream:
    def __init__(self, **kw):
        self.kw = kw
        self.elindult = False

    def start(self):
        self.elindult = True

    def stop(self):
        pass

    def close(self):
        pass


def _hamis_sd(monkeypatch, bukik_ha_device=None):
    nyitasok = []

    class Sd:
        @staticmethod
        def RawOutputStream(**kw):
            nyitasok.append(kw.get("device"))
            if bukik_ha_device is not None and kw.get("device") == bukik_ha_device:
                raise OSError("Error opening RawOutputStream: Invalid device")
            return HamisStream(**kw)
    monkeypatch.setattr(A, "alapertelmezett_kimenet", lambda: "ALAP")
    return Sd, nyitasok


def test_a_stream_a_valasztott_eszkozre_nyilik(monkeypatch):
    sd, nyitasok = _hamis_sd(monkeypatch)
    p = A.Player()
    p.set_device("Fejhallgató (WI-C100)")
    p._stream_nyit(sd)
    assert nyitasok == ["Fejhallgató (WI-C100)"]


def test_a_rendszer_alapertelmezettnel_nem_adunk_at_eszkozt(monkeypatch):
    sd, nyitasok = _hamis_sd(monkeypatch)
    p = A.Player()
    p._stream_nyit(sd)
    assert nyitasok == [None]


def test_kihuzott_fejhallgatonal_NEM_nemulunk_el(monkeypatch):
    """⚠️ A néma elnémulás vakon megkülönböztethetetlen attól, hogy a
    program lefagyott. Visszaesünk a rendszer alapértelmezettjére, és
    ezt MEG IS MONDJUK."""
    sd, nyitasok = _hamis_sd(monkeypatch, bukik_ha_device="Kihúzott fül")
    jelzesek = []
    p = A.Player()
    p.on_device_change = lambda regi, uj: jelzesek.append((regi, uj))
    p.set_device("Kihúzott fül")
    stream, visszaesett = p._stream_nyit(sd)
    assert stream is not None, "szólnia KELL valamin"
    assert visszaesett == "Kihúzott fül"
    assert nyitasok == ["Kihúzott fül", None], "másodszor alapértelmezettre"
    assert p.device == A.RENDSZER_ESZKOZ
    assert jelzesek, "a felhasználó tudja meg, hogy váltottunk"


def test_ha_maga_az_alapertelmezett_bukik_akkor_hiba(monkeypatch):
    """Ha a rendszer kimenete sem nyílik, az VALÓDI hiba – ne nyeljük el."""
    sd, _ = _hamis_sd(monkeypatch, bukik_ha_device=None)

    class Robbano:
        @staticmethod
        def RawOutputStream(**kw):
            raise OSError("nincs hangeszköz")
    p = A.Player()
    with pytest.raises(OSError):
        p._stream_nyit(Robbano)


# ───────── a menet közbeni váltás kódja tényleg ott van ─────────────

def test_a_feed_figyeli_az_eszkozvaltast():
    """Forrásszintű őr: a `_feed` ciklusában legyen ott a váltás-ellenőrzés
    ÉS a rendszer-alapértelmezett figyelése (Karcsi kérése)."""
    import inspect
    forras = inspect.getsource(A.Player._feed)
    assert "_device_valt" in forras
    assert "alapertelmezett_kimenet" in forras
    assert "on_device_change" in forras
    assert re.search(r"stream\s*,\s*_\w*\s*=\s*self\._stream_nyit", forras)
