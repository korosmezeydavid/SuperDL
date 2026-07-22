# -*- coding: utf-8 -*-
"""Alfolyamatok BIZTOS leállítása és „learatása" – erőforrás-szivárgás ellen.

Ismételt indítás/leállítás mellett (rádió-/IPTV-váltás, lejátszó stop/play) a
puszta ``terminate()`` NEM elég: a folyamat- és cső-leírók a Popen-objektum
véglegesítéséig NYITVA maradnak, és egy hosszú munkamenetben elfogyhatnak a
leírók. Ezek a segédek terminate→wait→kill→wait sorrendben GARANTÁLTAN
lezárják a gyerekfolyamatot, és bezárják a csöveket.

Szándékosan függőségmentes (csak subprocess), hogy bárhonnan importálható
legyen. A modulok saját másolatot használnak, hogy ne kössék a Core-verzióhoz.
"""
from __future__ import annotations


def close_pipes(proc) -> None:
    """A Popen összes nyitott csövének bezárása (a reader-szál felszabadulhat)."""
    if proc is None:
        return
    for name in ("stdout", "stderr", "stdin"):
        s = getattr(proc, name, None)
        if s is not None:
            try:
                s.close()
            except Exception:
                pass


def stop_proc(proc, timeout: float = 3.0) -> None:
    """Gyerekfolyamat BIZTOS leállítása: terminate→wait, ha nem hal meg időben
    kill→wait, végül a csövek bezárása. Minden hibát elnyel; None esetén no-op."""
    if proc is None:
        return
    try:
        alive = proc.poll() is None
    except Exception:
        alive = False
    if alive:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=timeout)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.wait(timeout=timeout)
            except Exception:
                pass
    close_pipes(proc)


def reap(proc, timeout: float = 3.0) -> None:
    """Egy MÁR (közel) befejeződött folyamat learatása a normál lefutás végén:
    csövek bezárása + rövid wait, hogy ne maradjon nyitott leíró/zombi."""
    if proc is None:
        return
    close_pipes(proc)
    try:
        proc.wait(timeout=timeout)
    except Exception:
        pass
