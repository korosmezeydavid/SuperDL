# -*- coding: utf-8 -*-
"""MK4: a superdl.proc segéd VALÓDI folyamaton – terminate→wait→kill→wait,
csövek bezárása, learatás. Nincs mockolás (a mockolt teszt hamis biztonság)."""
import subprocess
import sys

from superdl import proc as procutil


def _spawn_sleeper():
    # egy hosszan futó, csővel rendelkező gyerekfolyamat (platformfüggetlen)
    return subprocess.Popen(
        [sys.executable, "-c", "import time,sys; time.sleep(30)"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        stdin=subprocess.PIPE)


def test_stop_proc_megoli_a_folyamatot_es_bezarja_a_csoveket():
    p = _spawn_sleeper()
    assert p.poll() is None            # fut
    procutil.stop_proc(p, timeout=5)
    assert p.poll() is not None        # tényleg leállt
    # a csövek zárva
    assert p.stdout is None or p.stdout.closed
    assert p.stderr is None or p.stderr.closed
    assert p.stdin is None or p.stdin.closed


def test_stop_proc_none_no_op():
    procutil.stop_proc(None)           # nem dobhat kivételt


def test_stop_proc_ketszeri_hivas_biztonsagos():
    p = _spawn_sleeper()
    procutil.stop_proc(p, timeout=5)
    procutil.stop_proc(p, timeout=5)   # idempotens, nem dob
    assert p.poll() is not None


def test_reap_learat_egy_befejezett_folyamatot():
    p = subprocess.Popen([sys.executable, "-c", "pass"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    procutil.reap(p, timeout=5)
    assert p.poll() is not None
    assert p.stdout is None or p.stdout.closed
