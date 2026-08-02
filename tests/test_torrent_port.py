# -*- coding: utf-8 -*-
"""Torrent (aria2c) portválasztás és önjavító indítás.

A WinError 10013 (WSAEACCES) ellen: a Windows rebootonként lefoglal
port-blokkokat épp az alacsony dinamikus tartományból, és ha az aria2c
egy ilyen tiltott portra próbál ülni, elhasal. A fix: kizárt sávokat
elkerülő portválasztás + több portot végigpróbáló, önjavító indítás +
akadálymentes hibaüzenet, ha tényleg semmi nem megy."""
import subprocess

import pytest

from superdl import torrent


@pytest.fixture(autouse=True)
def _reset_cache():
    torrent._EXCLUDED_CACHE = None
    yield
    torrent._EXCLUDED_CACHE = None


# ---- netsh-kimenet feldolgozása ------------------------------------------

def test_netsh_excluded_range_parse(monkeypatch):
    minta = (
        "\nProtocol tcp Port Exclusion Ranges\n\n"
        "Start Port    End Port\n"
        "----------    --------\n"
        "      1024        1123\n"
        "     50000       50059\n"
        "* - Administered port exclusions.\n"
    )
    monkeypatch.setattr(torrent.sys, "platform", "win32")
    monkeypatch.setattr(
        torrent.subprocess, "run",
        lambda *a, **k: type("R", (), {"stdout": minta})())
    r = torrent._excluded_port_ranges()
    assert (1024, 1123) in r
    assert (50000, 50059) in r
    # a fejléc/elválasztó/csillag sorok NEM kerülnek be
    assert all(isinstance(a, int) and isinstance(b, int) for a, b in r)


def test_netsh_hiba_eseten_ures(monkeypatch):
    monkeypatch.setattr(torrent.sys, "platform", "win32")
    def _boom(*a, **k):
        raise OSError("netsh nincs")
    monkeypatch.setattr(torrent.subprocess, "run", _boom)
    assert torrent._excluded_port_ranges() == []


# ---- biztonságos portválasztás -------------------------------------------

def test_pick_safe_port_kerulI_a_kizart_savot(monkeypatch):
    # a 30000-60000 sáv tiltott -> csak 20000-29999 maradhat
    monkeypatch.setattr(torrent, "_excluded_port_ranges",
                        lambda: [(30000, 60000)])
    for _ in range(20):
        p = torrent._pick_safe_port()
        assert 20000 <= p <= 29999, f"kizárt sávból választott: {p}"


def test_pick_safe_port_mindent_kizarva_van_tartalek(monkeypatch):
    # minden magas port tiltott -> a bind(0)-os tartalék ágnak kell portot adnia
    monkeypatch.setattr(torrent, "_excluded_port_ranges",
                        lambda: [(1, 65535)])
    p = torrent._pick_safe_port()
    assert isinstance(p, int) and p > 0


# ---- önjavító indítás + felolvasható hiba --------------------------------

class _DeadProc:
    """aria2c, ami azonnal kilép (mintha a portot letiltották volna)."""
    def __init__(self, *a, **k):
        pass
    def poll(self):
        return 1              # már nem fut
    def kill(self):
        pass
    def wait(self, timeout=None):
        return 1


def test_indit_tobb_portot_probal_majd_ertheto_hibat_dob(monkeypatch):
    monkeypatch.setattr(torrent, "find_aria2c", lambda: "aria2c.exe")
    hivasok = {"port": 0}
    def _fake_port():
        hivasok["port"] += 1
        return 20000 + hivasok["port"]
    monkeypatch.setattr(torrent, "_pick_safe_port", _fake_port)
    monkeypatch.setattr(torrent.subprocess, "Popen",
                        lambda *a, **k: _DeadProc())

    with pytest.raises(RuntimeError) as ei:
        torrent.Aria2Client()
    uzenet = str(ei.value)
    # akadálymentes, cselekvésre váltható üzenet a nyers stack trace helyett
    assert "10013" in uzenet
    assert "Indítsd újra" in uzenet
    assert "aria2c" in uzenet
    # tényleg több portot végigpróbált (nem egyet)
    assert hivasok["port"] >= 8


def test_engine_error_tartalmaz_utmutatot():
    e = torrent._engine_error("aria2c: valami stderr")
    assert "10013" in e
    assert "Hyper-V" in e
    assert "tűzfal" in e
