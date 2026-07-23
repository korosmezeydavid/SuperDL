# -*- coding: utf-8 -*-
"""Herman Tibi auditok KV1 köre: titokvédelem + naptár-helyesség + bájt-limit.
Minden teszt a KONKRÉT, bizonyított hibát fogja meg (nem mockolt látszat)."""
import datetime
import inspect

from superdl import audiobook, organizer, tts


# ---- CAL-P0-01: ismétlődő esemény NEM sülhet el a kezdődátum előtt ----------

def _ev(**kw):
    base = dict(id="x", title="Teszt", date="2026-08-15", time="10:00",
                repeat=organizer.REPEAT_DAILY)
    base.update(kw)
    return organizer.Event(**base)


def test_napi_ismetlodes_nem_fordul_elo_a_kezdodatum_elott():
    ev = _ev(repeat=organizer.REPEAT_DAILY, date="2026-08-15")
    assert ev.occurs_on(datetime.date(2026, 8, 14)) is False   # előtte NEM
    assert ev.occurs_on(datetime.date(2026, 8, 15)) is True    # aznap IGEN
    assert ev.occurs_on(datetime.date(2026, 9, 1)) is True     # utána IGEN


def test_heti_ismetlodes_nem_fordul_elo_a_kezdodatum_elott():
    # 2026-08-15 szombat; a hétfői (0) ismétlés a kezdés ELŐTTI hétfőn nem jöhet
    ev = _ev(repeat=organizer.REPEAT_WEEKLY, date="2026-08-15", weekdays=[0])
    assert ev.occurs_on(datetime.date(2026, 8, 10)) is False   # korábbi hétfő
    assert ev.occurs_on(datetime.date(2026, 8, 17)) is True    # utáni hétfő


def test_hibas_kezdodatum_nem_dob_kivetelt():
    ev = _ev(repeat=organizer.REPEAT_DAILY, date="nem-datum")
    assert ev.occurs_on(datetime.date(2026, 8, 15)) is True    # régi viselkedés


# ---- CAL-P0-06: az ütemező hibái NEM tűnhetnek el némán --------------------

def test_scheduler_nem_nyeli_el_nemam_a_hibat():
    src = inspect.getsource(organizer.OrganizerManager._loop)
    assert "except Exception:\n                pass" not in src, \
        "a scheduler néma except-pass-t használ"
    assert "tick_errors" in src and "_log" in src


def test_scheduler_health_jelentes_letezik():
    assert hasattr(organizer.OrganizerManager, "scheduler_health")


# ---- AB-P0-05 / TTS-SEC: az API-kulcs nem szivároghat ----------------------

def test_kulcs_nincs_az_urlben():
    src = inspect.getsource(tts)
    assert "?key={api_key}" not in src, "az API-kulcs URL query-ben van"
    assert "x-goog-api-key" in src, "nincs fejléc-alapú kulcsátadás"


def test_redact_maszkolja_a_kulcsot():
    key = "AIzaSyD-EXAMPLE-TESTKEY-1234567890"
    msg = f"HTTP 403 https://x.googleapis.com/v1/a?key={key}&b=1"
    out = tts.redact(msg, key)
    assert key not in out
    assert "***" in out


def test_redact_akkor_is_maszkol_ha_a_kulcsot_nem_kapja_meg():
    msg = "HTTP 400 https://x.googleapis.com/v1/a?key=TITKOS_KULCS_123&b=1"
    assert "TITKOS_KULCS_123" not in tts.redact(msg)


def test_rovid_szoveget_nem_maszkol_ki_feleslegesen():
    # 8 karakternél rövidebb „kulcs” nem valódi titok – ne csonkítsa a szöveget
    assert tts.redact("hiba: abc", "abc") == "hiba: abc"


# ---- AB-P1-10: a Cloud korlát BÁJT, nem karakter ---------------------------

def test_cloud_motor_bajt_limitet_deklaral():
    assert getattr(tts.ENGINES["cloud"], "byte_limit", 0) > 0


def test_magyar_ekezetes_darabok_a_bajtlimit_alatt_maradnak():
    # csupa kétbájtos ékezet: karakterben mérve átmenne, bájtban nem
    text = ("Árvíztűrő tükörfúrógép őőő űűű. " * 400).strip()
    limit = 1000
    parts = audiobook.chunk_text(text, limit, by_bytes=True)
    assert parts, "nem keletkezett darab"
    for p in parts:
        assert len(p.encode("utf-8")) <= limit, \
            f"{len(p.encode('utf-8'))} bájt > {limit}"


def test_bajt_modban_sem_veszik_el_szoveg():
    text = "Árvíztűrő tükörfúrógép. " * 50
    parts = audiobook.chunk_text(text, 200, by_bytes=True)
    # minden szó megmarad (a darabolás nem csonkol)
    assert "".join(parts).replace(" ", "").replace("\n", "") \
        == text.replace(" ", "").strip().replace(" ", "")


def test_egyetlen_hosszu_ekezetes_szo_is_bajthataron_torik():
    parts = audiobook.chunk_text("Á" * 5000, 300, by_bytes=True)
    for p in parts:
        assert len(p.encode("utf-8")) <= 300


# ---- AB-P0-01: az API-kulcs mező jelszómező --------------------------------

def test_api_kulcs_mezo_jelszomezo():
    import pathlib
    p = (pathlib.Path(__file__).parent.parent / "modules_src" / "konyvek"
         / "konyvek_mod" / "bookwin.py")
    src = p.read_text(encoding="utf-8")
    assert "wx.TextCtrl(p, style=wx.TE_PASSWORD)" in src, \
        "az API-kulcs mező nem TE_PASSWORD"


# ---- READ-P1-14: a 0.0 hangerő érvényes érték ------------------------------

def test_nulla_hangero_nem_valtozik_07_re():
    import pathlib
    p = (pathlib.Path(__file__).parent.parent / "modules_src" / "konyvek"
         / "konyvek_mod" / "readerwin.py")
    src = p.read_text(encoding="utf-8")
    assert "player.volume or 0.7" not in src, \
        "a 0.0 hangerőt még mindig 0.7-re cseréli"
